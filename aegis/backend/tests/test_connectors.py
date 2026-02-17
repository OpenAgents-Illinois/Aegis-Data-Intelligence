"""Tests for WarehouseConnector discovery methods."""

from unittest.mock import MagicMock, patch

import pytest

from aegis.core.connectors import WarehouseConnector


@pytest.fixture
def mock_connector():
    """Create a connector with a mocked engine."""
    with patch("aegis.core.connectors.create_engine") as mock_engine:
        connector = WarehouseConnector("sqlite:///:memory:", "postgresql")
        connector._engine = mock_engine.return_value
        yield connector, mock_engine.return_value


class TestListSchemas:
    def test_returns_user_schemas(self, mock_connector):
        connector, engine = mock_connector
        mock_conn = MagicMock()
        engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        mock_conn.execute.return_value.fetchall.return_value = [
            ("public",),
            ("staging",),
            ("analytics",),
            ("information_schema",),
            ("pg_catalog",),
        ]

        schemas = connector.list_schemas()
        assert "public" in schemas
        assert "staging" in schemas
        assert "analytics" in schemas
        assert "information_schema" not in schemas
        assert "pg_catalog" not in schemas

    def test_filters_snowflake_system_schemas(self, mock_connector):
        connector, engine = mock_connector
        mock_conn = MagicMock()
        engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        mock_conn.execute.return_value.fetchall.return_value = [
            ("PUBLIC",),
            ("SNOWFLAKE",),
            ("SNOWFLAKE_SAMPLE_DATA",),
        ]

        schemas = connector.list_schemas()
        assert "PUBLIC" in schemas
        assert "SNOWFLAKE" not in schemas
        assert "SNOWFLAKE_SAMPLE_DATA" not in schemas


class TestListTables:
    def test_returns_tables_and_views(self, mock_connector):
        connector, engine = mock_connector
        mock_conn = MagicMock()
        engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        engine.connect.return_value.__exit__ = MagicMock(return_value=False)

        mock_conn.execute.return_value.fetchall.return_value = [
            ("users", "BASE TABLE",),
            ("active_users", "VIEW",),
        ]

        tables = connector.list_tables("public")
        assert len(tables) == 2
        assert tables[0] == {"name": "users", "type": "BASE TABLE", "schema": "public"}
        assert tables[1] == {"name": "active_users", "type": "VIEW", "schema": "public"}
