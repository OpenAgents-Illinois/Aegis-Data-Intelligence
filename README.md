# Aegis Data Intelligence Platform

Self-healing data quality monitoring with autonomous AI agents.

## What It Does

Aegis connects to your data warehouse, continuously monitors table health, and automatically detects and remediates data quality issues — schema drift, stale tables, broken lineage — before they impact downstream consumers.

## Architecture

```
aegis/
├── backend/           → FastAPI + SQLAlchemy + LangChain
│   ├── agents/        → Sentinel, Orchestrator, Architect, Executor, Investigator
│   ├── api/           → REST endpoints + WebSocket notifications
│   ├── core/          → ORM models, connectors, lineage engine
│   └── services/      → Scanner loop, LLM services, notifier
├── frontend/          → React + TypeScript + Vite + Tailwind CSS
│   ├── pages/         → Dashboard, Incidents, Lineage, Setup
│   └── components/    → Charts, Tables, Connection Forms, Splash Screen
└── docker-compose.yml
```

## Agent Pipeline

1. **Investigator** — Discovers warehouse tables, classifies them (fact/dim/staging/raw), proposes monitoring config
2. **Sentinels** — SchemaSentinel detects column drift; FreshnessSentinel detects stale tables
3. **Orchestrator** — Routes anomalies into incidents with deduplication
4. **Architect** — LLM-powered root cause analysis using lineage graph for blast radius
5. **Executor** — Applies remediation actions from architect recommendations

## Quick Start

### Backend

```bash
cd aegis/backend
pip install -e .
AEGIS_API_KEY=dev-key python -m aegis.main
```

### Frontend

```bash
cd aegis/frontend
npm install
npm run dev
```

### Connect a Warehouse

```bash
# Register a PostgreSQL connection
curl -X POST http://localhost:8000/api/v1/connections \
  -H "Content-Type: application/json" \
  -d '{"name": "my-warehouse", "dialect": "postgresql", "connection_string": "postgresql://user:pass@host:5432/db"}'

# Test connectivity
curl -X POST http://localhost:8000/api/v1/connections/1/test

# Discover tables
curl -X POST http://localhost:8000/api/v1/connections/1/discover
```

## Supported Warehouses (SQLAlchemy-compatible)

| Warehouse   | Dialect      | Optional install        |
|------------|--------------|-------------------------|
| PostgreSQL | `postgresql` | (built-in)              |
| Snowflake  | `snowflake`  | `pip install -e ".[snowflake]"` |
| BigQuery   | `bigquery`   | `pip install -e ".[bigquery]"`  |
| Databricks | `databricks` | `pip install -e ".[databricks]"` |

Discovery and monitoring work with any of these. Query-log lineage extractors exist for PostgreSQL, Snowflake, and BigQuery only. Canonical list: `aegis/backend/aegis/core/connectors.py` → `SUPPORTED_WAREHOUSE_DIALECTS`.

## Tech Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0, LangChain, Alembic
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Zustand, Recharts
- **Database**: SQLite (WAL mode) for metadata
- **AI**: OpenAI GPT for root cause analysis and table classification

## Running Tests

```bash
cd aegis/backend
python -m pytest tests/ -v --tb=short
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `AEGIS_API_KEY` | API key (`dev-key` for development) |
| `OPENAI_API_KEY` | OpenAI key for LLM-powered agents |
| `AEGIS_DATABASE_URL` | SQLite path (default: `./aegis.db`) |
| `AEGIS_SCAN_INTERVAL` | Scan frequency in seconds (default: 300) |

## License

MIT
