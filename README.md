<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black" alt="React">
  <img src="https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white" alt="TypeScript">
  <img src="https://img.shields.io/badge/LangChain-0.3-1C3C3C?logo=langchain&logoColor=white" alt="LangChain">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
</p>

# Aegis Data Intelligence

**Self-healing data quality monitoring with autonomous AI agents.**

Aegis connects to your data warehouse, discovers tables automatically, monitors them for schema drift and freshness violations, and runs an AI agent pipeline to diagnose root causes, assess downstream impact, and propose remediations — all surfaced through a real-time dashboard.

---

## The Problem

Data quality failures are silent killers. A column gets renamed in a staging table, an ETL pipeline misses a run, a type changes from `INT` to `VARCHAR` — and nobody notices until a dashboard shows wrong numbers or a downstream model produces garbage. By then, the blast radius is unclear and debugging is manual.

## How Aegis Solves It

```
Warehouse ──> Sentinels ──> Orchestrator ──> Architect ──> Executor ──> Dashboard
   ^              |              |              |              |            |
   |         detect drift    create incident  GPT-4 root    remediation   approve/
   |         & freshness     & deduplicate    cause analysis  plans       dismiss
   |                                                                        |
   └──── Investigator (LangChain) ── auto-discovers & classifies tables ────┘
```

1. **Connect** to any SQLAlchemy-compatible warehouse (PostgreSQL, Snowflake, BigQuery, Databricks, SQLite)
2. **Discover** tables using a LangChain AI agent that classifies each table (fact, dimension, staging, raw, snapshot, system) and proposes monitoring configuration
3. **Monitor** enrolled tables on a configurable schedule for schema drift (column add/delete/type change via SHA-256 hashing) and freshness violations (SLA breaches)
4. **Diagnose** anomalies with GPT-4 to identify root cause, upstream source, blast radius, and severity — with a deterministic fallback when no API key is set
5. **Remediate** with structured action plans (some with executable SQL, some manual)
6. **Track lineage** by parsing SQL query logs (INSERT/CTAS/MERGE) with sqlglot, building a dependency DAG for blast radius analysis
7. **Review** from the dashboard: approve to resolve, dismiss with a reason, or drill into the full incident report

---

## Architecture

### Agent Pipeline

| Agent | Role | LLM? |
|-------|------|------|
| **Investigator** | Explores warehouse schemas, classifies tables, proposes monitoring config | LangChain (tool-calling agent) |
| **SchemaSentinel** | Detects column additions, deletions, type changes via INFORMATION_SCHEMA snapshots | No |
| **FreshnessSentinel** | Detects tables overdue relative to their freshness SLA | No |
| **Orchestrator** | Creates incidents, deduplicates, manages lifecycle state machine | No |
| **Architect** | Root cause analysis, blast radius assessment, severity classification | GPT-4 (with deterministic fallback) |
| **Executor** | Transforms diagnosis into prioritized remediation actions | No |
| **ReportGenerator** | Assembles structured incident reports from pipeline outputs | No |

### Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.0 (async + sync), Alembic, Pydantic v2 |
| AI | OpenAI SDK (GPT-4), LangChain (AgentExecutor, tool calling) |
| Database | SQLite (WAL mode) via aiosqlite (async) + sqlite3 (sync) |
| SQL Parsing | sqlglot |
| Encryption | Fernet (cryptography) |
| Real-time | WebSocket (FastAPI native) |
| Frontend | React 18, TypeScript 5, Vite 5, Tailwind CSS 3 |
| State | Zustand 4 |
| Visualization | Recharts (charts), XY Flow (lineage DAG) |
| Testing | pytest + pytest-asyncio (backend), Vitest + Testing Library + MSW (frontend) |
| Containerization | Docker + docker-compose |

### Key Design Decisions

- **Async/sync bridge**: FastAPI is fully async. Agents and connectors run synchronously. Bridged via `asyncio.to_thread` so the event loop stays unblocked.
- **Dual SQLAlchemy engines**: `AsyncSessionLocal` (aiosqlite) for API request handling; `SyncSessionLocal` for agent tasks and background scanning.
- **LangChain tool binding**: `make_tools()` closure factory binds connector, db session, and lineage graph per invocation — no global state.
- **Deterministic fallback**: Every LLM-dependent agent has a rule-based fallback. The platform works without an OpenAI key — you just get heuristic classification and diagnosis instead of GPT-4.
- **Single-file models**: All ORM models and Pydantic schemas live in `core/models.py` for discoverability.

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- (Optional) OpenAI API key for AI-powered diagnosis
- (Optional) Docker for containerized deployment

### Local Development

```bash
# Clone the repo
git clone https://github.com/OpenAgents-Illinois/Aegis-Data-Intelligence.git
cd Aegis-Data-Intelligence/aegis

# Set up environment
cp .env.example .env
# Edit .env — at minimum set AEGIS_API_KEY and optionally OPENAI_API_KEY

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cd ..

# Frontend
cd frontend
npm install
cd ..

# Run both (backend on :8000, frontend on :5173)
make dev
```

### Docker

```bash
# Build and start (backend on :8000, frontend on :3000)
make up

# View logs
make logs

# Stop
make down
```

### Verify

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Run backend tests (68 tests)
cd backend && python -m pytest tests/ -v --tb=short
```

---

## Configuration

All backend settings use the `AEGIS_` prefix and can be set via environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `AEGIS_API_KEY` | `dev-key` | API authentication key |
| `AEGIS_DB_PATH` | `data/aegis.db` | SQLite database path |
| `AEGIS_SCAN_INTERVAL_SECONDS` | `300` | How often sentinels check tables (5 min) |
| `AEGIS_LINEAGE_REFRESH_SECONDS` | `3600` | How often lineage edges are refreshed (1 hr) |
| `AEGIS_REDISCOVERY_INTERVAL_SECONDS` | `86400` | How often new/dropped tables are detected (24 hr) |
| `AEGIS_LOG_LEVEL` | `INFO` | Logging level |
| `AEGIS_ENCRYPTION_KEY` | — | Fernet key for encrypting connection URIs |
| `OPENAI_API_KEY` | — | OpenAI key for GPT-4 diagnosis (optional) |
| `VITE_API_URL` | `http://localhost:8000` | Frontend API base URL |
| `VITE_WS_URL` | `ws://localhost:8000/ws` | Frontend WebSocket URL |

Generate an encryption key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## API Reference

All endpoints are prefixed with `/api/v1`. Authentication via `X-API-Key` header or `api_key` query parameter.

<details>
<summary><strong>Connections</strong></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/connections` | List all warehouse connections |
| `POST` | `/connections` | Create a new connection |
| `GET` | `/connections/{id}` | Get connection details |
| `PUT` | `/connections/{id}` | Update a connection |
| `DELETE` | `/connections/{id}` | Delete a connection |
| `POST` | `/connections/{id}/test` | Test connectivity |
| `POST` | `/connections/{id}/discover` | Run AI discovery on warehouse |
| `POST` | `/connections/{id}/discover/confirm` | Enroll discovered tables |

</details>

<details>
<summary><strong>Tables</strong></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/tables` | List monitored tables |
| `POST` | `/tables` | Enroll a table for monitoring |
| `GET` | `/tables/{id}` | Get table details |
| `PUT` | `/tables/{id}` | Update table config |
| `DELETE` | `/tables/{id}` | Remove table from monitoring |

</details>

<details>
<summary><strong>Incidents</strong></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/incidents` | List incidents (filterable by status, severity, table_id) |
| `GET` | `/incidents/{id}` | Get incident details |
| `GET` | `/incidents/{id}/report` | Get structured incident report |
| `POST` | `/incidents/{id}/approve` | Approve and resolve incident |
| `POST` | `/incidents/{id}/dismiss` | Dismiss with reason |

</details>

<details>
<summary><strong>Lineage & System</strong></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/lineage/graph` | Full lineage DAG (nodes + edges) |
| `GET` | `/lineage/blast-radius/{table}` | Downstream impact analysis |
| `GET` | `/health` | Health check (no auth) |
| `GET` | `/status` | Scanner status + WebSocket client count |
| `GET` | `/stats` | Health score, incident counts |
| `POST` | `/scan/trigger` | Trigger manual scan |
| `WS` | `/ws` | Real-time event stream |

</details>

### WebSocket Events

Connect to `ws://localhost:8000/ws` for real-time updates:

```json
{"type": "incident.created", "data": {"id": 1, "severity": "critical", ...}}
{"type": "incident.updated", "data": {"id": 1, "status": "resolved", ...}}
{"type": "scan.completed", "data": {"tables_scanned": 15, "anomalies_found": 2}}
{"type": "discovery.update", "data": {"new_tables": 3, "dropped_tables": 1}}
```

---

## Project Structure

```
aegis/
├── backend/
│   ├── aegis/
│   │   ├── main.py                 # App entrypoint, lifespan, CORS
│   │   ├── config.py               # Pydantic Settings (AEGIS_ prefix)
│   │   ├── agents/                 # AI agent implementations
│   │   │   ├── sentinel.py         #   Schema + Freshness sentinels
│   │   │   ├── orchestrator.py     #   Incident state machine
│   │   │   ├── architect.py        #   GPT-4 root cause analysis
│   │   │   ├── executor.py         #   Remediation plan builder
│   │   │   ├── investigator.py     #   LangChain discovery agent
│   │   │   └── report_generator.py #   Incident report assembly
│   │   ├── api/                    # FastAPI route modules
│   │   ├── core/                   # Database, models, connectors, lineage
│   │   └── services/              # Scanner, LLM client, notifier
│   ├── tests/                     # 68+ tests
│   ├── alembic/                   # Database migrations
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── pages/                 # Landing, Overview, IncidentDetail, Lineage, Settings
│   │   ├── components/            # LineageGraph, BlastRadius, Heatmap, IncidentFeed, ...
│   │   ├── stores/                # Zustand state (incidents, tables, system, lineage)
│   │   ├── api/                   # Axios client, endpoints, TypeScript types
│   │   └── hooks/                 # useAutoRefresh, useWebSocket
│   └── package.json
├── docker-compose.yml
├── Makefile
└── .env.example
```

---

## Supported Warehouses

| Warehouse | Status | Extra Dependency |
|-----------|--------|-----------------|
| PostgreSQL | Supported | (included) |
| SQLite | Supported | (included) |
| Snowflake | Supported | `pip install "aegis[snowflake]"` |
| BigQuery | Supported | `pip install "aegis[bigquery]"` |
| Databricks | Supported | `pip install "aegis[databricks]"` |

Any SQLAlchemy-compatible dialect can be added by extending `WarehouseConnector`.

---

## Development

### Running Tests

```bash
# Backend (68 tests)
cd backend && python -m pytest tests/ -v --tb=short

# Backend with coverage
make test-backend-cov

# Frontend
cd frontend && npm test

# All
make test
```

### Linting & Formatting

```bash
# Lint
make lint

# Format
make format
```

### Database Migrations

Migrations run automatically on startup. To create a new migration:

```bash
make db-revision msg="add new column"
make db-migrate
```

---

## Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Write tests first, then implement
4. Ensure all 68+ tests pass: `cd backend && python -m pytest tests/ -v --tb=short`
5. Commit with conventional messages: `feat(component):`, `fix(component):`, `test(component):`
6. Open a PR

---

## License

MIT

---

<p align="center">
  Built at the University of Illinois at Urbana-Champaign<br>
  <strong>AgenticAI@UIUC</strong>
</p>
