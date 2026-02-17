"""CRUD endpoints for monitored tables."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.api.deps import get_db, verify_api_key
from aegis.core.models import (
    MonitoredTableModel,
    SchemaSnapshotModel,
    TableCreate,
    TableResponse,
    TableUpdate,
)

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.post("", response_model=TableResponse, status_code=201)
async def add_table(body: TableCreate, db: AsyncSession = Depends(get_db)):
    table = MonitoredTableModel(
        connection_id=body.connection_id,
        schema_name=body.schema_name,
        table_name=body.table_name,
        fully_qualified_name=f"{body.schema_name}.{body.table_name}",
        check_types=json.dumps(body.check_types),
        freshness_sla_minutes=body.freshness_sla_minutes,
    )
    db.add(table)
    await db.commit()
    await db.refresh(table)
    return TableResponse.from_orm_model(table)


@router.get("", response_model=list[TableResponse])
async def list_tables(
    connection_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(MonitoredTableModel)
    if connection_id:
        stmt = stmt.where(MonitoredTableModel.connection_id == connection_id)
    stmt = stmt.order_by(MonitoredTableModel.created_at.desc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(stmt)
    return [TableResponse.from_orm_model(t) for t in result.scalars().all()]


@router.get("/{table_id}", response_model=TableResponse)
async def get_table(table_id: int, db: AsyncSession = Depends(get_db)):
    table = await db.get(MonitoredTableModel, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    return TableResponse.from_orm_model(table)


@router.put("/{table_id}", response_model=TableResponse)
async def update_table(
    table_id: int, body: TableUpdate, db: AsyncSession = Depends(get_db)
):
    table = await db.get(MonitoredTableModel, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")

    if body.check_types is not None:
        table.check_types = json.dumps(body.check_types)
    if body.freshness_sla_minutes is not None:
        table.freshness_sla_minutes = body.freshness_sla_minutes

    await db.commit()
    await db.refresh(table)
    return TableResponse.from_orm_model(table)


@router.delete("/{table_id}", status_code=204)
async def delete_table(table_id: int, db: AsyncSession = Depends(get_db)):
    table = await db.get(MonitoredTableModel, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    await db.delete(table)
    await db.commit()


@router.get("/{table_id}/snapshots")
async def get_snapshots(
    table_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(SchemaSnapshotModel)
        .where(SchemaSnapshotModel.table_id == table_id)
        .order_by(SchemaSnapshotModel.captured_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    snapshots = result.scalars().all()
    return [
        {
            "id": s.id,
            "columns": json.loads(s.columns),
            "snapshot_hash": s.snapshot_hash,
            "captured_at": s.captured_at.isoformat(),
        }
        for s in snapshots
    ]
