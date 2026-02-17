"""Warehouse connection abstraction using SQLAlchemy dialects."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import create_engine, text

logger = logging.getLogger("aegis.connectors")


class WarehouseConnector:
    """Connects to a warehouse and executes queries via SQLAlchemy."""

    def __init__(self, connection_uri: str, dialect: str):
        self.dialect = dialect
        self._engine = create_engine(connection_uri, pool_pre_ping=True)

    def test_connection(self) -> bool:
        """Verify connectivity with SELECT 1."""
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            logger.exception("Connection test failed")
            return False

    def fetch_schema(self, schema_name: str, table_name: str) -> list[dict[str, Any]]:
        """Query INFORMATION_SCHEMA.COLUMNS for a table's column metadata."""
        sql = text(
            "SELECT column_name, data_type, is_nullable, ordinal_position "
            "FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table "
            "ORDER BY ordinal_position"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(sql, {"schema": schema_name, "table": table_name}).fetchall()
        return [
            {
                "name": row[0],
                "type": row[1],
                "nullable": row[2] in ("YES", True, "true", 1),
                "ordinal": row[3],
            }
            for row in rows
        ]

    def fetch_last_update_time(
        self, schema_name: str, table_name: str, timestamp_column: str | None = None
    ) -> datetime | None:
        """Get the most recent row timestamp for freshness checking."""
        fqn = f"{schema_name}.{table_name}"

        if timestamp_column:
            sql = text(f"SELECT MAX({timestamp_column}) FROM {fqn}")  # noqa: S608
        else:
            # Try common timestamp columns
            for col in ("updated_at", "_loaded_at", "created_at", "_etl_loaded_at"):
                try:
                    sql = text(f"SELECT MAX({col}) FROM {fqn}")  # noqa: S608
                    with self._engine.connect() as conn:
                        result = conn.execute(sql).scalar()
                    if result:
                        if isinstance(result, str):
                            return datetime.fromisoformat(result)
                        return result
                except Exception:
                    continue
            return None

        with self._engine.connect() as conn:
            result = conn.execute(sql).scalar()
        if result is None:
            return None
        if isinstance(result, str):
            return datetime.fromisoformat(result)
        return result

    SYSTEM_SCHEMAS = frozenset({
        "information_schema", "pg_catalog", "pg_toast", "pg_temp_1",
        "pg_toast_temp_1", "crdb_internal",
        "INFORMATION_SCHEMA",
        "SNOWFLAKE", "SNOWFLAKE_SAMPLE_DATA",
    })

    def list_schemas(self) -> list[str]:
        """List all user-accessible schemas, filtering system schemas."""
        sql = text("SELECT schema_name FROM information_schema.schemata ORDER BY schema_name")
        with self._engine.connect() as conn:
            rows = conn.execute(sql).fetchall()
        return [
            row[0]
            for row in rows
            if row[0] not in self.SYSTEM_SCHEMAS
            and not row[0].lower().startswith("pg_")
            and not row[0].lower().startswith("snowflake")
        ]

    def list_tables(self, schema_name: str) -> list[dict[str, str]]:
        """List all tables and views in a schema."""
        sql = text(
            "SELECT table_name, table_type "
            "FROM information_schema.tables "
            "WHERE table_schema = :schema "
            "ORDER BY table_name"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(sql, {"schema": schema_name}).fetchall()
        return [
            {"name": row[0], "type": row[1], "schema": schema_name}
            for row in rows
        ]

    def dispose(self):
        """Dispose of the engine connection pool."""
        self._engine.dispose()


class QueryLogExtractor(Protocol):
    """Protocol for dialect-specific query log extraction."""

    def extract(self, since: datetime, limit: int = 10000) -> list[dict[str, Any]]:
        """Fetch recent query history from the warehouse."""
        ...


class SnowflakeExtractor:
    """Extract query logs from Snowflake ACCOUNT_USAGE.QUERY_HISTORY."""

    def __init__(self, connector: WarehouseConnector):
        self._connector = connector

    def extract(self, since: datetime, limit: int = 10000) -> list[dict[str, Any]]:
        sql = text(
            "SELECT query_text, user_name, start_time, total_elapsed_time "
            "FROM snowflake.account_usage.query_history "
            "WHERE query_type IN ('INSERT', 'CREATE_TABLE_AS_SELECT', 'MERGE') "
            "AND start_time >= :since "
            "ORDER BY start_time DESC "
            "LIMIT :limit"
        )
        with self._connector._engine.connect() as conn:
            rows = conn.execute(sql, {"since": since, "limit": limit}).fetchall()
        return [
            {"sql": r[0], "user": r[1], "executed_at": r[2], "duration_ms": r[3]}
            for r in rows
        ]


class PostgreSQLExtractor:
    """Extract query logs from pg_stat_statements."""

    def __init__(self, connector: WarehouseConnector):
        self._connector = connector

    def extract(self, since: datetime, limit: int = 10000) -> list[dict[str, Any]]:
        sql = text(
            "SELECT query, '' as user_name, now() as executed_at, "
            "mean_exec_time as duration_ms "
            "FROM pg_stat_statements "
            "WHERE query ILIKE 'INSERT%%' OR query ILIKE 'CREATE%%AS%%SELECT%%' "
            "OR query ILIKE 'MERGE%%' "
            "LIMIT :limit"
        )
        with self._connector._engine.connect() as conn:
            rows = conn.execute(sql, {"limit": limit}).fetchall()
        return [
            {"sql": r[0], "user": r[1], "executed_at": r[2], "duration_ms": r[3]}
            for r in rows
        ]


class BigQueryExtractor:
    """Extract query logs from BigQuery INFORMATION_SCHEMA.JOBS."""

    def __init__(self, connector: WarehouseConnector):
        self._connector = connector

    def extract(self, since: datetime, limit: int = 10000) -> list[dict[str, Any]]:
        sql = text(
            "SELECT query, user_email, creation_time, "
            "TIMESTAMP_DIFF(end_time, start_time, MILLISECOND) as duration_ms "
            "FROM `region-us`.INFORMATION_SCHEMA.JOBS "
            "WHERE statement_type IN ('INSERT', 'CREATE_TABLE_AS_SELECT', 'MERGE') "
            "AND creation_time >= :since "
            "ORDER BY creation_time DESC "
            "LIMIT :limit"
        )
        with self._connector._engine.connect() as conn:
            rows = conn.execute(sql, {"since": since, "limit": limit}).fetchall()
        return [
            {"sql": r[0], "user": r[1], "executed_at": r[2], "duration_ms": r[3]}
            for r in rows
        ]


def get_extractor(connector: WarehouseConnector) -> QueryLogExtractor | None:
    """Return the appropriate query log extractor for a connector's dialect."""
    extractors = {
        "snowflake": SnowflakeExtractor,
        "postgresql": PostgreSQLExtractor,
        "postgres": PostgreSQLExtractor,
        "bigquery": BigQueryExtractor,
    }
    cls = extractors.get(connector.dialect)
    if cls is None:
        return None
    return cls(connector)
