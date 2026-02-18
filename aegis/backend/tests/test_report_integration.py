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
