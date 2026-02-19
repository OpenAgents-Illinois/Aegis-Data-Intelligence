# Aegis `.claude/` Skills & Agents Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create `aegis/.claude/` with 4 skills (2 portable, 2 project-specific), 3 domain agents, and settings.

**Architecture:** Flat per-project directory. Skills follow the existing `SKILL.md` frontmatter pattern. Agents follow the existing YAML frontmatter + system prompt pattern. Each file is self-contained.

**Tech Stack:** Claude Code skills/agents (Markdown with YAML frontmatter), `gh` CLI for PR/issue operations, pytest for test verification.

**Design doc:** `docs/plans/2026-02-19-aegis-claude-skills-design.md`

---

### Task 1: Create directory structure

**Files:**
- Create: `aegis/.claude/skills/pr-review/` (directory)
- Create: `aegis/.claude/skills/issue-fix/` (directory)
- Create: `aegis/.claude/skills/aegis-debug/` (directory)
- Create: `aegis/.claude/skills/aegis-test/` (directory)
- Create: `aegis/.claude/agents/` (directory)

**Step 1: Create all directories**

```bash
mkdir -p aegis/.claude/skills/pr-review \
         aegis/.claude/skills/issue-fix \
         aegis/.claude/skills/aegis-debug \
         aegis/.claude/skills/aegis-test \
         aegis/.claude/agents
```

**Step 2: Verify structure**

```bash
find aegis/.claude -type d | sort
```

Expected:
```
aegis/.claude
aegis/.claude/agents
aegis/.claude/skills
aegis/.claude/skills/aegis-debug
aegis/.claude/skills/aegis-test
aegis/.claude/skills/issue-fix
aegis/.claude/skills/pr-review
```

No commit yet — directories alone don't get committed.

---

### Task 2: Create `pr-review` skill (portable)

**Files:**
- Create: `aegis/.claude/skills/pr-review/SKILL.md`

**Reference patterns:** Existing `code-reviewer/SKILL.md` for structure, `bug-fix/SKILL.md` for phase-based workflow.

**Step 1: Write the skill file**

Create `aegis/.claude/skills/pr-review/SKILL.md` with this content:

```markdown
---
name: pr-review
description: Review GitHub pull requests by fetching diffs, analyzing code quality, checking conventions, and optionally posting review comments. Use when user says "review this PR", "check PR #N", or shares a PR URL.
---

# PR Review Skill
**Usage:** /pr-review [PR number or URL]

**Trigger this skill when:**
- User says "review this PR", "check PR #N", "review pull request"
- User shares a GitHub PR URL
- User asks to assess code quality of a PR
- Before merging a PR

**Skip for:** Local code review (use code-reviewer), bug fixing (use bug-fix), writing code (use code-implementation)

---

## Phase 1: Fetch PR Context

### Step 1.1: Extract PR Details

Run in parallel:
- `gh pr view <number> --json title,body,author,baseRefName,headRefName,files,additions,deletions,labels,reviewDecision`
- `gh pr diff <number>`
- `gh pr checks <number>`

### Step 1.2: Parse Linked Issues

Check the PR body for issue references (`#N`, `Fixes #N`, `Closes #N`). If found:
- `gh issue view <N> --json title,body,labels`

### Step 1.3: Read Project Conventions

Read the project's CLAUDE.md to understand:
- Commit message format
- Code conventions
- Test requirements
- Architectural patterns

---

## Phase 2: Analyze Changes

### 2.1: File-by-File Review

For each changed file, assess:

| Check | What to Look For |
|-------|-----------------|
| **Correctness** | Logic errors, off-by-one, null handling, edge cases |
| **Security** | Injection, XSS, hardcoded secrets, auth bypasses |
| **Conventions** | Naming, file placement, import ordering, patterns |
| **Tests** | New code has tests, tests cover key paths |
| **Types** | Proper annotations, no suppressions |

### 2.2: Cross-File Analysis

- Do changes maintain consistency across modules?
- Are imports and dependencies updated correctly?
- Does the change break any existing contracts or APIs?

### 2.3: Plan Alignment (if linked issue exists)

| Question | Action if Failed |
|----------|------------------|
| Does the PR address the linked issue? | Flag incomplete work |
| Are there unrelated changes? | Flag scope creep |
| Is the approach reasonable? | Note alternatives |

---

## Phase 3: Produce Review

### Review Report Template

```markdown
## PR Review: #<number> — <title>

### Overview
- **Author:** <author>
- **Branch:** <head> → <base>
- **Files Changed:** <count> (+<additions>, -<deletions>)
- **CI Status:** <pass/fail/pending>

### What Was Done Well
- [Positive point 1]
- [Positive point 2]

### Issues Found

#### Critical (Must Fix)
[Issues that would cause bugs, security holes, or data loss]

#### High (Should Fix)
[Issues that affect correctness, performance, or maintainability]

#### Medium (Recommended)
[Code quality improvements, missing tests, convention violations]

#### Low (Suggestions)
[Style nits, optional improvements]

### Verdict
- [ ] APPROVE — Ready to merge
- [ ] COMMENT — Non-blocking feedback
- [ ] REQUEST CHANGES — Must address issues before merge
```

---

## Phase 4: Post Review (Optional)

### Step 4.1: Ask User

```
Review complete. Would you like me to:
1. Post this as a GitHub review comment
2. Just show you the findings (no GitHub action)
```

### Step 4.2: If Posting

Use `gh pr review <number>` with appropriate flag:
- `--approve` — for APPROVE verdict
- `--comment` — for COMMENT verdict
- `--request-changes` — for REQUEST CHANGES verdict

```bash
gh pr review <number> --<action> --body "$(cat <<'EOF'
<review body>
EOF
)"
```

---

## Quality Guidelines

**ALWAYS:**
- Fetch the actual diff — never review from memory
- Read CLAUDE.md for project conventions
- Start with positives before issues
- Classify issues by severity
- Be specific: file:line references

**NEVER:**
- Guess about code you haven't read
- Post reviews without user approval
- Nitpick style when logic issues exist
- Approve PRs with critical issues
```

**Step 2: Verify file exists and frontmatter is valid**

```bash
head -3 aegis/.claude/skills/pr-review/SKILL.md
```

Expected: `---`, `name: pr-review`, `description: ...`

**Step 3: Commit**

```bash
git add aegis/.claude/skills/pr-review/SKILL.md
git commit -m "feat(aegis): add pr-review skill — portable GitHub PR review"
```

---

### Task 3: Create `issue-fix` skill (portable)

**Files:**
- Create: `aegis/.claude/skills/issue-fix/SKILL.md`

**Reference patterns:** Existing `bug-fix/SKILL.md` for phase-based workflow, `investigator/SKILL.md` for sub-agent delegation.

**Step 1: Write the skill file**

Create `aegis/.claude/skills/issue-fix/SKILL.md` with this content:

```markdown
---
name: issue-fix
description: Triage and fix GitHub issues end-to-end. Fetches the issue, explores relevant code, plans the fix, implements with TDD, and verifies. Use when user says "fix issue #N", "work on this issue", or references a GitHub issue number.
---

# Issue Fix Skill
**Usage:** /issue-fix <issue-number>

**Trigger this skill when:**
- User says "fix issue #N", "work on issue #N"
- User references a GitHub issue number
- User says "work on this issue" with a number
- Automated pipeline triggers issue resolution

**Skip for:** Known bugs with clear cause (use bug-fix), PR review (use pr-review), feature requests without issue (use code-implementation)

---

## Phase 1: Issue Intake

### Step 1.1: Fetch Issue Details

```bash
gh issue view <number> --json title,body,labels,assignees,comments
```

### Step 1.2: Triage

Classify the issue:

| Type | Indicators | Next Action |
|------|-----------|-------------|
| **Bug report** | Error message, "not working", reproduction steps | Investigate root cause |
| **Feature request** | "Add", "implement", "support" | Plan implementation |
| **Unclear** | Vague description, no reproduction steps | Ask user for clarification |

### Step 1.3: Create Working Branch

```bash
git checkout -b fix/<issue-number>-<short-description> main
```

---

## Phase 2: Investigate

### Step 2.1: Locate Relevant Code

Fire an `explore` sub-agent to find:
- Files mentioned in the issue
- Code related to the error or feature area
- Existing tests for the affected area
- Recent changes that may have caused the issue

### Step 2.2: Root Cause Analysis (for bugs)

Deploy `root-cause-hunter` sub-agent with context packet:
- Issue title and body
- Affected file paths from Step 2.1
- Error messages or stack traces from the issue

### Step 2.3: Scope Analysis (for features)

Determine:
- What files need to change
- What new files are needed
- What tests must be written
- What existing tests might break

---

## Phase 3: Plan the Fix

### Fix Plan Template

```markdown
## Fix Plan: Issue #<number>

### Summary
[One sentence: what this fix does]

### Root Cause (bugs) / Approach (features)
[Why the issue exists OR how the feature will be implemented]

### Files to Modify
- `path/to/file1` — [what changes]
- `path/to/file2` — [what changes]

### New Files
- `path/to/new_file` — [purpose]

### Tests
- `tests/path/test_file.py::test_name` — [what it verifies]

### Success Criteria
- [ ] [Specific testable outcome]
- [ ] [Specific testable outcome]
- [ ] All existing tests still pass
```

### Step 3.1: Present Plan

Show the plan to the user and wait for approval before proceeding.

---

## Phase 4: Implement (TDD)

### Step 4.1: Write Failing Tests

Write tests that define the expected behavior:
- For bugs: test that reproduces the bug
- For features: test that defines the new behavior

### Step 4.2: Run Tests to Confirm Failure

```bash
python -m pytest tests/path/test_file.py::test_name -v
```

Expected: FAIL

### Step 4.3: Implement the Fix

Make the minimal code changes to pass the tests.

### Step 4.4: Run Full Test Suite

```bash
python -m pytest tests/ -v --tb=short
```

Expected: ALL PASS (including new tests)

---

## Phase 5: Verify & Present

### Step 5.1: Final Verification

- [ ] New tests pass
- [ ] All existing tests pass
- [ ] No lint/type errors
- [ ] Changes are minimal and focused

### Step 5.2: Commit

```bash
git add <specific-files>
git commit -m "fix(component): resolve issue #<number> — <short description>"
```

### Step 5.3: Report to User

```markdown
## Issue #<number> — Fixed

### Changes Made
- `file1:line` — [what changed]
- `file2:line` — [what changed]

### Tests Added
- `test_name` — [what it verifies]

### Verification
- All tests passing (N/N)
- No regressions detected

### Next Steps
- Push and open PR? (use /gitpush)
- Close the issue?
```

---

## Quality Guidelines

**ALWAYS:**
- Read the full issue before acting
- Create a branch before making changes
- Write tests before implementation
- Run the full test suite, not just new tests
- Present a plan before implementing

**NEVER:**
- Start coding without reading the issue
- Skip the planning phase
- Commit without running tests
- Close the issue without user confirmation
- Mix fixes for multiple issues in one branch
```

**Step 2: Verify**

```bash
head -3 aegis/.claude/skills/issue-fix/SKILL.md
```

**Step 3: Commit**

```bash
git add aegis/.claude/skills/issue-fix/SKILL.md
git commit -m "feat(aegis): add issue-fix skill — portable GitHub issue resolution"
```

---

### Task 4: Create `aegis-debug` skill (project-specific)

**Files:**
- Create: `aegis/.claude/skills/aegis-debug/SKILL.md`

**Key context to embed:** Agent pipeline (Investigator → Sentinels → Orchestrator → Architect → Executor), async/sync bridge, common gotchas from MEMORY.md.

**Step 1: Write the skill file**

Create `aegis/.claude/skills/aegis-debug/SKILL.md` with this content:

```markdown
---
name: aegis-debug
description: Debug the Aegis agent pipeline — sentinels, investigator, orchestrator, architect, executor, scanner, and connectors. Use when user says "debug the scanner", "why isn't the investigator working", "sentinel not detecting changes", or any Aegis pipeline issue.
---

# Aegis Debug Skill
**Usage:** /aegis-debug [description of the pipeline issue]

**Trigger this skill when:**
- Scanner not running or misbehaving
- Sentinel not detecting anomalies
- Investigator discovery failing or returning wrong results
- Orchestrator not routing anomalies to incidents
- Architect analysis failing or producing bad recommendations
- Executor not applying remediations
- Any issue in the Aegis agent pipeline

**Skip for:** General Python bugs (use bug-fix), test failures without pipeline context (use aegis-test), new features (use code-implementation)

---

## Aegis Agent Pipeline Reference

```
Investigator (discovery)
    → Sentinels (anomaly detection: SchemaSentinel + FreshnessSentinel)
        → Orchestrator (anomaly → incident routing, deduplication)
            → Architect (LLM root cause analysis + blast radius via lineage)
                → Executor (remediation actions)
```

**Scanner loop** drives sentinels on cadences:
- Scan: every 5 min (`AEGIS_SCAN_INTERVAL`)
- Lineage refresh: every 1 hr (`AEGIS_LINEAGE_REFRESH`)
- Rediscovery: every 24 hr (`AEGIS_REDISCOVERY_INTERVAL`)

### Key Files

| Component | File | Notes |
|-----------|------|-------|
| Investigator | `aegis/backend/aegis/agents/investigator.py` | LangChain AgentExecutor, deterministic fallback |
| Investigator tools | `aegis/backend/aegis/agents/investigator_tools.py` | 5 tools via `make_tools()` closure factory |
| Investigator prompts | `aegis/backend/aegis/agents/investigator_prompts.py` | System + human templates |
| Sentinels | `aegis/backend/aegis/agents/sentinel.py` | SchemaSentinel + FreshnessSentinel |
| Orchestrator | `aegis/backend/aegis/agents/orchestrator.py` | Anomaly → incident routing |
| Architect | `aegis/backend/aegis/agents/architect.py` | LLM-powered root cause analysis |
| Executor | `aegis/backend/aegis/agents/executor.py` | Remediation execution |
| Scanner | `aegis/backend/aegis/services/scanner.py` | Background scan loop |
| Connectors | `aegis/backend/aegis/core/connectors.py` | WarehouseConnector |
| Models | `aegis/backend/aegis/core/models.py` | All ORM + Pydantic schemas |
| Config | `aegis/backend/aegis/config.py` | Pydantic Settings, `AEGIS_` prefix |

---

## Phase 1: Identify the Failing Component

### Step 1.1: Map Symptom to Component

| Symptom | Likely Component | Start Here |
|---------|-----------------|------------|
| Tables not discovered | Investigator | `investigator.py`, connector methods |
| Schema changes not detected | SchemaSentinel | `sentinel.py`, `scanner.py` |
| Stale tables not flagged | FreshnessSentinel | `sentinel.py`, `scanner.py` |
| Anomalies not creating incidents | Orchestrator | `orchestrator.py` |
| No root cause analysis | Architect | `architect.py`, LLM service |
| Remediation not applied | Executor | `executor.py` |
| Nothing running at all | Scanner loop | `scanner.py`, `main.py` lifespan |
| Connection failures | Connector | `connectors.py`, connection params |

### Step 1.2: Read the Component Code

Read the identified file(s) and trace the data flow from input to output.

---

## Phase 2: Check Common Aegis Gotchas

### Async/Sync Bridge Issues
- **API is async** (FastAPI + AsyncSession)
- **Agents are sync** (SQLAlchemy Session via SyncSessionLocal)
- Bridge: `asyncio.to_thread` + `SyncSessionLocal`
- **Gotcha:** Don't pass AsyncSession to agent code — extract what you need first

### Mock Patterns in Tests
- **`side_effect` overrides `return_value`** — if a mock has `side_effect` set, `return_value` is ignored. Clear with `mock.side_effect = None` first.
- **Lazy imports need source patching** — `notifier` is imported inside scanner functions. Patch at `aegis.services.notifier.notifier`, NOT `aegis.services.scanner.notifier`.
- **`sample_connection` vs `sample_table`** — `sample_connection` only creates a ConnectionModel. For a monitored table, also request `sample_table` fixture.

### LangChain Tool Binding
- `make_tools()` is a closure factory — connector, db, lineage_graph are bound per invocation
- If tools fail, check that the closure arguments are valid (not None, not stale sessions)

### Deterministic Fallback
- Investigator uses `_classify_by_rules()` when LangChain agent fails
- If classification is wrong but discovery runs, check the rule-based fallback logic

---

## Phase 3: Deep Investigation

### Step 3.1: Deploy `pipeline-expert` Agent

Use the Task tool to spawn the `pipeline-expert` sub-agent with:
- The identified component and symptom
- Relevant code snippets (20-50 lines max)
- Any error messages or unexpected outputs

### Step 3.2: Review Findings

Evaluate the sub-agent's report:
- Is the root cause specific (file:line)?
- Does evidence support the conclusion?
- Does the fix address root cause, not symptoms?

---

## Phase 4: Present Findings & Fix

Follow the same approval gate pattern as the `investigator` skill:
1. Present findings with root cause, evidence, and proposed fix
2. Wait for user approval
3. Hand off to `/code-implementation` or `/bug-fix` for the actual fix

---

## Quality Guidelines

**ALWAYS:**
- Check the gotchas list before diving deep
- Use the file reference table to find the right code
- Spawn `pipeline-expert` for complex investigations
- Trace data flow through the full pipeline, not just one component

**NEVER:**
- Assume async code works the same as sync
- Forget to check mock patterns when debugging tests
- Skip the connector/session validity check
- Modify pipeline code without understanding upstream/downstream effects
```

**Step 2: Verify**

```bash
head -3 aegis/.claude/skills/aegis-debug/SKILL.md
```

**Step 3: Commit**

```bash
git add aegis/.claude/skills/aegis-debug/SKILL.md
git commit -m "feat(aegis): add aegis-debug skill — Aegis pipeline debugging"
```

---

### Task 5: Create `aegis-test` skill (project-specific)

**Files:**
- Create: `aegis/.claude/skills/aegis-test/SKILL.md`

**Key context to embed:** Test command, fixture infrastructure, test file conventions, baseline count (68).

**Step 1: Write the skill file**

Create `aegis/.claude/skills/aegis-test/SKILL.md` with this content:

```markdown
---
name: aegis-test
description: Run and manage Aegis backend tests. Knows the test infrastructure, fixtures, and conventions. Use when user says "run tests", "check coverage", "validate before commit", or any test-related request for the Aegis project.
---

# Aegis Test Skill
**Usage:** /aegis-test [optional: specific test file or pattern]

**Trigger this skill when:**
- User says "run tests", "run the test suite"
- User says "check coverage", "validate before commit"
- Test failures need interpretation
- User is adding new tests and needs fixture guidance
- Before committing Aegis backend changes

**Skip for:** Pipeline debugging (use aegis-debug), general bug investigation (use investigator), non-Aegis tests

---

## Quick Reference

### Run All Tests

```bash
cd aegis/backend && python -m pytest tests/ -v --tb=short
```

**Baseline:** 68 tests passing (as of 2026-02-17)

### Run Specific Test File

```bash
cd aegis/backend && python -m pytest tests/test_<name>.py -v --tb=short
```

### Run Specific Test

```bash
cd aegis/backend && python -m pytest tests/test_<name>.py::test_function -v --tb=short
```

---

## Test Infrastructure

### Test Files (15 files)

Located at `aegis/backend/tests/`. Key files:

| File | What It Tests | Special Setup |
|------|--------------|---------------|
| `conftest.py` | Shared fixtures | In-memory SQLite |
| `test_api.py` | REST API endpoints | Temp-file SQLite, own fixtures |
| `test_discovery_api.py` | Discovery endpoints | Temp-file SQLite, own fixtures |
| `test_sentinel.py` | SchemaSentinel + FreshnessSentinel | conftest fixtures |
| `test_orchestrator.py` | Anomaly → incident routing | conftest fixtures |
| `test_architect.py` | LLM root cause analysis | Mocked LLM |
| `test_executor.py` | Remediation execution | conftest fixtures |
| `test_investigator.py` | Investigator agent | Mocked LLM + tools |
| `test_scanner.py` | Scanner loop + cadences | Mocked services |
| `test_connectors.py` | WarehouseConnector | Mocked DB connections |
| `test_lineage.py` | SQL parsing + lineage graph | conftest fixtures |
| `test_models.py` | ORM + Pydantic schemas | conftest fixtures |

### Fixture Hierarchy

```
db (in-memory SQLite session)
├── sample_connection (ConnectionModel)
│   └── sample_table (MonitoredTableModel, requires sample_connection)
│       ├── sample_snapshot (SnapshotModel)
│       ├── sample_anomaly (AnomalyModel)
│       │   └── sample_incident (IncidentModel)
│       └── sample_lineage_edges (LineageEdgeModel list)
└── api_client (TestClient for FastAPI)
```

**Gotcha:** `sample_connection` only creates a ConnectionModel. To have a monitored table in the DB, you must also request `sample_table`.

### Two Test Environments

| Environment | Used By | Engine | Why |
|-------------|---------|--------|-----|
| In-memory SQLite | Most tests (via conftest `db`) | `create_engine("sqlite://")` | Fast, isolated |
| Temp-file SQLite | `test_api.py`, `test_discovery_api.py` | `create_engine(f"sqlite:///{tmp.name}")` | Async + sync engines must share state |

---

## Interpreting Failures

### Common Failure Patterns

| Error Pattern | Likely Cause | Fix |
|--------------|-------------|-----|
| `fixture 'sample_table' not found` | Missing fixture request | Add `sample_table` to test function params |
| `side_effect` ignoring `return_value` | Mock has `side_effect` set | Clear with `mock.side_effect = None` first |
| `notifier` mock not working | Wrong patch location | Patch at `aegis.services.notifier.notifier` |
| `async` test hanging | Async/sync bridge issue | Check `asyncio.to_thread` usage |
| Import errors | Missing dependency | Check `requirements.txt` |

### When Tests Fail

1. **Read the error** — what assertion failed, what was expected vs actual
2. **Check fixtures** — is the test requesting all needed fixtures?
3. **Check mocks** — are side_effect/return_value set correctly?
4. **Check imports** — is the patch location correct?
5. **Run in isolation** — does the test pass alone? (`-k test_name`)

---

## Adding New Tests

### Template

```python
def test_<component>_<behavior>(db, sample_connection, sample_table):
    """Test that <component> <expected behavior>."""
    # Arrange
    <setup>

    # Act
    result = <function_under_test>(<args>)

    # Assert
    assert result == expected
```

### Conventions
- Test files: `tests/test_<component>.py`
- Test functions: `test_<component>_<behavior>`
- Use conftest fixtures, don't create new DB sessions
- Mock external services (LLM, connectors) — never call real APIs in tests
- Keep tests focused: one assertion per test when possible

---

## Quality Guidelines

**ALWAYS:**
- Run the full suite before committing (`python -m pytest tests/ -v --tb=short`)
- Check test count against baseline (68)
- Use existing fixtures from conftest
- Mock external dependencies

**NEVER:**
- Skip running tests before commit
- Create new DB engines in individual tests (use fixtures)
- Call real external APIs in tests
- Ignore test count changes (added tests should increase count, not decrease)
```

**Step 2: Verify**

```bash
head -3 aegis/.claude/skills/aegis-test/SKILL.md
```

**Step 3: Commit**

```bash
git add aegis/.claude/skills/aegis-test/SKILL.md
git commit -m "feat(aegis): add aegis-test skill — test infrastructure and runner"
```

---

### Task 6: Create `pipeline-expert` agent

**Files:**
- Create: `aegis/.claude/agents/pipeline-expert.md`

**Reference pattern:** Existing `root-cause-hunter.md` for YAML frontmatter + system prompt format.

**Step 1: Write the agent file**

Create `aegis/.claude/agents/pipeline-expert.md` with this content:

```markdown
---
name: pipeline-expert
description: |
  Use this agent when investigating, debugging, or extending the Aegis agent pipeline. Has deep knowledge of the Investigator → Sentinels → Orchestrator → Architect → Executor chain, async/sync bridging, LangChain tool binding, and scanner cadences.

  <example>
  Context: User reports that discovered tables have wrong classification.
  user: "The investigator is classifying dimension tables as fact tables"
  assistant: "I'll spawn the pipeline-expert agent to trace the classification logic."
  </example>

  <example>
  Context: Scanner loop appears to skip rediscovery.
  user: "Rediscovery hasn't run in over 48 hours"
  assistant: "Let me deploy the pipeline-expert agent to check the scanner cadence logic."
  </example>

  <example>
  Context: User wants to add a new agent to the pipeline.
  user: "I want to add a data quality scoring agent between Orchestrator and Architect"
  assistant: "I'll use the pipeline-expert agent to analyze the pipeline integration points."
  </example>
model: sonnet
---

You are **Pipeline Expert**, a specialist in the Aegis data intelligence platform's agent pipeline. You have deep knowledge of every component in the chain and how they interact.

## Pipeline Architecture

```
Investigator (discovery + classification)
    ↓ discovers tables, classifies as fact/dim/staging/raw/snapshot/system
    ↓ proposes monitoring config (freshness_sla, row_count thresholds)
Sentinels (anomaly detection)
    ├── SchemaSentinel: detects column drift (added/removed/type-changed)
    └── FreshnessSentinel: detects stale tables (last_seen > freshness_sla)
    ↓ produce AnomalyModel records
Orchestrator (anomaly → incident routing)
    ↓ deduplicates anomalies, creates IncidentModel records
    ↓ routes by severity and type
Architect (root cause analysis)
    ↓ LLM-powered analysis using lineage graph for blast radius
    ↓ produces remediation recommendations
Executor (remediation)
    ↓ applies approved remediation actions
```

## Key Files

| Component | Path |
|-----------|------|
| Investigator agent | `aegis/backend/aegis/agents/investigator.py` |
| Investigator tools | `aegis/backend/aegis/agents/investigator_tools.py` |
| Investigator prompts | `aegis/backend/aegis/agents/investigator_prompts.py` |
| Sentinels | `aegis/backend/aegis/agents/sentinel.py` |
| Orchestrator | `aegis/backend/aegis/agents/orchestrator.py` |
| Architect | `aegis/backend/aegis/agents/architect.py` |
| Executor | `aegis/backend/aegis/agents/executor.py` |
| Scanner loop | `aegis/backend/aegis/services/scanner.py` |
| Connectors | `aegis/backend/aegis/core/connectors.py` |
| Models (all) | `aegis/backend/aegis/core/models.py` |
| Lineage | `aegis/backend/aegis/core/lineage.py` |
| LLM service | `aegis/backend/aegis/services/llm.py` |
| LangChain LLM | `aegis/backend/aegis/services/langchain_llm.py` |
| Config | `aegis/backend/aegis/config.py` |

## Critical Patterns

### Async/Sync Bridge
- API layer: async (FastAPI + AsyncSession)
- Agent layer: sync (SQLAlchemy Session via `SyncSessionLocal`)
- Bridge: `asyncio.to_thread` wraps sync agent calls
- Discovery API extracts connection info from async session, then runs sync Investigator in thread

### LangChain Tool Binding
- `make_tools(connector, db, lineage_graph)` is a closure factory
- Each invocation creates fresh `@tool` functions with bound arguments
- Tools: `list_schemas`, `list_tables`, `get_columns`, `get_row_counts`, `get_freshness`

### Deterministic Fallback
- Investigator uses `_classify_by_rules()` when LangChain AgentExecutor fails
- Rule-based classification: name patterns, column heuristics, row count ratios
- Ensures discovery works even without OPENAI_API_KEY

### Scanner Cadences
- Scan interval: 5 min (`AEGIS_SCAN_INTERVAL`)
- Lineage refresh: 1 hr (`AEGIS_LINEAGE_REFRESH`)
- Rediscovery: 24 hr (`AEGIS_REDISCOVERY_INTERVAL`)
- All configurable via environment variables

## Investigation Protocol

1. Read the relevant component file(s)
2. Trace data flow from input to output
3. Check for common gotchas (async/sync, mock patterns, closure binding)
4. Look for similar working patterns elsewhere in the codebase
5. Identify the exact failure point with file:line evidence
6. Propose minimal fix with clear reasoning

## Output Format

1. **Component Identified** — which part of the pipeline is affected
2. **Data Flow Trace** — how data moves through the affected section
3. **Root Cause** — specific file:line with explanation
4. **Evidence** — code snippets or behavior that proves the cause
5. **Proposed Fix** — minimal changes needed
6. **Risks** — what could break if the fix is applied
```

**Step 2: Verify frontmatter**

```bash
head -5 aegis/.claude/agents/pipeline-expert.md
```

Expected: `---`, `name: pipeline-expert`, `description: |`

**Step 3: Commit**

```bash
git add aegis/.claude/agents/pipeline-expert.md
git commit -m "feat(aegis): add pipeline-expert agent — Aegis pipeline specialist"
```

---

### Task 7: Create `aegis-tester` agent

**Files:**
- Create: `aegis/.claude/agents/aegis-tester.md`

**Step 1: Write the agent file**

Create `aegis/.claude/agents/aegis-tester.md` with this content:

```markdown
---
name: aegis-tester
description: |
  Use this agent when running Aegis tests, interpreting test failures, or creating new test fixtures. Knows the full test infrastructure including conftest fixtures, temp-file SQLite for async tests, mock patterns, and common failure causes.

  <example>
  Context: Tests are failing after a code change.
  user: "3 tests are failing after I modified the sentinel"
  assistant: "I'll deploy the aegis-tester agent to run the tests and diagnose the failures."
  </example>

  <example>
  Context: User needs to add tests for a new feature.
  user: "I need to write tests for the new notification service"
  assistant: "Let me use the aegis-tester agent to set up the test structure with proper fixtures."
  </example>
model: sonnet
---

You are **Aegis Tester**, an expert in the Aegis backend test infrastructure. You know every fixture, every test convention, and every gotcha in the test suite.

## Test Command

```bash
cd aegis/backend && python -m pytest tests/ -v --tb=short
```

**Baseline:** 68 tests passing across 15 test files.

## Fixture Hierarchy (conftest.py)

```
db (in-memory SQLite session)
├── sample_connection → ConnectionModel
│   └── sample_table → MonitoredTableModel
│       ├── sample_snapshot → SnapshotModel
│       ├── sample_anomaly → AnomalyModel
│       │   └── sample_incident → IncidentModel
│       └── sample_lineage_edges → [LineageEdgeModel]
└── api_client → TestClient
```

**Critical:** `sample_connection` only creates a ConnectionModel. For a monitored table, ALSO request `sample_table`.

## Two Test Environments

| Tests | Engine | Why |
|-------|--------|-----|
| Most tests (conftest `db`) | In-memory SQLite | Fast, isolated per test |
| `test_api.py`, `test_discovery_api.py` | Temp-file SQLite | Async + sync engines must share the same file |

## Known Gotchas

1. **`side_effect` overrides `return_value`** — When a mock has `side_effect` set, `return_value` is ignored. Clear with `mock.side_effect = None` before setting `return_value`.

2. **Lazy imports need source patching** — `notifier` is imported inside scanner functions at call time, not at module level. Patch at `aegis.services.notifier.notifier`, NOT `aegis.services.scanner.notifier`.

3. **Fixture dependencies** — If a test needs a table in the DB, requesting `sample_connection` alone is not enough. Must also request `sample_table`.

4. **Async test isolation** — `test_api.py` and `test_discovery_api.py` have their own `_reset_db` + `client` fixtures. Don't mix with conftest's `db` fixture.

## Your Protocol

1. Run the test suite (full or targeted)
2. Parse failures — identify the pattern (fixture, mock, async, logic)
3. Check the gotchas list above
4. For each failure, provide: file:line, cause, and specific fix
5. Verify fixes by re-running affected tests
6. Report final test count vs baseline

## Output Format

1. **Test Results** — pass/fail count, which tests failed
2. **Failure Analysis** — for each failure: cause, evidence, fix
3. **Gotcha Match** — whether any known gotcha applies
4. **Baseline Check** — current count vs 68 baseline
```

**Step 2: Verify**

```bash
head -5 aegis/.claude/agents/aegis-tester.md
```

**Step 3: Commit**

```bash
git add aegis/.claude/agents/aegis-tester.md
git commit -m "feat(aegis): add aegis-tester agent — test infrastructure expert"
```

---

### Task 8: Create `connector-debugger` agent

**Files:**
- Create: `aegis/.claude/agents/connector-debugger.md`

**Step 1: Write the agent file**

Create `aegis/.claude/agents/connector-debugger.md` with this content:

```markdown
---
name: connector-debugger
description: |
  Use this agent when debugging warehouse connection failures, discovery issues, or connector configuration problems. Specializes in WarehouseConnector, the Investigator discovery flow, and the async/sync bridge for discovery API calls.

  <example>
  Context: Connection test failing for a warehouse.
  user: "The Snowflake connection keeps timing out"
  assistant: "I'll deploy the connector-debugger agent to trace the connection flow."
  </example>

  <example>
  Context: Discovery returns empty results.
  user: "Discovery ran but found zero tables"
  assistant: "Let me use the connector-debugger to check the connector's schema introspection."
  </example>
model: sonnet
---

You are **Connector Debugger**, a specialist in Aegis warehouse connections and the discovery flow.

## Key Files

| Component | Path |
|-----------|------|
| WarehouseConnector | `aegis/backend/aegis/core/connectors.py` |
| Investigator agent | `aegis/backend/aegis/agents/investigator.py` |
| Investigator tools | `aegis/backend/aegis/agents/investigator_tools.py` |
| Discovery API | `aegis/backend/aegis/api/discovery.py` |
| Connection API | `aegis/backend/aegis/api/connections.py` |
| Models | `aegis/backend/aegis/core/models.py` |
| LangChain LLM | `aegis/backend/aegis/services/langchain_llm.py` |

## WarehouseConnector Methods

- `test_connection()` — validates connectivity
- `get_schemas()` — lists available schemas
- `get_tables(schema)` — lists tables in a schema
- `get_columns(schema, table)` — returns column metadata
- `get_row_count(schema, table)` — approximate row count
- `get_freshness(schema, table)` — last modified timestamp

## Discovery Flow

```
POST /api/v1/connections/{id}/discover
    → discovery.py: extract connection info from AsyncSession
    → asyncio.to_thread(run_investigator, ...)
        → investigator.py: create WarehouseConnector
        → make_tools(connector, db, lineage_graph)
        → LangChain AgentExecutor runs tools
        → classify tables (LLM or rule-based fallback)
    → return DiscoveryResult with classified tables
```

## Common Failure Points

| Symptom | Check | Likely Cause |
|---------|-------|-------------|
| Connection timeout | `test_connection()` | Wrong host/port, firewall, credentials |
| Empty schema list | `get_schemas()` | Insufficient permissions, wrong database |
| Tables found but 0 classified | Investigator output | LLM failure + fallback bug |
| Discovery hangs | `asyncio.to_thread` | Sync code blocking, no timeout |
| "Connector not found" | Connection type | Unsupported warehouse type |

## LangChain Tool Closure Pattern

```python
def make_tools(connector, db, lineage_graph):
    @tool
    def list_schemas() -> str:
        return connector.get_schemas()  # connector is closure-bound
    # ... 4 more tools
    return [list_schemas, ...]
```

**Gotcha:** If `connector` is None or stale, all tools will fail silently or raise confusing errors. Always verify the connector is valid before calling `make_tools()`.

## Investigation Protocol

1. Identify which step in the discovery flow is failing
2. Check connection parameters (host, port, database, credentials)
3. Verify connector method outputs (schema list, table list)
4. If LangChain tools fail, check closure binding
5. If classification is wrong, check `_classify_by_rules()` fallback
6. Trace through the async/sync bridge for API-level issues

## Output Format

1. **Failure Point** — which step in the discovery flow failed
2. **Connection Status** — can we reach the warehouse at all?
3. **Root Cause** — specific file:line with explanation
4. **Evidence** — error output, unexpected return values
5. **Fix** — minimal changes to resolve the issue
```

**Step 2: Verify**

```bash
head -5 aegis/.claude/agents/connector-debugger.md
```

**Step 3: Commit**

```bash
git add aegis/.claude/agents/connector-debugger.md
git commit -m "feat(aegis): add connector-debugger agent — warehouse connector specialist"
```

---

### Task 9: Create `settings.local.json`

**Files:**
- Create: `aegis/.claude/settings.local.json`

**Step 1: Write the settings file**

Create `aegis/.claude/settings.local.json`:

```json
{
  "permissions": {
    "allow": [],
    "deny": []
  }
}
```

Minimal — no overly permissive rules. Skills and agents are auto-discovered from the directory structure.

**Step 2: Verify**

```bash
cat aegis/.claude/settings.local.json | python3 -m json.tool
```

Expected: valid JSON, empty allow/deny arrays.

**Step 3: Commit**

```bash
git add aegis/.claude/settings.local.json
git commit -m "feat(aegis): add .claude settings for Aegis project"
```

---

### Task 10: Verify all skills and agents load correctly

**Step 1: List all created files**

```bash
find aegis/.claude -type f | sort
```

Expected:
```
aegis/.claude/agents/aegis-tester.md
aegis/.claude/agents/connector-debugger.md
aegis/.claude/agents/pipeline-expert.md
aegis/.claude/settings.local.json
aegis/.claude/skills/aegis-debug/SKILL.md
aegis/.claude/skills/aegis-test/SKILL.md
aegis/.claude/skills/issue-fix/SKILL.md
aegis/.claude/skills/pr-review/SKILL.md
```

**Step 2: Validate all YAML frontmatter**

```bash
for f in aegis/.claude/skills/*/SKILL.md aegis/.claude/agents/*.md; do
  echo "=== $f ==="
  head -3 "$f"
  echo
done
```

Expected: each file starts with `---` and has a `name:` field.

**Step 3: Check file sizes are reasonable**

```bash
wc -l aegis/.claude/skills/*/SKILL.md aegis/.claude/agents/*.md
```

Expected: each file is 80-200 lines.

**Step 4: Final commit (if any unstaged changes)**

```bash
git status
```

If clean, done. If not, stage and commit remaining files.
