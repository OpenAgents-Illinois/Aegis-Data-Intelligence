"""ReportGenerator — assembles structured incident reports from pipeline data."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from aegis.core.models import (
    AnomalyDetail,
    AnomalyModel,
    BlastRadiusDetail,
    Diagnosis,
    IncidentModel,
    IncidentReport,
    MonitoredTableModel,
    RecommendedAction,
    Remediation,
    RootCauseDetail,
    TimelineEvent,
)

logger = logging.getLogger("aegis.report_generator")

# Mapping from anomaly type to human-readable title fragment
_TYPE_TITLES = {
    "schema_drift": "Schema Drift",
    "freshness_violation": "Freshness Breach",
    "freshness_breach": "Freshness Breach",
}


class ReportGenerator:
    """Transforms incident pipeline data into a structured IncidentReport."""

    def generate(
        self,
        incident: IncidentModel,
        anomaly: AnomalyModel,
        table: MonitoredTableModel,
        diagnosis: Diagnosis | None,
        remediation: Remediation | None,
    ) -> IncidentReport:
        """Build a complete incident report from pipeline outputs."""
        now = datetime.now(timezone.utc)
        table_name = table.fully_qualified_name
        type_label = _TYPE_TITLES.get(anomaly.type, anomaly.type.replace("_", " ").title())
        title = f"{type_label} on {table_name}"

        anomaly_details = self._build_anomaly_details(anomaly, table_name)
        root_cause = self._build_root_cause(diagnosis, table_name)
        blast_radius = self._build_blast_radius(diagnosis)
        actions = self._build_actions(remediation)
        timeline = self._build_timeline(anomaly, incident, diagnosis, remediation)
        summary = self._build_summary(
            type_label, table_name, incident.severity, root_cause, blast_radius
        )

        return IncidentReport(
            incident_id=incident.id,
            title=title,
            severity=incident.severity,
            status=incident.status,
            generated_at=now,
            summary=summary,
            anomaly_details=anomaly_details,
            root_cause=root_cause,
            blast_radius=blast_radius,
            recommended_actions=actions,
            timeline=timeline,
        )

    def _build_anomaly_details(
        self, anomaly: AnomalyModel, table_name: str
    ) -> AnomalyDetail:
        detail = anomaly.detail
        if isinstance(detail, str):
            detail = json.loads(detail)
        changes = detail if isinstance(detail, list) else [detail]

        return AnomalyDetail(
            type=anomaly.type,
            table=table_name,
            detected_at=anomaly.detected_at,
            changes=changes,
        )

    def _build_root_cause(
        self, diagnosis: Diagnosis | None, table_name: str
    ) -> RootCauseDetail:
        if diagnosis is None:
            return RootCauseDetail(
                explanation="Analysis unavailable",
                source_table=table_name,
                confidence=0.0,
            )
        return RootCauseDetail(
            explanation=diagnosis.root_cause,
            source_table=diagnosis.root_cause_table,
            confidence=diagnosis.confidence,
        )

    def _build_blast_radius(self, diagnosis: Diagnosis | None) -> BlastRadiusDetail:
        if diagnosis is None:
            return BlastRadiusDetail(total_affected=0, affected_tables=[])
        return BlastRadiusDetail(
            total_affected=len(diagnosis.blast_radius),
            affected_tables=diagnosis.blast_radius,
        )

    def _build_actions(self, remediation: Remediation | None) -> list[RecommendedAction]:
        if remediation is None:
            return []
        return [
            RecommendedAction(
                action=a["type"],
                description=a["description"],
                priority=a.get("priority", 1),
                status=a.get("status", "manual"),
            )
            for a in remediation.actions
        ]

    def _build_timeline(
        self,
        anomaly: AnomalyModel,
        incident: IncidentModel,
        diagnosis: Diagnosis | None,
        remediation: Remediation | None,
    ) -> list[TimelineEvent]:
        events: list[TimelineEvent] = []

        type_label = _TYPE_TITLES.get(anomaly.type, anomaly.type)
        events.append(TimelineEvent(
            timestamp=anomaly.detected_at,
            event=f"Anomaly detected: {type_label} on {anomaly.type}",
        ))

        events.append(TimelineEvent(
            timestamp=incident.created_at,
            event=f"Incident created (severity: {incident.severity})",
        ))

        if diagnosis is not None:
            events.append(TimelineEvent(
                timestamp=incident.created_at,
                event=f"Root cause identified: {diagnosis.root_cause} (confidence: {diagnosis.confidence:.0%})",
            ))

        if remediation is not None:
            events.append(TimelineEvent(
                timestamp=remediation.generated_at,
                event=f"Remediation plan generated: {len(remediation.actions)} action(s)",
            ))

        return events

    def _build_summary(
        self,
        type_label: str,
        table_name: str,
        severity: str,
        root_cause: RootCauseDetail,
        blast_radius: BlastRadiusDetail,
    ) -> str:
        parts = [f"{type_label} detected on {table_name} ({severity} severity)."]

        if root_cause.confidence > 0:
            parts.append(f"Root cause: {root_cause.explanation}.")
        else:
            parts.append("Root cause analysis unavailable.")

        if blast_radius.total_affected > 0:
            parts.append(
                f"{blast_radius.total_affected} downstream table(s) affected."
            )

        return " ".join(parts)
