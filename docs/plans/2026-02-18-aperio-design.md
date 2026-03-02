# Aperio — System Architecture Design

**Date:** 2026-02-18
**Status:** Approved

---

## Overview

Aperio is an autonomous, AI-driven job acquisition engine that runs entirely on the user's local machine. The user pastes a job URL; Aperio scrapes the posting, tailors their profile, navigates the ATS autonomously, and submits — pausing only when confidence is low or human judgment is needed.

**One-line install:** `pip install aperio && aperio start`

---

## Architecture: Monolithic Local App

A single Python process hosts both the FastAPI backend and the React frontend (served as a pre-built static bundle). All data lives in a local SQLite database. Nothing leaves the machine except LLM API calls.

```
User Browser (localhost:3000)
        ↓
  FastAPI Backend
   ├── LangGraph Agent Pipeline
   ├── Playwright ATS Navigator
   ├── APScheduler (background tracker)
   └── SQLite Database
```

---

## Agent Pipeline (LangGraph)

A stateful LangGraph graph orchestrates six agents. State flows through each node and is checkpointed to SQLite after every node so crashed runs can resume.

```
URL Input
   ↓
Planning Agent          ← analyzes JD, breaks down requirements, routes tasks
   ↓
Job Research Agent      ← scrapes ATS structure, researches company, maps fields
   ↓          ↓                    ↓
Resume Agent  Cover Letter Agent   Answer Agent     ← run in parallel
   ↓          ↓                    ↓
Synthesis Agent         ← assembles submission package, validates completeness
   ↓
Preview Gate            ← human-in-the-loop review and approval
   ↓
ATS Navigator           ← autonomously fills and submits the application
   ↓
Tracker                 ← background job polls ATS for status updates
```

### Agent Responsibilities

| Agent | Responsibility |
|---|---|
| **Planner** | Parses JD, identifies role type, required docs, open questions, creates task list |
| **Job Researcher** | Scrapes ATS form structure, researches company culture/values, flags tricky fields |
| **Resume Agent** | Tailors bullet points and skills section to match JD keywords using `experience_json` |
| **Cover Letter Agent** | Writes targeted cover letter using company research + user profile |
| **Answer Agent** | Generates responses to open-ended ATS questions (essays, "why this company?", etc.) |
| **Synthesis Agent** | Assembles all outputs into a structured submission package, validates nothing is missing |

### LangGraph State

```python
class AperioState(TypedDict):
    # Input
    job_url: str
    profile: dict

    # Planner output
    jd_raw: str
    jd_parsed: dict
    ats_type: str                  # workday / greenhouse / lever / generic
    planner_tasks: list[str]

    # Job Researcher output
    ats_fields: list[dict]
    company_research: dict

    # Parallel agent outputs
    resume_tailored: str
    cover_letter: str
    ats_answers: dict[str, str]

    # Synthesis output
    submission_package: dict
    confidence_scores: dict[str, float]   # field → 0.0–1.0
    low_confidence_fields: list[str]
    requires_human_input: bool

    # Human gate
    human_overrides: dict[str, str]
    approved: bool

    # Meta
    run_id: str
    error: str | None
```

---

## Confidence & Human-in-the-Loop

Every agent output carries a confidence score per field. The system gates submission on human approval and requires manual input when confidence is too low.

**Thresholds (configurable):**

```
≥ 0.75  → auto-filled, shown green in preview
< 0.75  → flagged yellow, user can override
< 0.40  → blocked red, user must fill before submission
```

**Preview Gate — two phases:**

**Phase 1: Human Input** (only shown if low-confidence fields exist)
- Displays each flagged field with the confidence score and reason
- User fills in missing or uncertain values
- Red (< 0.40) fields block progression until resolved

**Phase 2: Full Preview & Approve**
- Shows every field that will be submitted, color-coded by confidence
- User can edit any field inline
- "Approve & Submit" triggers the ATS Navigator

---

## ATS Navigator — Autonomous Navigation

The navigator runs a continuous perception-action loop, treating each ATS page as a state to analyze and act on.

```
Perceive → Analyze → Fill → Validate → Act → (next page) → loop
```

**Per iteration:**
1. **Perceive** — Playwright dumps current DOM + accessibility tree
2. **Analyze** — LLM classifies page type, extracts all fields with labels/types/required status
3. **Fill** — Maps each field to profile or AI-generated value; assigns confidence score
4. **Validate** — Checks required fields filled, no inline errors shown
5. **Act** — Clicks Next / Continue / Save / Upload; detects new page and loops

**Page types handled autonomously:**

| Page Type | Strategy |
|---|---|
| Basic info (name, email, phone) | Direct profile map |
| Work history | Loop through `experience_json`, add entries |
| Education | Loop through `education_json` |
| Resume upload | Upload tailored PDF from Resume Agent |
| Dropdowns / radio buttons | DOM scan → closest profile match |
| Open text questions | Answer Agent generated response |
| Work authorization / EEO | Profile preferences + sensible defaults |
| Review page | Final validation, then trigger human Preview Gate |

**Pause conditions** (navigator stops, surfaces to user):
- Required field confidence below threshold
- CAPTCHA detected
- Unknown page structure (no recognized fields)
- File upload required with no file available
- Login wall / MFA required

**Navigation stack:**
- **Primary:** Playwright accessibility tree + DOM parsing (fast, reliable for standard ATS)
- **Fallback:** Claude Computer Use API (handles obfuscated / visual-only UIs)

**ATS Adapter interface:**
```python
class ATSAdapter:
    def detect(self, url: str) -> bool
    def get_page_type(self, dom: str) -> str
    def extract_fields(self, dom: str) -> list[dict]
    def get_next_action(self, dom: str) -> str
```

Concrete adapters: `WorkdayAdapter`, `GreenhouseAdapter`, `LeverAdapter`, `GenericAdapter`.

---

## Data Model (SQLite)

### `profiles`
```
id, name, email, phone, linkedin_url, location
resume_json, experience_json, education_json
skills[], certifications_json, preferences_json
created_at, updated_at
```
`preferences_json`: salary range, remote/hybrid/onsite preference, target roles, locations.

### `jobs`
```
id, url, title, company, ats_type
jd_raw, jd_parsed_json, requirements_json
salary_range, location, remote_type, deadline
created_at
```
`requirements_json`: `{ must_have: [], nice_to_have: [] }` — Planner output.

### `applications`
```
id, job_id, profile_id
status: enum(queued, running, previewing, submitted, tracking)
tracker_status: enum(applied, phone_screen, interview, offer, rejected, withdrawn)
submission_package_json
resume_version, cover_letter_version
human_overrides_json
confidence_report_json
error_log
preview_approved_at, submitted_at, last_tracked_at
notes
```

### `agent_runs`
```
id, application_id, run_id
node_name
input_snapshot_json, output_snapshot_json
duration_ms, error
created_at
```

---

## Background Tracker

APScheduler runs a tracker job every 6 hours per submitted application:

1. Re-opens the ATS candidate portal URL with Playwright
2. Scrapes current status field
3. Diffs against `tracker_status` in SQLite
4. Updates record and pushes notification to dashboard

Status funnel: `Applied → Under Review → Phone Screen → Interview → Offer / Rejected / Withdrawn`

---

## Error Handling & Resilience

| Failure | Recovery |
|---|---|
| Playwright crash mid-form | Resume from last LangGraph checkpoint in SQLite |
| LLM API timeout | Exponential backoff (3 attempts) → flag field as low-confidence |
| CAPTCHA | Pause, notify user, wait for manual solve, then resume |
| Unknown ATS | Fall back to `GenericAdapter`, lower confidence threshold |
| Network drop during submit | Mark status as `uncertain`, prompt user to verify manually |
| No confirmation page detected | Flag as `uncertain`, surface to user |

---

## Frontend (React + Vite)

Served as a static build by FastAPI at `localhost:3000`. Five main views:

### 1. Dashboard
- **Kanban-style funnel** across application stages: Queued → Submitted → In Review → Interview → Offer / Rejected
- Each card shows: company, role, date, tracker status, confidence badge
- Quick actions: View Details, Withdraw, Re-run

### 2. New Application
- Single URL input field with a "Start" button
- Live progress feed as agents run (streamed via SSE):
  - `[Planning Agent] Analyzing job description...`
  - `[Resume Agent] Tailoring 3 bullet points...`
  - `[Cover Letter Agent] Writing cover letter...`
- Transitions to Preview Gate when pipeline completes

### 3. Preview Gate (Human-in-the-Loop)
- **Phase 1 — Input panel** (conditional): flagged fields listed with confidence badge + reason, inline text inputs
- **Phase 2 — Review panel**: full submission package rendered as a diff view
  - Green = high confidence, auto-filled
  - Yellow = medium confidence, user can override
  - Red = low confidence, user must fill
- Inline edit for any field
- "Approve & Submit" button (disabled until all red fields resolved)

### 4. Application Detail
- Timeline of agent run steps with timestamps and confidence scores
- Tailored resume diff (original vs. submitted version)
- Cover letter and ATS answers rendered
- Tracker status history
- User notes field

### 5. Profile Setup (Onboarding)
- Multi-step wizard: Contact Info → Work Experience → Education → Skills → Preferences
- Resume upload with AI-assisted parsing to pre-fill fields
- Preview of how profile maps to a sample job

### 6. Settings
- LLM provider + API key
- Confidence threshold sliders
- Tracker poll interval
- ATS adapter overrides

---

## Project Structure

```
aperio/
├── aperio/
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # Settings (APERIO_ env vars)
│   ├── database.py              # SQLite setup, SQLAlchemy models
│   ├── api/
│   │   ├── router.py
│   │   ├── applications.py
│   │   ├── profiles.py
│   │   └── jobs.py
│   ├── agents/
│   │   ├── graph.py             # LangGraph definition
│   │   ├── state.py             # AperioState TypedDict
│   │   ├── planner.py
│   │   ├── researcher.py
│   │   ├── resume.py
│   │   ├── cover_letter.py
│   │   ├── answer.py
│   │   └── synthesis.py
│   ├── navigator/
│   │   ├── base.py              # ATSAdapter base class
│   │   ├── workday.py
│   │   ├── greenhouse.py
│   │   ├── lever.py
│   │   └── generic.py
│   ├── tracker/
│   │   └── scheduler.py         # APScheduler background jobs
│   └── llm/
│       └── client.py            # LLM client wrapper
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── NewApplication.tsx
│   │   │   ├── PreviewGate.tsx
│   │   │   ├── ApplicationDetail.tsx
│   │   │   ├── Profile.tsx
│   │   │   └── Settings.tsx
│   │   ├── components/
│   │   │   ├── ConfidenceBadge.tsx
│   │   │   ├── AgentProgressFeed.tsx
│   │   │   ├── FieldReviewCard.tsx
│   │   │   └── ApplicationCard.tsx
│   │   └── App.tsx
│   └── vite.config.ts
├── tests/
└── pyproject.toml
```

---

## Tech Stack Summary

| Layer | Technology |
|---|---|
| Backend | FastAPI + Python 3.11+ |
| Agent orchestration | LangGraph + LangChain |
| Browser automation | Playwright (primary), Claude Computer Use API (fallback) |
| Database | SQLite via SQLAlchemy |
| Background jobs | APScheduler |
| Frontend | React + Vite + TypeScript |
| LLM | Claude API (configurable) |
| Install | `pip install aperio && aperio start` |
