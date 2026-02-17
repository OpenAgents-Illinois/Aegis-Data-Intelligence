"""Tests for Orchestrator — incident lifecycle and deduplication."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

from aegis.agents.orchestrator import Orchestrator
from aegis.core.models import AnomalyModel, Diagnosis, IncidentModel, Recommendation


def _mock_architect():
    architect = MagicMock()
    architect.analyze.return_value = Diagnosis(
        root_cause="Upstream schema change",
        root_cause_table="staging.orders",
        blast_radius=["analytics.daily_revenue"],
        severity="critical",
        confidence=0.85,
        recommendations=[
            Recommendation(action="revert_schema", description="Revert the change", priority=1)
        ],
    )
    return architect


def _mock_executor():
    from aegis.agents.executor import Executor

    return Executor()


class TestOrchestrator:
    def test_creates_incident_from_anomaly(self, db, sample_anomaly):
        orchestrator = Orchestrator(_mock_architect(), _mock_executor())
        incident = orchestrator.handle_anomaly(sample_anomaly, db)

        assert incident.id is not None
        assert incident.status == "pending_review"
        assert incident.severity == "critical"
        assert incident.diagnosis is not None
        assert incident.remediation is not None

    def test_deduplicates_same_table_and_type(self, db, sample_table):
        """Second anomaly on same table+type merges into existing incident."""
        orchestrator = Orchestrator(_mock_architect(), _mock_executor())

        anomaly1 = AnomalyModel(
            table_id=sample_table.id,
            type="schema_drift",
            severity="medium",
            detail=json.dumps([{"change": "column_added", "column": "new_col"}]),
            detected_at=datetime.now(timezone.utc),
        )
        db.add(anomaly1)
        db.flush()

        incident1 = orchestrator.handle_anomaly(anomaly1, db)

        anomaly2 = AnomalyModel(
            table_id=sample_table.id,
            type="schema_drift",
            severity="critical",
            detail=json.dumps([{"change": "column_deleted", "column": "price"}]),
            detected_at=datetime.now(timezone.utc),
        )
        db.add(anomaly2)
        db.flush()

        incident2 = orchestrator.handle_anomaly(anomaly2, db)

        # Should merge into same incident
        assert incident2.id == incident1.id
        # Severity should escalate
        assert incident2.severity == "critical"

    def test_different_type_creates_new_incident(self, db, sample_table):
        """Different anomaly type on same table creates a new incident."""
        orchestrator = Orchestrator(_mock_architect(), _mock_executor())

        anomaly1 = AnomalyModel(
            table_id=sample_table.id,
            type="schema_drift",
            severity="medium",
            detail=json.dumps([]),
            detected_at=datetime.now(timezone.utc),
        )
        db.add(anomaly1)
        db.flush()
        incident1 = orchestrator.handle_anomaly(anomaly1, db)

        anomaly2 = AnomalyModel(
            table_id=sample_table.id,
            type="freshness_violation",
            severity="high",
            detail=json.dumps({"sla_minutes": 60, "minutes_overdue": 30}),
            detected_at=datetime.now(timezone.utc),
        )
        db.add(anomaly2)
        db.flush()
        incident2 = orchestrator.handle_anomaly(anomaly2, db)

        assert incident2.id != incident1.id

    def test_notifier_called_on_incident_creation(self, db, sample_anomaly):
        notifier = MagicMock()
        orchestrator = Orchestrator(_mock_architect(), _mock_executor(), notifier=notifier)

        orchestrator.handle_anomaly(sample_anomaly, db)

        notifier.broadcast.assert_called()
        call_args = notifier.broadcast.call_args
        assert call_args[0][0] == "incident.created"
