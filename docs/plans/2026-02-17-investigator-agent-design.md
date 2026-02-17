# Investigator Agent — Design Specification

**Date:** 2026-02-17
**Status:** Approved
**Scope:** New LangChain-powered agent for automated warehouse discovery and table enrollment

---

## Problem

Today, users must manually register every table they want to monitor via `POST /tables`. For warehouses with hundreds of tables, this is tedious and error-prone. Users don't know which tables matter, what checks apply, or what freshness SLAs are reasonable.

## Solution

An **Investigator agent** built on **LangChain** that autonomously crawls a connected warehouse using tool calling, classifies tables via LLM-powered analysis, and proposes a monitoring configuration. The user reviews and confirms. Sentinels then take over unchanged.

## Architecture

```
USER CONNECTS WAREHOUSE
         |
         v
    Investigator.discover()           <-- NEW: LangChain agent with tool calling
         |                                 LLM drives the investigation,
         |                                 calling warehouse tools as needed
         v
    DiscoveryReport returned          <-- User sees proposals on dashboard
         |
         v
    User confirms selections          <-- POST /connections/:id/discover/confirm
         |
         v
    MonitoredTableModel rows created  <-- Same rows the Sentinel already reads
         |
         v
    EXISTING PIPELINE (UNCHANGED)
    Scanner -> SchemaSentinel -> FreshnessSentinel -> Orchestrator -> Architect -> Executor
```

The Investigator is a **setup agent**. It populates `monitored_tables` rows. Once enrolled, Sentinels take over. The Investigator never modifies Sentinel behavior.

## Trigger Points

| Trigger | Method | Description |
|---------|--------|-------------|
| Automatic | On `POST /connections` | Auto-triggers `discover()`, returns report |
| Manual | Dashboard "Discover Tables" button | User triggers `POST /connections/:id/discover` at any time |
| Periodic | Scanner loop (daily cadence) | `rediscover()` detects new/dropped tables, broadcasts WebSocket event |

## LangChain Integration

### Dependencies

Added to `pyproject.toml`:
- `langchain-core` — prompt templates, tool definitions, output parsers
- `langchain-openai` — ChatOpenAI model wrapper

**Scope:** LangChain is used for the Investigator and future new agents only. The existing Architect agent keeps using the raw OpenAI SDK via `services/llm.py`.

### LLM Service

**File:** `aegis/backend/aegis/services/langchain_llm.py`

Separate from the existing `llm.py`. Provides a factory for `ChatOpenAI`:

```python
from langchain_openai import ChatOpenAI
from aegis.config import settings

def get_chat_model(temperature: float = 0.0) -> ChatOpenAI:
    return ChatOpenAI(
        model="gpt-4",
        temperature=temperature,
        api_key=settings.openai_api_key,
        model_kwargs={"response_format": {"type": "json_object"}},
    )
```

### LangChain Tools

The LLM drives the investigation by calling warehouse tools on-demand. This is more efficient than dumping all metadata upfront — the LLM can skip obvious system tables and focus on interesting ones.

**File:** `aegis/backend/aegis/agents/investigator_tools.py`

Tools are created per-invocation via a closure that binds the current `connector`, `db`, and `lineage_graph`:

```python
def make_tools(connector, db, lineage_graph=None) -> list:

    @tool
    def list_warehouse_schemas() -> list[str]:
        """List all user-accessible schemas in the warehouse.
        Excludes system schemas (information_schema, pg_catalog, etc.)."""

    @tool
    def list_schema_tables(schema_name: str) -> list[dict]:
        """List all tables/views in a schema.
        Returns: [{name, type (TABLE/VIEW), schema}]"""

    @tool
    def inspect_table_columns(schema_name: str, table_name: str) -> list[dict]:
        """Get detailed column metadata for a specific table.
        Returns: [{name, type, nullable, ordinal}]"""

    @tool
    def check_table_freshness(schema_name: str, table_name: str) -> dict:
        """Check if a table has timestamp columns and when it was last updated.
        Returns: {has_timestamp, last_update, timestamp_column}"""

    @tool
    def get_known_lineage(table_name: str) -> dict:
        """Get known upstream/downstream dependencies from the lineage graph.
        Returns: {upstream: [str], downstream: [str]}"""

    return [list_warehouse_schemas, list_schema_tables,
            inspect_table_columns, check_table_freshness,
            get_known_lineage]
```

### Tool Calling Flow

```
LLM                              Tools                        Warehouse
 |                                 |                              |
 |  "List schemas first"           |                              |
 |---> list_warehouse_schemas() -->|-- INFORMATION_SCHEMA ------->|
 |<--- ["public", "staging",      |<-- SCHEMATA query -----------|
 |      "analytics"]               |                              |
 |                                 |                              |
 |  "Check public schema"          |                              |
 |---> list_schema_tables          |                              |
 |     ("public") --------------->|-- INFORMATION_SCHEMA ------->|
 |<--- [{users, TABLE}, ...]      |<-- TABLES query ------------|
 |                                 |                              |
 |  "users looks important"        |                              |
 |---> inspect_table_columns       |                              |
 |     ("public", "users") ------>|-- INFORMATION_SCHEMA ------->|
 |<--- [{id, INT, NOT NULL}, ...] |<-- COLUMNS query ------------|
 |                                 |                              |
 |  "_tmp_dedup is obviously       |                              |
 |   temp — skip inspection"       |                              |
 |                                 |                              |
 |  ... continues selectively ...  |                              |
 |                                 |                              |
 |  "Final classification:"        |                              |
 |  {"proposals": [...],           |                              |
 |   "concerns": [...]}            |                              |
```

The LLM decides which tables to inspect deeply vs. skip based on naming patterns. For a 200-table warehouse, it might only call `inspect_table_columns` on ~50 important tables.

### Prompt Template

**File:** `aegis/backend/aegis/agents/investigator_prompts.py`

**System prompt** instructs the LLM to:
1. Use tools to explore the warehouse (list schemas → list tables → inspect interesting ones)
2. Classify each table into roles (fact/dimension/staging/raw/snapshot/system/unknown)
3. Recommend monitoring checks per table
4. Suggest freshness SLAs with reasoning
5. Flag tables to skip (system, temp, test)
6. Report data quality concerns
7. Return structured JSON matching DiscoveryReport schema

**Classification rules embedded in system prompt:**

| Role | Pattern | Checks | SLA |
|------|---------|--------|-----|
| fact | Event/transaction tables with timestamps | schema + freshness | 360 min |
| dimension | Reference/lookup tables | schema + freshness | 360 min |
| staging | `stg_*`, `staging.*` | schema only | 60 min |
| raw | `raw_*`, `raw.*` | schema only | 1440 min |
| snapshot | `*_snapshot`, `*_hist` | schema only | None |
| system | Internal/metadata | skip=true | None |

**Human prompt template:**
```
Investigate the warehouse connected as "{connection_name}"
(dialect: {dialect}, connection_id: {connection_id}).
Discover all schemas and tables, classify each one, and return
your monitoring recommendations as JSON.
```

## Connector Extensions

Two new methods on `WarehouseConnector`:

### `list_schemas() -> list[str]`
- Queries `INFORMATION_SCHEMA.SCHEMATA`
- Filters system schemas: `information_schema`, `pg_catalog`, `pg_toast`, `snowflake.*`, `INFORMATION_SCHEMA`

### `list_tables(schema_name: str) -> list[dict]`
- Queries `INFORMATION_SCHEMA.TABLES`
- Returns: `[{name, type (TABLE/VIEW), schema}]`

These are thin query wrappers. The existing `fetch_schema()` handles column-level detail.

## Investigator Agent

**File:** `aegis/backend/aegis/agents/investigator.py`

### `discover(connector, db, connection_model) -> DiscoveryReport`

Creates a LangChain `AgentExecutor` with tool calling:

1. Build tools via `make_tools(connector, db, lineage_graph)` — binds current connector
2. Create `ChatOpenAI` via `get_chat_model()`
3. Build agent via `create_tool_calling_agent(llm, tools, prompt)`
4. Run `AgentExecutor.invoke()` with `max_iterations=25`
5. Parse the final JSON output into `DiscoveryReport`
6. If LangChain agent fails (any exception), fall back to deterministic heuristics

### `rediscover(connector, db, connection_id) -> list[TableDelta]`

Lightweight diff operation (**no LLM**, no LangChain):

1. List current warehouse tables via `list_schemas()` + `list_tables()`
2. Query `MonitoredTableModel` for this connection
3. Return deltas: new tables (in warehouse but not monitored) and dropped tables (monitored but gone)

### `_deterministic_fallback(connector, db, connection_model) -> DiscoveryReport`

Rule-based classification when LangChain agent fails:

| Pattern | Role | Checks | SLA |
|---------|------|--------|-----|
| `stg_*`, `staging.*` | staging | schema only | 60 min |
| `raw_*`, `raw.*` | raw | schema only | 1440 min |
| `dim_*` | dimension | schema + freshness | 360 min |
| `fct_*` | fact | schema + freshness | 360 min |
| `*_snapshot` | snapshot | schema only | None |
| has `updated_at` column | (any) | schema + freshness | (inferred) |
| default | unknown | schema + freshness | None (user sets) |

## Data Model

New Pydantic schemas only (no new database tables). Discovery reports are transient.

```python
class TableProposal(BaseModel):
    schema_name: str
    table_name: str
    fully_qualified_name: str
    role: str                          # fact/dimension/staging/raw/snapshot/system/unknown
    columns: list[dict]                # column metadata
    recommended_checks: list[str]      # ["schema", "freshness"] or ["schema"]
    suggested_sla_minutes: int | None
    reasoning: str                     # LLM's explanation
    skip: bool                         # True if not worth monitoring

class TableDelta(BaseModel):
    action: str                        # "new" or "dropped"
    schema_name: str
    table_name: str
    fully_qualified_name: str
    proposal: TableProposal | None     # Only for "new" tables

class DiscoveryReport(BaseModel):
    connection_id: int
    connection_name: str
    schemas_found: list[str]
    total_tables: int
    proposals: list[TableProposal]
    concerns: list[str]                # LLM-flagged quality concerns
    generated_at: datetime

class DiscoveryConfirm(BaseModel):
    table_selections: list[TableSelectionItem]

class TableSelectionItem(BaseModel):
    schema_name: str
    table_name: str
    check_types: list[str] = ["schema", "freshness"]
    freshness_sla_minutes: int | None = None
```

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/connections/:id/discover` | POST | Trigger full discovery, returns `DiscoveryReport` |
| `/api/v1/connections/:id/discover/confirm` | POST | Accept `DiscoveryConfirm`, creates `MonitoredTableModel` rows |
| `/api/v1/connections/:id/deltas` | GET | Get pending new/dropped table alerts from last rediscovery |

## Scanner Integration

In `services/scanner.py`, add a daily cadence for rediscovery (similar to lineage refresh):

```python
# In _scan_loop():
if now - last_rediscovery >= rediscovery_interval:  # default: 86400 (24h)
    await asyncio.to_thread(_run_rediscovery)
    last_rediscovery = now
```

`_run_rediscovery()` iterates connections, calls `investigator.rediscover()`, stores deltas, and broadcasts `discovery.update` via WebSocket.

## Frontend Components

- **"Discover Tables" button** on connection detail page
- **Discovery proposal view:** table list with role badges, recommended checks, SLA suggestions, LLM reasoning per table
- **Checkbox selection** + "Enroll Selected" confirmation button
- **Notification badge** when periodic rediscovery finds new/dropped tables

## Design Decisions

1. **LangChain with tool calling** — the LLM drives the investigation by calling warehouse tools on-demand, rather than receiving a massive prompt dump. More efficient for large warehouses.
2. **Closure-bound tools** — tools are created per-invocation with the current connector/db bound, solving LangChain's stateless tool limitation.
3. **LangChain for new agents only** — existing Architect keeps raw OpenAI SDK. No migration risk. Future agents use LangChain.
4. **Deterministic fallback** — same dual-path pattern as the Architect. System works without OpenAI.
5. **Structure-only discovery** — no row counts, distributions, or profiling. Keeps warehouse load minimal.
6. **Propose-and-confirm** — Investigator never auto-enrolls. User reviews and selects.
7. **Transient reports** — not persisted to DB. Returned via API and consumed by the frontend.
8. **Investigator feeds Sentinels** — creates the same `MonitoredTableModel` rows. Pipeline unchanged.
9. **max_iterations=25** — sufficient for ~200 tables (list schemas + list tables per schema + selective column inspection).

## Files Changed

| File | Change |
|------|--------|
| `aegis/backend/aegis/agents/investigator.py` | **NEW** — LangChain agent with tool calling |
| `aegis/backend/aegis/agents/investigator_tools.py` | **NEW** — LangChain tool definitions (closure factory) |
| `aegis/backend/aegis/agents/investigator_prompts.py` | **NEW** — System/human prompt templates |
| `aegis/backend/aegis/services/langchain_llm.py` | **NEW** — ChatOpenAI factory for LangChain agents |
| `aegis/backend/aegis/core/connectors.py` | Add `list_schemas()`, `list_tables()` |
| `aegis/backend/aegis/core/models.py` | Add Pydantic schemas (TableProposal, DiscoveryReport, etc.) |
| `aegis/backend/aegis/api/discovery.py` | **NEW** — Discovery API endpoints |
| `aegis/backend/aegis/api/router.py` | Register discovery router |
| `aegis/backend/aegis/services/scanner.py` | Add daily rediscovery cadence |
| `aegis/backend/aegis/config.py` | Add `AEGIS_REDISCOVERY_INTERVAL_SECONDS` setting |
| `aegis/backend/pyproject.toml` | Add `langchain-core`, `langchain-openai` dependencies |
