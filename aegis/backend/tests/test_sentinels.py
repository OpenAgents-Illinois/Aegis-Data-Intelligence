"""Tests for Schema and Freshness Sentinels."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from aegis.agents.sentinel import FreshnessSentinel, SchemaSentinel


class TestSchemaSentinel:
    def test_first_snapshot_no_anomaly(self, db, sample_table):
        """First scan creates a baseline snapshot — no anomaly."""
        connector = MagicMock()
        connector.fetch_schema.return_value = [
            {"name": "id", "type": "INTEGER", "nullable": False, "ordinal": 1},
            {"name": "price", "type": "FLOAT", "nullable": True, "ordinal": 2},
        ]

        sentinel = SchemaSentinel()
        result = sentinel.inspect(sample_table, connector, db)

        assert result is None  # First snapshot, no baseline

    def test_no_drift_returns_none(self, db, sample_table, sample_snapshot):
        """Identical schema returns no anomaly."""
        columns = json.loads(sample_snapshot.columns)
        connector = MagicMock()
        connector.fetch_schema.return_value = columns

        sentinel = SchemaSentinel()
        result = sentinel.inspect(sample_table, connector, db)

        assert result is None

    def test_detects_column_deletion(self, db, sample_table, sample_snapshot):
        """Deleting a column triggers a critical anomaly."""
        connector = MagicMock()
        connector.fetch_schema.return_value = [
            {"name": "id", "type": "INTEGER", "nullable": False, "ordinal": 1},
            # price column removed
            {"name": "name", "type": "VARCHAR", "nullable": True, "ordinal": 3},
        ]

        sentinel = SchemaSentinel()
        result = sentinel.inspect(sample_table, connector, db)

        assert result is not None
        assert result.type == "schema_drift"
        assert result.severity == "critical"

        detail = json.loads(result.detail)
        changes = [c["change"] for c in detail]
        assert "column_deleted" in changes

    def test_detects_type_change(self, db, sample_table, sample_snapshot):
        """Type change triggers a critical anomaly."""
        connector = MagicMock()
        connector.fetch_schema.return_value = [
            {"name": "id", "type": "INTEGER", "nullable": False, "ordinal": 1},
            {"name": "price", "type": "VARCHAR", "nullable": True, "ordinal": 2},
            {"name": "name", "type": "VARCHAR", "nullable": True, "ordinal": 3},
        ]

        sentinel = SchemaSentinel()
        result = sentinel.inspect(sample_table, connector, db)

        assert result is not None
        assert result.severity == "critical"

        detail = json.loads(result.detail)
        type_changes = [c for c in detail if c["change"] == "type_changed"]
        assert len(type_changes) == 1
        assert type_changes[0]["old_type"] == "FLOAT"
        assert type_changes[0]["new_type"] == "VARCHAR"

    def test_detects_nullable_column_added(self, db, sample_table, sample_snapshot):
        """Adding a nullable column triggers low severity."""
        columns = json.loads(sample_snapshot.columns) + [
            {"name": "description", "type": "TEXT", "nullable": True, "ordinal": 4}
        ]
        connector = MagicMock()
        connector.fetch_schema.return_value = columns

        sentinel = SchemaSentinel()
        result = sentinel.inspect(sample_table, connector, db)

        assert result is not None
        assert result.severity == "low"


class TestFreshnessSentinel:
    def test_no_sla_returns_none(self, db, sample_table):
        """Table with no SLA configured is skipped."""
        sample_table.freshness_sla_minutes = None
        db.flush()

        sentinel = FreshnessSentinel()
        result = sentinel.inspect(sample_table, MagicMock(), db)

        assert result is None

    def test_fresh_table_returns_none(self, db, sample_table):
        """Table updated within SLA returns no anomaly."""
        connector = MagicMock()
        connector.fetch_last_update_time.return_value = datetime.now(timezone.utc) - timedelta(
            minutes=30
        )

        sentinel = FreshnessSentinel()
        result = sentinel.inspect(sample_table, connector, db)

        assert result is None

    def test_stale_table_returns_anomaly(self, db, sample_table):
        """Table overdue by >1x SLA returns medium severity."""
        connector = MagicMock()
        connector.fetch_last_update_time.return_value = datetime.now(timezone.utc) - timedelta(
            minutes=90  # SLA is 60 min, so 1.5x overdue → medium
        )

        sentinel = FreshnessSentinel()
        result = sentinel.inspect(sample_table, connector, db)

        assert result is not None
        assert result.type == "freshness_violation"
        assert result.severity == "medium"

    def test_very_stale_table_is_critical(self, db, sample_table):
        """Table overdue by >5x SLA returns critical severity."""
        connector = MagicMock()
        connector.fetch_last_update_time.return_value = datetime.now(timezone.utc) - timedelta(
            minutes=360  # 6x the 60-min SLA
        )

        sentinel = FreshnessSentinel()
        result = sentinel.inspect(sample_table, connector, db)

        assert result is not None
        assert result.severity == "critical"
