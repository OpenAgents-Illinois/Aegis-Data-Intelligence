# Aegis Data Intelligence Platform — Design Specification

**Version:** 1.0
**Date:** February 15, 2026
**Status:** Approved for Implementation

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Product Vision](#3-product-vision)
4. [Architecture Overview](#4-architecture-overview)
5. [Agent System](#5-agent-system)
6. [Data Model](#6-data-model)
7. [Lineage Engine](#7-lineage-engine)
8. [API Design](#8-api-design)
9. [Dashboard](#9-dashboard)
10. [Project Structure](#10-project-structure)
11. [Deployment](#11-deployment)
12. [Error Handling](#12-error-handling)
13. [Testing Strategy](#13-testing-strategy)
14. [Technology Stack](#14-technology-stack)
15. [Future Roadmap](#15-future-roadmap)

---

## 1. Executive Summary

Aegis is a next-generation "self-healing" data intelligence platform that replaces manual, reactive data monitoring with autonomous AI agents. Unlike traditional tools that rely on static SQL rules and human intervention, Aegis uses a multi-agent architecture to manage the entire data quality lifecycle — from anomaly detection through root-cause analysis to remediation recommendations.

The platform consists of three agent types:

- **Sentinels** — real-time anomaly detection (schema drift, freshness violations)
- **Architects** — LLM-powered root-cause reasoning with lineage-aware blast radius analysis
- **Executors** — automated remediation recommendation and incident management

By perceiving environmental shifts, reasoning through complex lineage dependencies, and generating actionable remediation plans, Aegis ensures that downstream AI models and business dashboards remain powered by trustworthy data — reducing data downtime and operational "firefighting" by up to 80%.

---

## 2. Problem Statement

Modern data teams face a growing reliability crisis:

- **Schema drift** — upstream changes silently break downstream consumers. An engineer renames a column in a staging table; three dashboards go blank, and nobody notices until a VP asks why the numbers are wrong.
- **Stale data** — ETL pipelines fail silently. Tables that should refresh hourly haven't been updated in 12 hours. Business decisions are made on yesterday's numbers.
- **Blast radius blindness** — when something breaks, teams spend hours tracing which downstream tables, dashboards, and ML models are affected because lineage is undocumented.
- **Alert fatigue** — existing tools generate too many false positives with static thresholds. Teams ignore alerts, and real incidents slip through.
- **Manual firefighting** — even after detection, root-cause analysis is manual. Engineers query `INFORMATION_SCHEMA`, diff schemas by hand, and trace dependencies through tribal knowledge.

**The cost:** Data teams spend 30-40% of their time on reactive firefighting instead of building new data products. Each hour of undetected data downtime can cost organizations $100K+ in bad decisions.

---

## 3. Product Vision

### MVP Scope

The MVP delivers a **detect + recommend** system:

| Capability | MVP | Post-MVP |
|-----------|-----|----------|
| Schema drift detection | Yes | - |
| Freshness monitoring | Yes | - |
| Volume anomaly detection | - | Yes |
| Distribution drift (statistical) | - | Yes |
| Custom rule engine | - | Yes |
| LLM root-cause analysis | Yes | - |
| Automatic lineage discovery | Yes | - |
| Blast radius visualization | Yes | - |
| Remediation recommendations | Yes | - |
| Auto-remediation (circuit breakers) | - | Yes |
| Full interactive dashboard | Yes | - |
| Real-time WebSocket updates | Yes | - |
| Multi-warehouse support | Yes (via SQL abstraction) | - |
| Multi-tenancy | - | Yes |
| Slack/PagerDuty integrations | - | Yes |
| API key auth | Yes | OAuth/SSO |

### Design Principles

1. **Warehouse-agnostic** — connect to Snowflake, BigQuery, PostgreSQL, Databricks, or any SQLAlchemy-compatible database
2. **Automatic discovery** — lineage is inferred from query logs, not manually defined
3. **Human-in-the-loop** — agents detect and recommend, humans approve and execute
4. **Graceful degradation** — if the LLM is unavailable, fall back to rule-based diagnosis
5. **Observable agents** — every agent decision is logged, auditable, and explainable

---

## 4. Architecture Overview

### Approach: Monolith-First

Aegis uses a monolith-first architecture. All agents run within a single Python process (FastAPI), with the React dashboard as a separate container. This provides:

- Simplest possible deployment (2 Docker containers)
- Shared memory for agent state (no serialization overhead)
- Easy debugging (single process, single log stream)
- Clean agent boundaries (Python classes) that can be extracted to microservices later

```
┌─────────────────────────────────────────────────────────────┐
│                    AEGIS BACKEND (FastAPI)                   │
│                                                             │
│  ┌──────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │ Scheduler │────►│  Sentinels   │────►│ Orchestrator │    │
│  └──────────┘     └──────────────┘     └──────┬───────┘    │
│                                               │             │
│                          ┌────────────────────┤             │
│                          ▼                    ▼             │
│                   ┌──────────────┐     ┌──────────────┐    │
│                   │  Architect   │     │  Executor    │    │
│                   │  (OpenAI)    │     │  (recommend) │    │
│                   └──────────────┘     └──────────────┘    │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  REST API    │  │  WebSocket   │  │  SQLite DB   │     │
│  │  (FastAPI)   │  │  (live feed) │  │  (persisted) │     │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘     │
└─────────┼─────────────────┼────────────────────────────────┘
          │                 │
          ▼                 ▼
   ┌─────────────────────────────┐
   │     REACT DASHBOARD         │
   │  (Vite + TypeScript)        │
   └─────────────────────────────┘
```

### Key decisions:

- **Why not microservices?** For an MVP with SQLite and Docker Compose, distributed systems complexity adds no value. Agent boundaries are logical (classes), not physical (network calls).
- **Why not event-driven?** The orchestrator pattern gives us clear, debuggable control flow. Event-driven adds Redis as a dependency and makes tracing harder.
- **Why SQLite?** Zero-config, embedded, no additional container. The data access layer uses SQLAlchemy, so migration to PostgreSQL is a configuration change, not a rewrite.

---

## 5. Agent System

### 5.1 Sentinels (Detection Layer)

Sentinels are deterministic detectors — they do **not** use the LLM. They run on a schedule (configurable, default: every 5 minutes) and monitor warehouse tables for anomalies.

#### Schema Sentinel

**Purpose:** Detect schema drift — column additions, deletions, type changes, and renaming.

**How it works:**

1. Queries `INFORMATION_SCHEMA.COLUMNS` for each monitored table
2. Serializes the column list as JSON and hashes it (SHA-256)
3. Compares hash against the last stored snapshot
4. If hash differs, diffs the two JSON column lists to identify exact changes
5. Emits an `Anomaly` object with the specific changes

```python
class SchemaSentinel:
    def inspect(self, table: MonitoredTable) -> Anomaly | None:
        current_columns = self.fetch_schema(table)
        current_hash = sha256(serialize(current_columns))

        last_snapshot = self.get_latest_snapshot(table.id)
        if last_snapshot and last_snapshot.hash == current_hash:
            return None  # No drift

        # Store new snapshot
        self.save_snapshot(table.id, current_columns, current_hash)

        if last_snapshot is None:
            return None  # First snapshot, no baseline to compare

        # Compute diff
        changes = self.diff_schemas(last_snapshot.columns, current_columns)
        return Anomaly(
            table_id=table.id,
            type="schema_drift",
            severity=self.classify_severity(changes),
            detail=changes
        )
```

**Severity classification:**

| Change | Severity |
|--------|----------|
| Column deleted | Critical |
| Column type changed | Critical |
| Column added (nullable) | Low |
| Column added (non-nullable) | Medium |
| Column renamed (inferred) | High |

#### Freshness Sentinel

**Purpose:** Detect when tables are not updated within their expected SLA.

**How it works:**

1. For each monitored table with a `freshness_sla_minutes` configured:
2. Queries `MAX(updated_at)` or `MAX(_loaded_at)` or falls back to row count comparison
3. Calculates time since last update
4. If time exceeds SLA, emits a freshness violation

```python
class FreshnessSentinel:
    def inspect(self, table: MonitoredTable) -> Anomaly | None:
        if not table.freshness_sla_minutes:
            return None

        last_update = self.get_last_update_time(table)
        minutes_since = (now() - last_update).total_minutes()

        if minutes_since <= table.freshness_sla_minutes:
            return None

        return Anomaly(
            table_id=table.id,
            type="freshness_violation",
            severity=self.classify_severity(minutes_since, table.freshness_sla_minutes),
            detail={
                "last_update": last_update.isoformat(),
                "sla_minutes": table.freshness_sla_minutes,
                "minutes_overdue": minutes_since - table.freshness_sla_minutes
            }
        )
```

**Severity classification:**

| Overdue | Severity |
|---------|----------|
| < 2x SLA | Medium |
| 2-5x SLA | High |
| > 5x SLA | Critical |

### 5.2 Orchestrator (Coordination Layer)

The Orchestrator is a **state machine** — not an LLM agent. It manages the incident lifecycle: receiving anomalies from Sentinels, dispatching work to Architects and Executors, and handling deduplication.

```python
class Orchestrator:
    def handle_anomaly(self, anomaly: Anomaly) -> Incident:
        # 1. Deduplication — is there an open incident for the same table + type?
        existing = self.find_open_incident(anomaly.table_id, anomaly.type)
        if existing:
            return self.merge_anomaly(existing, anomaly)

        # 2. Create incident
        incident = Incident(
            anomaly_id=anomaly.id,
            status="investigating"
        )
        self.db.save(incident)

        # 3. Dispatch to Architect for root-cause analysis
        diagnosis = self.architect.analyze(anomaly)
        incident.diagnosis = diagnosis
        incident.blast_radius = diagnosis.blast_radius

        # 4. Dispatch to Executor for remediation recommendation
        remediation = self.executor.prepare(anomaly, diagnosis)
        incident.remediation = remediation
        incident.status = "pending_review"

        self.db.save(incident)

        # 5. Notify dashboard via WebSocket
        self.notifier.broadcast("incident.created", incident)

        return incident
```

**Deduplication rules:**

- Same table + same anomaly type + open status → merge into existing incident
- Same table + different anomaly type → create separate incident
- Same anomaly type + resolved status → create new incident (recurrence)

### 5.3 Architect (Reasoning Layer)

The Architect is the only agent that uses the **OpenAI API (GPT-4)**. It receives an anomaly and performs root-cause analysis using lineage context and historical data.

**Inputs provided to the LLM:**

1. The anomaly details (what changed, when, on which table)
2. The lineage graph (upstream and downstream tables, depth 3)
3. Recent anomaly history for the same table and its lineage neighbors
4. Table metadata (column schemas, freshness history, row counts)

**Structured output (enforced via function calling):**

```python
@dataclass
class Diagnosis:
    root_cause: str           # Human-readable explanation
    root_cause_table: str     # Which upstream table is the likely source
    blast_radius: list[str]   # All affected downstream tables
    severity: str             # "critical" | "high" | "medium" | "low"
    confidence: float         # 0.0 - 1.0
    recommendations: list[Recommendation]

@dataclass
class Recommendation:
    action: str               # "revert_schema" | "add_cast" | "notify_team" | "pause_pipeline"
    description: str          # Human-readable description
    sql: str | None           # Optional remediation SQL
    priority: int             # 1 = do first
```

**Prompt structure:**

```
SYSTEM: You are Aegis Architect, a data reliability agent. You analyze data
anomalies and perform root-cause analysis. You have access to the table's
lineage graph and historical anomaly data.

Always respond with structured JSON matching the Diagnosis schema.
Consider: What upstream change could have caused this? How far does the
impact reach downstream? What's the simplest fix?

USER:
## Anomaly
Type: schema_drift
Table: analytics.orders
Change: Column `price` type changed from FLOAT(64) to VARCHAR(255)
Detected: 2026-02-15T14:05:00Z

## Lineage (upstream → downstream)
raw_orders → staging_orders → analytics.orders → daily_revenue
                                               → customer_ltv
                                               → exec_dashboard

## Recent History
- No previous anomalies on analytics.orders (last 30 days)
- staging_orders had a schema change 2 hours ago (column `price` FLOAT → VARCHAR)

## Table Metadata
- analytics.orders: 14 columns, ~2.3M rows, refreshes hourly
- Last successful refresh: 2026-02-15T13:00:00Z
```

**Fallback behavior:** If OpenAI is unavailable (timeout, rate limit, error), the Architect falls back to a rule-based analysis:

```python
class RuleBasedFallback:
    def analyze(self, anomaly: Anomaly) -> Diagnosis:
        blast_radius = self.lineage.get_downstream(anomaly.table)
        return Diagnosis(
            root_cause="Automated analysis unavailable. Manual investigation required.",
            blast_radius=blast_radius,
            severity=anomaly.severity,  # Use Sentinel's severity
            confidence=0.0,
            recommendations=[
                Recommendation(action="investigate", description="Check upstream tables for recent changes")
            ]
        )
```

### 5.4 Executor (Action Layer)

In the MVP, the Executor does **not** auto-execute anything. It formats the Architect's diagnosis into actionable remediation plans for human review.

**Responsibilities:**

1. Generate specific remediation SQL based on the anomaly type and diagnosis
2. Create a formatted incident report
3. Push notifications (WebSocket to dashboard)
4. Track incident status through the approval workflow

```python
class Executor:
    def prepare(self, anomaly: Anomaly, diagnosis: Diagnosis) -> Remediation:
        actions = []

        for rec in diagnosis.recommendations:
            if rec.sql:
                actions.append(RemediationAction(
                    type=rec.action,
                    description=rec.description,
                    sql=rec.sql,
                    status="pending_approval"
                ))
            else:
                actions.append(RemediationAction(
                    type=rec.action,
                    description=rec.description,
                    status="manual"
                ))

        return Remediation(
            actions=actions,
            summary=self.format_summary(anomaly, diagnosis),
            generated_at=now()
        )
```

### 5.5 Full End-to-End Flow

Here is the complete lifecycle of a data incident:

```
T+0:00  Engineer pushes dbt model change
        → orders.price changes from FLOAT to VARCHAR

T+5:00  Scheduler triggers Sentinel scan cycle
        → Schema Sentinel queries INFORMATION_SCHEMA for all monitored tables
        → Detects: orders.price type changed FLOAT(64) → VARCHAR(255)
        → Emits: Anomaly(type="schema_drift", table="orders")

T+5:01  Orchestrator receives anomaly
        → Checks for duplicates: none found
        → Creates Incident(status="investigating")
        → Dispatches to Architect

T+5:02  Architect performs root-cause analysis
        → Loads lineage: raw_orders → orders → daily_revenue, customer_ltv, exec_dashboard
        → Loads history: staging_orders had same change 2 hours ago
        → Calls GPT-4 with full context
        → Returns: Diagnosis(
            root_cause="upstream ETL schema change in staging_orders",
            blast_radius=["daily_revenue", "customer_ltv", "exec_dashboard"],
            severity="critical",
            confidence=0.85,
            recommendations=[revert column type, add CAST in transform]
          )

T+5:03  Executor prepares remediation
        → Generates SQL: ALTER TABLE orders ALTER COLUMN price TYPE FLOAT USING price::FLOAT
        → Creates formatted incident report
        → Orchestrator updates incident status to "pending_review"

T+5:03  WebSocket push to dashboard
        → anomaly.detected event
        → incident.created event with full details
        → Dashboard shows red alert banner

T+??    Human reviews on dashboard
        → Sees incident with root cause, blast radius visualization, recommended SQL
        → Clicks "Approve" → incident marked resolved with audit trail
        → OR clicks "Dismiss" with reason → incident archived
```

---

## 6. Data Model

### Entity Relationship

```
connections 1──N monitored_tables 1──N schema_snapshots
                      │
                      1──N anomalies 1──1 incidents
                                          │
                                          └── diagnosis (JSON)
                                          └── remediation (JSON)

lineage_edges (standalone, references tables by fully-qualified name)
```

### Schema

```sql
-- Warehouse connections (warehouse-agnostic)
CREATE TABLE connections (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,        -- "prod-snowflake", "staging-bigquery"
    dialect         TEXT NOT NULL,               -- "snowflake", "bigquery", "postgresql", "databricks"
    connection_uri  TEXT NOT NULL,               -- SQLAlchemy connection string (encrypted at rest)
    is_active       BOOLEAN NOT NULL DEFAULT 1,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Tables being monitored by Aegis
CREATE TABLE monitored_tables (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    connection_id           INTEGER NOT NULL REFERENCES connections(id) ON DELETE CASCADE,
    schema_name             TEXT NOT NULL,
    table_name              TEXT NOT NULL,
    fully_qualified_name    TEXT NOT NULL,           -- "schema.table" for lineage lookups
    check_types             TEXT NOT NULL DEFAULT '["schema", "freshness"]',  -- JSON array
    freshness_sla_minutes   INTEGER,                 -- NULL = no freshness check
    created_at              TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(connection_id, schema_name, table_name)
);

-- Point-in-time schema snapshots for drift detection
CREATE TABLE schema_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id        INTEGER NOT NULL REFERENCES monitored_tables(id) ON DELETE CASCADE,
    columns         TEXT NOT NULL,       -- JSON: [{"name": "price", "type": "FLOAT", "nullable": true, "ordinal": 1}]
    snapshot_hash   TEXT NOT NULL,       -- SHA-256 of columns JSON for O(1) drift detection
    captured_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_snapshots_table_id ON schema_snapshots(table_id, captured_at DESC);

-- Detected anomalies (raw signals from Sentinels)
CREATE TABLE anomalies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id        INTEGER NOT NULL REFERENCES monitored_tables(id) ON DELETE CASCADE,
    type            TEXT NOT NULL,       -- "schema_drift" | "freshness_violation"
    severity        TEXT NOT NULL,       -- "critical" | "high" | "medium" | "low"
    detail          TEXT NOT NULL,       -- JSON: change-specific details
    detected_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_anomalies_table_type ON anomalies(table_id, type, detected_at DESC);

-- Full incidents with diagnosis + remediation
CREATE TABLE incidents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    anomaly_id      INTEGER NOT NULL REFERENCES anomalies(id),
    status          TEXT NOT NULL DEFAULT 'open',
                    -- "open" | "investigating" | "pending_review" | "resolved" | "dismissed"
    diagnosis       TEXT,               -- JSON: Architect's full analysis (Diagnosis schema)
    blast_radius    TEXT,               -- JSON: ["table1", "table2", ...] affected downstream
    remediation     TEXT,               -- JSON: Executor's recommended actions
    severity        TEXT NOT NULL,      -- Denormalized from diagnosis for filtering
    resolved_at     TIMESTAMP,
    resolved_by     TEXT,               -- Who approved/dismissed
    dismiss_reason  TEXT,               -- Required when status = "dismissed"
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_incidents_status ON incidents(status, severity, created_at DESC);

-- Lineage edges parsed from query logs
CREATE TABLE lineage_edges (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_table    TEXT NOT NULL,       -- Fully qualified: "schema.table"
    target_table    TEXT NOT NULL,       -- Fully qualified: "schema.table"
    relationship    TEXT NOT NULL DEFAULT 'direct',  -- "direct" | "derived" | "aggregated"
    query_hash      TEXT,               -- Hash of the SQL that established this edge
    confidence      REAL NOT NULL DEFAULT 1.0,       -- 0.0-1.0
    first_seen_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_table, target_table)
);
CREATE INDEX idx_lineage_source ON lineage_edges(source_table);
CREATE INDEX idx_lineage_target ON lineage_edges(target_table);
```

### Key Design Decisions

- **JSON columns** (`TEXT` in SQLite) for flexible semi-structured data — avoids schema explosion for varied anomaly types. These are accessed via Python, not queried with SQL.
- **`snapshot_hash`** enables O(1) drift detection — only parse and diff the JSON when the hash changes.
- **`lineage_edges`** are directional and timestamped. Edges not seen for 30 days are considered stale and excluded from blast radius calculations.
- **Denormalized `severity`** on incidents enables fast filtering without JSON parsing.
- **`fully_qualified_name`** on `monitored_tables` bridges the relational model to the lineage graph which uses string-based table references.

---

## 7. Lineage Engine

### Overview

The lineage engine is the core differentiator — automatic dependency discovery without users defining anything manually. It parses SQL query logs from the warehouse to build a directed acyclic graph (DAG) of table-to-table relationships.

### Architecture

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Warehouse       │     │   SQL Parser      │     │  Lineage DB      │
│  Query Logs      │────►│  (sqlglot)        │────►│  (lineage_edges) │
│                  │     │                   │     │                  │
│  Snowflake:      │     │  Extracts:        │     │  Serves:         │
│   QUERY_HISTORY  │     │  INSERT INTO t    │     │  get_upstream()  │
│  BigQuery:       │     │  SELECT FROM s    │     │  get_downstream()│
│   JOBS           │     │  → edge(s→t)      │     │  blast_radius()  │
│  PostgreSQL:     │     │                   │     │                  │
│   pg_stat_stmts  │     │                   │     │                  │
└──────────────────┘     └──────────────────┘     └──────────────────┘
```

### Query Log Extraction

Each warehouse exposes query history through different interfaces. Aegis abstracts this behind a `QueryLogExtractor` interface:

```python
class QueryLogExtractor(Protocol):
    def extract(self, since: datetime, limit: int = 10000) -> list[QueryLogEntry]:
        """Fetch recent query history from the warehouse."""
        ...

@dataclass
class QueryLogEntry:
    sql: str
    user: str
    executed_at: datetime
    duration_ms: int
    warehouse: str          # Connection name for attribution

# Dialect-specific implementations:
class SnowflakeExtractor(QueryLogExtractor):
    # Queries: SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
    # Filters: QUERY_TYPE IN ('INSERT', 'CREATE_TABLE_AS_SELECT', 'MERGE')

class BigQueryExtractor(QueryLogExtractor):
    # Queries: INFORMATION_SCHEMA.JOBS
    # Filters: statement_type IN ('INSERT', 'CREATE_TABLE_AS_SELECT', 'MERGE')

class PostgreSQLExtractor(QueryLogExtractor):
    # Queries: pg_stat_statements (requires extension)
    # Filters: query ILIKE 'INSERT%' OR query ILIKE 'CREATE%AS%SELECT%'

class DatabricksExtractor(QueryLogExtractor):
    # Uses: Databricks Query History API
    # Filters: statement_type in relevant categories
```

### SQL Parsing with sqlglot

[sqlglot](https://github.com/tobymao/sqlglot) is a Python SQL parser supporting all major dialects. For each query, we extract source and target tables:

```python
import sqlglot
from sqlglot import exp

def extract_lineage_edges(sql: str, dialect: str) -> list[LineageEdge]:
    edges = []
    try:
        parsed = sqlglot.parse(sql, dialect=dialect)
    except sqlglot.errors.ParseError:
        return []  # Unparseable query, skip

    for statement in parsed:
        target = None
        sources = set()

        # Extract target table
        if isinstance(statement, exp.Insert):
            target = statement.find(exp.Table).sql()
        elif isinstance(statement, exp.Create):
            target = statement.find(exp.Table).sql()
        elif isinstance(statement, exp.Merge):
            target = statement.find(exp.Table).sql()
        else:
            continue  # SELECT-only queries don't create lineage

        # Extract source tables (including subqueries and CTEs)
        for table in statement.find_all(exp.Table):
            table_name = table.sql()
            if table_name != target:
                sources.add(table_name)

        for source in sources:
            edges.append(LineageEdge(
                source=source,
                target=target,
                confidence=compute_confidence(statement, source)
            ))

    return edges
```

**Confidence scoring:**

| Pattern | Confidence |
|---------|-----------|
| Direct `INSERT INTO target SELECT FROM source` | 1.0 |
| `CREATE TABLE AS SELECT FROM source` | 1.0 |
| `MERGE INTO target USING source` | 1.0 |
| Source in subquery | 0.8 |
| Source in CTE | 0.8 |
| Source in deeply nested subquery (3+ levels) | 0.6 |

### Graph API

The lineage graph is served through a `LineageGraph` class that queries `lineage_edges` and traverses the DAG:

```python
class LineageGraph:
    def get_upstream(self, table: str, depth: int = 3) -> list[LineageNode]:
        """What feeds INTO this table? BFS up to `depth` hops."""

    def get_downstream(self, table: str, depth: int = 3) -> list[LineageNode]:
        """What does this table feed INTO? BFS up to `depth` hops."""

    def get_blast_radius(self, table: str) -> BlastRadius:
        """Full downstream impact assessment."""
        downstream = self.get_downstream(table, depth=10)
        return BlastRadius(
            affected_tables=downstream,
            total_count=len(downstream),
            max_depth=max(n.depth for n in downstream) if downstream else 0,
            has_dashboard_consumers=any(n.is_terminal for n in downstream)
        )

    def get_path(self, source: str, target: str) -> list[str] | None:
        """Shortest dependency path between two tables. Returns None if no path."""

    def get_full_graph(self) -> Graph:
        """Returns all nodes and edges for visualization."""
        # Used by the Lineage Explorer view in the dashboard
```

### Refresh Schedule

| Event | Action |
|-------|--------|
| First connection added | Full scan: last 30 days of query history |
| Hourly (cron) | Incremental scan: last 2 hours of queries (1-hour overlap for safety) |
| User triggers manual scan | Full rescan from UI |
| Edge not seen for 30 days | Marked as stale, excluded from blast radius calculations |

### Known Limitations (MVP)

- **Dynamic SQL** — queries built via string concatenation in application code won't be in warehouse query logs
- **External orchestrators** — Airflow DAGs, Fivetran syncs, and other tools that don't go through the warehouse's query interface
- **Views** — `CREATE VIEW` dependencies are captured, but views that reference other views may require multiple parsing passes
- **Cross-database lineage** — edges only exist within a single warehouse connection. Cross-warehouse lineage is not supported in MVP

---

## 8. API Design

### Base URL: `/api/v1`

All endpoints return JSON. Authentication via `X-API-Key` header.

### Connections

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/connections` | Create a warehouse connection |
| `GET` | `/connections` | List all connections |
| `GET` | `/connections/:id` | Get connection details |
| `PUT` | `/connections/:id` | Update connection |
| `DELETE` | `/connections/:id` | Remove connection |
| `POST` | `/connections/:id/test` | Test connectivity (runs `SELECT 1`) |

**Create connection request:**
```json
{
  "name": "prod-snowflake",
  "dialect": "snowflake",
  "connection_uri": "snowflake://user:pass@account/db/schema"
}
```

### Monitored Tables

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/tables` | Add table to monitoring |
| `GET` | `/tables` | List monitored tables |
| `GET` | `/tables/:id` | Get table details + health |
| `PUT` | `/tables/:id` | Update check config / SLA |
| `DELETE` | `/tables/:id` | Stop monitoring |
| `GET` | `/tables/:id/snapshots` | Schema snapshot history |

**Query parameters for `GET /tables`:**
- `?connection_id=1` — filter by connection
- `?status=healthy|warning|critical` — filter by current health
- `?page=1&per_page=50` — pagination

### Incidents

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/incidents` | List incidents |
| `GET` | `/incidents/:id` | Full incident detail |
| `POST` | `/incidents/:id/approve` | Mark as resolved |
| `POST` | `/incidents/:id/dismiss` | Dismiss incident |

**Query parameters for `GET /incidents`:**
- `?status=open|investigating|pending_review|resolved|dismissed`
- `?severity=critical|high|medium|low`
- `?table_id=5`
- `?since=2026-02-01T00:00:00Z`
- `?page=1&per_page=50`

**Approve request:**
```json
{
  "note": "Applied the recommended ALTER TABLE fix"
}
```

**Dismiss request:**
```json
{
  "reason": "Expected change — new column added for feature X"
}
```

### Lineage

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/lineage/graph` | Full lineage graph (nodes + edges) |
| `GET` | `/lineage/:table/upstream` | Upstream dependencies |
| `GET` | `/lineage/:table/downstream` | Downstream consumers |
| `GET` | `/lineage/:table/blast-radius` | Blast radius summary |

**Query parameters:**
- `?depth=3` — traversal depth (default: 3, max: 10)
- `?min_confidence=0.5` — exclude low-confidence edges

**Blast radius response:**
```json
{
  "table": "analytics.orders",
  "affected_tables": [
    {"name": "analytics.daily_revenue", "depth": 1, "confidence": 1.0},
    {"name": "analytics.customer_ltv", "depth": 1, "confidence": 1.0},
    {"name": "reporting.exec_dashboard", "depth": 1, "confidence": 0.8}
  ],
  "total_affected": 3,
  "max_depth": 1
}
```

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Service health check |
| `GET` | `/status` | Agent status |
| `GET` | `/stats` | Dashboard aggregate stats |
| `POST` | `/scan/trigger` | Manually trigger scan cycle |

**Stats response:**
```json
{
  "health_score": 94.0,
  "total_tables": 42,
  "healthy_tables": 39,
  "open_incidents": 3,
  "critical_incidents": 1,
  "anomalies_24h": 5,
  "avg_resolution_time_minutes": 34.5
}
```

### WebSocket

| Endpoint | Description |
|----------|-------------|
| `WS /ws` | Real-time event stream |

**Events:**
```json
{"event": "anomaly.detected", "data": {"anomaly_id": 15, "table": "orders", "type": "schema_drift"}}
{"event": "incident.created", "data": {"incident_id": 42, "severity": "critical"}}
{"event": "incident.updated", "data": {"incident_id": 42, "status": "resolved"}}
{"event": "scan.completed", "data": {"tables_scanned": 42, "anomalies_found": 1, "duration_ms": 3400}}
```

### Authentication (MVP)

- Single API key stored in `.env` as `AEGIS_API_KEY`
- Validated via `X-API-Key` header on all endpoints
- React dashboard stores key in `localStorage`
- No multi-tenancy, no RBAC for MVP

---

## 9. Dashboard

### Technology

| Concern | Library |
|---------|---------|
| Framework | React 18 + TypeScript |
| Build tool | Vite |
| Routing | React Router v6 |
| State management | Zustand |
| Charts | Recharts |
| Graph visualization | React Flow |
| Styling | Tailwind CSS |
| WebSocket | Native WebSocket API + auto-reconnect wrapper |
| HTTP client | Axios |

### View 1: Overview Dashboard (Home)

The landing page showing at-a-glance health of the data ecosystem.

**Components:**

- **Health Score Card** — large percentage showing `healthy_tables / total_tables`. Color: green (>90%), yellow (70-90%), red (<70%)
- **Stat Cards** — open incidents, critical count, tables monitored
- **Incident Feed** — real-time scrolling list, newest first. Each entry shows: severity badge, anomaly type, table name, time ago. Clicking navigates to Incident Detail
- **Freshness Heatmap** — horizontal bars per table showing time-to-SLA. Green (on time) → yellow (approaching) → red (overdue). Uses Recharts BarChart
- **Timeline Sparkline** — anomaly count per hour over last 7 days. Helps identify patterns (e.g., anomalies spike every Monday at 3am after weekend ETL runs)

### View 2: Incident Detail

Full context for a single incident.

**Sections:**

1. **Header** — incident ID, severity badge, status, timestamps
2. **What Happened** — human-readable anomaly description. For schema drift: shows exact column changes in a diff format
3. **Root Cause Analysis** — Architect's diagnosis. Shows root cause explanation, confidence percentage, and the reasoning
4. **Blast Radius** — mini lineage graph (React Flow) showing the affected table highlighted in red and all downstream consumers. Shows depth and total affected count
5. **Recommended Actions** — list of remediation steps. SQL is shown in a syntax-highlighted code block with a "Copy" button
6. **Action Buttons** — "Approve" (marks resolved), "Dismiss" (requires reason input), "Copy SQL"

### View 3: Lineage Explorer

Interactive graph visualization of the full table dependency network.

**Features:**

- **Search bar** — type a table name, graph centers on it
- **Interactive DAG** — React Flow with zoom, pan, drag. Nodes represent tables, edges represent data flow
- **Node coloring** — red (active anomaly), green (healthy), gray (stale/unmonitored)
- **Click node** — side panel shows: table metadata, upstream/downstream counts, last schema change, freshness status, recent incidents
- **Highlight paths** — click two nodes to highlight the shortest dependency path between them

### View 4: Settings

Configuration management.

**Tabs:**

1. **Connections** — add/edit/remove warehouse connections. Test button validates connectivity. Shows connection status (active/error)
2. **Monitored Tables** — table listing all monitored tables. Inline edit for check types and SLA. Bulk import from warehouse schema browser
3. **Agent Activity** — log of recent Sentinel scans, Architect LLM calls (with token usage), and scan durations. Useful for debugging and cost monitoring
4. **API Key** — view/regenerate the API key

### Real-Time Updates

The dashboard maintains a persistent WebSocket connection to `/ws`. On connection:

1. Fetches current state via REST (incidents, tables, stats)
2. Subscribes to WebSocket for live updates
3. On disconnect: auto-reconnects with exponential backoff (1s, 2s, 4s, 8s, max 30s)
4. On reconnect: fetches events since last received timestamp to fill any gaps

State updates flow: `WebSocket event → Zustand store → React component re-render`

---

## 10. Project Structure

```
aegis/
├── docker-compose.yml              # 2 services: backend + frontend
├── .env.example                    # Template for configuration
├── README.md                       # Project overview + quickstart
├── Makefile                        # Common commands (dev, build, test, lint)
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml              # Dependencies + project metadata
│   ├── alembic.ini                 # Database migration config
│   ├── alembic/                    # Migration scripts
│   │   ├── env.py
│   │   └── versions/
│   │       └── 001_initial_schema.py
│   │
│   ├── aegis/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app, lifespan events, CORS, middleware
│   │   ├── config.py               # Pydantic Settings (from env vars)
│   │   │
│   │   ├── api/                    # Route handlers (thin layer)
│   │   │   ├── __init__.py
│   │   │   ├── router.py           # Aggregates all route modules
│   │   │   ├── connections.py      # CRUD for warehouse connections
│   │   │   ├── tables.py           # CRUD for monitored tables
│   │   │   ├── incidents.py        # Incident listing, approval, dismissal
│   │   │   ├── lineage.py          # Graph queries, blast radius
│   │   │   ├── system.py           # Health, status, stats, manual scan trigger
│   │   │   └── websocket.py        # WebSocket endpoint + connection manager
│   │   │
│   │   ├── agents/                 # The three agent types + orchestrator
│   │   │   ├── __init__.py
│   │   │   ├── orchestrator.py     # State machine: anomaly → incident lifecycle
│   │   │   ├── sentinel.py         # SchemaSentinel + FreshnessSentinel classes
│   │   │   ├── architect.py        # LLM-powered root cause analysis
│   │   │   └── executor.py         # Remediation recommendation formatter
│   │   │
│   │   ├── core/                   # Business logic (no framework dependencies)
│   │   │   ├── __init__.py
│   │   │   ├── models.py           # SQLAlchemy ORM models + Pydantic schemas
│   │   │   ├── database.py         # Engine, session factory, migration runner
│   │   │   ├── lineage.py          # Query log parser + LineageGraph
│   │   │   └── connectors.py       # Warehouse abstraction (SQLAlchemy dialects)
│   │   │
│   │   ├── services/               # Application services (glue layer)
│   │   │   ├── __init__.py
│   │   │   ├── scanner.py          # Scheduled scan loop (asyncio)
│   │   │   ├── notifier.py         # WebSocket event broadcaster
│   │   │   └── llm.py              # OpenAI client wrapper, retry logic, fallback
│   │   │
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── sql_parser.py       # sqlglot helpers for lineage extraction
│   │       └── crypto.py           # Connection string encryption/decryption
│   │
│   └── tests/
│       ├── conftest.py             # Shared fixtures (in-memory SQLite, mock OpenAI)
│       ├── test_sentinels.py       # Schema + freshness detection tests
│       ├── test_architect.py       # LLM prompt construction + response parsing
│       ├── test_orchestrator.py    # Incident lifecycle + deduplication
│       ├── test_lineage.py         # SQL parsing + graph traversal
│       ├── test_api.py             # FastAPI endpoint tests
│       └── fixtures/               # Sample data
│           ├── query_logs/         # Sample SQL queries per dialect
│           ├── schemas/            # Sample INFORMATION_SCHEMA results
│           └── openai_responses/   # Mock LLM responses
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── index.html
│   │
│   └── src/
│       ├── main.tsx                # React entry point
│       ├── App.tsx                 # Router + layout wrapper
│       │
│       ├── api/                    # HTTP + WebSocket clients
│       │   ├── client.ts           # Axios instance with auth header
│       │   ├── endpoints.ts        # Typed API functions
│       │   └── types.ts            # TypeScript interfaces matching API responses
│       │
│       ├── stores/                 # Zustand state management
│       │   ├── incidentStore.ts    # Incidents list + real-time updates
│       │   ├── lineageStore.ts     # Graph data for explorer
│       │   ├── tableStore.ts       # Monitored tables + health
│       │   └── systemStore.ts      # Stats, agent status
│       │
│       ├── hooks/
│       │   ├── useWebSocket.ts     # Auto-reconnecting WebSocket hook
│       │   └── useAutoRefresh.ts   # Polling fallback for non-WS data
│       │
│       ├── pages/
│       │   ├── Overview.tsx        # Home dashboard
│       │   ├── IncidentDetail.tsx  # Single incident view
│       │   ├── LineageExplorer.tsx  # Interactive graph
│       │   └── Settings.tsx        # Connections + tables + activity log
│       │
│       └── components/
│           ├── Layout.tsx          # Sidebar + header + footer shell
│           ├── IncidentFeed.tsx    # Real-time incident list
│           ├── FreshnessHeatmap.tsx # Table freshness bars
│           ├── TimelineChart.tsx   # Anomaly timeline sparkline
│           ├── LineageGraph.tsx    # React Flow graph component
│           ├── BlastRadiusGraph.tsx # Mini lineage for incident detail
│           ├── SeverityBadge.tsx   # Colored severity indicator
│           ├── SqlBlock.tsx        # Syntax-highlighted SQL with copy
│           └── ConnectionForm.tsx  # Add/edit warehouse connection
│
└── docs/
    ├── plans/
    │   └── 2026-02-15-aegis-design.md  # This document
    └── api/
        └── openapi.json            # Auto-generated from FastAPI
```

### Key Structural Decisions

- **Monorepo** — backend and frontend in one repo for atomic commits and easy Docker builds
- **`aegis/core/`** is framework-agnostic — no FastAPI imports, testable in isolation
- **`aegis/agents/`** contains the agent logic, depends on `core/` and `services/`
- **`aegis/api/`** is a thin layer that delegates to agents and services
- **`alembic/`** for database migrations — essential for SQLite → PostgreSQL migration path
- **`tests/fixtures/`** contains realistic sample data for deterministic testing

---

## 11. Deployment

### Docker Compose (MVP)

```yaml
version: "3.8"

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - aegis-data:/app/data        # SQLite file persisted here
    env_file: .env
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 5s
      retries: 3

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    depends_on:
      backend:
        condition: service_healthy
    environment:
      - VITE_API_URL=http://localhost:8000

volumes:
  aegis-data:
```

### Environment Variables

```bash
# Backend
AEGIS_API_KEY=your-api-key-here
OPENAI_API_KEY=sk-...
AEGIS_DB_PATH=/app/data/aegis.db
AEGIS_SCAN_INTERVAL_SECONDS=300       # 5 minutes
AEGIS_LINEAGE_REFRESH_SECONDS=3600    # 1 hour
AEGIS_LOG_LEVEL=INFO
AEGIS_ENCRYPTION_KEY=...              # For connection string encryption

# Frontend
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
```

### Startup Sequence

1. Backend container starts → runs Alembic migrations → starts FastAPI
2. FastAPI `lifespan` event starts the scanner (background asyncio task) and lineage refresh task
3. Frontend container starts → Vite serves the React app
4. User opens `http://localhost:3000` → dashboard loads → WebSocket connects

---

## 12. Error Handling

### By Component

| Component | Failure Mode | Response |
|-----------|-------------|----------|
| **Sentinel** | Warehouse connection fails | Log error, skip table, retry next cycle. Create `connection_error` incident if persists for 3 cycles |
| **Sentinel** | `INFORMATION_SCHEMA` query fails | Log error, skip table. May indicate insufficient permissions — surface in Settings > Activity Log |
| **Architect** | OpenAI API timeout (30s) | Retry with exponential backoff: 2s, 4s, 8s. Max 3 attempts |
| **Architect** | OpenAI rate limit (429) | Respect `Retry-After` header. Queue diagnosis for later |
| **Architect** | OpenAI returns invalid JSON | Retry once with stricter prompt. If still fails, use rule-based fallback |
| **Architect** | All retries exhausted | Fall back to `RuleBasedFallback`: provides blast radius (from lineage) without root-cause reasoning. Diagnosis marked `confidence: 0.0` |
| **Lineage** | SQL parsing fails (sqlglot error) | Log unparseable query, skip it, continue. Confidence scores naturally reflect coverage gaps |
| **Lineage** | Query log extraction fails | Log error, retry next cycle. Dashboard shows "Lineage may be stale" warning |
| **WebSocket** | Client disconnects | Server cleans up connection. Client auto-reconnects with backoff |
| **WebSocket** | Client reconnects after gap | Client fetches missed events via `GET /incidents?since=<last_event_time>` |
| **API** | Invalid request | 422 with Pydantic validation errors |
| **API** | Unauthenticated | 401 with message |
| **Database** | SQLite lock contention | Retry with WAL mode enabled (default). Extremely unlikely with single-process monolith |

### Graceful Degradation Priority

1. **Detection must always work** — Sentinels are deterministic, no LLM dependency
2. **Lineage can be stale** — blast radius uses last-known graph, warns if stale
3. **Diagnosis can be basic** — rule-based fallback always available
4. **Dashboard can recover** — auto-reconnect + REST backfill covers all gap scenarios

---

## 13. Testing Strategy

### Backend Tests

| Test Type | Scope | Tools |
|-----------|-------|-------|
| **Unit: Sentinels** | Schema diff logic, freshness calculation, severity classification | pytest, mock SQLAlchemy engine returning fixture data |
| **Unit: Architect** | Prompt construction, response parsing, fallback logic | pytest, mock OpenAI client returning fixture responses |
| **Unit: Orchestrator** | Incident lifecycle, deduplication, status transitions | pytest, in-memory SQLite |
| **Unit: Lineage** | SQL parsing → edge extraction for each dialect | pytest, sqlglot, fixture SQL files per dialect |
| **Unit: LineageGraph** | BFS traversal, blast radius, path finding | pytest, pre-built edge fixtures |
| **API: Endpoints** | Full request/response cycle | FastAPI `TestClient`, in-memory SQLite |
| **Integration** | Full anomaly → incident cycle | Docker Compose with local PostgreSQL as mock warehouse |

**Fixture strategy:**
- `tests/fixtures/schemas/` — sample `INFORMATION_SCHEMA` results (before/after for drift testing)
- `tests/fixtures/query_logs/` — real-world SQL per dialect for lineage parsing
- `tests/fixtures/openai_responses/` — recorded GPT-4 responses for deterministic testing

### Frontend Tests

| Test Type | Scope | Tools |
|-----------|-------|-------|
| **Component** | Individual components render correctly | Vitest, React Testing Library |
| **Integration** | Pages load data and handle interactions | Vitest, MSW (Mock Service Worker) |
| **WebSocket** | Real-time updates flow to UI | Vitest, mock WebSocket server |

### Test Commands

```bash
# Backend
cd backend && pytest                          # All tests
cd backend && pytest tests/test_sentinels.py  # Sentinel tests only
cd backend && pytest --cov=aegis              # With coverage

# Frontend
cd frontend && npm test                       # All tests
cd frontend && npm run test:coverage          # With coverage

# Integration (requires Docker)
docker compose -f docker-compose.test.yml up --abort-on-container-exit
```

---

## 14. Technology Stack

### Backend

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Language | Python | 3.11+ | Core platform language |
| Web framework | FastAPI | 0.100+ | REST API + WebSocket |
| ASGI server | Uvicorn | 0.24+ | Production server |
| ORM | SQLAlchemy | 2.0+ | Database abstraction (SQLite now, Postgres later) |
| Migrations | Alembic | 1.12+ | Schema versioning |
| Data validation | Pydantic | 2.0+ | Request/response schemas, settings |
| SQL parser | sqlglot | 20.0+ | Query log parsing for lineage |
| LLM client | openai | 1.0+ | GPT-4 for Architect agent |
| Scheduling | APScheduler | 3.10+ | Sentinel scan scheduling |
| Testing | pytest | 8.0+ | Test framework |
| Linting | ruff | 0.1+ | Fast Python linter + formatter |

### Frontend

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Language | TypeScript | 5.0+ | Type safety |
| Framework | React | 18+ | UI components |
| Build tool | Vite | 5.0+ | Fast dev server + production build |
| Routing | React Router | 6+ | Client-side navigation |
| State | Zustand | 4.0+ | Lightweight state management |
| Charts | Recharts | 2.0+ | Timeline, heatmap, stat cards |
| Graph viz | React Flow | 11+ | Lineage DAG visualization |
| Styling | Tailwind CSS | 3.0+ | Utility-first CSS |
| HTTP | Axios | 1.6+ | API client |
| Testing | Vitest | 1.0+ | Unit + component tests |
| Mock API | MSW | 2.0+ | Mock Service Worker for testing |

### Infrastructure

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Containerization | Docker | Package backend + frontend |
| Orchestration | Docker Compose | Local/single-server deployment |
| Database | SQLite (MVP) → PostgreSQL | Persistent state |
| Encryption | Fernet (cryptography) | Connection string encryption at rest |

---

## 15. Future Roadmap

### Phase 2: Extended Detection
- Volume anomaly detection (row count spikes/drops)
- Distribution drift (statistical tests on column values)
- Null rate monitoring
- Uniqueness/constraint violation detection
- Custom SQL rule engine

### Phase 3: Auto-Remediation
- Configurable autonomy levels per action (auto/approve/notify-only)
- Circuit breakers — automatically pause downstream pipelines when upstream breaks
- Virtual patches — temporary CASTs or filters while root cause is fixed
- Rollback support — revert to last known-good schema snapshot

### Phase 4: Integrations
- Slack/PagerDuty/email notifications
- dbt manifest ingestion for enhanced lineage
- Airflow/Dagster DAG integration
- Webhook system for custom integrations
- Terraform provider for infrastructure-as-code setup

### Phase 5: Scale + Multi-Tenancy
- Migrate to PostgreSQL + Redis
- Kubernetes deployment (Helm chart)
- Multi-tenancy with org/team isolation
- OAuth/SSO authentication
- Role-based access control (RBAC)
- Multi-provider LLM routing (cost optimization)

### Phase 6: Intelligence
- Anomaly correlation — link related anomalies across tables
- Predictive alerts — ML models that predict failures before they happen
- Impact scoring — rank tables by business criticality
- Natural language querying — "What broke the executive dashboard last week?"

---

## Appendix: Glossary

| Term | Definition |
|------|-----------|
| **Sentinel** | Detection agent that monitors tables for anomalies on a schedule |
| **Architect** | Reasoning agent that uses LLM + lineage to diagnose root causes |
| **Executor** | Action agent that formats remediation plans for human review |
| **Orchestrator** | State machine that coordinates the incident lifecycle |
| **Lineage** | The directed graph of table-to-table data dependencies |
| **Blast Radius** | The set of downstream tables affected by an anomaly |
| **Schema Drift** | Unexpected changes to a table's column structure |
| **Freshness Violation** | A table not updating within its expected SLA window |
| **Virtual Patch** | A temporary SQL transformation applied to fix data in-flight |
| **Circuit Breaker** | Mechanism to pause downstream processing when upstream data is unreliable |
