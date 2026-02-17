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
