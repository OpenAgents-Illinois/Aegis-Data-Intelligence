"""Shared API dependencies."""

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.config import settings
from aegis.core.database import get_async_session

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str | None = Security(api_key_header)):
    if not settings.api_key or settings.api_key == "dev-key":
        return  # Skip auth in dev mode
    if api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


async def get_db(session: AsyncSession = Depends(get_async_session)):
    yield session
