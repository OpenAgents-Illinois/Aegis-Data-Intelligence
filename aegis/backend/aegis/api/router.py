"""Aggregate all API route modules."""

from fastapi import APIRouter

from aegis.api.connections import router as connections_router
from aegis.api.incidents import router as incidents_router
from aegis.api.lineage import router as lineage_router
from aegis.api.system import router as system_router
from aegis.api.tables import router as tables_router
from aegis.api.websocket import router as ws_router

api_router = APIRouter()

api_router.include_router(connections_router, prefix="/connections", tags=["connections"])
api_router.include_router(tables_router, prefix="/tables", tags=["tables"])
api_router.include_router(incidents_router, prefix="/incidents", tags=["incidents"])
api_router.include_router(lineage_router, prefix="/lineage", tags=["lineage"])
api_router.include_router(system_router, tags=["system"])
api_router.include_router(ws_router, tags=["websocket"])
