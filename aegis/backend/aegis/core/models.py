"""SQLAlchemy ORM models and Pydantic schemas."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aegis.core.database import Base


# ---------------------------------------------------------------------------
# SQLAlchemy ORM Models
# ---------------------------------------------------------------------------


class ConnectionModel(Base):
    __tablename__ = "connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    dialect: Mapped[str] = mapped_column(String, nullable=False)
    connection_uri: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    tables: Mapped[list[MonitoredTableModel]] = relationship(
        back_populates="connection", cascade="all, delete-orphan"
    )


class MonitoredTableModel(Base):
    __tablename__ = "monitored_tables"
    __table_args__ = (
        Index("uq_conn_schema_table", "connection_id", "schema_name", "table_name", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    connection_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("connections.id", ondelete="CASCADE"), nullable=False
    )
    schema_name: Mapped[str] = mapped_column(String, nullable=False)
    table_name: Mapped[str] = mapped_column(String, nullable=False)
    fully_qualified_name: Mapped[str] = mapped_column(String, nullable=False)
    check_types: Mapped[str] = mapped_column(
        Text, default='["schema", "freshness"]', nullable=False
    )
    freshness_sla_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_observed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    connection: Mapped[ConnectionModel] = relationship(back_populates="tables")
    snapshots: Mapped[list[SchemaSnapshotModel]] = relationship(
        back_populates="table", cascade="all, delete-orphan"
    )
    anomalies: Mapped[list[AnomalyModel]] = relationship(
        back_populates="table", cascade="all, delete-orphan"
    )


class SchemaSnapshotModel(Base):
    __tablename__ = "schema_snapshots"
    __table_args__ = (
        Index("idx_snapshots_table_id", "table_id", "captured_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("monitored_tables.id", ondelete="CASCADE"), nullable=False
    )
    columns: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    table: Mapped[MonitoredTableModel] = relationship(back_populates="snapshots")


class AnomalyModel(Base):
    __tablename__ = "anomalies"
    __table_args__ = (
        Index("idx_anomalies_table_type", "table_id", "type", "detected_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("monitored_tables.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    table: Mapped[MonitoredTableModel] = relationship(back_populates="anomalies")
    incident: Mapped[IncidentModel | None] = relationship(back_populates="anomaly")


class IncidentModel(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        Index("idx_incidents_status", "status", "severity", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    anomaly_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("anomalies.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String, default="open", nullable=False)
    diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)
    blast_radius: Mapped[str | None] = mapped_column(Text, nullable=True)
    remediation: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    dismiss_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    report: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    anomaly: Mapped[AnomalyModel] = relationship(back_populates="incident")


class LineageEdgeModel(Base):
    __tablename__ = "lineage_edges"
    __table_args__ = (
        Index("idx_lineage_source", "source_table"),
        Index("idx_lineage_target", "target_table"),
        Index("uq_lineage_edge", "source_table", "target_table", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_table: Mapped[str] = mapped_column(String, nullable=False)
    target_table: Mapped[str] = mapped_column(String, nullable=False)
    relationship_type: Mapped[str] = mapped_column(String, default="direct", nullable=False)
    query_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# Pydantic Schemas (API request/response)
# ---------------------------------------------------------------------------


class ConnectionCreate(BaseModel):
    name: str
    dialect: str
    connection_uri: str


class ConnectionUpdate(BaseModel):
    name: str | None = None
    dialect: str | None = None
    connection_uri: str | None = None
    is_active: bool | None = None


class ConnectionResponse(BaseModel):
    id: int
    name: str
    dialect: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TableCreate(BaseModel):
    connection_id: int
    schema_name: str
    table_name: str
    check_types: list[str] = Field(default=["schema", "freshness"])
    freshness_sla_minutes: int | None = None


class TableUpdate(BaseModel):
    check_types: list[str] | None = None
    freshness_sla_minutes: int | None = None


class TableResponse(BaseModel):
    id: int
    connection_id: int
    schema_name: str
    table_name: str
    fully_qualified_name: str
    check_types: list[str]
    freshness_sla_minutes: int | None
    last_observed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, obj: MonitoredTableModel) -> TableResponse:
        return cls(
            id=obj.id,
            connection_id=obj.connection_id,
            schema_name=obj.schema_name,
            table_name=obj.table_name,
            fully_qualified_name=obj.fully_qualified_name,
            check_types=json.loads(obj.check_types),
            freshness_sla_minutes=obj.freshness_sla_minutes,
            last_observed_at=obj.last_observed_at,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )


class AnomalyResponse(BaseModel):
    id: int
    table_id: int
    type: str
    severity: str
    detail: dict[str, Any]
    detected_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, obj: AnomalyModel) -> AnomalyResponse:
        return cls(
            id=obj.id,
            table_id=obj.table_id,
            type=obj.type,
            severity=obj.severity,
            detail=json.loads(obj.detail),
            detected_at=obj.detected_at,
        )


class IncidentResponse(BaseModel):
    id: int
    anomaly_id: int
    status: str
    diagnosis: dict[str, Any] | None
    blast_radius: list[str] | None
    remediation: dict[str, Any] | None
    severity: str
    resolved_at: datetime | None
    resolved_by: str | None
    dismiss_reason: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, obj: IncidentModel) -> IncidentResponse:
        return cls(
            id=obj.id,
            anomaly_id=obj.anomaly_id,
            status=obj.status,
            diagnosis=json.loads(obj.diagnosis) if obj.diagnosis else None,
            blast_radius=json.loads(obj.blast_radius) if obj.blast_radius else None,
            remediation=json.loads(obj.remediation) if obj.remediation else None,
            severity=obj.severity,
            resolved_at=obj.resolved_at,
            resolved_by=obj.resolved_by,
            dismiss_reason=obj.dismiss_reason,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )


class IncidentApprove(BaseModel):
    note: str | None = None


class IncidentDismiss(BaseModel):
    reason: str


# Agent data classes

class Recommendation(BaseModel):
    action: str
    description: str
    sql: str | None = None
    priority: int = 1


class Diagnosis(BaseModel):
    root_cause: str
    root_cause_table: str
    blast_radius: list[str]
    severity: str
    confidence: float
    recommendations: list[Recommendation]


class Remediation(BaseModel):
    actions: list[dict[str, Any]]
    summary: str
    generated_at: datetime


class BlastRadiusResponse(BaseModel):
    table: str
    affected_tables: list[dict[str, Any]]
    total_affected: int
    max_depth: int


class StatsResponse(BaseModel):
    health_score: float
    total_tables: int
    healthy_tables: int
    open_incidents: int
    critical_incidents: int
    anomalies_24h: int
    avg_resolution_time_minutes: float | None


# Discovery schemas (transient — not persisted to DB)


class TableProposal(BaseModel):
    """A single table proposed for monitoring by the Investigator."""
    schema_name: str
    table_name: str
    fully_qualified_name: str
    role: str
    columns: list[dict[str, Any]]
    recommended_checks: list[str]
    suggested_sla_minutes: int | None
    reasoning: str
    skip: bool


class TableDelta(BaseModel):
    """A change detected during warehouse rediscovery."""
    action: str
    schema_name: str
    table_name: str
    fully_qualified_name: str
    proposal: TableProposal | None = None


class DiscoveryReport(BaseModel):
    """Complete discovery output for a warehouse connection."""
    connection_id: int
    connection_name: str
    schemas_found: list[str]
    total_tables: int
    proposals: list[TableProposal]
    concerns: list[str]
    generated_at: datetime


class TableSelectionItem(BaseModel):
    """A single table the user chose to monitor from a discovery report."""
    schema_name: str
    table_name: str
    check_types: list[str] = Field(default=["schema", "freshness"])
    freshness_sla_minutes: int | None = None


class DiscoveryConfirm(BaseModel):
    """User's selection from a discovery report."""
    table_selections: list[TableSelectionItem]


# Incident report schemas


class AnomalyDetail(BaseModel):
    """Anomaly section of an incident report."""
    type: str
    table: str
    detected_at: datetime
    changes: list[dict[str, Any]]


class RootCauseDetail(BaseModel):
    """Root cause section of an incident report."""
    explanation: str
    source_table: str
    confidence: float


class BlastRadiusDetail(BaseModel):
    """Blast radius section of an incident report."""
    total_affected: int
    affected_tables: list[str]


class RecommendedAction(BaseModel):
    """A single recommended action in an incident report."""
    action: str
    description: str
    priority: int
    status: str


class TimelineEvent(BaseModel):
    """A single event in the incident timeline."""
    timestamp: datetime
    event: str


class IncidentReport(BaseModel):
    """Structured incident report for user consumption."""
    incident_id: int
    title: str
    severity: str
    status: str
    generated_at: datetime
    summary: str
    anomaly_details: AnomalyDetail
    root_cause: RootCauseDetail
    blast_radius: BlastRadiusDetail
    recommended_actions: list[RecommendedAction]
    timeline: list[TimelineEvent]
