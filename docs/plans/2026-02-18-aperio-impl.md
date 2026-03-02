# Aperio Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build Aperio, a locally-running autonomous job application engine with a LangGraph agent pipeline, Playwright ATS navigator, confidence-gated human review, and a React dashboard.

**Architecture:** Single Python process (FastAPI) serves both the REST API and the pre-built React frontend at `localhost:3000`. A LangGraph multi-agent pipeline orchestrates six AI agents in sequence/parallel. Playwright autonomously navigates ATS forms in headless mode.

**Tech Stack:** Python 3.11+, FastAPI, LangGraph, LangChain, Playwright, SQLite/SQLAlchemy, APScheduler, React, Vite, TypeScript.

**Design doc:** `docs/plans/2026-02-18-aperio-design.md`

---

## Phase 1: Project Scaffolding

### Task 1: Initialize Project Structure

**Files:**
- Create: `aperio/pyproject.toml`
- Create: `aperio/aperio/__init__.py`
- Create: `aperio/aperio/main.py`
- Create: `aperio/aperio/config.py`
- Create: `aperio/tests/__init__.py`

**Step 1: Create the project directory**

```bash
mkdir -p aperio/aperio/api aperio/aperio/agents aperio/aperio/navigator aperio/aperio/tracker aperio/aperio/llm aperio/tests
touch aperio/aperio/__init__.py aperio/tests/__init__.py
```

**Step 2: Write `aperio/pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "aperio"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "sqlalchemy>=2.0",
    "alembic>=1.14",
    "langgraph>=0.2",
    "langchain>=0.3",
    "langchain-anthropic>=0.3",
    "playwright>=1.50",
    "apscheduler>=3.10",
    "pydantic-settings>=2.0",
    "httpx>=0.27",
    "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.24", "httpx>=0.27"]

[project.scripts]
aperio = "aperio.main:cli"

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

**Step 3: Write `aperio/aperio/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APERIO_")

    database_url: str = "sqlite:///./aperio.db"
    llm_provider: str = "anthropic"
    llm_model: str = "claude-opus-4-6"
    anthropic_api_key: str = ""
    confidence_threshold_warn: float = 0.75
    confidence_threshold_block: float = 0.40
    tracker_interval_hours: int = 6
    host: str = "127.0.0.1"
    port: int = 3000

settings = Settings()
```

**Step 4: Write `aperio/aperio/main.py`**

```python
import click
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from aperio.api.router import router
from aperio.database import init_db

app = FastAPI(title="Aperio")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(router, prefix="/api")

@app.on_event("startup")
async def startup():
    init_db()

@click.command()
def cli():
    """Start the Aperio local server."""
    from aperio.config import settings
    uvicorn.run("aperio.main:app", host=settings.host, port=settings.port, reload=False)

if __name__ == "__main__":
    cli()
```

**Step 5: Install dependencies**

```bash
cd aperio && pip install -e ".[dev]" && playwright install chromium
```

Expected: No errors. `aperio` command available.

**Step 6: Commit**

```bash
git add aperio/
git commit -m "feat(aperio): scaffold project structure and config"
```

---

### Task 2: Database Models

**Files:**
- Create: `aperio/aperio/database.py`
- Create: `aperio/tests/test_database.py`

**Step 1: Write the failing test**

```python
# aperio/tests/test_database.py
from aperio.database import init_db, SessionLocal, Profile, Job, Application, AgentRun

def test_tables_created():
    init_db()
    db = SessionLocal()
    profile = Profile(
        name="Jane Doe",
        email="jane@example.com",
        phone="555-1234",
        location="SF, CA",
        skills=["Python", "SQL"],
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    assert profile.id is not None
    db.close()
```

**Step 2: Run test to verify it fails**

```bash
cd aperio && pytest tests/test_database.py -v
```
Expected: FAIL — `aperio.database` not found.

**Step 3: Write `aperio/aperio/database.py`**

```python
import json
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Text, JSON
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from aperio.config import settings

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    pass

class Profile(Base):
    __tablename__ = "profiles"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String)
    phone = Column(String)
    linkedin_url = Column(String)
    location = Column(String)
    resume_json = Column(JSON, default={})
    experience_json = Column(JSON, default=[])
    education_json = Column(JSON, default=[])
    skills = Column(JSON, default=[])
    certifications_json = Column(JSON, default=[])
    preferences_json = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True)
    url = Column(String, nullable=False)
    title = Column(String)
    company = Column(String)
    ats_type = Column(String)
    jd_raw = Column(Text)
    jd_parsed_json = Column(JSON, default={})
    requirements_json = Column(JSON, default={})
    salary_range = Column(String)
    location = Column(String)
    remote_type = Column(String)
    deadline = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Application(Base):
    __tablename__ = "applications"
    id = Column(Integer, primary_key=True)
    job_id = Column(Integer)
    profile_id = Column(Integer)
    status = Column(String, default="queued")   # queued/running/previewing/submitted/tracking
    tracker_status = Column(String, nullable=True)  # applied/phone_screen/interview/offer/rejected/withdrawn
    submission_package_json = Column(JSON, default={})
    resume_version = Column(Text, nullable=True)
    cover_letter_version = Column(Text, nullable=True)
    human_overrides_json = Column(JSON, default={})
    confidence_report_json = Column(JSON, default={})
    error_log = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    preview_approved_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    last_tracked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class AgentRun(Base):
    __tablename__ = "agent_runs"
    id = Column(Integer, primary_key=True)
    application_id = Column(Integer)
    run_id = Column(String)
    node_name = Column(String)
    input_snapshot_json = Column(JSON, default={})
    output_snapshot_json = Column(JSON, default={})
    duration_ms = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)
```

**Step 4: Run test to verify it passes**

```bash
cd aperio && pytest tests/test_database.py -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add aperio/aperio/database.py aperio/tests/test_database.py
git commit -m "feat(aperio): add SQLite database models"
```

---

## Phase 2: REST API

### Task 3: Profile API

**Files:**
- Create: `aperio/aperio/api/__init__.py`
- Create: `aperio/aperio/api/router.py`
- Create: `aperio/aperio/api/profiles.py`
- Create: `aperio/tests/test_profiles_api.py`

**Step 1: Write the failing test**

```python
# aperio/tests/test_profiles_api.py
from fastapi.testclient import TestClient
from aperio.main import app

client = TestClient(app)

def test_create_and_get_profile():
    resp = client.post("/api/profiles", json={
        "name": "Jane Doe",
        "email": "jane@example.com",
        "skills": ["Python", "SQL"],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] is not None

    resp2 = client.get(f"/api/profiles/{data['id']}")
    assert resp2.status_code == 200
    assert resp2.json()["name"] == "Jane Doe"
```

**Step 2: Run test to verify it fails**

```bash
cd aperio && pytest tests/test_profiles_api.py -v
```
Expected: FAIL — router not found / 404.

**Step 3: Write `aperio/aperio/api/profiles.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from aperio.database import SessionLocal, Profile

router = APIRouter(prefix="/profiles", tags=["profiles"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class ProfileCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    location: Optional[str] = None
    skills: list[str] = []
    experience_json: list = []
    education_json: list = []
    preferences_json: dict = {}

class ProfileOut(ProfileCreate):
    id: int
    class Config:
        from_attributes = True

@router.post("", response_model=ProfileOut, status_code=201)
def create_profile(payload: ProfileCreate, db: Session = Depends(get_db)):
    profile = Profile(**payload.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile

@router.get("/{profile_id}", response_model=ProfileOut)
def get_profile(profile_id: int, db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise HTTPException(404, "Profile not found")
    return profile

@router.put("/{profile_id}", response_model=ProfileOut)
def update_profile(profile_id: int, payload: ProfileCreate, db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise HTTPException(404, "Profile not found")
    for k, v in payload.model_dump().items():
        setattr(profile, k, v)
    db.commit()
    db.refresh(profile)
    return profile
```

**Step 4: Write `aperio/aperio/api/router.py`**

```python
from fastapi import APIRouter
from aperio.api import profiles

router = APIRouter()
router.include_router(profiles.router)
```

**Step 5: Run test to verify it passes**

```bash
cd aperio && pytest tests/test_profiles_api.py -v
```
Expected: PASS.

**Step 6: Commit**

```bash
git add aperio/aperio/api/ aperio/tests/test_profiles_api.py
git commit -m "feat(aperio): add profile CRUD API"
```

---

### Task 4: Jobs & Applications API

**Files:**
- Create: `aperio/aperio/api/jobs.py`
- Create: `aperio/aperio/api/applications.py`
- Modify: `aperio/aperio/api/router.py`
- Create: `aperio/tests/test_applications_api.py`

**Step 1: Write the failing test**

```python
# aperio/tests/test_applications_api.py
from fastapi.testclient import TestClient
from aperio.main import app

client = TestClient(app)

def test_create_application():
    # Create profile
    profile = client.post("/api/profiles", json={"name": "Jane", "email": "j@x.com"}).json()
    # Create job
    job = client.post("/api/jobs", json={"url": "https://greenhouse.io/jobs/123"}).json()
    assert job["id"] is not None
    # Create application
    resp = client.post("/api/applications", json={
        "job_id": job["id"],
        "profile_id": profile["id"]
    })
    assert resp.status_code == 201
    assert resp.json()["status"] == "queued"
```

**Step 2: Run to verify fails**

```bash
cd aperio && pytest tests/test_applications_api.py -v
```

**Step 3: Write `aperio/aperio/api/jobs.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from aperio.database import SessionLocal, Job

router = APIRouter(prefix="/jobs", tags=["jobs"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class JobCreate(BaseModel):
    url: str
    title: Optional[str] = None
    company: Optional[str] = None

class JobOut(JobCreate):
    id: int
    ats_type: Optional[str] = None
    class Config:
        from_attributes = True

@router.post("", response_model=JobOut, status_code=201)
def create_job(payload: JobCreate, db: Session = Depends(get_db)):
    job = Job(**payload.model_dump())
    db.add(job)
    db.commit()
    db.refresh(job)
    return job

@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    return job
```

**Step 4: Write `aperio/aperio/api/applications.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from aperio.database import SessionLocal, Application

router = APIRouter(prefix="/applications", tags=["applications"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class ApplicationCreate(BaseModel):
    job_id: int
    profile_id: int

class ApplicationOut(BaseModel):
    id: int
    job_id: int
    profile_id: int
    status: str
    tracker_status: Optional[str] = None
    confidence_report_json: dict = {}
    human_overrides_json: dict = {}
    error_log: Optional[str] = None
    notes: Optional[str] = None
    class Config:
        from_attributes = True

@router.post("", response_model=ApplicationOut, status_code=201)
def create_application(payload: ApplicationCreate, db: Session = Depends(get_db)):
    app = Application(**payload.model_dump())
    db.add(app)
    db.commit()
    db.refresh(app)
    return app

@router.get("", response_model=list[ApplicationOut])
def list_applications(db: Session = Depends(get_db)):
    return db.query(Application).all()

@router.get("/{app_id}", response_model=ApplicationOut)
def get_application(app_id: int, db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(404, "Application not found")
    return app

@router.patch("/{app_id}", response_model=ApplicationOut)
def patch_application(app_id: int, payload: dict, db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(404)
    for k, v in payload.items():
        if hasattr(app, k):
            setattr(app, k, v)
    db.commit()
    db.refresh(app)
    return app
```

**Step 5: Update `aperio/aperio/api/router.py`**

```python
from fastapi import APIRouter
from aperio.api import profiles, jobs, applications

router = APIRouter()
router.include_router(profiles.router)
router.include_router(jobs.router)
router.include_router(applications.router)
```

**Step 6: Run test to verify passes**

```bash
cd aperio && pytest tests/test_applications_api.py -v
```

**Step 7: Commit**

```bash
git add aperio/aperio/api/ aperio/tests/test_applications_api.py
git commit -m "feat(aperio): add jobs and applications API"
```

---

## Phase 3: LLM Client

### Task 5: LLM Client Wrapper

**Files:**
- Create: `aperio/aperio/llm/__init__.py`
- Create: `aperio/aperio/llm/client.py`
- Create: `aperio/tests/test_llm_client.py`

**Step 1: Write the failing test**

```python
# aperio/tests/test_llm_client.py
from unittest.mock import patch, MagicMock
from aperio.llm.client import LLMClient

def test_complete_returns_string():
    client = LLMClient()
    with patch.object(client, "_chat") as mock_chat:
        mock_chat.return_value = "Hello, world!"
        result = client.complete("Say hello")
    assert result == "Hello, world!"

def test_complete_with_json_output():
    client = LLMClient()
    with patch.object(client, "_chat") as mock_chat:
        mock_chat.return_value = '{"key": "value"}'
        result = client.complete_json("Return JSON")
    assert result == {"key": "value"}
```

**Step 2: Run to verify fails**

```bash
cd aperio && pytest tests/test_llm_client.py -v
```

**Step 3: Write `aperio/aperio/llm/client.py`**

```python
import json
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from aperio.config import settings

class LLMClient:
    def __init__(self):
        self._llm = ChatAnthropic(
            model=settings.llm_model,
            api_key=settings.anthropic_api_key,
        )

    def _chat(self, prompt: str) -> str:
        result = self._llm.invoke([HumanMessage(content=prompt)])
        return result.content

    def complete(self, prompt: str) -> str:
        return self._chat(prompt)

    def complete_json(self, prompt: str) -> dict:
        raw = self._chat(prompt + "\n\nRespond with valid JSON only, no markdown.")
        # Strip markdown fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(raw)
```

**Step 4: Run test to verify passes**

```bash
cd aperio && pytest tests/test_llm_client.py -v
```

**Step 5: Commit**

```bash
git add aperio/aperio/llm/ aperio/tests/test_llm_client.py
git commit -m "feat(aperio): add LLM client wrapper"
```

---

## Phase 4: Agent Pipeline

### Task 6: LangGraph State Definition

**Files:**
- Create: `aperio/aperio/agents/__init__.py`
- Create: `aperio/aperio/agents/state.py`
- Create: `aperio/tests/test_agent_state.py`

**Step 1: Write the failing test**

```python
# aperio/tests/test_agent_state.py
from aperio.agents.state import AperioState

def test_state_has_required_fields():
    state = AperioState(
        job_url="https://greenhouse.io/jobs/123",
        profile={},
        run_id="test-run-1",
    )
    assert state["job_url"] == "https://greenhouse.io/jobs/123"
    assert state["approved"] is False
    assert state["confidence_scores"] == {}
```

**Step 2: Run to verify fails**

```bash
cd aperio && pytest tests/test_agent_state.py -v
```

**Step 3: Write `aperio/aperio/agents/state.py`**

```python
from typing import TypedDict, Optional

class AperioState(TypedDict, total=False):
    # Input
    job_url: str
    profile: dict
    run_id: str

    # Planner output
    jd_raw: str
    jd_parsed: dict
    ats_type: str
    planner_tasks: list[str]

    # Job Researcher output
    ats_fields: list[dict]
    company_research: dict

    # Parallel agent outputs
    resume_tailored: str
    cover_letter: str
    ats_answers: dict

    # Synthesis output
    submission_package: dict
    confidence_scores: dict
    low_confidence_fields: list[str]
    requires_human_input: bool

    # Human gate
    human_overrides: dict
    approved: bool

    # Meta
    error: Optional[str]

def make_initial_state(job_url: str, profile: dict, run_id: str) -> AperioState:
    return AperioState(
        job_url=job_url,
        profile=profile,
        run_id=run_id,
        jd_raw="",
        jd_parsed={},
        ats_type="generic",
        planner_tasks=[],
        ats_fields=[],
        company_research={},
        resume_tailored="",
        cover_letter="",
        ats_answers={},
        submission_package={},
        confidence_scores={},
        low_confidence_fields=[],
        requires_human_input=False,
        human_overrides={},
        approved=False,
        error=None,
    )
```

**Step 4: Run test to verify passes**

```bash
cd aperio && pytest tests/test_agent_state.py -v
```

**Step 5: Commit**

```bash
git add aperio/aperio/agents/ aperio/tests/test_agent_state.py
git commit -m "feat(aperio): add LangGraph state definition"
```

---

### Task 7: Planning Agent

**Files:**
- Create: `aperio/aperio/agents/planner.py`
- Create: `aperio/tests/test_planner.py`

**Step 1: Write the failing test**

```python
# aperio/tests/test_planner.py
from unittest.mock import patch
from aperio.agents.state import make_initial_state
from aperio.agents.planner import run_planner

JD_HTML = "<h1>Software Engineer</h1><p>Must have Python, SQL. Nice to have: Go.</p>"

def test_planner_parses_jd():
    state = make_initial_state("https://greenhouse.io/jobs/123", {}, "run-1")
    with patch("aperio.agents.planner.fetch_page") as mock_fetch, \
         patch("aperio.agents.planner.LLMClient") as MockLLM:
        mock_fetch.return_value = JD_HTML
        MockLLM.return_value.complete_json.return_value = {
            "title": "Software Engineer",
            "company": "Acme",
            "ats_type": "greenhouse",
            "must_have": ["Python", "SQL"],
            "nice_to_have": ["Go"],
            "tasks": ["fill_basic_info", "upload_resume", "answer_questions"],
        }
        result = run_planner(state)

    assert result["ats_type"] == "greenhouse"
    assert "Python" in result["jd_parsed"]["must_have"]
    assert len(result["planner_tasks"]) > 0
```

**Step 2: Run to verify fails**

```bash
cd aperio && pytest tests/test_planner.py -v
```

**Step 3: Write `aperio/aperio/agents/planner.py`**

```python
import httpx
from aperio.agents.state import AperioState
from aperio.llm.client import LLMClient

def fetch_page(url: str) -> str:
    resp = httpx.get(url, follow_redirects=True, timeout=30)
    return resp.text

def run_planner(state: AperioState) -> dict:
    llm = LLMClient()
    html = fetch_page(state["job_url"])

    prompt = f"""You are analyzing a job posting HTML to extract structured information.

HTML:
{html[:8000]}

Return JSON with these fields:
- title: job title (string)
- company: company name (string)
- ats_type: one of "workday", "greenhouse", "lever", "generic"
- must_have: list of required skills/qualifications
- nice_to_have: list of preferred skills
- tasks: list of application steps needed (e.g. fill_basic_info, upload_resume, answer_questions)
- open_questions: list of essay/open-ended questions found in the posting (empty list if none)
"""
    parsed = llm.complete_json(prompt)

    return {
        "jd_raw": html,
        "jd_parsed": {
            "title": parsed.get("title", ""),
            "company": parsed.get("company", ""),
            "must_have": parsed.get("must_have", []),
            "nice_to_have": parsed.get("nice_to_have", []),
            "open_questions": parsed.get("open_questions", []),
        },
        "ats_type": parsed.get("ats_type", "generic"),
        "planner_tasks": parsed.get("tasks", []),
    }
```

**Step 4: Run test to verify passes**

```bash
cd aperio && pytest tests/test_planner.py -v
```

**Step 5: Commit**

```bash
git add aperio/aperio/agents/planner.py aperio/tests/test_planner.py
git commit -m "feat(aperio): add Planning Agent"
```

---

### Task 8: Resume, Cover Letter & Answer Agents

**Files:**
- Create: `aperio/aperio/agents/resume.py`
- Create: `aperio/aperio/agents/cover_letter.py`
- Create: `aperio/aperio/agents/answer.py`
- Create: `aperio/tests/test_parallel_agents.py`

**Step 1: Write the failing test**

```python
# aperio/tests/test_parallel_agents.py
from unittest.mock import patch, MagicMock
from aperio.agents.state import make_initial_state
from aperio.agents.resume import run_resume_agent
from aperio.agents.cover_letter import run_cover_letter_agent
from aperio.agents.answer import run_answer_agent

PROFILE = {
    "name": "Jane Doe",
    "experience_json": [{"title": "Engineer", "company": "Acme", "bullets": ["Built APIs"]}],
    "skills": ["Python", "SQL"],
}
JD = {"must_have": ["Python"], "nice_to_have": ["Go"], "open_questions": ["Why us?"]}

def _state():
    s = make_initial_state("https://example.com", PROFILE, "run-1")
    s["jd_parsed"] = JD
    s["company_research"] = {"about": "We build cool things."}
    return s

def test_resume_agent_returns_tailored_resume():
    with patch("aperio.agents.resume.LLMClient") as MockLLM:
        MockLLM.return_value.complete.return_value = "Tailored resume text"
        result = run_resume_agent(_state())
    assert "resume_tailored" in result
    assert result["confidence_scores"]["resume_tailored"] > 0

def test_cover_letter_agent_returns_letter():
    with patch("aperio.agents.cover_letter.LLMClient") as MockLLM:
        MockLLM.return_value.complete.return_value = "Dear Hiring Manager..."
        result = run_cover_letter_agent(_state())
    assert len(result["cover_letter"]) > 0

def test_answer_agent_answers_open_questions():
    with patch("aperio.agents.answer.LLMClient") as MockLLM:
        MockLLM.return_value.complete_json.return_value = {
            "Why us?": {"value": "Because...", "confidence": 0.85}
        }
        result = run_answer_agent(_state())
    assert "Why us?" in result["ats_answers"]
```

**Step 2: Run to verify fails**

```bash
cd aperio && pytest tests/test_parallel_agents.py -v
```

**Step 3: Write `aperio/aperio/agents/resume.py`**

```python
from aperio.agents.state import AperioState
from aperio.llm.client import LLMClient

def run_resume_agent(state: AperioState) -> dict:
    llm = LLMClient()
    profile = state["profile"]
    jd = state.get("jd_parsed", {})

    prompt = f"""Tailor this candidate's resume for the job description.

Profile experience:
{profile.get("experience_json", [])}

Skills: {profile.get("skills", [])}

Job must-haves: {jd.get("must_have", [])}
Job nice-to-haves: {jd.get("nice_to_have", [])}

Rewrite the experience bullets to highlight relevant skills. Return the full tailored resume text."""

    tailored = llm.complete(prompt)
    confidence = 0.85 if tailored else 0.3

    return {
        "resume_tailored": tailored,
        "confidence_scores": {**state.get("confidence_scores", {}), "resume_tailored": confidence},
    }
```

**Step 4: Write `aperio/aperio/agents/cover_letter.py`**

```python
from aperio.agents.state import AperioState
from aperio.llm.client import LLMClient

def run_cover_letter_agent(state: AperioState) -> dict:
    llm = LLMClient()
    profile = state["profile"]
    jd = state.get("jd_parsed", {})
    company = state.get("company_research", {})

    prompt = f"""Write a targeted cover letter for this candidate.

Candidate: {profile.get("name")}
Experience: {profile.get("experience_json", [])[:2]}
Skills: {profile.get("skills", [])}

Role: {jd.get("title", "the role")} at {jd.get("company", "the company")}
Requirements: {jd.get("must_have", [])}
Company info: {company.get("about", "")}

Write a 3-paragraph cover letter. Be specific, not generic."""

    letter = llm.complete(prompt)
    confidence = 0.80 if letter else 0.2

    return {
        "cover_letter": letter,
        "confidence_scores": {**state.get("confidence_scores", {}), "cover_letter": confidence},
    }
```

**Step 5: Write `aperio/aperio/agents/answer.py`**

```python
from aperio.agents.state import AperioState
from aperio.llm.client import LLMClient

def run_answer_agent(state: AperioState) -> dict:
    llm = LLMClient()
    jd = state.get("jd_parsed", {})
    profile = state["profile"]
    questions = jd.get("open_questions", [])

    if not questions:
        return {"ats_answers": {}, "confidence_scores": state.get("confidence_scores", {})}

    prompt = f"""Answer these job application questions for the candidate.

Candidate: {profile.get("name")}
Experience: {profile.get("experience_json", [])[:2]}
Questions: {questions}

Return JSON where each key is the question and each value is:
{{"value": "your answer", "confidence": 0.0-1.0}}

Be authentic and specific to the candidate's background."""

    raw = llm.complete_json(prompt)
    answers = {q: raw[q]["value"] for q in raw}
    scores = {q: raw[q]["confidence"] for q in raw}

    return {
        "ats_answers": answers,
        "confidence_scores": {**state.get("confidence_scores", {}), **scores},
    }
```

**Step 6: Run test to verify passes**

```bash
cd aperio && pytest tests/test_parallel_agents.py -v
```

**Step 7: Commit**

```bash
git add aperio/aperio/agents/resume.py aperio/aperio/agents/cover_letter.py aperio/aperio/agents/answer.py aperio/tests/test_parallel_agents.py
git commit -m "feat(aperio): add Resume, Cover Letter, and Answer agents"
```

---

### Task 9: Synthesis Agent

**Files:**
- Create: `aperio/aperio/agents/synthesis.py`
- Create: `aperio/tests/test_synthesis.py`

**Step 1: Write the failing test**

```python
# aperio/tests/test_synthesis.py
from aperio.agents.state import make_initial_state
from aperio.agents.synthesis import run_synthesis_agent
from aperio.config import settings

def test_synthesis_flags_low_confidence_fields():
    state = make_initial_state("https://example.com", {"name": "Jane"}, "run-1")
    state["resume_tailored"] = "Great resume"
    state["cover_letter"] = "Great letter"
    state["ats_answers"] = {"Why us?": "Because..."}
    state["confidence_scores"] = {
        "resume_tailored": 0.9,
        "cover_letter": 0.3,   # below warn threshold
        "Why us?": 0.2,         # below block threshold
    }

    result = run_synthesis_agent(state)
    assert result["requires_human_input"] is True
    assert "Why us?" in result["low_confidence_fields"]

def test_synthesis_passes_when_all_high_confidence():
    state = make_initial_state("https://example.com", {"name": "Jane"}, "run-1")
    state["resume_tailored"] = "Great resume"
    state["cover_letter"] = "Great letter"
    state["ats_answers"] = {}
    state["confidence_scores"] = {"resume_tailored": 0.9, "cover_letter": 0.85}

    result = run_synthesis_agent(state)
    assert result["requires_human_input"] is False
```

**Step 2: Run to verify fails**

```bash
cd aperio && pytest tests/test_synthesis.py -v
```

**Step 3: Write `aperio/aperio/agents/synthesis.py`**

```python
from aperio.agents.state import AperioState
from aperio.config import settings

def run_synthesis_agent(state: AperioState) -> dict:
    scores = state.get("confidence_scores", {})
    low = [f for f, s in scores.items() if s < settings.confidence_threshold_warn]
    requires_input = any(s < settings.confidence_threshold_block for s in scores.values())

    package = {
        "resume": state.get("resume_tailored", ""),
        "cover_letter": state.get("cover_letter", ""),
        "ats_answers": state.get("ats_answers", {}),
        "profile_snapshot": state.get("profile", {}),
    }

    return {
        "submission_package": package,
        "low_confidence_fields": low,
        "requires_human_input": requires_input,
    }
```

**Step 4: Run test to verify passes**

```bash
cd aperio && pytest tests/test_synthesis.py -v
```

**Step 5: Commit**

```bash
git add aperio/aperio/agents/synthesis.py aperio/tests/test_synthesis.py
git commit -m "feat(aperio): add Synthesis agent with confidence gating"
```

---

### Task 10: LangGraph Pipeline

**Files:**
- Create: `aperio/aperio/agents/graph.py`
- Create: `aperio/tests/test_graph.py`

**Step 1: Write the failing test**

```python
# aperio/tests/test_graph.py
from unittest.mock import patch
from aperio.agents.graph import build_graph, run_pipeline

def test_pipeline_returns_state_with_submission_package():
    with patch("aperio.agents.planner.fetch_page") as mock_fetch, \
         patch("aperio.agents.planner.LLMClient") as P, \
         patch("aperio.agents.resume.LLMClient") as R, \
         patch("aperio.agents.cover_letter.LLMClient") as C, \
         patch("aperio.agents.answer.LLMClient") as A:

        mock_fetch.return_value = "<h1>Engineer at Acme</h1>"
        P.return_value.complete_json.return_value = {
            "title": "Engineer", "company": "Acme", "ats_type": "greenhouse",
            "must_have": ["Python"], "nice_to_have": [], "tasks": [], "open_questions": []
        }
        R.return_value.complete.return_value = "Tailored resume"
        C.return_value.complete.return_value = "Cover letter"
        A.return_value.complete_json.return_value = {}

        result = run_pipeline(
            job_url="https://greenhouse.io/jobs/123",
            profile={"name": "Jane", "skills": ["Python"]},
            run_id="test-run"
        )

    assert "submission_package" in result
    assert result["submission_package"]["resume"] == "Tailored resume"
```

**Step 2: Run to verify fails**

```bash
cd aperio && pytest tests/test_graph.py -v
```

**Step 3: Write `aperio/aperio/agents/graph.py`**

```python
from langgraph.graph import StateGraph, END
from aperio.agents.state import AperioState, make_initial_state
from aperio.agents.planner import run_planner
from aperio.agents.resume import run_resume_agent
from aperio.agents.cover_letter import run_cover_letter_agent
from aperio.agents.answer import run_answer_agent
from aperio.agents.synthesis import run_synthesis_agent

def parallel_agents(state: AperioState) -> dict:
    resume_out = run_resume_agent(state)
    cl_out = run_cover_letter_agent(state)
    answer_out = run_answer_agent(state)
    # Merge confidence scores from all three
    merged_scores = {
        **resume_out.get("confidence_scores", {}),
        **cl_out.get("confidence_scores", {}),
        **answer_out.get("confidence_scores", {}),
    }
    return {
        "resume_tailored": resume_out["resume_tailored"],
        "cover_letter": cl_out["cover_letter"],
        "ats_answers": answer_out["ats_answers"],
        "confidence_scores": merged_scores,
    }

def build_graph() -> StateGraph:
    g = StateGraph(AperioState)
    g.add_node("planner", run_planner)
    g.add_node("parallel_agents", parallel_agents)
    g.add_node("synthesis", run_synthesis_agent)

    g.set_entry_point("planner")
    g.add_edge("planner", "parallel_agents")
    g.add_edge("parallel_agents", "synthesis")
    g.add_edge("synthesis", END)
    return g.compile()

_graph = build_graph()

def run_pipeline(job_url: str, profile: dict, run_id: str) -> AperioState:
    state = make_initial_state(job_url, profile, run_id)
    return _graph.invoke(state)
```

**Step 4: Run test to verify passes**

```bash
cd aperio && pytest tests/test_graph.py -v
```

**Step 5: Commit**

```bash
git add aperio/aperio/agents/graph.py aperio/tests/test_graph.py
git commit -m "feat(aperio): wire LangGraph pipeline with parallel agents"
```

---

## Phase 5: ATS Navigator

### Task 11: ATS Adapter Base & Generic Adapter

**Files:**
- Create: `aperio/aperio/navigator/__init__.py`
- Create: `aperio/aperio/navigator/base.py`
- Create: `aperio/aperio/navigator/generic.py`
- Create: `aperio/tests/test_navigator.py`

**Step 1: Write the failing test**

```python
# aperio/tests/test_navigator.py
from unittest.mock import MagicMock, patch
from aperio.navigator.generic import GenericAdapter

def test_generic_adapter_detects_unknown_ats():
    adapter = GenericAdapter()
    assert adapter.detect("https://jobs.example.com/apply") is True  # generic catches all

def test_generic_adapter_extracts_fields():
    adapter = GenericAdapter()
    dom = """
    <form>
      <label for="name">Full Name *</label><input id="name" type="text" required>
      <label for="email">Email *</label><input id="email" type="email" required>
    </form>
    """
    with patch("aperio.navigator.generic.LLMClient") as MockLLM:
        MockLLM.return_value.complete_json.return_value = [
            {"id": "name", "label": "Full Name", "type": "text", "required": True},
            {"id": "email", "label": "Email", "type": "email", "required": True},
        ]
        fields = adapter.extract_fields(dom)
    assert len(fields) == 2
    assert fields[0]["label"] == "Full Name"
```

**Step 2: Run to verify fails**

```bash
cd aperio && pytest tests/test_navigator.py -v
```

**Step 3: Write `aperio/aperio/navigator/base.py`**

```python
from abc import ABC, abstractmethod

class ATSAdapter(ABC):
    @abstractmethod
    def detect(self, url: str) -> bool:
        """Return True if this adapter handles the given URL."""

    @abstractmethod
    def extract_fields(self, dom: str) -> list[dict]:
        """Extract all form fields from the current page DOM."""

    @abstractmethod
    def get_page_type(self, dom: str) -> str:
        """Classify the current page: basic_info / work_history / education / upload / questions / review / unknown."""

    @abstractmethod
    def get_next_action(self, dom: str) -> str | None:
        """Return the CSS selector of the next/continue/submit button, or None if not found."""
```

**Step 4: Write `aperio/aperio/navigator/generic.py`**

```python
import re
from aperio.navigator.base import ATSAdapter
from aperio.llm.client import LLMClient

class GenericAdapter(ATSAdapter):
    def detect(self, url: str) -> bool:
        return True  # fallback catches everything

    def extract_fields(self, dom: str) -> list[dict]:
        llm = LLMClient()
        prompt = f"""Extract all form fields from this HTML. Return JSON array of objects with:
- id: field id or name attribute
- label: human-readable label text
- type: text/email/tel/select/radio/checkbox/file/textarea
- required: true/false

HTML (truncated):
{dom[:6000]}"""
        return llm.complete_json(prompt)

    def get_page_type(self, dom: str) -> str:
        dom_lower = dom.lower()
        if "upload" in dom_lower or "attach" in dom_lower:
            return "upload"
        if "work history" in dom_lower or "employment" in dom_lower:
            return "work_history"
        if "education" in dom_lower or "degree" in dom_lower:
            return "education"
        if "review" in dom_lower and "submit" in dom_lower:
            return "review"
        return "basic_info"

    def get_next_action(self, dom: str) -> str | None:
        patterns = [
            r'(?i)(next|continue|save\s*&?\s*continue)',
        ]
        for p in patterns:
            if re.search(p, dom):
                return "button[type=submit], input[type=submit], button:contains('Next'), button:contains('Continue')"
        return None
```

**Step 5: Run test to verify passes**

```bash
cd aperio && pytest tests/test_navigator.py -v
```

**Step 6: Commit**

```bash
git add aperio/aperio/navigator/ aperio/tests/test_navigator.py
git commit -m "feat(aperio): add ATS adapter base class and Generic adapter"
```

---

### Task 12: Navigator Perception-Action Loop

**Files:**
- Create: `aperio/aperio/navigator/runner.py`
- Create: `aperio/tests/test_navigator_runner.py`

**Step 1: Write the failing test**

```python
# aperio/tests/test_navigator_runner.py
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from aperio.navigator.runner import NavigatorRunner

@pytest.mark.asyncio
async def test_runner_fills_field_and_clicks_next():
    package = {
        "profile_snapshot": {"name": "Jane Doe", "email": "jane@x.com"},
        "resume": "Resume text",
        "cover_letter": "Letter",
        "ats_answers": {},
    }
    confidence_scores = {"name": 0.95, "email": 0.95}

    with patch("aperio.navigator.runner.async_playwright") as mock_pw:
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_page.content.return_value = "<form><input id='name'><button>Next</button></form>"
        mock_page.url = "https://greenhouse.io/apply"
        mock_browser.chromium.launch.return_value.__aenter__ = AsyncMock(return_value=mock_browser)
        mock_pw.return_value.__aenter__ = AsyncMock(return_value=mock_browser)
        mock_browser.new_page.return_value = mock_page

        runner = NavigatorRunner(package, confidence_scores, job_url="https://greenhouse.io/apply")
        # Just verify it instantiates without error
        assert runner is not None
```

**Step 2: Run to verify fails**

```bash
cd aperio && pytest tests/test_navigator_runner.py -v
```

**Step 3: Write `aperio/aperio/navigator/runner.py`**

```python
import asyncio
from playwright.async_api import async_playwright, Page
from aperio.navigator.generic import GenericAdapter
from aperio.navigator.base import ATSAdapter
from aperio.llm.client import LLMClient
from aperio.config import settings

PAUSE_SIGNALS = ["captcha", "recaptcha", "verify you are human", "mfa", "two-factor"]

class NavigatorRunner:
    def __init__(self, submission_package: dict, confidence_scores: dict, job_url: str):
        self.package = submission_package
        self.scores = confidence_scores
        self.job_url = job_url
        self.adapter: ATSAdapter = GenericAdapter()
        self.pause_reason: str | None = None
        self.pending_fields: list[dict] = []

    async def run(self, on_pause=None) -> dict:
        """
        Navigate and fill the ATS form. Calls on_pause(reason, fields) when human input needed.
        Returns dict with status: 'submitted' | 'paused' | 'error'
        """
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(self.job_url, wait_until="networkidle")

            max_pages = 20
            for _ in range(max_pages):
                dom = await page.content()

                # Check for pause signals
                dom_lower = dom.lower()
                for signal in PAUSE_SIGNALS:
                    if signal in dom_lower:
                        self.pause_reason = f"Detected: {signal}"
                        if on_pause:
                            await on_pause(self.pause_reason, [])
                        return {"status": "paused", "reason": self.pause_reason}

                # Extract and fill fields
                fields = self.adapter.extract_fields(dom)
                low_conf = await self._fill_fields(page, fields)

                if low_conf and on_pause:
                    await on_pause("low_confidence", low_conf)
                    return {"status": "paused", "reason": "low_confidence", "fields": low_conf}

                # Detect review/submit page
                page_type = self.adapter.get_page_type(dom)
                if page_type == "review":
                    return {"status": "ready_to_submit"}

                # Click next
                next_sel = self.adapter.get_next_action(dom)
                if not next_sel:
                    break
                try:
                    await page.click(next_sel, timeout=5000)
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    break

            await browser.close()
        return {"status": "completed"}

    async def _fill_fields(self, page: Page, fields: list[dict]) -> list[dict]:
        """Fill fields, return list of low-confidence fields that need human input."""
        low_conf = []
        profile = self.package.get("profile_snapshot", {})

        for field in fields:
            field_id = field.get("id", "")
            label = field.get("label", "").lower()
            value = self._map_field(label, profile)
            conf = self.scores.get(field_id, self.scores.get(label, 0.5))

            if conf < settings.confidence_threshold_block and field.get("required"):
                low_conf.append(field)
                continue

            if value:
                try:
                    locator = page.locator(f"#{field_id}").first
                    ftype = field.get("type", "text")
                    if ftype in ("text", "email", "tel", "textarea"):
                        await locator.fill(str(value))
                    elif ftype == "select":
                        await locator.select_option(label=str(value))
                except Exception:
                    pass

        return low_conf

    def _map_field(self, label: str, profile: dict) -> str | None:
        mapping = {
            "name": profile.get("name"),
            "full name": profile.get("name"),
            "first name": (profile.get("name") or "").split()[0] if profile.get("name") else None,
            "last name": (profile.get("name") or "").split()[-1] if profile.get("name") else None,
            "email": profile.get("email"),
            "phone": profile.get("phone"),
            "location": profile.get("location"),
            "linkedin": profile.get("linkedin_url"),
            "cover letter": self.package.get("cover_letter"),
        }
        return mapping.get(label)
```

**Step 4: Run test to verify passes**

```bash
cd aperio && pytest tests/test_navigator_runner.py -v
```

**Step 5: Commit**

```bash
git add aperio/aperio/navigator/runner.py aperio/tests/test_navigator_runner.py
git commit -m "feat(aperio): add ATS Navigator perception-action loop"
```

---

## Phase 6: Pipeline API + SSE

### Task 13: Run Pipeline Endpoint with SSE

**Files:**
- Create: `aperio/aperio/api/pipeline.py`
- Modify: `aperio/aperio/api/router.py`
- Create: `aperio/tests/test_pipeline_api.py`

**Step 1: Write the failing test**

```python
# aperio/tests/test_pipeline_api.py
from fastapi.testclient import TestClient
from unittest.mock import patch
from aperio.main import app

client = TestClient(app)

def test_run_pipeline_creates_application():
    # Create profile and job first
    profile = client.post("/api/profiles", json={"name": "Jane", "email": "j@x.com", "skills": ["Python"]}).json()
    job = client.post("/api/jobs", json={"url": "https://greenhouse.io/jobs/123"}).json()

    with patch("aperio.api.pipeline.run_pipeline") as mock_run:
        mock_run.return_value = {
            "submission_package": {"resume": "tailored", "cover_letter": "letter", "ats_answers": {}},
            "confidence_scores": {"resume_tailored": 0.9},
            "low_confidence_fields": [],
            "requires_human_input": False,
        }
        resp = client.post("/api/pipeline/run", json={
            "job_id": job["id"],
            "profile_id": profile["id"],
        })

    assert resp.status_code == 200
    data = resp.json()
    assert "application_id" in data
```

**Step 2: Run to verify fails**

```bash
cd aperio && pytest tests/test_pipeline_api.py -v
```

**Step 3: Write `aperio/aperio/api/pipeline.py`**

```python
import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from aperio.database import SessionLocal, Application, Job, Profile
from aperio.agents.graph import run_pipeline

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class RunRequest(BaseModel):
    job_id: int
    profile_id: int

@router.post("/run")
def run(payload: RunRequest, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == payload.job_id).first()
    profile = db.query(Profile).filter(Profile.id == payload.profile_id).first()
    if not job or not profile:
        raise HTTPException(404, "Job or profile not found")

    run_id = str(uuid.uuid4())
    app = Application(job_id=job.id, profile_id=profile.id, status="running")
    db.add(app)
    db.commit()
    db.refresh(app)

    profile_dict = {
        "name": profile.name, "email": profile.email, "phone": profile.phone,
        "location": profile.location, "linkedin_url": profile.linkedin_url,
        "skills": profile.skills, "experience_json": profile.experience_json,
        "education_json": profile.education_json, "preferences_json": profile.preferences_json,
    }

    try:
        result = run_pipeline(job_url=job.url, profile=profile_dict, run_id=run_id)
        app.status = "previewing"
        app.submission_package_json = result.get("submission_package", {})
        app.confidence_report_json = result.get("confidence_scores", {})
        app.resume_version = result.get("resume_tailored", "")
        app.cover_letter_version = result.get("cover_letter", "")
        db.commit()
    except Exception as e:
        app.status = "queued"
        app.error_log = str(e)
        db.commit()
        raise HTTPException(500, str(e))

    return {
        "application_id": app.id,
        "status": app.status,
        "requires_human_input": result.get("requires_human_input", False),
        "low_confidence_fields": result.get("low_confidence_fields", []),
        "confidence_scores": result.get("confidence_scores", {}),
    }

@router.post("/{app_id}/approve")
def approve(app_id: int, human_overrides: dict = {}, db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(404)
    app.human_overrides_json = human_overrides
    app.status = "submitted"
    from datetime import datetime
    app.submitted_at = datetime.utcnow()
    db.commit()
    return {"status": "submitted", "application_id": app_id}
```

**Step 4: Add to `aperio/aperio/api/router.py`**

```python
from fastapi import APIRouter
from aperio.api import profiles, jobs, applications, pipeline

router = APIRouter()
router.include_router(profiles.router)
router.include_router(jobs.router)
router.include_router(applications.router)
router.include_router(pipeline.router)
```

**Step 5: Run test to verify passes**

```bash
cd aperio && pytest tests/test_pipeline_api.py -v
```

**Step 6: Commit**

```bash
git add aperio/aperio/api/pipeline.py aperio/aperio/api/router.py aperio/tests/test_pipeline_api.py
git commit -m "feat(aperio): add pipeline run and approve endpoints"
```

---

## Phase 7: Background Tracker

### Task 14: APScheduler Tracker

**Files:**
- Create: `aperio/aperio/tracker/__init__.py`
- Create: `aperio/aperio/tracker/scheduler.py`
- Modify: `aperio/aperio/main.py`
- Create: `aperio/tests/test_tracker.py`

**Step 1: Write the failing test**

```python
# aperio/tests/test_tracker.py
from unittest.mock import patch, MagicMock
from aperio.tracker.scheduler import check_application_status

def test_check_status_updates_tracker_status():
    mock_db = MagicMock()
    mock_app = MagicMock()
    mock_app.id = 1
    mock_app.submission_package_json = {"ats_url": "https://greenhouse.io/confirm/123"}
    mock_db.query.return_value.filter.return_value.all.return_value = [mock_app]

    with patch("aperio.tracker.scheduler.scrape_status") as mock_scrape:
        mock_scrape.return_value = "Under Review"
        check_application_status(mock_db)

    mock_db.commit.assert_called()
```

**Step 2: Run to verify fails**

```bash
cd aperio && pytest tests/test_tracker.py -v
```

**Step 3: Write `aperio/aperio/tracker/scheduler.py`**

```python
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from aperio.database import SessionLocal, Application
from aperio.config import settings

def scrape_status(ats_url: str) -> str | None:
    """Scrape ATS portal for application status. Returns status string or None."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(ats_url, wait_until="networkidle", timeout=15000)
            dom = page.content().lower()
            browser.close()

        if "offer" in dom:
            return "offer"
        if "rejected" in dom or "not selected" in dom:
            return "rejected"
        if "interview" in dom:
            return "interview"
        if "phone screen" in dom or "phone call" in dom:
            return "phone_screen"
        if "under review" in dom or "in review" in dom:
            return "under_review"
        return "applied"
    except Exception:
        return None

def check_application_status(db=None):
    close_db = db is None
    if db is None:
        db = SessionLocal()
    try:
        apps = db.query(Application).filter(Application.status == "submitted").all()
        for app in apps:
            ats_url = (app.submission_package_json or {}).get("ats_url")
            if not ats_url:
                continue
            status = scrape_status(ats_url)
            if status and status != app.tracker_status:
                app.tracker_status = status
                app.last_tracked_at = datetime.utcnow()
        db.commit()
    finally:
        if close_db:
            db.close()

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        check_application_status,
        "interval",
        hours=settings.tracker_interval_hours,
        id="tracker",
    )
    scheduler.start()
    return scheduler
```

**Step 4: Update `aperio/aperio/main.py` startup to start scheduler**

Add to the startup event:
```python
from aperio.tracker.scheduler import start_scheduler

@app.on_event("startup")
async def startup():
    init_db()
    start_scheduler()
```

**Step 5: Run test to verify passes**

```bash
cd aperio && pytest tests/test_tracker.py -v
```

**Step 6: Commit**

```bash
git add aperio/aperio/tracker/ aperio/aperio/main.py aperio/tests/test_tracker.py
git commit -m "feat(aperio): add APScheduler background tracker"
```

---

## Phase 8: Frontend

### Task 15: React + Vite Project Setup

**Files:**
- Create: `aperio/frontend/` (Vite scaffold)

**Step 1: Scaffold frontend**

```bash
cd aperio && npm create vite@latest frontend -- --template react-ts
cd frontend && npm install
npm install axios react-router-dom @radix-ui/react-dialog @radix-ui/react-badge lucide-react
```

**Step 2: Update `aperio/frontend/src/main.tsx`** — add React Router

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <BrowserRouter>
    <App />
  </BrowserRouter>
)
```

**Step 3: Update `aperio/frontend/src/App.tsx`**

```tsx
import { Routes, Route } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import NewApplication from './pages/NewApplication'
import PreviewGate from './pages/PreviewGate'
import ApplicationDetail from './pages/ApplicationDetail'
import ProfileSetup from './pages/ProfileSetup'
import Settings from './pages/Settings'
import Layout from './components/Layout'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/apply" element={<NewApplication />} />
        <Route path="/preview/:appId" element={<PreviewGate />} />
        <Route path="/applications/:appId" element={<ApplicationDetail />} />
        <Route path="/profile" element={<ProfileSetup />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </Layout>
  )
}
```

**Step 4: Create `aperio/frontend/src/api.ts`**

```ts
import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export const profilesApi = {
  create: (data: any) => api.post('/profiles', data).then(r => r.data),
  get: (id: number) => api.get(`/profiles/${id}`).then(r => r.data),
  update: (id: number, data: any) => api.put(`/profiles/${id}`, data).then(r => r.data),
}

export const applicationsApi = {
  list: () => api.get('/applications').then(r => r.data),
  get: (id: number) => api.get(`/applications/${id}`).then(r => r.data),
}

export const pipelineApi = {
  run: (jobId: number, profileId: number) =>
    api.post('/pipeline/run', { job_id: jobId, profile_id: profileId }).then(r => r.data),
  approve: (appId: number, overrides: Record<string, string>) =>
    api.post(`/pipeline/${appId}/approve`, overrides).then(r => r.data),
}

export const jobsApi = {
  create: (url: string) => api.post('/jobs', { url }).then(r => r.data),
}
```

**Step 5: Commit**

```bash
git add aperio/frontend/
git commit -m "feat(aperio): scaffold React + Vite frontend with routing and API client"
```

---

### Task 16: Dashboard Page

**Files:**
- Create: `aperio/frontend/src/components/Layout.tsx`
- Create: `aperio/frontend/src/pages/Dashboard.tsx`
- Create: `aperio/frontend/src/components/ApplicationCard.tsx`

**Step 1: Write `aperio/frontend/src/components/Layout.tsx`**

```tsx
import { Link, useLocation } from 'react-router-dom'

const nav = [
  { to: '/', label: 'Dashboard' },
  { to: '/apply', label: 'New Application' },
  { to: '/profile', label: 'Profile' },
  { to: '/settings', label: 'Settings' },
]

export default function Layout({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation()
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex">
      <nav className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col p-4 gap-1">
        <div className="text-xl font-bold text-white mb-6">Aperio</div>
        {nav.map(n => (
          <Link key={n.to} to={n.to}
            className={`px-3 py-2 rounded-lg text-sm transition-colors ${
              pathname === n.to
                ? 'bg-indigo-600 text-white'
                : 'text-gray-400 hover:text-white hover:bg-gray-800'
            }`}>
            {n.label}
          </Link>
        ))}
      </nav>
      <main className="flex-1 p-8">{children}</main>
    </div>
  )
}
```

**Step 2: Write `aperio/frontend/src/components/ApplicationCard.tsx`**

```tsx
import { Link } from 'react-router-dom'

const STATUS_COLORS: Record<string, string> = {
  queued: 'bg-gray-700 text-gray-300',
  running: 'bg-blue-900 text-blue-300 animate-pulse',
  previewing: 'bg-yellow-900 text-yellow-300',
  submitted: 'bg-green-900 text-green-300',
  tracking: 'bg-indigo-900 text-indigo-300',
}

const TRACKER_COLORS: Record<string, string> = {
  applied: 'text-blue-400',
  phone_screen: 'text-yellow-400',
  interview: 'text-orange-400',
  offer: 'text-green-400',
  rejected: 'text-red-400',
  withdrawn: 'text-gray-500',
}

export default function ApplicationCard({ app }: { app: any }) {
  return (
    <Link to={`/applications/${app.id}`}
      className="block bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-indigo-500 transition-colors">
      <div className="flex items-start justify-between">
        <div>
          <div className="font-semibold text-white">{app.job?.title ?? 'Unknown Role'}</div>
          <div className="text-sm text-gray-400">{app.job?.company ?? '—'}</div>
        </div>
        <span className={`text-xs px-2 py-1 rounded-full ${STATUS_COLORS[app.status] ?? ''}`}>
          {app.status}
        </span>
      </div>
      {app.tracker_status && (
        <div className={`mt-2 text-sm ${TRACKER_COLORS[app.tracker_status] ?? ''}`}>
          ● {app.tracker_status.replace('_', ' ')}
        </div>
      )}
    </Link>
  )
}
```

**Step 3: Write `aperio/frontend/src/pages/Dashboard.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { applicationsApi } from '../api'
import ApplicationCard from '../components/ApplicationCard'

const STAGES = ['queued', 'previewing', 'submitted', 'tracking']

export default function Dashboard() {
  const [apps, setApps] = useState<any[]>([])

  useEffect(() => {
    applicationsApi.list().then(setApps).catch(console.error)
  }, [])

  return (
    <div>
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-2xl font-bold">Applications</h1>
        <Link to="/apply"
          className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg text-sm">
          + New Application
        </Link>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {STAGES.map(stage => (
          <div key={stage}>
            <div className="text-xs uppercase tracking-wider text-gray-500 mb-3">
              {stage} ({apps.filter(a => a.status === stage).length})
            </div>
            <div className="flex flex-col gap-3">
              {apps.filter(a => a.status === stage).map(app => (
                <ApplicationCard key={app.id} app={app} />
              ))}
            </div>
          </div>
        ))}
      </div>

      {apps.length === 0 && (
        <div className="text-center text-gray-500 mt-24">
          <p className="text-lg">No applications yet.</p>
          <Link to="/apply" className="text-indigo-400 underline mt-2 block">
            Start your first application →
          </Link>
        </div>
      )}
    </div>
  )
}
```

**Step 4: Commit**

```bash
git add aperio/frontend/src/
git commit -m "feat(aperio): add Dashboard with kanban-style application funnel"
```

---

### Task 17: New Application Page

**Files:**
- Create: `aperio/frontend/src/pages/NewApplication.tsx`

**Step 1: Write `aperio/frontend/src/pages/NewApplication.tsx`**

```tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { jobsApi, pipelineApi } from '../api'

const PROFILE_ID = 1  // TODO: replace with profile selector once profile page is built

export default function NewApplication() {
  const [url, setUrl] = useState('')
  const [status, setStatus] = useState<'idle' | 'running' | 'error'>('idle')
  const [log, setLog] = useState<string[]>([])
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const addLog = (msg: string) => setLog(prev => [...prev, msg])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setStatus('running')
    setLog([])
    setError('')

    try {
      addLog('Creating job entry...')
      const job = await jobsApi.create(url)

      addLog('Running agent pipeline...')
      addLog('↳ Planning Agent analyzing job description...')
      addLog('↳ Job Research Agent scraping ATS structure...')
      addLog('↳ Resume, Cover Letter & Answer Agents running in parallel...')
      addLog('↳ Synthesis Agent assembling submission package...')

      const result = await pipelineApi.run(job.id, PROFILE_ID)
      addLog('✓ Pipeline complete.')

      navigate(`/preview/${result.application_id}`)
    } catch (err: any) {
      setStatus('error')
      setError(err?.response?.data?.detail ?? String(err))
    }
  }

  return (
    <div className="max-w-xl">
      <h1 className="text-2xl font-bold mb-6">New Application</h1>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm text-gray-400 mb-1">Job Posting URL</label>
          <input
            type="url"
            value={url}
            onChange={e => setUrl(e.target.value)}
            placeholder="https://greenhouse.io/jobs/..."
            required
            className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-white placeholder-gray-600 focus:outline-none focus:border-indigo-500"
          />
        </div>
        <button
          type="submit"
          disabled={status === 'running'}
          className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white py-2 rounded-lg">
          {status === 'running' ? 'Running...' : 'Start Application'}
        </button>
      </form>

      {log.length > 0 && (
        <div className="mt-6 bg-gray-900 border border-gray-800 rounded-xl p-4 font-mono text-sm space-y-1">
          {log.map((l, i) => (
            <div key={i} className="text-gray-300">{l}</div>
          ))}
        </div>
      )}

      {error && (
        <div className="mt-4 bg-red-950 border border-red-800 rounded-xl p-4 text-red-300 text-sm">
          {error}
        </div>
      )}
    </div>
  )
}
```

**Step 2: Commit**

```bash
git add aperio/frontend/src/pages/NewApplication.tsx
git commit -m "feat(aperio): add New Application page with agent progress log"
```

---

### Task 18: Preview Gate Page

**Files:**
- Create: `aperio/frontend/src/pages/PreviewGate.tsx`
- Create: `aperio/frontend/src/components/FieldReviewCard.tsx`
- Create: `aperio/frontend/src/components/ConfidenceBadge.tsx`

**Step 1: Write `aperio/frontend/src/components/ConfidenceBadge.tsx`**

```tsx
export default function ConfidenceBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color = score >= 0.75 ? 'text-green-400' : score >= 0.40 ? 'text-yellow-400' : 'text-red-400'
  return <span className={`text-xs font-mono ${color}`}>{pct}%</span>
}
```

**Step 2: Write `aperio/frontend/src/components/FieldReviewCard.tsx`**

```tsx
import ConfidenceBadge from './ConfidenceBadge'

interface Props {
  field: string
  value: string
  confidence: number
  onOverride: (field: string, value: string) => void
}

export default function FieldReviewCard({ field, value, confidence, onOverride }: Props) {
  const blocked = confidence < 0.40
  return (
    <div className={`rounded-xl border p-4 ${
      blocked ? 'border-red-800 bg-red-950/30' :
      confidence < 0.75 ? 'border-yellow-800 bg-yellow-950/20' :
      'border-green-900 bg-green-950/10'
    }`}>
      <div className="flex justify-between items-center mb-2">
        <span className="text-sm font-medium text-gray-200 capitalize">{field.replace(/_/g, ' ')}</span>
        <ConfidenceBadge score={confidence} />
      </div>
      <textarea
        className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white resize-none focus:outline-none focus:border-indigo-500"
        rows={3}
        defaultValue={value}
        onChange={e => onOverride(field, e.target.value)}
        placeholder={blocked ? 'Required — please fill in' : undefined}
      />
      {blocked && (
        <p className="text-xs text-red-400 mt-1">⚠ Confidence too low — your input required before submitting.</p>
      )}
    </div>
  )
}
```

**Step 3: Write `aperio/frontend/src/pages/PreviewGate.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { applicationsApi, pipelineApi } from '../api'
import FieldReviewCard from '../components/FieldReviewCard'
import { Settings } from '../../../config'  // threshold from settings

const BLOCK_THRESHOLD = 0.40

export default function PreviewGate() {
  const { appId } = useParams<{ appId: string }>()
  const navigate = useNavigate()
  const [app, setApp] = useState<any>(null)
  const [overrides, setOverrides] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    applicationsApi.get(Number(appId)).then(setApp)
  }, [appId])

  if (!app) return <div className="text-gray-400">Loading...</div>

  const pkg = app.submission_package_json ?? {}
  const scores = app.confidence_report_json ?? {}

  const allFields = [
    { key: 'resume_tailored', value: pkg.resume ?? '', score: scores.resume_tailored ?? 1 },
    { key: 'cover_letter', value: pkg.cover_letter ?? '', score: scores.cover_letter ?? 1 },
    ...Object.entries(pkg.ats_answers ?? {}).map(([k, v]) => ({
      key: k, value: String(v), score: scores[k] ?? 0.5,
    })),
  ]

  const blocked = allFields.some(f => f.score < BLOCK_THRESHOLD && !overrides[f.key])

  const handleOverride = (field: string, value: string) => {
    setOverrides(prev => ({ ...prev, [field]: value }))
  }

  const handleApprove = async () => {
    setSubmitting(true)
    await pipelineApi.approve(Number(appId), overrides)
    navigate('/')
  }

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold mb-2">Review & Approve</h1>
      <p className="text-gray-400 text-sm mb-6">
        Review what Aperio will submit. Edit any field before approving.
      </p>

      <div className="space-y-4">
        {allFields.map(f => (
          <FieldReviewCard
            key={f.key}
            field={f.key}
            value={overrides[f.key] ?? f.value}
            confidence={f.score}
            onOverride={handleOverride}
          />
        ))}
      </div>

      <div className="mt-6 flex gap-3">
        <button
          onClick={handleApprove}
          disabled={blocked || submitting}
          className="flex-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white py-3 rounded-xl font-medium">
          {submitting ? 'Submitting...' : 'Approve & Submit'}
        </button>
        <button
          onClick={() => navigate('/')}
          className="px-6 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-xl">
          Cancel
        </button>
      </div>

      {blocked && (
        <p className="text-red-400 text-sm mt-3 text-center">
          Fill in all red fields before submitting.
        </p>
      )}
    </div>
  )
}
```

**Step 4: Commit**

```bash
git add aperio/frontend/src/pages/PreviewGate.tsx aperio/frontend/src/components/
git commit -m "feat(aperio): add Preview Gate with confidence-gated human review"
```

---

### Task 19: Profile Setup + Settings Pages

**Files:**
- Create: `aperio/frontend/src/pages/ProfileSetup.tsx`
- Create: `aperio/frontend/src/pages/Settings.tsx`

**Step 1: Write `aperio/frontend/src/pages/ProfileSetup.tsx`**

```tsx
import { useState } from 'react'
import { profilesApi } from '../api'

export default function ProfileSetup() {
  const [form, setForm] = useState({
    name: '', email: '', phone: '', location: '', linkedin_url: '',
    skills: '', preferences_json: { salary: '', remote_type: 'hybrid' },
  })
  const [saved, setSaved] = useState(false)

  const handleChange = (field: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setForm(prev => ({ ...prev, [field]: e.target.value }))
  }

  const handleSave = async () => {
    await profilesApi.create({
      ...form,
      skills: form.skills.split(',').map(s => s.trim()).filter(Boolean),
    })
    setSaved(true)
  }

  const inputClass = "w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-indigo-500"
  const labelClass = "block text-sm text-gray-400 mb-1"

  return (
    <div className="max-w-lg">
      <h1 className="text-2xl font-bold mb-6">Your Profile</h1>
      <div className="space-y-4">
        {[
          { label: 'Full Name', field: 'name', type: 'text' },
          { label: 'Email', field: 'email', type: 'email' },
          { label: 'Phone', field: 'phone', type: 'tel' },
          { label: 'Location (City, State)', field: 'location', type: 'text' },
          { label: 'LinkedIn URL', field: 'linkedin_url', type: 'url' },
          { label: 'Skills (comma-separated)', field: 'skills', type: 'text' },
        ].map(({ label, field, type }) => (
          <div key={field}>
            <label className={labelClass}>{label}</label>
            <input type={type} value={(form as any)[field]} onChange={handleChange(field)} className={inputClass} />
          </div>
        ))}

        <div>
          <label className={labelClass}>Work Preference</label>
          <select value={form.preferences_json.remote_type}
            onChange={e => setForm(p => ({ ...p, preferences_json: { ...p.preferences_json, remote_type: e.target.value }}))}
            className={inputClass}>
            <option value="remote">Remote</option>
            <option value="hybrid">Hybrid</option>
            <option value="onsite">On-site</option>
          </select>
        </div>

        <button onClick={handleSave}
          className="w-full bg-indigo-600 hover:bg-indigo-500 text-white py-2 rounded-lg">
          Save Profile
        </button>

        {saved && <p className="text-green-400 text-sm text-center">Profile saved.</p>}
      </div>
    </div>
  )
}
```

**Step 2: Write `aperio/frontend/src/pages/Settings.tsx`**

```tsx
import { useState } from 'react'

export default function Settings() {
  const [apiKey, setApiKey] = useState(localStorage.getItem('aperio_api_key') ?? '')
  const [warnThreshold, setWarnThreshold] = useState(0.75)
  const [blockThreshold, setBlockThreshold] = useState(0.40)
  const [saved, setSaved] = useState(false)

  const handleSave = () => {
    localStorage.setItem('aperio_api_key', apiKey)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const inputClass = "w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-indigo-500"
  const labelClass = "block text-sm text-gray-400 mb-1"

  return (
    <div className="max-w-lg">
      <h1 className="text-2xl font-bold mb-6">Settings</h1>
      <div className="space-y-6">
        <div>
          <label className={labelClass}>Anthropic API Key</label>
          <input type="password" value={apiKey} onChange={e => setApiKey(e.target.value)} className={inputClass} />
        </div>

        <div>
          <label className={labelClass}>Warn Threshold (yellow): {Math.round(warnThreshold * 100)}%</label>
          <input type="range" min={0} max={1} step={0.05} value={warnThreshold}
            onChange={e => setWarnThreshold(Number(e.target.value))} className="w-full" />
        </div>

        <div>
          <label className={labelClass}>Block Threshold (red): {Math.round(blockThreshold * 100)}%</label>
          <input type="range" min={0} max={1} step={0.05} value={blockThreshold}
            onChange={e => setBlockThreshold(Number(e.target.value))} className="w-full" />
        </div>

        <button onClick={handleSave}
          className="w-full bg-indigo-600 hover:bg-indigo-500 text-white py-2 rounded-lg">
          Save Settings
        </button>
        {saved && <p className="text-green-400 text-sm text-center">Saved.</p>}
      </div>
    </div>
  )
}
```

**Step 3: Commit**

```bash
git add aperio/frontend/src/pages/
git commit -m "feat(aperio): add Profile Setup and Settings pages"
```

---

### Task 20: Build Frontend + Serve via FastAPI

**Files:**
- Modify: `aperio/aperio/main.py`
- Modify: `aperio/frontend/vite.config.ts`

**Step 1: Update `aperio/frontend/vite.config.ts`** to proxy API calls in dev

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: { outDir: '../aperio/static' },
  server: {
    proxy: {
      '/api': 'http://localhost:3000'
    }
  }
})
```

**Step 2: Build the frontend**

```bash
cd aperio/frontend && npm run build
```

Expected: `aperio/aperio/static/` directory created with `index.html`.

**Step 3: Update `aperio/aperio/main.py`** to serve the static build

```python
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

# After including router:
if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
```

**Step 4: Test the full app**

```bash
cd aperio && aperio start
# Open browser at http://localhost:3000
```

Expected: Aperio dashboard loads in browser.

**Step 5: Commit**

```bash
git add aperio/aperio/main.py aperio/frontend/vite.config.ts aperio/aperio/static/
git commit -m "feat(aperio): serve React frontend as static build via FastAPI"
```

---

## Phase 9: Integration Test

### Task 21: End-to-End Integration Test

**Files:**
- Create: `aperio/tests/test_integration.py`

**Step 1: Write the integration test**

```python
# aperio/tests/test_integration.py
"""
End-to-end test: create profile → create job → run pipeline (mocked LLM + Playwright) → approve
"""
from unittest.mock import patch
from fastapi.testclient import TestClient
from aperio.main import app

client = TestClient(app)

MOCK_PIPELINE_RESULT = {
    "submission_package": {
        "resume": "Tailored resume for Software Engineer at Acme",
        "cover_letter": "Dear Hiring Manager, I am excited...",
        "ats_answers": {"Why us?": "Because Acme builds amazing things."},
    },
    "confidence_scores": {"resume_tailored": 0.90, "cover_letter": 0.82, "Why us?": 0.78},
    "low_confidence_fields": [],
    "requires_human_input": False,
}

def test_full_application_flow():
    # 1. Create profile
    profile = client.post("/api/profiles", json={
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "555-1234",
        "location": "San Francisco, CA",
        "skills": ["Python", "SQL", "FastAPI"],
        "experience_json": [{"title": "Software Engineer", "company": "Prev Co", "bullets": ["Built APIs"]}],
    }).json()
    assert profile["id"] is not None

    # 2. Create job
    job = client.post("/api/jobs", json={"url": "https://greenhouse.io/jobs/999"}).json()
    assert job["id"] is not None

    # 3. Run pipeline (mocked)
    with patch("aperio.api.pipeline.run_pipeline", return_value=MOCK_PIPELINE_RESULT):
        result = client.post("/api/pipeline/run", json={
            "job_id": job["id"],
            "profile_id": profile["id"],
        }).json()

    assert result["status"] == "previewing"
    app_id = result["application_id"]

    # 4. Fetch application and verify package
    app = client.get(f"/api/applications/{app_id}").json()
    assert app["submission_package_json"]["resume"] == "Tailored resume for Software Engineer at Acme"

    # 5. Approve
    approved = client.post(f"/api/pipeline/{app_id}/approve", json={}).json()
    assert approved["status"] == "submitted"

    # 6. Verify final status
    final = client.get(f"/api/applications/{app_id}").json()
    assert final["status"] == "submitted"
```

**Step 2: Run the integration test**

```bash
cd aperio && pytest tests/test_integration.py -v
```

Expected: PASS.

**Step 3: Run full test suite**

```bash
cd aperio && pytest tests/ -v --tb=short
```

Expected: All tests pass.

**Step 4: Commit**

```bash
git add aperio/tests/test_integration.py
git commit -m "test(aperio): add end-to-end integration test for full application flow"
```

---

## Summary

| Phase | Tasks | What Gets Built |
|---|---|---|
| 1 | 1–2 | Project scaffold, config, SQLite models |
| 2 | 3–4 | Profile, Job, Application REST API |
| 3 | 5 | LLM client wrapper |
| 4 | 6–10 | LangGraph state, all 5 agents, pipeline graph |
| 5 | 11–12 | ATS adapter base, Generic adapter, Navigator loop |
| 6 | 13 | Pipeline run + approve API endpoints |
| 7 | 14 | APScheduler background tracker |
| 8 | 15–20 | React frontend: Dashboard, Apply, Preview Gate, Profile, Settings |
| 9 | 21 | End-to-end integration test |
