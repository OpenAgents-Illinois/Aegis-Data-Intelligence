"""Tests for the Investigator agent."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from aegis.agents.investigator import Investigator
from aegis.core.models import ConnectionModel, MonitoredTableModel


@pytest.fixture
def mock_connector():
    connector = MagicMock()
    connector.list_schemas.return_value = ["public", "staging"]
    connector.list_tables.side_effect = lambda s: {
        "public": [
            {"name": "users", "type": "BASE TABLE", "schema": "public"},
            {"name": "orders", "type": "BASE TABLE", "schema": "public"},
        ],
        "staging": [
            {"name": "stg_orders", "type": "BASE TABLE", "schema": "staging"},
            {"name": "_tmp_dedup", "type": "BASE TABLE", "schema": "staging"},
        ],
    }.get(s, [])
    connector.fetch_schema.return_value = [
        {"name": "id", "type": "INTEGER", "nullable": False, "ordinal": 1},
        {"name": "created_at", "type": "TIMESTAMP", "nullable": False, "ordinal": 2},
    ]
    connector.fetch_last_update_time.return_value = datetime(2026, 2, 17, tzinfo=timezone.utc)
    return connector


@pytest.fixture
def mock_connection_model():
    model = MagicMock(spec=ConnectionModel)
    model.id = 1
    model.name = "test-warehouse"
    model.dialect = "postgresql"
    return model


class TestDeterministicFallback:
    def test_classifies_staging_tables(self, mock_connector, db, mock_connection_model):
        investigator = Investigator()
        report = investigator._deterministic_fallback(mock_connector, db, mock_connection_model)
        stg_proposals = [p for p in report.proposals if p.table_name == "stg_orders"]
        assert len(stg_proposals) == 1
        assert stg_proposals[0].role == "staging"
        assert stg_proposals[0].recommended_checks == ["schema"]
        assert stg_proposals[0].suggested_sla_minutes == 60

    def test_classifies_tmp_as_system(self, mock_connector, db, mock_connection_model):
        investigator = Investigator()
        report = investigator._deterministic_fallback(mock_connector, db, mock_connection_model)
        tmp_proposals = [p for p in report.proposals if p.table_name == "_tmp_dedup"]
        assert len(tmp_proposals) == 1
        assert tmp_proposals[0].role == "system"
        assert tmp_proposals[0].skip is True

    def test_classifies_regular_tables(self, mock_connector, db, mock_connection_model):
        investigator = Investigator()
        report = investigator._deterministic_fallback(mock_connector, db, mock_connection_model)
        user_proposals = [p for p in report.proposals if p.table_name == "users"]
        assert len(user_proposals) == 1
        assert user_proposals[0].recommended_checks == ["schema", "freshness"]

    def test_report_has_all_tables(self, mock_connector, db, mock_connection_model):
        investigator = Investigator()
        report = investigator._deterministic_fallback(mock_connector, db, mock_connection_model)
        assert report.total_tables == 4
        assert report.connection_id == 1
        assert "public" in report.schemas_found
        assert "staging" in report.schemas_found


class TestRediscover:
    def test_detects_new_tables(self, mock_connector, db, sample_connection, sample_table):
        # "orders" is monitored (from sample_table fixture), warehouse has "users" too
        mock_connector.list_schemas.return_value = ["public"]
        mock_connector.list_tables.side_effect = None
        mock_connector.list_tables.return_value = [
            {"name": "orders", "type": "BASE TABLE", "schema": "public"},
            {"name": "users", "type": "BASE TABLE", "schema": "public"},
        ]
        investigator = Investigator()
        deltas = investigator.rediscover(mock_connector, db, sample_connection.id)
        new_deltas = [d for d in deltas if d.action == "new"]
        assert len(new_deltas) == 1
        assert new_deltas[0].table_name == "users"

    def test_detects_dropped_tables(self, mock_connector, db, sample_connection, sample_table):
        # "orders" is monitored but warehouse is empty
        mock_connector.list_schemas.return_value = ["public"]
        mock_connector.list_tables.side_effect = None
        mock_connector.list_tables.return_value = []
        investigator = Investigator()
        deltas = investigator.rediscover(mock_connector, db, sample_connection.id)
        dropped = [d for d in deltas if d.action == "dropped"]
        assert len(dropped) == 1
        assert dropped[0].table_name == "orders"

    def test_no_deltas_when_in_sync(self, mock_connector, db, sample_connection, sample_table):
        mock_connector.list_schemas.return_value = ["public"]
        mock_connector.list_tables.side_effect = None
        mock_connector.list_tables.return_value = [
            {"name": "orders", "type": "BASE TABLE", "schema": "public"},
        ]
        investigator = Investigator()
        deltas = investigator.rediscover(mock_connector, db, sample_connection.id)
        assert len(deltas) == 0
