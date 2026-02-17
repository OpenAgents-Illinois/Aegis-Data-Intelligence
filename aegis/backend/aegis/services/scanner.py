"""Scheduled scan loop — runs Sentinels on all monitored tables."""

from __future__ import annotations

import asyncio
import json
import logging

from sqlalchemy import select

from aegis.agents.architect import Architect
from aegis.agents.executor import Executor
from aegis.agents.orchestrator import Orchestrator
from aegis.agents.sentinel import FreshnessSentinel, SchemaSentinel
from aegis.config import settings
from aegis.core.connectors import WarehouseConnector
from aegis.core.database import SyncSessionLocal
from aegis.core.lineage import LineageGraph, LineageRefresher
from aegis.core.models import ConnectionModel, MonitoredTableModel

logger = logging.getLogger("aegis.scanner")


async def start_scanner() -> asyncio.Task | None:
    """Start the background scan loop as an asyncio task."""
    task = asyncio.create_task(_scan_loop())
    return task


async def _scan_loop():
    """Main scan loop — runs sentinels every SCAN_INTERVAL_SECONDS."""
    interval = settings.scan_interval_seconds
    lineage_interval = settings.lineage_refresh_seconds
    last_lineage_refresh = 0.0

    while True:
        try:
            await asyncio.to_thread(_run_scan_cycle)
        except Exception:
            logger.exception("Scan cycle failed")

        # Lineage refresh on its own cadence
        import time

        now = time.monotonic()
        if now - last_lineage_refresh >= lineage_interval:
            try:
                await asyncio.to_thread(_run_lineage_refresh)
                last_lineage_refresh = now
            except Exception:
                logger.exception("Lineage refresh failed")

        await asyncio.sleep(interval)


def _run_scan_cycle():
    """Execute one full scan cycle across all connections and tables."""
    schema_sentinel = SchemaSentinel()
    freshness_sentinel = FreshnessSentinel()

    with SyncSessionLocal() as db:
        lineage_graph = LineageGraph(db)
        architect = Architect(lineage_graph=lineage_graph)
        executor = Executor()

        from aegis.services.notifier import notifier

        orchestrator = Orchestrator(architect, executor, notifier=notifier)

        connections = db.execute(
            select(ConnectionModel).where(ConnectionModel.is_active.is_(True))
        ).scalars().all()

        total_anomalies = 0
        total_tables = 0

        for conn_model in connections:
            try:
                connector = WarehouseConnector(conn_model.connection_uri, conn_model.dialect)
            except Exception:
                logger.exception("Failed to connect to %s", conn_model.name)
                continue

            tables = db.execute(
                select(MonitoredTableModel).where(
                    MonitoredTableModel.connection_id == conn_model.id
                )
            ).scalars().all()

            for table in tables:
                total_tables += 1
                check_types = json.loads(table.check_types)

                if "schema" in check_types:
                    anomaly = schema_sentinel.inspect(table, connector, db)
                    if anomaly:
                        total_anomalies += 1
                        orchestrator.handle_anomaly(anomaly, db)

                if "freshness" in check_types:
                    anomaly = freshness_sentinel.inspect(table, connector, db)
                    if anomaly:
                        total_anomalies += 1
                        orchestrator.handle_anomaly(anomaly, db)

            connector.dispose()

        db.commit()

        logger.info(
            "Scan cycle complete: %d tables scanned, %d anomalies found",
            total_tables,
            total_anomalies,
        )

        # Broadcast scan completion
        from aegis.services.notifier import notifier

        notifier.broadcast(
            "scan.completed",
            {
                "tables_scanned": total_tables,
                "anomalies_found": total_anomalies,
            },
        )


def _run_lineage_refresh():
    """Refresh lineage edges from all active connections' query logs."""
    with SyncSessionLocal() as db:
        connections = db.execute(
            select(ConnectionModel).where(ConnectionModel.is_active.is_(True))
        ).scalars().all()

        total_edges = 0
        for conn_model in connections:
            try:
                connector = WarehouseConnector(conn_model.connection_uri, conn_model.dialect)
                refresher = LineageRefresher(db)
                edges = refresher.refresh(connector)
                total_edges += edges
                connector.dispose()
            except Exception:
                logger.exception("Lineage refresh failed for %s", conn_model.name)

        logger.info("Lineage refresh complete: %d edges updated", total_edges)


def run_manual_scan():
    """Trigger a single scan cycle (for API endpoint)."""
    _run_scan_cycle()
