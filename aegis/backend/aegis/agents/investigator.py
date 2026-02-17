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
            return "dimension", checks, sla, "Dimension table (dim_ prefix)", False

        # Fact
        if name_lower.startswith(("fct_", "fact_")):
            checks = ["schema", "freshness"] if has_timestamp else ["schema"]
            sla = 360 if has_timestamp else None
            return "fact", checks, sla, "Fact table (fct_ prefix)", False

        # Snapshot
        if name_lower.endswith(("_snapshot", "_hist", "_history")):
            return "snapshot", ["schema"], None, "Snapshot/history table", False

        # Default — use timestamps to decide
        if has_timestamp:
            return "unknown", ["schema", "freshness"], None, "Has timestamp columns; role unknown", False

        return "unknown", ["schema"], None, "No timestamp columns detected; role unknown", False
