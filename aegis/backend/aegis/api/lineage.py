"""Lineage graph query endpoints."""

from fastapi import APIRouter, Depends, Query

from aegis.api.deps import verify_api_key
from aegis.core.database import SyncSessionLocal
from aegis.core.lineage import LineageGraph

router = APIRouter(dependencies=[Depends(verify_api_key)])


def _get_lineage_graph() -> LineageGraph:
    db = SyncSessionLocal()
    return LineageGraph(db)


@router.get("/graph")
async def get_full_graph(connection_id: int | None = Query(None)):
    graph = _get_lineage_graph()
    return graph.get_full_graph(connection_id=connection_id)


@router.get("/{table}/upstream")
async def get_upstream(
    table: str,
    depth: int = Query(3, ge=1, le=10),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
):
    graph = _get_lineage_graph()
    nodes = graph.get_upstream(table, depth=depth)
    if min_confidence > 0:
        nodes = [n for n in nodes if n["confidence"] >= min_confidence]
    return {"table": table, "upstream": nodes}


@router.get("/{table}/downstream")
async def get_downstream(
    table: str,
    depth: int = Query(3, ge=1, le=10),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
):
    graph = _get_lineage_graph()
    nodes = graph.get_downstream(table, depth=depth)
    if min_confidence > 0:
        nodes = [n for n in nodes if n["confidence"] >= min_confidence]
    return {"table": table, "downstream": nodes}


@router.get("/{table}/blast-radius")
async def get_blast_radius(table: str):
    graph = _get_lineage_graph()
    return graph.get_blast_radius(table)
