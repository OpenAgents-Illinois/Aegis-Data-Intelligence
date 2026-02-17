"""Shared test fixtures — in-memory SQLite, mock services."""

import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from aegis.core.database import Base
from aegis.core.models import (
    AnomalyModel,
    ConnectionModel,
    IncidentModel,
    LineageEdgeModel,
    MonitoredTableModel,
    SchemaSnapshotModel,
)


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db(db_engine):
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def sample_connection(db: Session):
    conn = ConnectionModel(
        name="test-postgres",
        dialect="postgresql",
        connection_uri="postgresql://user:pass@localhost/testdb",
        is_active=True,
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


@pytest.fixture
def sample_table(db: Session, sample_connection: ConnectionModel):
    table = MonitoredTableModel(
        connection_id=sample_connection.id,
        schema_name="public",
        table_name="orders",
        fully_qualified_name="public.orders",
        check_types='["schema", "freshness"]',
        freshness_sla_minutes=60,
    )
    db.add(table)
    db.commit()
    db.refresh(table)
    return table


@pytest.fixture
def sample_snapshot(db: Session, sample_table: MonitoredTableModel):
    columns = [
        {"name": "id", "type": "INTEGER", "nullable": False, "ordinal": 1},
        {"name": "price", "type": "FLOAT", "nullable": True, "ordinal": 2},
        {"name": "name", "type": "VARCHAR", "nullable": True, "ordinal": 3},
    ]
    import hashlib

    columns_json = json.dumps(columns, sort_keys=True)
    snapshot = SchemaSnapshotModel(
        table_id=sample_table.id,
        columns=columns_json,
        snapshot_hash=hashlib.sha256(columns_json.encode()).hexdigest(),
        captured_at=datetime.now(timezone.utc),
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


@pytest.fixture
def sample_anomaly(db: Session, sample_table: MonitoredTableModel):
    anomaly = AnomalyModel(
        table_id=sample_table.id,
        type="schema_drift",
        severity="critical",
        detail=json.dumps([{"change": "column_deleted", "column": "price"}]),
        detected_at=datetime.now(timezone.utc),
    )
    db.add(anomaly)
    db.commit()
    db.refresh(anomaly)
    return anomaly


@pytest.fixture
def sample_incident(db: Session, sample_anomaly: AnomalyModel):
    incident = IncidentModel(
        anomaly_id=sample_anomaly.id,
        status="pending_review",
        severity="critical",
        diagnosis=json.dumps({
            "root_cause": "Column deleted upstream",
            "root_cause_table": "staging.orders",
            "blast_radius": ["analytics.daily_revenue"],
            "severity": "critical",
            "confidence": 0.85,
            "recommendations": [
                {"action": "revert_schema", "description": "Revert column deletion", "priority": 1}
            ],
        }),
        blast_radius=json.dumps(["analytics.daily_revenue"]),
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident


@pytest.fixture
def sample_lineage_edges(db: Session):
    edges = [
        LineageEdgeModel(
            source_table="raw.orders",
            target_table="staging.orders",
            confidence=1.0,
        ),
        LineageEdgeModel(
            source_table="staging.orders",
            target_table="analytics.orders",
            confidence=1.0,
        ),
        LineageEdgeModel(
            source_table="analytics.orders",
            target_table="analytics.daily_revenue",
            confidence=1.0,
        ),
        LineageEdgeModel(
            source_table="analytics.orders",
            target_table="analytics.customer_ltv",
            confidence=0.8,
        ),
    ]
    db.add_all(edges)
    db.commit()
    return edges


@pytest.fixture
def api_client():
    """FastAPI test client with in-memory database."""
    from unittest.mock import AsyncMock, patch

    from aegis.main import app

    # Override the scanner to not start
    with patch("aegis.main.run_migrations"), \
         patch("aegis.services.scanner.start_scanner", new_callable=AsyncMock, return_value=None):
        client = TestClient(app)
        yield client
