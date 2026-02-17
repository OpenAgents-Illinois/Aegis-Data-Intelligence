# Incident Report Generator Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Generate a structured incident report at creation time, store it on the incident, and serve it via a dedicated API endpoint.

**Architecture:** A `ReportGenerator` class transforms existing incident/anomaly/diagnosis/remediation data into a structured `IncidentReport` Pydantic model. The Orchestrator calls it after diagnosis+remediation, stores the JSON on the incident's new `report` column. A `GET /incidents/{id}/report` endpoint returns it.

**Tech Stack:** Existing FastAPI/SQLAlchemy/Pydantic stack. No new dependencies.

**Design Doc:** `docs/plans/2026-02-17-incident-report-design.md`

---

### Task 1: Add Pydantic Report Schemas

**Files:**
- Modify: `aegis/backend/aegis/core/models.py`
- Test: `aegis/backend/tests/test_models_report.py`

**Step 1: Write the failing test**

Create `aegis/backend/tests/test_models_report.py`:

```python
"""Tests for incident report Pydantic schemas."""

from datetime import datetime, timezone

from aegis.core.models import (
    AnomalyDetail,
    BlastRadiusDetail,
    IncidentReport,
    RecommendedAction,
    RootCauseDetail,
    TimelineEvent,
)


def test_incident_report_creation():
    report = IncidentReport(
        incident_id=1,
        title="Schema Drift on public.orders",
        severity="critical",
        status="pending_review",
        generated_at=datetime.now(timezone.utc),
        summary="Column 'price' was deleted from public.orders.",
        anomaly_details=AnomalyDetail(
            type="schema_drift",
            table="public.orders",
            detected_at=datetime.now(timezone.utc),
            changes=[{"change": "column_deleted", "column": "price"}],
        ),
        root_cause=RootCauseDetail(
            explanation="Column deleted upstream",
            source_table="staging.orders",
            confidence=0.85,
        ),
        blast_radius=BlastRadiusDetail(
            total_affected=2,
            affected_tables=["analytics.daily_revenue", "analytics.customer_ltv"],
        ),
        recommended_actions=[
            RecommendedAction(
                action="revert_schema",
                description="Revert column deletion",
                priority=1,
                status="pending_approval",
            ),
        ],
        timeline=[
            TimelineEvent(
                timestamp=datetime.now(timezone.utc),
                event="Anomaly detected: schema_drift on public.orders",
            ),
        ],
    )
    assert report.incident_id == 1
    assert report.severity == "critical"
    assert report.blast_radius.total_affected == 2
    assert len(report.recommended_actions) == 1
    assert len(report.timeline) == 1


def test_incident_report_empty_blast_radius():
    report = IncidentReport(
        incident_id=2,
        title="Freshness Breach on public.users",
        severity="medium",
        status="pending_review",
        generated_at=datetime.now(timezone.utc),
        summary="Table public.users is 30 minutes overdue.",
        anomaly_details=AnomalyDetail(
            type="freshness_breach",
            table="public.users",
            detected_at=datetime.now(timezone.utc),
            changes=[{"sla_minutes": 60, "minutes_overdue": 30}],
        ),
        root_cause=RootCauseDetail(
            explanation="Manual investigation required.",
            source_table="public.users",
            confidence=0.0,
        ),
        blast_radius=BlastRadiusDetail(
            total_affected=0,
            affected_tables=[],
        ),
        recommended_actions=[],
        timeline=[],
    )
    assert report.blast_radius.total_affected == 0
    assert report.recommended_actions == []
```

**Step 2: Run tests to verify they fail**

Run: `cd aegis/backend && python -m pytest tests/test_models_report.py -v`
Expected: FAIL — ImportError, schemas not defined.

**Step 3: Add Pydantic schemas to models.py**

Add at the end of `aegis/backend/aegis/core/models.py`, after the `DiscoveryConfirm` class:

```python
# Incident report schemas


class AnomalyDetail(BaseModel):
    """Anomaly section of an incident report."""
    type: str
    table: str
    detected_at: datetime
    changes: list[dict[str, Any]]


class RootCauseDetail(BaseModel):
    """Root cause section of an incident report."""
    explanation: str
    source_table: str
    confidence: float


class BlastRadiusDetail(BaseModel):
    """Blast radius section of an incident report."""
    total_affected: int
    affected_tables: list[str]


class RecommendedAction(BaseModel):
    """A single recommended action in an incident report."""
    action: str
    description: str
    priority: int
    status: str


class TimelineEvent(BaseModel):
    """A single event in the incident timeline."""
    timestamp: datetime
    event: str


class IncidentReport(BaseModel):
    """Structured incident report for user consumption."""
    incident_id: int
    title: str
    severity: str
    status: str
    generated_at: datetime
    summary: str
    anomaly_details: AnomalyDetail
    root_cause: RootCauseDetail
    blast_radius: BlastRadiusDetail
    recommended_actions: list[RecommendedAction]
    timeline: list[TimelineEvent]
```

**Step 4: Run tests to verify they pass**

Run: `cd aegis/backend && python -m pytest tests/test_models_report.py -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add aegis/backend/aegis/core/models.py aegis/backend/tests/test_models_report.py
git commit -m "feat(report): add incident report Pydantic schemas"
```

---

### Task 2: Add `report` Column to IncidentModel + Migration

**Files:**
- Modify: `aegis/backend/aegis/core/models.py`
- Create: `aegis/backend/alembic/versions/002_add_incident_report.py`

**Step 1: Add column to ORM model**

In `aegis/backend/aegis/core/models.py`, in the `IncidentModel` class, add after the `dismiss_reason` column:

```python
    report: Mapped[str | None] = mapped_column(Text, nullable=True)
```

**Step 2: Create Alembic migration**

Create `aegis/backend/alembic/versions/002_add_incident_report.py`:

```python
"""Add report column to incidents table.

Revision ID: 002
Revises: 001
Create Date: 2026-02-17
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("incidents", sa.Column("report", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("incidents", "report")
```

**Step 3: Run full test suite to verify nothing breaks**

Run: `cd aegis/backend && python -m pytest tests/ -v --tb=short`
Expected: All PASS (the new column is nullable, so existing tests are unaffected).

**Step 4: Commit**

```bash
git add aegis/backend/aegis/core/models.py aegis/backend/alembic/versions/002_add_incident_report.py
git commit -m "feat(report): add report column to incidents table"
```

---

### Task 3: Create the ReportGenerator

**Files:**
- Create: `aegis/backend/aegis/agents/report_generator.py`
- Test: `aegis/backend/tests/test_report_generator.py`

**Step 1: Write the failing tests**

Create `aegis/backend/tests/test_report_generator.py`:

```python
"""Tests for ReportGenerator — incident report assembly."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

from aegis.agents.report_generator import ReportGenerator
from aegis.core.models import (
    AnomalyModel,
    Diagnosis,
    IncidentModel,
    MonitoredTableModel,
    Recommendation,
    Remediation,
)


def _make_anomaly(table_id=1, anomaly_type="schema_drift"):
    anomaly = MagicMock(spec=AnomalyModel)
    anomaly.id = 10
    anomaly.table_id = table_id
    anomaly.type = anomaly_type
    anomaly.severity = "critical"
    anomaly.detected_at = datetime(2026, 2, 17, 15, 0, tzinfo=timezone.utc)
    if anomaly_type == "schema_drift":
        anomaly.detail = json.dumps([{"change": "column_deleted", "column": "price"}])
    else:
        anomaly.detail = json.dumps({"sla_minutes": 60, "minutes_overdue": 30})
    return anomaly


def _make_table():
    table = MagicMock(spec=MonitoredTableModel)
    table.id = 1
    table.fully_qualified_name = "public.orders"
    table.schema_name = "public"
    table.table_name = "orders"
    return table


def _make_incident(anomaly_id=10):
    incident = MagicMock(spec=IncidentModel)
    incident.id = 42
    incident.anomaly_id = anomaly_id
    incident.status = "pending_review"
    incident.severity = "critical"
    incident.created_at = datetime(2026, 2, 17, 15, 0, 1, tzinfo=timezone.utc)
    return incident


def _make_diagnosis():
    return Diagnosis(
        root_cause="Column deleted upstream",
        root_cause_table="staging.orders",
        blast_radius=["analytics.daily_revenue", "analytics.customer_ltv"],
        severity="critical",
        confidence=0.85,
        recommendations=[
            Recommendation(
                action="revert_schema",
                description="Revert column deletion",
                priority=1,
            ),
        ],
    )


def _make_remediation():
    return Remediation(
        actions=[
            {
                "type": "revert_schema",
                "description": "Revert column deletion",
                "priority": 1,
                "status": "pending_approval",
            }
        ],
        summary="Incident: Schema Drift\nSeverity: CRITICAL",
        generated_at=datetime(2026, 2, 17, 15, 0, 2, tzinfo=timezone.utc),
    )


class TestReportGenerator:
    def test_generates_report_with_all_sections(self):
        gen = ReportGenerator()
        report = gen.generate(
            incident=_make_incident(),
            anomaly=_make_anomaly(),
            table=_make_table(),
            diagnosis=_make_diagnosis(),
            remediation=_make_remediation(),
        )
        assert report.incident_id == 42
        assert "Schema Drift" in report.title
        assert "public.orders" in report.title
        assert report.severity == "critical"
        assert report.anomaly_details.type == "schema_drift"
        assert report.root_cause.confidence == 0.85
        assert report.blast_radius.total_affected == 2
        assert len(report.recommended_actions) == 1
        assert len(report.timeline) >= 3  # detected, created, diagnosed at minimum

    def test_generates_report_without_diagnosis(self):
        gen = ReportGenerator()
        report = gen.generate(
            incident=_make_incident(),
            anomaly=_make_anomaly(),
            table=_make_table(),
            diagnosis=None,
            remediation=None,
        )
        assert report.root_cause.explanation == "Analysis unavailable"
        assert report.root_cause.confidence == 0.0
        assert report.blast_radius.total_affected == 0
        assert report.recommended_actions == []

    def test_generates_report_for_freshness_breach(self):
        gen = ReportGenerator()
        report = gen.generate(
            incident=_make_incident(),
            anomaly=_make_anomaly(anomaly_type="freshness_breach"),
            table=_make_table(),
            diagnosis=_make_diagnosis(),
            remediation=_make_remediation(),
        )
        assert "Freshness Breach" in report.title
        assert report.anomaly_details.type == "freshness_breach"

    def test_summary_mentions_key_facts(self):
        gen = ReportGenerator()
        report = gen.generate(
            incident=_make_incident(),
            anomaly=_make_anomaly(),
            table=_make_table(),
            diagnosis=_make_diagnosis(),
            remediation=_make_remediation(),
        )
        assert "public.orders" in report.summary
        assert "critical" in report.summary.lower()
```

**Step 2: Run tests to verify they fail**

Run: `cd aegis/backend && python -m pytest tests/test_report_generator.py -v`
Expected: FAIL — ModuleNotFoundError.

**Step 3: Create the ReportGenerator**

Create `aegis/backend/aegis/agents/report_generator.py`:

```python
"""ReportGenerator — assembles structured incident reports from pipeline data."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from aegis.core.models import (
    AnomalyDetail,
    AnomalyModel,
    BlastRadiusDetail,
    Diagnosis,
    IncidentModel,
    IncidentReport,
    MonitoredTableModel,
    RecommendedAction,
    Remediation,
    RootCauseDetail,
    TimelineEvent,
)

logger = logging.getLogger("aegis.report_generator")

# Mapping from anomaly type to human-readable title fragment
_TYPE_TITLES = {
    "schema_drift": "Schema Drift",
    "freshness_violation": "Freshness Breach",
    "freshness_breach": "Freshness Breach",
}


class ReportGenerator:
    """Transforms incident pipeline data into a structured IncidentReport."""

    def generate(
        self,
        incident: IncidentModel,
        anomaly: AnomalyModel,
        table: MonitoredTableModel,
        diagnosis: Diagnosis | None,
        remediation: Remediation | None,
    ) -> IncidentReport:
        """Build a complete incident report from pipeline outputs."""
        now = datetime.now(timezone.utc)
        table_name = table.fully_qualified_name
        type_label = _TYPE_TITLES.get(anomaly.type, anomaly.type.replace("_", " ").title())
        title = f"{type_label} on {table_name}"

        anomaly_details = self._build_anomaly_details(anomaly, table_name)
        root_cause = self._build_root_cause(diagnosis, table_name)
        blast_radius = self._build_blast_radius(diagnosis)
        actions = self._build_actions(remediation)
        timeline = self._build_timeline(anomaly, incident, diagnosis, remediation)
        summary = self._build_summary(
            type_label, table_name, incident.severity, root_cause, blast_radius
        )

        return IncidentReport(
            incident_id=incident.id,
            title=title,
            severity=incident.severity,
            status=incident.status,
            generated_at=now,
            summary=summary,
            anomaly_details=anomaly_details,
            root_cause=root_cause,
            blast_radius=blast_radius,
            recommended_actions=actions,
            timeline=timeline,
        )

    def _build_anomaly_details(
        self, anomaly: AnomalyModel, table_name: str
    ) -> AnomalyDetail:
        detail = anomaly.detail
        if isinstance(detail, str):
            detail = json.loads(detail)
        changes = detail if isinstance(detail, list) else [detail]

        return AnomalyDetail(
            type=anomaly.type,
            table=table_name,
            detected_at=anomaly.detected_at,
            changes=changes,
        )

    def _build_root_cause(
        self, diagnosis: Diagnosis | None, table_name: str
    ) -> RootCauseDetail:
        if diagnosis is None:
            return RootCauseDetail(
                explanation="Analysis unavailable",
                source_table=table_name,
                confidence=0.0,
            )
        return RootCauseDetail(
            explanation=diagnosis.root_cause,
            source_table=diagnosis.root_cause_table,
            confidence=diagnosis.confidence,
        )

    def _build_blast_radius(self, diagnosis: Diagnosis | None) -> BlastRadiusDetail:
        if diagnosis is None:
            return BlastRadiusDetail(total_affected=0, affected_tables=[])
        return BlastRadiusDetail(
            total_affected=len(diagnosis.blast_radius),
            affected_tables=diagnosis.blast_radius,
        )

    def _build_actions(self, remediation: Remediation | None) -> list[RecommendedAction]:
        if remediation is None:
            return []
        return [
            RecommendedAction(
                action=a["type"],
                description=a["description"],
                priority=a.get("priority", 1),
                status=a.get("status", "manual"),
            )
            for a in remediation.actions
        ]

    def _build_timeline(
        self,
        anomaly: AnomalyModel,
        incident: IncidentModel,
        diagnosis: Diagnosis | None,
        remediation: Remediation | None,
    ) -> list[TimelineEvent]:
        events: list[TimelineEvent] = []

        type_label = _TYPE_TITLES.get(anomaly.type, anomaly.type)
        events.append(TimelineEvent(
            timestamp=anomaly.detected_at,
            event=f"Anomaly detected: {type_label} on {anomaly.type}",
        ))

        events.append(TimelineEvent(
            timestamp=incident.created_at,
            event=f"Incident created (severity: {incident.severity})",
        ))

        if diagnosis is not None:
            events.append(TimelineEvent(
                timestamp=incident.created_at,
                event=f"Root cause identified: {diagnosis.root_cause} (confidence: {diagnosis.confidence:.0%})",
            ))

        if remediation is not None:
            events.append(TimelineEvent(
                timestamp=remediation.generated_at,
                event=f"Remediation plan generated: {len(remediation.actions)} action(s)",
            ))

        return events

    def _build_summary(
        self,
        type_label: str,
        table_name: str,
        severity: str,
        root_cause: RootCauseDetail,
        blast_radius: BlastRadiusDetail,
    ) -> str:
        parts = [f"{type_label} detected on {table_name} ({severity} severity)."]

        if root_cause.confidence > 0:
            parts.append(f"Root cause: {root_cause.explanation}.")
        else:
            parts.append("Root cause analysis unavailable.")

        if blast_radius.total_affected > 0:
            parts.append(
                f"{blast_radius.total_affected} downstream table(s) affected."
            )

        return " ".join(parts)
```

**Step 4: Run tests to verify they pass**

Run: `cd aegis/backend && python -m pytest tests/test_report_generator.py -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add aegis/backend/aegis/agents/report_generator.py aegis/backend/tests/test_report_generator.py
git commit -m "feat(report): implement ReportGenerator with structured report assembly"
```

---

### Task 4: Integrate ReportGenerator into Orchestrator

**Files:**
- Modify: `aegis/backend/aegis/agents/orchestrator.py`
- Modify: `aegis/backend/tests/test_orchestrator.py`

**Step 1: Add a failing test to test_orchestrator.py**

Add to the `TestOrchestrator` class in `aegis/backend/tests/test_orchestrator.py`:

```python
    def test_incident_has_report_after_creation(self, db, sample_anomaly):
        orchestrator = Orchestrator(_mock_architect(), _mock_executor())
        incident = orchestrator.handle_anomaly(sample_anomaly, db)

        assert incident.report is not None
        import json
        report_data = json.loads(incident.report)
        assert report_data["incident_id"] == incident.id
        assert "title" in report_data
        assert "summary" in report_data
        assert "anomaly_details" in report_data
        assert "root_cause" in report_data
        assert "blast_radius" in report_data
        assert "recommended_actions" in report_data
        assert "timeline" in report_data
```

**Step 2: Run tests to verify the new test fails**

Run: `cd aegis/backend && python -m pytest tests/test_orchestrator.py::TestOrchestrator::test_incident_has_report_after_creation -v`
Expected: FAIL — `incident.report` is None.

**Step 3: Integrate into Orchestrator**

In `aegis/backend/aegis/agents/orchestrator.py`, add the report generation step after the status update (after line `incident.status = "pending_review"`) and before the notifier block:

Add this import at the top with the other imports:

```python
from aegis.agents.report_generator import ReportGenerator
```

Then in `handle_anomaly`, after `incident.status = "pending_review"` and before `incident.updated_at = ...`, add:

```python
        # 6. Generate incident report
        try:
            table = db.get(MonitoredTableModel, anomaly.table_id)
            diag_obj = None
            if incident.diagnosis:
                diag_obj = Diagnosis.model_validate_json(incident.diagnosis)
            remed_obj = None
            if incident.remediation:
                remed_obj = Remediation.model_validate_json(incident.remediation)

            generator = ReportGenerator()
            report = generator.generate(incident, anomaly, table, diag_obj, remed_obj)
            incident.report = report.model_dump_json()
        except Exception:
            logger.exception("Report generation failed for incident %d", incident.id)
```

Also add `MonitoredTableModel` and `Remediation` to the imports from `aegis.core.models`.

**Step 4: Run the full orchestrator tests**

Run: `cd aegis/backend && python -m pytest tests/test_orchestrator.py -v`
Expected: All PASS (including the new test).

**Step 5: Commit**

```bash
git add aegis/backend/aegis/agents/orchestrator.py aegis/backend/tests/test_orchestrator.py
git commit -m "feat(report): integrate ReportGenerator into Orchestrator pipeline"
```

---

### Task 5: Add Report API Endpoint

**Files:**
- Modify: `aegis/backend/aegis/api/incidents.py`
- Test: `aegis/backend/tests/test_incident_report_api.py`

**Step 1: Write the failing test**

Create `aegis/backend/tests/test_incident_report_api.py`:

```python
"""Tests for the incident report API endpoint."""

import json
import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ.setdefault("AEGIS_DB_PATH", _tmp.name)
os.environ.setdefault("AEGIS_API_KEY", "dev-key")


@pytest.fixture(autouse=True)
def _reset_db():
    with patch("aegis.core.database.run_migrations"):
        from aegis.core.database import Base, sync_engine

        Base.metadata.drop_all(sync_engine)
        Base.metadata.create_all(sync_engine)
    yield


@pytest.fixture
def client():
    with patch("aegis.core.database.run_migrations"), \
         patch("aegis.core.database.ensure_db_directory"), \
         patch("aegis.services.scanner.start_scanner", new_callable=AsyncMock, return_value=None):

        from fastapi.testclient import TestClient
        from aegis.main import app

        with TestClient(app) as c:
            yield c


def _seed_incident_with_report(client):
    """Create a connection, table, anomaly, and incident with report via the DB directly."""
    from aegis.core.database import SyncSessionLocal
    from aegis.core.models import AnomalyModel, ConnectionModel, IncidentModel, MonitoredTableModel

    with SyncSessionLocal() as db:
        conn = ConnectionModel(name="rpt-test", dialect="postgresql", connection_uri="postgresql://x")
        db.add(conn)
        db.flush()

        table = MonitoredTableModel(
            connection_id=conn.id,
            schema_name="public",
            table_name="orders",
            fully_qualified_name="public.orders",
            check_types='["schema"]',
        )
        db.add(table)
        db.flush()

        anomaly = AnomalyModel(
            table_id=table.id,
            type="schema_drift",
            severity="critical",
            detail=json.dumps([{"change": "column_deleted", "column": "price"}]),
            detected_at=datetime.now(timezone.utc),
        )
        db.add(anomaly)
        db.flush()

        report_json = json.dumps({
            "incident_id": 1,
            "title": "Schema Drift on public.orders",
            "severity": "critical",
            "status": "pending_review",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": "Schema Drift detected on public.orders (critical severity).",
            "anomaly_details": {
                "type": "schema_drift",
                "table": "public.orders",
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "changes": [{"change": "column_deleted", "column": "price"}],
            },
            "root_cause": {
                "explanation": "Column deleted upstream",
                "source_table": "staging.orders",
                "confidence": 0.85,
            },
            "blast_radius": {"total_affected": 1, "affected_tables": ["analytics.daily_revenue"]},
            "recommended_actions": [
                {"action": "revert_schema", "description": "Revert column deletion", "priority": 1, "status": "pending_approval"}
            ],
            "timeline": [],
        })

        incident = IncidentModel(
            anomaly_id=anomaly.id,
            status="pending_review",
            severity="critical",
            report=report_json,
        )
        db.add(incident)
        db.commit()
        return incident.id


def test_get_report_returns_structured_report(client):
    incident_id = _seed_incident_with_report(client)
    resp = client.get(f"/api/v1/incidents/{incident_id}/report")
    assert resp.status_code == 200
    data = resp.json()
    assert data["incident_id"] == incident_id
    assert data["title"] == "Schema Drift on public.orders"
    assert data["severity"] == "critical"
    assert "anomaly_details" in data
    assert "root_cause" in data
    assert "blast_radius" in data
    assert "recommended_actions" in data


def test_get_report_404_for_missing_incident(client):
    resp = client.get("/api/v1/incidents/9999/report")
    assert resp.status_code == 404


def test_get_report_204_when_no_report(client):
    """Incident exists but report hasn't been generated."""
    from aegis.core.database import SyncSessionLocal
    from aegis.core.models import AnomalyModel, ConnectionModel, IncidentModel, MonitoredTableModel

    with SyncSessionLocal() as db:
        conn = ConnectionModel(name="rpt-test2", dialect="postgresql", connection_uri="postgresql://x")
        db.add(conn)
        db.flush()
        table = MonitoredTableModel(
            connection_id=conn.id, schema_name="public", table_name="users",
            fully_qualified_name="public.users", check_types='["schema"]',
        )
        db.add(table)
        db.flush()
        anomaly = AnomalyModel(
            table_id=table.id, type="schema_drift", severity="medium",
            detail="[]", detected_at=datetime.now(timezone.utc),
        )
        db.add(anomaly)
        db.flush()
        incident = IncidentModel(
            anomaly_id=anomaly.id, status="investigating", severity="medium",
        )
        db.add(incident)
        db.commit()
        incident_id = incident.id

    resp = client.get(f"/api/v1/incidents/{incident_id}/report")
    assert resp.status_code == 204
```

**Step 2: Run tests to verify they fail**

Run: `cd aegis/backend && python -m pytest tests/test_incident_report_api.py -v`
Expected: FAIL — 404 on the report endpoint (route doesn't exist).

**Step 3: Add the report endpoint**

In `aegis/backend/aegis/api/incidents.py`, add this import at the top:

```python
import json
from fastapi.responses import JSONResponse
```

Add this endpoint after the `get_incident` endpoint:

```python
@router.get("/{incident_id}/report")
async def get_incident_report(incident_id: int, db: AsyncSession = Depends(get_db)):
    """Return the structured incident report."""
    incident = await db.get(IncidentModel, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    if not incident.report:
        return JSONResponse(status_code=204, content=None)

    return json.loads(incident.report)
```

**Step 4: Run tests to verify they pass**

Run: `cd aegis/backend && python -m pytest tests/test_incident_report_api.py -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add aegis/backend/aegis/api/incidents.py aegis/backend/tests/test_incident_report_api.py
git commit -m "feat(report): add GET /incidents/{id}/report endpoint"
```

---

### Task 6: Full Integration Test + Final Suite

**Files:**
- Test: `aegis/backend/tests/test_report_integration.py`

**Step 1: Write integration test**

Create `aegis/backend/tests/test_report_integration.py`:

```python
"""Integration test: anomaly → orchestrator → incident with report → API serves it."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

from aegis.agents.orchestrator import Orchestrator
from aegis.core.models import (
    AnomalyModel,
    Diagnosis,
    IncidentReport,
    Recommendation,
)


def test_full_pipeline_produces_valid_report(db, sample_anomaly):
    """Orchestrator generates a report that validates as IncidentReport."""
    architect = MagicMock()
    architect.analyze.return_value = Diagnosis(
        root_cause="Column deleted upstream",
        root_cause_table="staging.orders",
        blast_radius=["analytics.daily_revenue"],
        severity="critical",
        confidence=0.85,
        recommendations=[
            Recommendation(action="revert_schema", description="Revert", priority=1)
        ],
    )

    from aegis.agents.executor import Executor
    orchestrator = Orchestrator(architect, Executor())
    incident = orchestrator.handle_anomaly(sample_anomaly, db)

    # Report should be stored as valid JSON
    assert incident.report is not None
    report_data = json.loads(incident.report)

    # Should validate as IncidentReport
    report = IncidentReport(**report_data)
    assert report.incident_id == incident.id
    assert report.severity == "critical"
    assert "public.orders" in report.title
    assert report.root_cause.confidence == 0.85
    assert report.blast_radius.total_affected == 1
    assert len(report.recommended_actions) == 1
    assert len(report.timeline) >= 3
```

**Step 2: Run integration test**

Run: `cd aegis/backend && python -m pytest tests/test_report_integration.py -v`
Expected: PASS.

**Step 3: Run complete test suite**

Run: `cd aegis/backend && python -m pytest tests/ -v --tb=short`
Expected: All tests PASS.

**Step 4: Commit**

```bash
git add aegis/backend/tests/test_report_integration.py
git commit -m "test(report): add integration test for full incident report pipeline"
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 1 | Report Pydantic schemas | `models.py`, `test_models_report.py` |
| 2 | DB column + migration | `models.py`, `002_add_incident_report.py` |
| 3 | ReportGenerator class | `report_generator.py`, `test_report_generator.py` |
| 4 | Orchestrator integration | `orchestrator.py`, `test_orchestrator.py` |
| 5 | Report API endpoint | `incidents.py`, `test_incident_report_api.py` |
| 6 | Integration test | `test_report_integration.py` |

**Total: 6 tasks, ~6 commits, TDD throughout.**
