"""Incident listing, detail, approval, and dismissal endpoints."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.api.deps import get_db, verify_api_key
from aegis.core.models import (
    IncidentApprove,
    IncidentDismiss,
    IncidentModel,
    IncidentResponse,
)
from aegis.services.notifier import notifier

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("", response_model=list[IncidentResponse])
async def list_incidents(
    status: str | None = Query(None),
    severity: str | None = Query(None),
    table_id: int | None = Query(None),
    since: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(IncidentModel)

    if status:
        stmt = stmt.where(IncidentModel.status == status)
    if severity:
        stmt = stmt.where(IncidentModel.severity == severity)
    if table_id:
        from aegis.core.models import AnomalyModel

        stmt = stmt.join(AnomalyModel).where(AnomalyModel.table_id == table_id)
    if since:
        stmt = stmt.where(IncidentModel.created_at >= since)

    stmt = stmt.order_by(IncidentModel.created_at.desc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(stmt)
    return [IncidentResponse.from_orm_model(i) for i in result.scalars().all()]


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(incident_id: int, db: AsyncSession = Depends(get_db)):
    incident = await db.get(IncidentModel, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return IncidentResponse.from_orm_model(incident)


@router.get("/{incident_id}/report")
async def get_incident_report(incident_id: int, db: AsyncSession = Depends(get_db)):
    """Return the structured incident report."""
    incident = await db.get(IncidentModel, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    if not incident.report:
        return JSONResponse(status_code=204, content=None)

    return json.loads(incident.report)


@router.post("/{incident_id}/approve", response_model=IncidentResponse)
async def approve_incident(
    incident_id: int, body: IncidentApprove, db: AsyncSession = Depends(get_db)
):
    incident = await db.get(IncidentModel, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident.status = "resolved"
    incident.resolved_at = datetime.now(timezone.utc)
    incident.resolved_by = "api_user"

    await db.commit()
    await db.refresh(incident)

    await notifier.broadcast_async(
        "incident.updated",
        {"incident_id": incident.id, "status": "resolved"},
    )

    return IncidentResponse.from_orm_model(incident)


@router.post("/{incident_id}/dismiss", response_model=IncidentResponse)
async def dismiss_incident(
    incident_id: int, body: IncidentDismiss, db: AsyncSession = Depends(get_db)
):
    incident = await db.get(IncidentModel, incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident.status = "dismissed"
    incident.dismiss_reason = body.reason
    incident.resolved_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(incident)

    await notifier.broadcast_async(
        "incident.updated",
        {"incident_id": incident.id, "status": "dismissed"},
    )

    return IncidentResponse.from_orm_model(incident)
