"""Orchestrator — state machine managing the anomaly→incident lifecycle."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from aegis.agents.architect import Architect
from aegis.agents.executor import Executor
from aegis.agents.report_generator import ReportGenerator
from aegis.core.models import AnomalyModel, IncidentModel, MonitoredTableModel, Remediation

logger = logging.getLogger("aegis.orchestrator")


class Orchestrator:
    """Coordinates the incident lifecycle: detection → diagnosis → remediation."""

    def __init__(self, architect: Architect, executor: Executor, notifier=None):
        self.architect = architect
        self.executor = executor
        self.notifier = notifier

    def handle_anomaly(self, anomaly: AnomalyModel, db: Session) -> IncidentModel:
        """Process a detected anomaly through the full incident pipeline."""

        # 1. Deduplication — check for open incident on same table + type
        existing = self._find_open_incident(anomaly.table_id, anomaly.type, db)
        if existing:
            logger.info(
                "Merging anomaly %d into existing incident %d",
                anomaly.id,
                existing.id,
            )
            return self._merge_anomaly(existing, anomaly, db)

        # 2. Create incident
        incident = IncidentModel(
            anomaly_id=anomaly.id,
            status="investigating",
            severity=anomaly.severity,
        )
        db.add(incident)
        db.flush()

        logger.info(
            "Created incident %d for anomaly %d (type=%s, severity=%s)",
            incident.id,
            anomaly.id,
            anomaly.type,
            anomaly.severity,
        )

        # 3. Dispatch to Architect for root-cause analysis
        try:
            diagnosis = self.architect.analyze(anomaly, db)
            incident.diagnosis = diagnosis.model_dump_json()
            incident.blast_radius = json.dumps(diagnosis.blast_radius)
            incident.severity = diagnosis.severity
        except Exception:
            logger.exception("Architect analysis failed for incident %d", incident.id)

        # 4. Dispatch to Executor for remediation recommendation
        try:
            if incident.diagnosis:
                from aegis.core.models import Diagnosis

                diag = Diagnosis.model_validate_json(incident.diagnosis)
                remediation = self.executor.prepare(anomaly, diag)
                incident.remediation = remediation.model_dump_json()
        except Exception:
            logger.exception("Executor preparation failed for incident %d", incident.id)

        # 5. Update status
        incident.status = "pending_review"

        # 6. Generate incident report
        try:
            table = db.get(MonitoredTableModel, anomaly.table_id)
            diag_obj = None
            if incident.diagnosis:
                diag_obj = Diagnosis.model_validate_json(incident.diagnosis)
            remed_obj = None
            if incident.remediation:
                remed_obj = Remediation.model_validate_json(incident.remediation)

            generator = ReportGenerator()
            report = generator.generate(incident, anomaly, table, diag_obj, remed_obj)
            incident.report = report.model_dump_json()
        except Exception:
            logger.exception("Report generation failed for incident %d", incident.id)

        incident.updated_at = datetime.now(timezone.utc)
        db.flush()

        # 7. Notify dashboard
        if self.notifier:
            self.notifier.broadcast(
                "incident.created",
                {"incident_id": incident.id, "severity": incident.severity},
            )

        return incident

    def _find_open_incident(
        self, table_id: int, anomaly_type: str, db: Session
    ) -> IncidentModel | None:
        """Check for an existing open incident for the same table + anomaly type."""
        stmt = (
            select(IncidentModel)
            .join(AnomalyModel)
            .where(AnomalyModel.table_id == table_id)
            .where(AnomalyModel.type == anomaly_type)
            .where(IncidentModel.status.in_(["open", "investigating", "pending_review"]))
            .order_by(IncidentModel.created_at.desc())
            .limit(1)
        )
        return db.execute(stmt).scalar_one_or_none()

    def _merge_anomaly(
        self, incident: IncidentModel, anomaly: AnomalyModel, db: Session
    ) -> IncidentModel:
        """Merge a new anomaly into an existing open incident."""
        # Update severity if the new anomaly is more severe
        severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        if severity_rank.get(anomaly.severity, 0) > severity_rank.get(incident.severity, 0):
            incident.severity = anomaly.severity

        incident.updated_at = datetime.now(timezone.utc)
        db.flush()

        if self.notifier:
            self.notifier.broadcast(
                "incident.updated",
                {"incident_id": incident.id, "severity": incident.severity},
            )

        return incident
