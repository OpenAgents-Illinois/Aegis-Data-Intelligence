"""Integration test: discover → confirm → sentinels can see tables."""

import json
from unittest.mock import MagicMock

from aegis.agents.investigator import Investigator
from aegis.core.models import ConnectionModel, MonitoredTableModel


def test_discover_then_confirm_creates_monitored_tables(db):
    """Full flow: discover returns proposals, confirm creates MonitoredTableModel rows."""
    # Setup: create a connection
    conn = ConnectionModel(
        name="integration-test",
        dialect="postgresql",
        connection_uri="postgresql://x",
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)

    # Mock connector
    mock_connector = MagicMock()
    mock_connector.list_schemas.return_value = ["public"]
    mock_connector.list_tables.return_value = [
        {"name": "users", "type": "BASE TABLE", "schema": "public"},
        {"name": "orders", "type": "BASE TABLE", "schema": "public"},
        {"name": "_tmp_scratch", "type": "BASE TABLE", "schema": "public"},
    ]
    mock_connector.fetch_schema.return_value = [
        {"name": "id", "type": "INTEGER", "nullable": False, "ordinal": 1},
        {"name": "updated_at", "type": "TIMESTAMP", "nullable": False, "ordinal": 2},
    ]
    mock_connector.fetch_last_update_time.return_value = None

    # Discover (deterministic fallback)
    investigator = Investigator()
    report = investigator._deterministic_fallback(mock_connector, db, conn)

    assert report.total_tables == 3
    skip_tables = [p for p in report.proposals if p.skip]
    assert len(skip_tables) == 1
    assert skip_tables[0].table_name == "_tmp_scratch"

    # Confirm only the non-skipped tables
    for proposal in report.proposals:
        if not proposal.skip:
            table = MonitoredTableModel(
                connection_id=conn.id,
                schema_name=proposal.schema_name,
                table_name=proposal.table_name,
                fully_qualified_name=proposal.fully_qualified_name,
                check_types=json.dumps(proposal.recommended_checks),
                freshness_sla_minutes=proposal.suggested_sla_minutes,
            )
            db.add(table)

    db.commit()

    # Verify: sentinel can now see these tables
    from sqlalchemy import select
    tables = db.execute(
        select(MonitoredTableModel).where(MonitoredTableModel.connection_id == conn.id)
    ).scalars().all()

    assert len(tables) == 2
    table_names = {t.table_name for t in tables}
    assert "users" in table_names
    assert "orders" in table_names
    assert "_tmp_scratch" not in table_names
