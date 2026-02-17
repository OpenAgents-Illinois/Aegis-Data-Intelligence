"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aegis.config import settings
from aegis.core.database import ensure_db_directory, run_migrations

logger = logging.getLogger("aegis")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    logging.basicConfig(level=getattr(logging, settings.log_level))
    logger.info("Starting Aegis Data Intelligence Platform v0.1.0")

    ensure_db_directory()
    run_migrations()
    logger.info("Database migrations applied")

    # Start background scanner and lineage refresh
    from aegis.services.scanner import start_scanner

    scanner_task = await start_scanner()
    logger.info("Background scanner started")

    yield

    # Shutdown
    if scanner_task:
        scanner_task.cancel()
    logger.info("Aegis shutting down")


app = FastAPI(
    title="Aegis Data Intelligence Platform",
    version="0.1.0",
    description="Self-healing data quality monitoring with autonomous AI agents",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
from aegis.api.router import api_router  # noqa: E402

app.include_router(api_router, prefix="/api/v1")
