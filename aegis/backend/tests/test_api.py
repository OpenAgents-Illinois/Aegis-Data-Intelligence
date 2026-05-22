"""Tests for FastAPI API endpoints."""

import os
import tempfile
from unittest.mock import AsyncMock, patch

import pytest

# Use a temp file so async and sync engines share the same database
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["AEGIS_DB_PATH"] = _tmp.name
os.environ["AEGIS_API_KEY"] = "dev-key"


@pytest.fixture(autouse=True)
def _reset_db():
    """Recreate tables before each test."""
    with patch("aegis.core.database.run_migrations"):
        from aegis.core.database import Base, sync_engine

        Base.metadata.drop_all(sync_engine)
        Base.metadata.create_all(sync_engine)
    yield


@pytest.fixture
def client():
    """Create a test client with temp-file SQLite."""
    with patch("aegis.core.database.run_migrations"), \
         patch("aegis.core.database.ensure_db_directory"), \
         patch("aegis.services.scanner.start_scanner", new_callable=AsyncMock, return_value=None):

        from fastapi.testclient import TestClient
        from aegis.main import app

        with TestClient(app) as c:
            yield c


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "aegis"


class TestConnectionEndpoints:
    def test_create_connection(self, client):
        response = client.post(
            "/api/v1/connections",
            json={
                "name": "test-db",
                "dialect": "postgresql",
                "connection_uri": "postgresql://user:pass@localhost/db",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-db"
        assert data["dialect"] == "postgresql"
        assert data["is_active"] is True

    def test_list_connections(self, client):
        client.post(
            "/api/v1/connections",
            json={
                "name": "list-test",
                "dialect": "snowflake",
                "connection_uri": "snowflake://user:pass@account/db",
            },
        )

        response = client.get("/api/v1/connections")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_connection_not_found(self, client):
        response = client.get("/api/v1/connections/9999")
        assert response.status_code == 404


class TestTableEndpoints:
    def test_create_and_list_tables(self, client):
        conn_resp = client.post(
            "/api/v1/connections",
            json={
                "name": "table-test-db",
                "dialect": "postgresql",
                "connection_uri": "postgresql://user:pass@localhost/db",
            },
        )
        conn_id = conn_resp.json()["id"]

        response = client.post(
            "/api/v1/tables",
            json={
                "connection_id": conn_id,
                "schema_name": "public",
                "table_name": "users",
                "check_types": ["schema"],
                "freshness_sla_minutes": 120,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["fully_qualified_name"] == "public.users"
        assert data["freshness_sla_minutes"] == 120

        list_resp = client.get("/api/v1/tables")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) >= 1

    def test_table_response_exposes_last_observed_at(self, client):
        """TableResponse must include last_observed_at so the heatmap can compute real SLA ratios."""
        conn_resp = client.post(
            "/api/v1/connections",
            json={
                "name": "obs-test-db",
                "dialect": "postgresql",
                "connection_uri": "postgresql://user:pass@localhost/db",
            },
        )
        conn_id = conn_resp.json()["id"]

        create_resp = client.post(
            "/api/v1/tables",
            json={
                "connection_id": conn_id,
                "schema_name": "public",
                "table_name": "orders",
                "freshness_sla_minutes": 60,
            },
        )
        assert create_resp.status_code == 201
        data = create_resp.json()
        assert "last_observed_at" in data
        assert data["last_observed_at"] is None  # never observed at creation


class TestAnomalyTimelineEndpoint:
    def test_returns_24_empty_buckets_by_default(self, client):
        response = client.get("/api/v1/stats/anomalies/timeline")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 24
        assert all(set(b.keys()) == {"hour_start", "count"} for b in data)
        assert all(b["count"] == 0 for b in data)

    def test_honors_hours_query_param(self, client):
        response = client.get("/api/v1/stats/anomalies/timeline?hours=6")
        assert response.status_code == 200
        assert len(response.json()) == 6

    def test_rejects_invalid_hours_range(self, client):
        assert client.get("/api/v1/stats/anomalies/timeline?hours=0").status_code == 422
        assert client.get("/api/v1/stats/anomalies/timeline?hours=169").status_code == 422

    def test_buckets_existing_anomalies_into_correct_hours(self, client):
        from datetime import datetime, timedelta, timezone
        from aegis.core.database import SyncSessionLocal
        from aegis.core.models import (
            AnomalyModel,
            ConnectionModel,
            MonitoredTableModel,
        )

        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        with SyncSessionLocal() as db:
            conn = ConnectionModel(name="tl-test", dialect="postgresql", connection_uri="x")
            db.add(conn)
            db.flush()
            table = MonitoredTableModel(
                connection_id=conn.id,
                schema_name="public",
                table_name="orders",
                fully_qualified_name="public.orders",
                check_types='["freshness"]',
            )
            db.add(table)
            db.flush()
            for offset_min in (5, 15, 25):  # all in the current hour bucket
                db.add(AnomalyModel(
                    table_id=table.id,
                    type="freshness_violation",
                    severity="medium",
                    detail="{}",
                    detected_at=now + timedelta(minutes=offset_min) - timedelta(hours=1),
                ))
            db.add(AnomalyModel(  # 3 hours ago
                table_id=table.id,
                type="schema_drift",
                severity="low",
                detail="{}",
                detected_at=now - timedelta(hours=3),
            ))
            db.commit()

        response = client.get("/api/v1/stats/anomalies/timeline?hours=4")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 4
        counts = [b["count"] for b in data]
        # buckets oldest -> newest: [hours-3, hours-2, hours-1, hours-0]
        # 1 anomaly 3h ago, 3 anomalies in the "1h ago" bucket, 0 in -2 and -0
        assert counts == [1, 0, 3, 0]


class TestIncidentEndpoints:
    def test_list_incidents_empty(self, client):
        response = client.get("/api/v1/incidents")
        assert response.status_code == 200
        assert response.json() == []


class TestLineageEndpoints:
    def test_get_full_graph_empty(self, client):
        response = client.get("/api/v1/lineage/graph")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
