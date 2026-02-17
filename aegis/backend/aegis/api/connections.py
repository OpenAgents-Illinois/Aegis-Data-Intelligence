"""CRUD endpoints for warehouse connections."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.api.deps import get_db, verify_api_key
from aegis.core.connectors import WarehouseConnector
from aegis.core.models import ConnectionCreate, ConnectionModel, ConnectionResponse, ConnectionUpdate

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.post("", response_model=ConnectionResponse, status_code=201)
async def create_connection(body: ConnectionCreate, db: AsyncSession = Depends(get_db)):
    conn = ConnectionModel(
        name=body.name,
        dialect=body.dialect,
        connection_uri=body.connection_uri,
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)
    return conn


@router.get("", response_model=list[ConnectionResponse])
async def list_connections(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ConnectionModel).order_by(ConnectionModel.created_at.desc()))
    return result.scalars().all()


@router.get("/{conn_id}", response_model=ConnectionResponse)
async def get_connection(conn_id: int, db: AsyncSession = Depends(get_db)):
    conn = await db.get(ConnectionModel, conn_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    return conn


@router.put("/{conn_id}", response_model=ConnectionResponse)
async def update_connection(
    conn_id: int, body: ConnectionUpdate, db: AsyncSession = Depends(get_db)
):
    conn = await db.get(ConnectionModel, conn_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(conn, field, value)

    await db.commit()
    await db.refresh(conn)
    return conn


@router.delete("/{conn_id}", status_code=204)
async def delete_connection(conn_id: int, db: AsyncSession = Depends(get_db)):
    conn = await db.get(ConnectionModel, conn_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    await db.delete(conn)
    await db.commit()


@router.post("/{conn_id}/test")
async def test_connection(conn_id: int, db: AsyncSession = Depends(get_db)):
    conn = await db.get(ConnectionModel, conn_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    connector = WarehouseConnector(conn.connection_uri, conn.dialect)
    success = connector.test_connection()
    connector.dispose()

    return {"success": success, "connection": conn.name}
