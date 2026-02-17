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
