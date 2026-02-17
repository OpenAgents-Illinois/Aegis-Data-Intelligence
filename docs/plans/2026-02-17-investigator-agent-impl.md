# Investigator Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a LangChain-powered Investigator agent that crawls warehouse metadata via tool calling, classifies tables, and proposes monitoring configuration for user confirmation.

**Architecture:** LangChain AgentExecutor with 5 tools that query the warehouse through the existing WarehouseConnector. Tools are closure-bound per invocation. The agent produces a DiscoveryReport that the user confirms via API, which creates MonitoredTableModel rows consumed by the existing Sentinel pipeline.

**Tech Stack:** LangChain (langchain-core, langchain-openai), existing FastAPI/SQLAlchemy stack, Pydantic schemas.

**Design Doc:** `docs/plans/2026-02-17-investigator-agent-design.md`

---

### Task 1: Add LangChain Dependencies

**Files:**
- Modify: `aegis/backend/pyproject.toml`

**Step 1: Add langchain packages to dependencies**

In `aegis/backend/pyproject.toml`, add to the `dependencies` list after the `aiosqlite` line:

```toml
    "langchain-core>=0.3.0",
    "langchain-openai>=0.2.0",
    "langchain>=0.3.0",
```

**Step 2: Add rediscovery config setting**

In `aegis/backend/aegis/config.py`, add to the `Settings` class after `lineage_refresh_seconds`:

```python
    rediscovery_interval_seconds: int = 86400  # 24 hours
```

**Step 3: Install dependencies**

Run: `cd aegis/backend && pip install -e ".[dev]"`
Expected: Successful installation of langchain packages.

**Step 4: Commit**

```bash
git add aegis/backend/pyproject.toml aegis/backend/aegis/config.py
git commit -m "feat(investigator): add langchain deps and rediscovery config"
```

---

### Task 2: Add Connector Methods (list_schemas, list_tables)

**Files:**
- Modify: `aegis/backend/aegis/core/connectors.py`
- Test: `aegis/backend/tests/test_connectors.py`

**Step 1: Write the failing tests**

Create `aegis/backend/tests/test_connectors.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `cd aegis/backend && python -m pytest tests/test_connectors.py -v`
Expected: FAIL — `list_schemas` and `list_tables` not defined on WarehouseConnector.

**Step 3: Implement list_schemas and list_tables**

Add to `aegis/backend/aegis/core/connectors.py`, in the `WarehouseConnector` class after the `fetch_last_update_time` method:

```python
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
```

**Step 4: Run tests to verify they pass**

Run: `cd aegis/backend && python -m pytest tests/test_connectors.py -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add aegis/backend/aegis/core/connectors.py aegis/backend/tests/test_connectors.py
git commit -m "feat(investigator): add list_schemas and list_tables to connector"
```

---

### Task 3: Add Pydantic Schemas

**Files:**
- Modify: `aegis/backend/aegis/core/models.py`
- Test: `aegis/backend/tests/test_models_discovery.py`

**Step 1: Write the failing test**

Create `aegis/backend/tests/test_models_discovery.py`:

```python
"""Tests for discovery Pydantic schemas."""

from datetime import datetime, timezone

from aegis.core.models import (
    DiscoveryConfirm,
    DiscoveryReport,
    TableDelta,
    TableProposal,
    TableSelectionItem,
)


def test_table_proposal_creation():
    proposal = TableProposal(
        schema_name="public",
        table_name="users",
        fully_qualified_name="public.users",
        role="dimension",
        columns=[{"name": "id", "type": "INTEGER", "nullable": False, "ordinal": 1}],
        recommended_checks=["schema", "freshness"],
        suggested_sla_minutes=360,
        reasoning="Core user table with updated_at",
        skip=False,
    )
    assert proposal.role == "dimension"
    assert proposal.skip is False


def test_table_proposal_skip():
    proposal = TableProposal(
        schema_name="staging",
        table_name="_tmp_dedup",
        fully_qualified_name="staging._tmp_dedup",
        role="system",
        columns=[],
        recommended_checks=[],
        suggested_sla_minutes=None,
        reasoning="Temporary table",
        skip=True,
    )
    assert proposal.skip is True
    assert proposal.recommended_checks == []


def test_discovery_report_creation():
    report = DiscoveryReport(
        connection_id=1,
        connection_name="test-warehouse",
        schemas_found=["public", "staging"],
        total_tables=5,
        proposals=[],
        concerns=["Table X has no timestamps"],
        generated_at=datetime.now(timezone.utc),
    )
    assert report.total_tables == 5
    assert len(report.concerns) == 1


def test_table_delta_new():
    delta = TableDelta(
        action="new",
        schema_name="public",
        table_name="new_table",
        fully_qualified_name="public.new_table",
        proposal=TableProposal(
            schema_name="public",
            table_name="new_table",
            fully_qualified_name="public.new_table",
            role="unknown",
            columns=[],
            recommended_checks=["schema"],
            suggested_sla_minutes=None,
            reasoning="New table detected",
            skip=False,
        ),
    )
    assert delta.action == "new"
    assert delta.proposal is not None


def test_table_delta_dropped():
    delta = TableDelta(
        action="dropped",
        schema_name="public",
        table_name="old_table",
        fully_qualified_name="public.old_table",
        proposal=None,
    )
    assert delta.action == "dropped"
    assert delta.proposal is None


def test_discovery_confirm():
    confirm = DiscoveryConfirm(
        table_selections=[
            TableSelectionItem(
                schema_name="public",
                table_name="users",
                check_types=["schema", "freshness"],
                freshness_sla_minutes=360,
            ),
            TableSelectionItem(
                schema_name="staging",
                table_name="stg_orders",
            ),
        ]
    )
    assert len(confirm.table_selections) == 2
    assert confirm.table_selections[1].check_types == ["schema", "freshness"]  # default
    assert confirm.table_selections[1].freshness_sla_minutes is None  # default
```

**Step 2: Run tests to verify they fail**

Run: `cd aegis/backend && python -m pytest tests/test_models_discovery.py -v`
Expected: FAIL — ImportError, schemas not defined.

**Step 3: Add Pydantic schemas to models.py**

Add at the end of `aegis/backend/aegis/core/models.py`, after the `StatsResponse` class:

```python
# Discovery schemas (transient — not persisted to DB)


class TableProposal(BaseModel):
    """A single table proposed for monitoring by the Investigator."""
    schema_name: str
    table_name: str
    fully_qualified_name: str
    role: str
    columns: list[dict[str, Any]]
    recommended_checks: list[str]
    suggested_sla_minutes: int | None
    reasoning: str
    skip: bool


class TableDelta(BaseModel):
    """A change detected during warehouse rediscovery."""
    action: str
    schema_name: str
    table_name: str
    fully_qualified_name: str
    proposal: TableProposal | None = None


class DiscoveryReport(BaseModel):
    """Complete discovery output for a warehouse connection."""
    connection_id: int
    connection_name: str
    schemas_found: list[str]
    total_tables: int
    proposals: list[TableProposal]
    concerns: list[str]
    generated_at: datetime


class TableSelectionItem(BaseModel):
    """A single table the user chose to monitor from a discovery report."""
    schema_name: str
    table_name: str
    check_types: list[str] = Field(default=["schema", "freshness"])
    freshness_sla_minutes: int | None = None


class DiscoveryConfirm(BaseModel):
    """User's selection from a discovery report."""
    table_selections: list[TableSelectionItem]
```

**Step 4: Run tests to verify they pass**

Run: `cd aegis/backend && python -m pytest tests/test_models_discovery.py -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add aegis/backend/aegis/core/models.py aegis/backend/tests/test_models_discovery.py
git commit -m "feat(investigator): add discovery Pydantic schemas"
```

---

### Task 4: Create LangChain LLM Service

**Files:**
- Create: `aegis/backend/aegis/services/langchain_llm.py`
- Test: `aegis/backend/tests/test_langchain_llm.py`

**Step 1: Write the failing test**

Create `aegis/backend/tests/test_langchain_llm.py`:

```python
"""Tests for LangChain LLM service."""

from unittest.mock import patch

from aegis.services.langchain_llm import get_chat_model


def test_get_chat_model_returns_chatopenai():
    with patch("aegis.services.langchain_llm.settings") as mock_settings:
        mock_settings.openai_api_key = "test-key"
        model = get_chat_model()
        assert model.model_name == "gpt-4"
        assert model.temperature == 0.0


def test_get_chat_model_custom_temperature():
    with patch("aegis.services.langchain_llm.settings") as mock_settings:
        mock_settings.openai_api_key = "test-key"
        model = get_chat_model(temperature=0.7)
        assert model.temperature == 0.7
```

**Step 2: Run tests to verify they fail**

Run: `cd aegis/backend && python -m pytest tests/test_langchain_llm.py -v`
Expected: FAIL — module not found.

**Step 3: Create the langchain_llm service**

Create `aegis/backend/aegis/services/langchain_llm.py`:

```python
"""LangChain-based LLM service for new agents (Investigator and future)."""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from aegis.config import settings


def get_chat_model(temperature: float = 0.0) -> ChatOpenAI:
    """Create a ChatOpenAI instance with project settings.

    Lazy — does not fail if OPENAI_API_KEY is unset until the model is invoked.
    """
    return ChatOpenAI(
        model="gpt-4",
        temperature=temperature,
        api_key=settings.openai_api_key or "not-set",
    )
```

**Step 4: Run tests to verify they pass**

Run: `cd aegis/backend && python -m pytest tests/test_langchain_llm.py -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add aegis/backend/aegis/services/langchain_llm.py aegis/backend/tests/test_langchain_llm.py
git commit -m "feat(investigator): add LangChain LLM service factory"
```

---

### Task 5: Create Investigator Tools

**Files:**
- Create: `aegis/backend/aegis/agents/investigator_tools.py`
- Test: `aegis/backend/tests/test_investigator_tools.py`

**Step 1: Write the failing test**

Create `aegis/backend/tests/test_investigator_tools.py`:

```python
"""Tests for Investigator LangChain tools."""

from unittest.mock import MagicMock

from aegis.agents.investigator_tools import make_tools


class TestMakeTools:
    def test_returns_five_tools(self):
        mock_connector = MagicMock()
        mock_db = MagicMock()
        tools = make_tools(mock_connector, mock_db)
        assert len(tools) == 5

    def test_list_schemas_calls_connector(self):
        mock_connector = MagicMock()
        mock_connector.list_schemas.return_value = ["public", "staging"]
        mock_db = MagicMock()
        tools = make_tools(mock_connector, mock_db)
        list_schemas = tools[0]
        result = list_schemas.invoke({})
        mock_connector.list_schemas.assert_called_once()
        assert result == ["public", "staging"]

    def test_list_tables_calls_connector(self):
        mock_connector = MagicMock()
        mock_connector.list_tables.return_value = [{"name": "users", "type": "BASE TABLE", "schema": "public"}]
        mock_db = MagicMock()
        tools = make_tools(mock_connector, mock_db)
        list_tables = tools[1]
        result = list_tables.invoke({"schema_name": "public"})
        mock_connector.list_tables.assert_called_once_with("public")

    def test_inspect_columns_calls_fetch_schema(self):
        mock_connector = MagicMock()
        mock_connector.fetch_schema.return_value = [
            {"name": "id", "type": "INTEGER", "nullable": False, "ordinal": 1}
        ]
        mock_db = MagicMock()
        tools = make_tools(mock_connector, mock_db)
        inspect = tools[2]
        result = inspect.invoke({"schema_name": "public", "table_name": "users"})
        mock_connector.fetch_schema.assert_called_once_with("public", "users")

    def test_check_freshness_returns_dict(self):
        mock_connector = MagicMock()
        mock_connector.fetch_last_update_time.return_value = None
        mock_db = MagicMock()
        tools = make_tools(mock_connector, mock_db)
        check_freshness = tools[3]
        result = check_freshness.invoke({"schema_name": "public", "table_name": "users"})
        assert result["has_timestamp"] is False

    def test_get_lineage_without_graph(self):
        mock_connector = MagicMock()
        mock_db = MagicMock()
        tools = make_tools(mock_connector, mock_db, lineage_graph=None)
        get_lineage = tools[4]
        result = get_lineage.invoke({"table_name": "public.users"})
        assert result == {"upstream": [], "downstream": []}
```

**Step 2: Run tests to verify they fail**

Run: `cd aegis/backend && python -m pytest tests/test_investigator_tools.py -v`
Expected: FAIL — module not found.

**Step 3: Create the investigator tools module**

Create `aegis/backend/aegis/agents/investigator_tools.py`:

```python
"""LangChain tools for the Investigator agent — closure-bound per invocation."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from langchain_core.tools import tool

from aegis.core.connectors import WarehouseConnector

logger = logging.getLogger("aegis.investigator.tools")


def make_tools(
    connector: WarehouseConnector,
    db: Any,
    lineage_graph: Any = None,
) -> list:
    """Create Investigator tools with connector/db bound via closure."""

    @tool
    def list_warehouse_schemas() -> list[str]:
        """List all user-accessible schemas in the warehouse.
        Excludes system schemas (information_schema, pg_catalog, etc.).
        Call this first to discover what schemas exist."""
        try:
            return connector.list_schemas()
        except Exception as exc:
            logger.warning("list_schemas failed: %s", exc)
            return []

    @tool
    def list_schema_tables(schema_name: str) -> list[dict]:
        """List all tables and views in a specific schema.
        Returns: [{name, type (BASE TABLE/VIEW), schema}]
        Call this for each schema to see what tables exist."""
        try:
            return connector.list_tables(schema_name)
        except Exception as exc:
            logger.warning("list_tables failed for %s: %s", schema_name, exc)
            return []

    @tool
    def inspect_table_columns(schema_name: str, table_name: str) -> list[dict]:
        """Get detailed column metadata for a specific table.
        Returns: [{name, type, nullable, ordinal}]
        Call this for tables you want to inspect more deeply."""
        try:
            return connector.fetch_schema(schema_name, table_name)
        except Exception as exc:
            logger.warning("fetch_schema failed for %s.%s: %s", schema_name, table_name, exc)
            return []

    @tool
    def check_table_freshness(schema_name: str, table_name: str) -> dict:
        """Check if a table has timestamp columns and when it was last updated.
        Returns: {has_timestamp: bool, last_update: str|null, timestamp_column: str|null}
        Useful for deciding if freshness monitoring is possible."""
        try:
            last_update = connector.fetch_last_update_time(schema_name, table_name)
            if last_update is not None:
                return {
                    "has_timestamp": True,
                    "last_update": last_update.isoformat() if isinstance(last_update, datetime) else str(last_update),
                    "timestamp_column": "detected",
                }
            return {"has_timestamp": False, "last_update": None, "timestamp_column": None}
        except Exception as exc:
            logger.warning("freshness check failed for %s.%s: %s", schema_name, table_name, exc)
            return {"has_timestamp": False, "last_update": None, "timestamp_column": None}

    @tool
    def get_known_lineage(table_name: str) -> dict:
        """Get known upstream and downstream dependencies for a table from the lineage graph.
        Returns: {upstream: [str], downstream: [str]}
        Only available if lineage has been previously refreshed."""
        if lineage_graph is None:
            return {"upstream": [], "downstream": []}
        try:
            upstream = lineage_graph.get_upstream(table_name, depth=3)
            downstream = lineage_graph.get_downstream(table_name, depth=3)
            return {
                "upstream": [n["table"] for n in upstream] if upstream else [],
                "downstream": [n["table"] for n in downstream] if downstream else [],
            }
        except Exception as exc:
            logger.warning("lineage lookup failed for %s: %s", table_name, exc)
            return {"upstream": [], "downstream": []}

    return [
        list_warehouse_schemas,
        list_schema_tables,
        inspect_table_columns,
        check_table_freshness,
        get_known_lineage,
    ]
```

**Step 4: Run tests to verify they pass**

Run: `cd aegis/backend && python -m pytest tests/test_investigator_tools.py -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add aegis/backend/aegis/agents/investigator_tools.py aegis/backend/tests/test_investigator_tools.py
git commit -m "feat(investigator): add LangChain tool definitions with closure binding"
```

---

### Task 6: Create Investigator Prompts

**Files:**
- Create: `aegis/backend/aegis/agents/investigator_prompts.py`
- Test: `aegis/backend/tests/test_investigator_prompts.py`

**Step 1: Write the failing test**

Create `aegis/backend/tests/test_investigator_prompts.py`:

```python
"""Tests for Investigator prompt templates."""

from aegis.agents.investigator_prompts import investigator_prompt, INVESTIGATOR_SYSTEM


def test_system_prompt_contains_classification_rules():
    assert "fact" in INVESTIGATOR_SYSTEM
    assert "dimension" in INVESTIGATOR_SYSTEM
    assert "staging" in INVESTIGATOR_SYSTEM
    assert "skip" in INVESTIGATOR_SYSTEM


def test_prompt_template_formats_correctly():
    messages = investigator_prompt.format_messages(
        connection_name="test-warehouse",
        dialect="postgresql",
        connection_id=1,
        agent_scratchpad=[],
    )
    assert len(messages) >= 2
    assert "test-warehouse" in messages[1].content
    assert "postgresql" in messages[1].content
```

**Step 2: Run tests to verify they fail**

Run: `cd aegis/backend && python -m pytest tests/test_investigator_prompts.py -v`
Expected: FAIL — module not found.

**Step 3: Create the prompts module**

Create `aegis/backend/aegis/agents/investigator_prompts.py`:

```python
"""Prompt templates for the Investigator agent."""

from langchain_core.prompts import ChatPromptTemplate

INVESTIGATOR_SYSTEM = """\
You are Aegis Investigator, a data warehouse analysis agent. Your job is to \
explore a connected warehouse and classify tables for monitoring.

## Your workflow:
1. Call list_warehouse_schemas to discover all schemas
2. For each schema, call list_schema_tables to see what tables exist
3. For tables that look important, call inspect_table_columns to understand structure
4. Optionally call check_table_freshness to see if timestamp columns exist
5. Optionally call get_known_lineage to understand dependencies
6. You can skip calling inspect_table_columns on tables that are obviously \
temporary or system tables based on their name (e.g., _tmp_*, _temp_*, _test_*)

## Classification rules:
- "fact": Event/transaction tables with timestamps, growing data. Monitor schema + freshness.
- "dimension": Reference/lookup tables (users, products, regions). Monitor schema + freshness.
- "staging": Intermediate tables (stg_*, staging.*). Monitor schema only.
- "raw": Ingestion landing tables (raw_*, raw.*). Monitor schema only.
- "snapshot": Point-in-time captures (*_snapshot, *_hist). Monitor schema only.
- "system": Internal/metadata/temp tables. Mark skip=true.
- "unknown": Cannot determine. Monitor schema + freshness, sla=null.

## SLA guidelines (minutes):
- Staging: 60 (hourly refresh)
- Fact/dimension: 360 (6-hour refresh)
- Raw: 1440 (daily refresh)
- No timestamp column: set freshness check to false, sla to null

## Skip these (set skip=true):
- System catalog/migration/metadata tables
- Temporary tables (_tmp, _temp, _test, _backup)
- Empty schema stubs

## After investigating, return your final classification as JSON:
{{
  "proposals": [
    {{
      "schema_name": "string",
      "table_name": "string",
      "fully_qualified_name": "schema.table",
      "role": "fact|dimension|staging|raw|snapshot|system|unknown",
      "columns": [],
      "recommended_checks": ["schema"] or ["schema", "freshness"],
      "suggested_sla_minutes": number or null,
      "reasoning": "1-2 sentences explaining classification",
      "skip": boolean
    }}
  ],
  "concerns": ["data quality risks or observations"]
}}

Important: For the "columns" field in each proposal, include the column metadata \
you retrieved from inspect_table_columns. If you did not inspect a table, use an \
empty list.

You MUST respond with valid JSON as your final answer after using the tools."""

INVESTIGATOR_HUMAN = """\
Investigate the warehouse connected as "{connection_name}" \
(dialect: {dialect}, connection_id: {connection_id}).

Discover all schemas and tables, classify each one, and return your \
monitoring recommendations as JSON."""

investigator_prompt = ChatPromptTemplate.from_messages([
    ("system", INVESTIGATOR_SYSTEM),
    ("human", INVESTIGATOR_HUMAN),
    ("placeholder", "{agent_scratchpad}"),
])
```

**Step 4: Run tests to verify they pass**

Run: `cd aegis/backend && python -m pytest tests/test_investigator_prompts.py -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add aegis/backend/aegis/agents/investigator_prompts.py aegis/backend/tests/test_investigator_prompts.py
git commit -m "feat(investigator): add LangChain prompt templates"
```

---

### Task 7: Create the Investigator Agent

**Files:**
- Create: `aegis/backend/aegis/agents/investigator.py`
- Test: `aegis/backend/tests/test_investigator.py`

**Step 1: Write the failing tests**

Create `aegis/backend/tests/test_investigator.py`:

```python
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
    def test_detects_new_tables(self, mock_connector, db, sample_connection):
        # Only "orders" is monitored (from fixture), but warehouse has "users" too
        mock_connector.list_schemas.return_value = ["public"]
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
        mock_connector.list_tables.return_value = []
        investigator = Investigator()
        deltas = investigator.rediscover(mock_connector, db, sample_connection.id)
        dropped = [d for d in deltas if d.action == "dropped"]
        assert len(dropped) == 1
        assert dropped[0].table_name == "orders"

    def test_no_deltas_when_in_sync(self, mock_connector, db, sample_connection, sample_table):
        mock_connector.list_schemas.return_value = ["public"]
        mock_connector.list_tables.return_value = [
            {"name": "orders", "type": "BASE TABLE", "schema": "public"},
        ]
        investigator = Investigator()
        deltas = investigator.rediscover(mock_connector, db, sample_connection.id)
        assert len(deltas) == 0
```

**Step 2: Run tests to verify they fail**

Run: `cd aegis/backend && python -m pytest tests/test_investigator.py -v`
Expected: FAIL — module not found.

**Step 3: Create the Investigator agent**

Create `aegis/backend/aegis/agents/investigator.py`:

```python
"""Investigator agent — LangChain-powered warehouse discovery and classification."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from aegis.core.connectors import WarehouseConnector
from aegis.core.models import (
    ConnectionModel,
    DiscoveryReport,
    MonitoredTableModel,
    TableDelta,
    TableProposal,
)

logger = logging.getLogger("aegis.investigator")


class Investigator:
    """Discovers warehouse structure and proposes monitoring configuration."""

    def __init__(self, lineage_graph=None):
        self.lineage = lineage_graph

    def discover(
        self,
        connector: WarehouseConnector,
        db: Session,
        connection_model: ConnectionModel,
    ) -> DiscoveryReport:
        """Run the LangChain agent to discover and classify warehouse tables."""
        try:
            return self._langchain_discover(connector, db, connection_model)
        except Exception:
            logger.warning("LangChain discovery failed, falling back to deterministic", exc_info=True)
            return self._deterministic_fallback(connector, db, connection_model)

    def _langchain_discover(
        self,
        connector: WarehouseConnector,
        db: Session,
        connection_model: ConnectionModel,
    ) -> DiscoveryReport:
        """LangChain agent-based discovery with tool calling."""
        from langchain.agents import AgentExecutor, create_tool_calling_agent

        from aegis.agents.investigator_prompts import investigator_prompt
        from aegis.agents.investigator_tools import make_tools
        from aegis.services.langchain_llm import get_chat_model

        llm = get_chat_model()
        tools = make_tools(connector, db, lineage_graph=self.lineage)
        agent = create_tool_calling_agent(llm, tools, investigator_prompt)
        executor = AgentExecutor(
            agent=agent,
            tools=tools,
            max_iterations=25,
            return_intermediate_steps=True,
            verbose=False,
        )

        result = executor.invoke({
            "connection_name": connection_model.name,
            "dialect": connection_model.dialect,
            "connection_id": connection_model.id,
        })

        return self._parse_result(result["output"], connection_model)

    def _parse_result(self, output: str, connection_model: ConnectionModel) -> DiscoveryReport:
        """Parse AgentExecutor output into DiscoveryReport."""
        # Extract JSON from the output (may have surrounding text)
        json_match = re.search(r"\{.*\}", output, re.DOTALL)
        if not json_match:
            raise ValueError("No JSON found in agent output")

        data = json.loads(json_match.group())
        proposals = [TableProposal(**p) for p in data["proposals"]]

        return DiscoveryReport(
            connection_id=connection_model.id,
            connection_name=connection_model.name,
            schemas_found=sorted({p.schema_name for p in proposals}),
            total_tables=len(proposals),
            proposals=proposals,
            concerns=data.get("concerns", []),
            generated_at=datetime.now(timezone.utc),
        )

    def rediscover(
        self,
        connector: WarehouseConnector,
        db: Session,
        connection_id: int,
    ) -> list[TableDelta]:
        """Compare current warehouse state against enrolled tables. No LLM."""
        # Get current warehouse tables
        warehouse_tables: set[str] = set()
        for schema in connector.list_schemas():
            for table in connector.list_tables(schema):
                fqn = f"{schema}.{table['name']}"
                warehouse_tables.add(fqn)

        # Get monitored tables for this connection
        stmt = select(MonitoredTableModel).where(
            MonitoredTableModel.connection_id == connection_id
        )
        monitored = db.execute(stmt).scalars().all()
        monitored_fqns = {t.fully_qualified_name for t in monitored}

        deltas: list[TableDelta] = []

        # New tables (in warehouse but not monitored)
        for fqn in sorted(warehouse_tables - monitored_fqns):
            parts = fqn.split(".", 1)
            schema_name = parts[0] if len(parts) == 2 else "default"
            table_name = parts[1] if len(parts) == 2 else parts[0]
            deltas.append(TableDelta(
                action="new",
                schema_name=schema_name,
                table_name=table_name,
                fully_qualified_name=fqn,
                proposal=None,
            ))

        # Dropped tables (monitored but not in warehouse)
        for fqn in sorted(monitored_fqns - warehouse_tables):
            parts = fqn.split(".", 1)
            schema_name = parts[0] if len(parts) == 2 else "default"
            table_name = parts[1] if len(parts) == 2 else parts[0]
            deltas.append(TableDelta(
                action="dropped",
                schema_name=schema_name,
                table_name=table_name,
                fully_qualified_name=fqn,
            ))

        return deltas

    def _deterministic_fallback(
        self,
        connector: WarehouseConnector,
        db: Session,
        connection_model: ConnectionModel,
    ) -> DiscoveryReport:
        """Rule-based classification when LangChain agent fails."""
        proposals: list[TableProposal] = []
        schemas_found: list[str] = []

        for schema in connector.list_schemas():
            schemas_found.append(schema)
            for table_info in connector.list_tables(schema):
                table_name = table_info["name"]
                fqn = f"{schema}.{table_name}"

                # Fetch columns for classification
                try:
                    columns = connector.fetch_schema(schema, table_name)
                except Exception:
                    columns = []

                role, checks, sla, reasoning, skip = self._classify_by_rules(
                    schema, table_name, columns
                )

                proposals.append(TableProposal(
                    schema_name=schema,
                    table_name=table_name,
                    fully_qualified_name=fqn,
                    role=role,
                    columns=columns,
                    recommended_checks=checks,
                    suggested_sla_minutes=sla,
                    reasoning=reasoning,
                    skip=skip,
                ))

        return DiscoveryReport(
            connection_id=connection_model.id,
            connection_name=connection_model.name,
            schemas_found=sorted(schemas_found),
            total_tables=len(proposals),
            proposals=proposals,
            concerns=[],
            generated_at=datetime.now(timezone.utc),
        )

    def _classify_by_rules(
        self,
        schema: str,
        table_name: str,
        columns: list[dict[str, Any]],
    ) -> tuple[str, list[str], int | None, str, bool]:
        """Deterministic heuristics. Returns (role, checks, sla, reasoning, skip)."""
        name_lower = table_name.lower()
        schema_lower = schema.lower()
        col_names = {c["name"].lower() for c in columns}
        has_timestamp = bool(col_names & {"updated_at", "modified_at", "created_at", "_loaded_at", "_etl_loaded_at"})

        # Temp/system tables
        if name_lower.startswith(("_tmp", "_temp", "_test", "_backup")):
            return "system", [], None, f"Temporary table ({name_lower[:5]}* prefix)", True

        # Staging
        if name_lower.startswith("stg_") or schema_lower in ("staging", "stg"):
            return "staging", ["schema"], 60, f"Staging table in {schema}", False

        # Raw
        if name_lower.startswith("raw_") or schema_lower in ("raw", "landing"):
            return "raw", ["schema"], 1440, f"Raw ingestion table in {schema}", False

        # Dimension
        if name_lower.startswith("dim_"):
            checks = ["schema", "freshness"] if has_timestamp else ["schema"]
            sla = 360 if has_timestamp else None
            return "dimension", checks, sla, f"Dimension table (dim_ prefix)", False

        # Fact
        if name_lower.startswith("fct_") or name_lower.startswith("fact_"):
            checks = ["schema", "freshness"] if has_timestamp else ["schema"]
            sla = 360 if has_timestamp else None
            return "fact", checks, sla, f"Fact table (fct_ prefix)", False

        # Snapshot
        if name_lower.endswith(("_snapshot", "_hist", "_history")):
            return "snapshot", ["schema"], None, "Snapshot/history table", False

        # Default — use timestamps to decide
        if has_timestamp:
            return "unknown", ["schema", "freshness"], None, "Has timestamp columns; role unknown", False

        return "unknown", ["schema"], None, "No timestamp columns detected; role unknown", False
```

**Step 4: Run tests to verify they pass**

Run: `cd aegis/backend && python -m pytest tests/test_investigator.py -v`
Expected: All PASS.

**Step 5: Commit**

```bash
git add aegis/backend/aegis/agents/investigator.py aegis/backend/tests/test_investigator.py
git commit -m "feat(investigator): implement Investigator agent with LangChain and fallback"
```

---

### Task 8: Create Discovery API Endpoints

**Files:**
- Create: `aegis/backend/aegis/api/discovery.py`
- Modify: `aegis/backend/aegis/api/router.py`
- Test: `aegis/backend/tests/test_discovery_api.py`

**Step 1: Write the failing tests**

Create `aegis/backend/tests/test_discovery_api.py`:

```python
"""Tests for discovery API endpoints."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from aegis.core.models import DiscoveryReport, TableProposal


@pytest.fixture
def mock_discovery_report():
    return DiscoveryReport(
        connection_id=1,
        connection_name="test-warehouse",
        schemas_found=["public"],
        total_tables=1,
        proposals=[
            TableProposal(
                schema_name="public",
                table_name="users",
                fully_qualified_name="public.users",
                role="dimension",
                columns=[{"name": "id", "type": "INTEGER", "nullable": False, "ordinal": 1}],
                recommended_checks=["schema", "freshness"],
                suggested_sla_minutes=360,
                reasoning="Core user table",
                skip=False,
            )
        ],
        concerns=[],
        generated_at=datetime.now(timezone.utc),
    )


def test_discover_endpoint(api_client, mock_discovery_report):
    # First create a connection
    with patch("aegis.api.discovery.Investigator") as MockInvestigator, \
         patch("aegis.api.discovery.WarehouseConnector") as MockConnector:
        mock_inv = MockInvestigator.return_value
        mock_inv.discover.return_value = mock_discovery_report
        mock_conn = MockConnector.return_value

        # Create connection first
        resp = api_client.post(
            "/api/v1/connections",
            json={"name": "test-wh", "dialect": "postgresql", "connection_uri": "postgresql://x"},
            headers={"X-API-Key": "dev-key"},
        )
        conn_id = resp.json()["id"]

        resp = api_client.post(
            f"/api/v1/connections/{conn_id}/discover",
            headers={"X-API-Key": "dev-key"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_tables"] == 1
        assert data["proposals"][0]["role"] == "dimension"


def test_confirm_endpoint_creates_tables(api_client):
    # Create connection first
    resp = api_client.post(
        "/api/v1/connections",
        json={"name": "test-wh2", "dialect": "postgresql", "connection_uri": "postgresql://x"},
        headers={"X-API-Key": "dev-key"},
    )
    conn_id = resp.json()["id"]

    resp = api_client.post(
        f"/api/v1/connections/{conn_id}/discover/confirm",
        json={
            "table_selections": [
                {
                    "schema_name": "public",
                    "table_name": "users",
                    "check_types": ["schema", "freshness"],
                    "freshness_sla_minutes": 360,
                }
            ]
        },
        headers={"X-API-Key": "dev-key"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["enrolled"]) == 1
    assert data["enrolled"][0]["table_name"] == "users"


def test_discover_404_for_missing_connection(api_client):
    resp = api_client.post(
        "/api/v1/connections/9999/discover",
        headers={"X-API-Key": "dev-key"},
    )
    assert resp.status_code == 404
```

**Step 2: Run tests to verify they fail**

Run: `cd aegis/backend && python -m pytest tests/test_discovery_api.py -v`
Expected: FAIL — module not found / routes not registered.

**Step 3: Create the discovery API module**

Create `aegis/backend/aegis/api/discovery.py`:

```python
"""Discovery API endpoints — trigger investigation and confirm table enrollment."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.agents.investigator import Investigator
from aegis.api.deps import get_db, verify_api_key
from aegis.core.connectors import WarehouseConnector
from aegis.core.models import (
    ConnectionModel,
    DiscoveryConfirm,
    MonitoredTableModel,
)

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.post("/{conn_id}/discover")
async def discover_tables(conn_id: int, db: AsyncSession = Depends(get_db)):
    """Trigger warehouse discovery and return classification proposals."""
    conn = await db.get(ConnectionModel, conn_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    connector = WarehouseConnector(conn.connection_uri, conn.dialect)
    try:
        investigator = Investigator()
        report = investigator.discover(connector, db, conn)
        return report.model_dump(mode="json")
    finally:
        connector.dispose()


@router.post("/{conn_id}/discover/confirm", status_code=201)
async def confirm_discovery(
    conn_id: int,
    body: DiscoveryConfirm,
    db: AsyncSession = Depends(get_db),
):
    """Enroll selected tables from a discovery report."""
    conn = await db.get(ConnectionModel, conn_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    enrolled = []
    for selection in body.table_selections:
        # Check for duplicates
        stmt = select(MonitoredTableModel).where(
            MonitoredTableModel.connection_id == conn_id,
            MonitoredTableModel.schema_name == selection.schema_name,
            MonitoredTableModel.table_name == selection.table_name,
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            continue  # Skip duplicates silently

        table = MonitoredTableModel(
            connection_id=conn_id,
            schema_name=selection.schema_name,
            table_name=selection.table_name,
            fully_qualified_name=f"{selection.schema_name}.{selection.table_name}",
            check_types=json.dumps(selection.check_types),
            freshness_sla_minutes=selection.freshness_sla_minutes,
        )
        db.add(table)
        enrolled.append({
            "schema_name": selection.schema_name,
            "table_name": selection.table_name,
            "check_types": selection.check_types,
            "freshness_sla_minutes": selection.freshness_sla_minutes,
        })

    await db.commit()
    return {"enrolled": enrolled, "total": len(enrolled)}
```

**Step 4: Register the discovery router**

In `aegis/backend/aegis/api/router.py`, add:

```python
from aegis.api.discovery import router as discovery_router
```

And add this line after the connections router include:

```python
api_router.include_router(discovery_router, prefix="/connections", tags=["discovery"])
```

**Step 5: Run tests to verify they pass**

Run: `cd aegis/backend && python -m pytest tests/test_discovery_api.py -v`
Expected: All PASS.

**Step 6: Commit**

```bash
git add aegis/backend/aegis/api/discovery.py aegis/backend/aegis/api/router.py aegis/backend/tests/test_discovery_api.py
git commit -m "feat(investigator): add discovery API endpoints"
```

---

### Task 9: Integrate Rediscovery into Scanner

**Files:**
- Modify: `aegis/backend/aegis/services/scanner.py`
- Test: `aegis/backend/tests/test_scanner_rediscovery.py`

**Step 1: Write the failing test**

Create `aegis/backend/tests/test_scanner_rediscovery.py`:

```python
"""Tests for scanner rediscovery integration."""

from unittest.mock import MagicMock, patch

from aegis.services.scanner import _run_rediscovery


def test_run_rediscovery_calls_investigator():
    with patch("aegis.services.scanner.SyncSessionLocal") as MockSession, \
         patch("aegis.services.scanner.WarehouseConnector") as MockConnector, \
         patch("aegis.services.scanner.Investigator") as MockInvestigator, \
         patch("aegis.services.scanner.notifier") as mock_notifier:

        mock_db = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_db)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        # Mock one active connection
        from aegis.core.models import ConnectionModel
        mock_conn = MagicMock(spec=ConnectionModel)
        mock_conn.id = 1
        mock_conn.name = "test"
        mock_conn.connection_uri = "postgresql://x"
        mock_conn.dialect = "postgresql"
        mock_db.execute.return_value.scalars.return_value.all.return_value = [mock_conn]

        mock_inv = MockInvestigator.return_value
        mock_inv.rediscover.return_value = []

        _run_rediscovery()

        mock_inv.rediscover.assert_called_once()
```

**Step 2: Run tests to verify they fail**

Run: `cd aegis/backend && python -m pytest tests/test_scanner_rediscovery.py -v`
Expected: FAIL — `_run_rediscovery` not defined.

**Step 3: Add rediscovery to the scanner**

In `aegis/backend/aegis/services/scanner.py`, add the import at the top (after existing imports):

```python
from aegis.agents.investigator import Investigator
```

Add to the `_scan_loop` function, after the lineage refresh block (before `await asyncio.sleep(interval)`):

```python
        # Rediscovery on its own cadence
        if now - last_rediscovery >= settings.rediscovery_interval_seconds:
            try:
                await asyncio.to_thread(_run_rediscovery)
                last_rediscovery = now
            except Exception:
                logger.exception("Rediscovery failed")
```

Also add `last_rediscovery = 0.0` after `last_lineage_refresh = 0.0` at the top of `_scan_loop`.

Add the `_run_rediscovery` function at the bottom of the file, before `run_manual_scan`:

```python
def _run_rediscovery():
    """Detect new/dropped tables across all active connections."""
    with SyncSessionLocal() as db:
        connections = db.execute(
            select(ConnectionModel).where(ConnectionModel.is_active.is_(True))
        ).scalars().all()

        investigator = Investigator()
        total_deltas = 0

        for conn_model in connections:
            try:
                connector = WarehouseConnector(conn_model.connection_uri, conn_model.dialect)
                deltas = investigator.rediscover(connector, db, conn_model.id)
                total_deltas += len(deltas)
                connector.dispose()

                if deltas:
                    logger.info(
                        "Rediscovery found %d changes for %s",
                        len(deltas),
                        conn_model.name,
                    )
            except Exception:
                logger.exception("Rediscovery failed for %s", conn_model.name)

        from aegis.services.notifier import notifier

        notifier.broadcast("discovery.update", {"total_deltas": total_deltas})
        logger.info("Rediscovery complete: %d total deltas", total_deltas)
```

**Step 4: Run tests to verify they pass**

Run: `cd aegis/backend && python -m pytest tests/test_scanner_rediscovery.py -v`
Expected: All PASS.

**Step 5: Run the full test suite to ensure nothing is broken**

Run: `cd aegis/backend && python -m pytest tests/ -v`
Expected: All existing tests still pass.

**Step 6: Commit**

```bash
git add aegis/backend/aegis/services/scanner.py aegis/backend/tests/test_scanner_rediscovery.py
git commit -m "feat(investigator): integrate daily rediscovery into scanner loop"
```

---

### Task 10: Final Integration Test

**Files:**
- Test: `aegis/backend/tests/test_investigator_integration.py`

**Step 1: Write an integration test for the full discover → confirm flow**

Create `aegis/backend/tests/test_investigator_integration.py`:

```python
"""Integration test: discover → confirm → sentinels can see tables."""

import json
from unittest.mock import MagicMock, patch

import pytest

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
```

**Step 2: Run the integration test**

Run: `cd aegis/backend && python -m pytest tests/test_investigator_integration.py -v`
Expected: All PASS.

**Step 3: Run the complete test suite**

Run: `cd aegis/backend && python -m pytest tests/ -v --tb=short`
Expected: All tests PASS.

**Step 4: Commit**

```bash
git add aegis/backend/tests/test_investigator_integration.py
git commit -m "test(investigator): add integration test for discover-confirm flow"
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 1 | Dependencies + config | `pyproject.toml`, `config.py` |
| 2 | Connector methods | `connectors.py`, `test_connectors.py` |
| 3 | Pydantic schemas | `models.py`, `test_models_discovery.py` |
| 4 | LangChain LLM service | `langchain_llm.py`, `test_langchain_llm.py` |
| 5 | LangChain tools | `investigator_tools.py`, `test_investigator_tools.py` |
| 6 | Prompt templates | `investigator_prompts.py`, `test_investigator_prompts.py` |
| 7 | Investigator agent | `investigator.py`, `test_investigator.py` |
| 8 | Discovery API | `discovery.py`, `router.py`, `test_discovery_api.py` |
| 9 | Scanner integration | `scanner.py`, `test_scanner_rediscovery.py` |
| 10 | Integration test | `test_investigator_integration.py` |

**Total: 10 tasks, ~10 commits, TDD throughout.**
