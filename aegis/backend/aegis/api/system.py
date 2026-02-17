"""System endpoints — health, status, stats, manual scan trigger."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.api.deps import get_db, verify_api_key
from aegis.core.models import (
    AnomalyModel,
    IncidentModel,
    MonitoredTableModel,
    StatsResponse,
)

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "service": "aegis", "version": "0.1.0"}


@router.get("/status", dependencies=[Depends(verify_api_key)])
async def status():
    from aegis.services.notifier import notifier

    return {
        "scanner": "running",
        "websocket_clients": notifier.connection_count,
    }


@router.get("/stats", response_model=StatsResponse, dependencies=[Depends(verify_api_key)])
async def stats(db: AsyncSession = Depends(get_db)):
    # Total tables
    total_result = await db.execute(select(func.count(MonitoredTableModel.id)))
    total_tables = total_result.scalar() or 0

    # Open incidents
    open_result = await db.execute(
        select(func.count(IncidentModel.id)).where(
            IncidentModel.status.in_(["open", "investigating", "pending_review"])
        )
    )
    open_incidents = open_result.scalar() or 0

    # Critical incidents
    critical_result = await db.execute(
        select(func.count(IncidentModel.id)).where(
            IncidentModel.status.in_(["open", "investigating", "pending_review"]),
            IncidentModel.severity == "critical",
        )
    )
    critical_incidents = critical_result.scalar() or 0

    # Anomalies in last 24h
    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    anomalies_result = await db.execute(
        select(func.count(AnomalyModel.id)).where(AnomalyModel.detected_at >= since_24h)
    )
    anomalies_24h = anomalies_result.scalar() or 0

    # Tables with open incidents
    tables_with_incidents_result = await db.execute(
        select(func.count(func.distinct(AnomalyModel.table_id)))
        .join(IncidentModel)
        .where(IncidentModel.status.in_(["open", "investigating", "pending_review"]))
    )
    tables_with_incidents = tables_with_incidents_result.scalar() or 0

    healthy_tables = total_tables - tables_with_incidents
    health_score = (healthy_tables / total_tables * 100) if total_tables > 0 else 100.0

    # Avg resolution time
    avg_result = await db.execute(
        select(func.avg(
            func.julianday(IncidentModel.resolved_at) - func.julianday(IncidentModel.created_at)
        )).where(IncidentModel.resolved_at.isnot(None))
    )
    avg_days = avg_result.scalar()
    avg_resolution_minutes = round(avg_days * 24 * 60, 1) if avg_days else None

    return StatsResponse(
        health_score=round(health_score, 1),
        total_tables=total_tables,
        healthy_tables=healthy_tables,
        open_incidents=open_incidents,
        critical_incidents=critical_incidents,
        anomalies_24h=anomalies_24h,
        avg_resolution_time_minutes=avg_resolution_minutes,
    )


@router.post("/scan/trigger", dependencies=[Depends(verify_api_key)])
async def trigger_scan():
    import asyncio

    from aegis.services.scanner import run_manual_scan

    await asyncio.to_thread(run_manual_scan)
    return {"status": "scan_completed"}
