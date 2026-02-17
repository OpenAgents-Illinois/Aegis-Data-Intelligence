"""SQL parsing helpers for lineage extraction using sqlglot."""

from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp


@dataclass
class ParsedEdge:
    source: str
    target: str
    confidence: float


def extract_lineage_edges(sql: str, dialect: str) -> list[ParsedEdge]:
    """Parse a SQL statement and extract source→target table edges.

    Returns edges with confidence scores based on the relationship pattern.
    """
    edges: list[ParsedEdge] = []

    try:
        parsed = sqlglot.parse(sql, dialect=dialect)
    except sqlglot.errors.ParseError:
        return []

    for statement in parsed:
        if statement is None:
            continue

        target = _extract_target(statement)
        if target is None:
            continue

        sources = _extract_sources(statement, target)

        for source, confidence in sources:
            edges.append(ParsedEdge(source=source, target=target, confidence=confidence))

    return edges


def _extract_target(statement: exp.Expression) -> str | None:
    """Extract the target table from a write statement."""
    if isinstance(statement, exp.Insert):
        table = statement.find(exp.Table)
        return _table_name(table) if table else None
    elif isinstance(statement, exp.Create):
        table = statement.find(exp.Table)
        return _table_name(table) if table else None
    elif isinstance(statement, exp.Merge):
        table = statement.find(exp.Table)
        return _table_name(table) if table else None
    return None


def _extract_sources(
    statement: exp.Expression, target: str
) -> list[tuple[str, float]]:
    """Extract all source tables from a statement with confidence scores."""
    sources: list[tuple[str, float]] = []
    seen: set[str] = set()

    for table in statement.find_all(exp.Table):
        name = _table_name(table)
        if name == target or name in seen:
            continue
        seen.add(name)

        confidence = _compute_confidence(table, statement)
        sources.append((name, confidence))

    return sources


def _compute_confidence(table: exp.Table, root: exp.Expression) -> float:
    """Score confidence based on nesting depth of the source table reference."""
    depth = 0
    node = table.parent
    while node is not None and node is not root:
        if isinstance(node, exp.Subquery):
            depth += 1
        node = node.parent

    if depth == 0:
        return 1.0
    elif depth <= 2:
        return 0.8
    else:
        return 0.6


def _table_name(table: exp.Table) -> str:
    """Build a fully qualified table name from a sqlglot Table node."""
    parts = []
    if table.catalog:
        parts.append(table.catalog)
    if table.db:
        parts.append(table.db)
    parts.append(table.name)
    return ".".join(parts)
