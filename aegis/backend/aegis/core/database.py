"""Database engine, session factory, and migration runner."""

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from aegis.config import settings


class Base(DeclarativeBase):
    pass


# Async engine for FastAPI request handling
async_engine = create_async_engine(
    settings.database_url,
    echo=settings.log_level == "DEBUG",
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Sync engine for Alembic migrations and background tasks
sync_engine = create_engine(
    settings.sync_database_url,
    echo=settings.log_level == "DEBUG",
)

SyncSessionLocal = sessionmaker(bind=sync_engine)


def _enable_wal(dbapi_conn, connection_record):
    """Enable WAL mode for SQLite to reduce lock contention."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


event.listen(sync_engine, "connect", _enable_wal)


@event.listens_for(async_engine.sync_engine, "connect")
def _enable_wal_async(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


async def get_async_session():
    """FastAPI dependency for async database sessions."""
    async with AsyncSessionLocal() as session:
        yield session


def ensure_db_directory():
    """Create the database directory if it doesn't exist."""
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)


def run_migrations():
    """Run Alembic migrations programmatically on startup."""
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", settings.sync_database_url)
    command.upgrade(alembic_cfg, "head")
