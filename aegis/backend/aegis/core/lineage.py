"""Lineage engine — query log parsing and DAG traversal."""

from __future__ import annotations

import hashlib
import logging
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from aegis.core.connectors import WarehouseConnector, get_extractor
from aegis.core.models import LineageEdgeModel
from aegis.utils.sql_parser import extract_lineage_edges

logger = logging.getLogger("aegis.lineage")

STALE_DAYS = 30


class LineageGraph:
    """DAG traversal over lineage_edges for blast-radius and path queries."""

    def __init__(self, db: Session):
        self.db = db

    def get_upstream(self, table: str, depth: int = 3) -> list[dict[str, Any]]:
        """BFS upstream — what feeds INTO this table."""
        return self._bfs(table, depth, direction="upstream")

    def get_downstream(self, table: str, depth: int = 3) -> list[dict[str, Any]]:
        """BFS downstream — what this table feeds INTO."""
        return self._bfs(table, depth, direction="downstream")

    def get_blast_radius(self, table: str) -> dict[str, Any]:
        """Full downstream impact assessment."""
        downstream = self.get_downstream(table, depth=10)
        return {
            "table": table,
            "affected_tables": downstream,
            "total_affected": len(downstream),
            "max_depth": max((n["depth"] for n in downstream), default=0),
        }

    def get_path(self, source: str, target: str) -> list[str] | None:
        """Shortest dependency path between two tables using BFS."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=STALE_DAYS)

        visited: set[str] = {source}
        queue: deque[tuple[str, list[str]]] = deque([(source, [source])])

        while queue:
            current, path = queue.popleft()

            stmt = (
                select(LineageEdgeModel.target_table)
                .where(LineageEdgeModel.source_table == current)
                .where(LineageEdgeModel.last_seen_at >= cutoff)
            )
            neighbors = [row[0] for row in self.db.execute(stmt).all()]

            for neighbor in neighbors:
                if neighbor == target:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return None

    def get_full_graph(self) -> dict[str, Any]:
        """Return all nodes and edges for visualization."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=STALE_DAYS)

        stmt = select(LineageEdgeModel).where(LineageEdgeModel.last_seen_at >= cutoff)
        edges = self.db.execute(stmt).scalars().all()

        nodes: set[str] = set()
        edge_list: list[dict[str, Any]] = []

        for edge in edges:
            nodes.add(edge.source_table)
            nodes.add(edge.target_table)
            edge_list.append({
                "source": edge.source_table,
                "target": edge.target_table,
                "relationship": edge.relationship_type,
                "confidence": edge.confidence,
            })

        return {
            "nodes": [{"id": n, "label": n} for n in sorted(nodes)],
            "edges": edge_list,
        }

    def _bfs(self, start: str, depth: int, direction: str) -> list[dict[str, Any]]:
        """Generic BFS traversal in either direction."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=STALE_DAYS)
        results: list[dict[str, Any]] = []
        visited: set[str] = {start}
        queue: deque[tuple[str, int]] = deque([(start, 0)])

        while queue:
            current, current_depth = queue.popleft()
            if current_depth >= depth:
                continue

            if direction == "downstream":
                stmt = (
                    select(LineageEdgeModel)
                    .where(LineageEdgeModel.source_table == current)
                    .where(LineageEdgeModel.last_seen_at >= cutoff)
                )
            else:
                stmt = (
                    select(LineageEdgeModel)
                    .where(LineageEdgeModel.target_table == current)
                    .where(LineageEdgeModel.last_seen_at >= cutoff)
                )

            edges = self.db.execute(stmt).scalars().all()

            for edge in edges:
                neighbor = (
                    edge.target_table if direction == "downstream" else edge.source_table
                )
                if neighbor not in visited:
                    visited.add(neighbor)
                    node = {
                        "table": neighbor,
                        "depth": current_depth + 1,
                        "confidence": edge.confidence,
                    }
                    results.append(node)
                    queue.append((neighbor, current_depth + 1))

        return results


class LineageRefresher:
    """Parses warehouse query logs to discover and update lineage edges."""

    def __init__(self, db: Session):
        self.db = db

    def refresh(
        self, connector: WarehouseConnector, since: datetime | None = None
    ) -> int:
        """Extract query logs and upsert lineage edges. Returns edge count."""
        extractor = get_extractor(connector)
        if extractor is None:
            logger.warning("No query log extractor for dialect: %s", connector.dialect)
            return 0

        if since is None:
            since = datetime.now(timezone.utc) - timedelta(hours=2)

        try:
            logs = extractor.extract(since)
        except Exception:
            logger.exception("Failed to extract query logs")
            return 0

        edge_count = 0
        now = datetime.now(timezone.utc)

        for entry in logs:
            sql = entry.get("sql", "")
            if not sql:
                continue

            parsed_edges = extract_lineage_edges(sql, connector.dialect)
            for pe in parsed_edges:
                self._upsert_edge(pe.source, pe.target, pe.confidence, sql, now)
                edge_count += 1

        self.db.commit()
        logger.info("Refreshed %d lineage edges from %d query log entries", edge_count, len(logs))
        return edge_count

    def _upsert_edge(
        self,
        source: str,
        target: str,
        confidence: float,
        sql: str,
        now: datetime,
    ) -> None:
        """Insert or update a lineage edge."""
        query_hash = hashlib.sha256(sql.encode()).hexdigest()[:16]

        stmt = select(LineageEdgeModel).where(
            LineageEdgeModel.source_table == source,
            LineageEdgeModel.target_table == target,
        )
        existing = self.db.execute(stmt).scalar_one_or_none()

        if existing:
            existing.last_seen_at = now
            existing.confidence = max(existing.confidence, confidence)
            existing.query_hash = query_hash
        else:
            edge = LineageEdgeModel(
                source_table=source,
                target_table=target,
                relationship_type="direct",
                query_hash=query_hash,
                confidence=confidence,
                first_seen_at=now,
                last_seen_at=now,
            )
            self.db.add(edge)
