"""Sentinel agents — deterministic anomaly detection (no LLM)."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from aegis.core.connectors import WarehouseConnector
from aegis.core.models import (
    AnomalyModel,
    MonitoredTableModel,
    SchemaSnapshotModel,
)

logger = logging.getLogger("aegis.sentinel")


class SchemaSentinel:
    """Detects schema drift by comparing INFORMATION_SCHEMA snapshots."""

    def inspect(
        self, table: MonitoredTableModel, connector: WarehouseConnector, db: Session
    ) -> AnomalyModel | None:
        # 1. Fetch current schema from warehouse
        try:
            current_columns = connector.fetch_schema(table.schema_name, table.table_name)
        except Exception:
            logger.exception("Failed to fetch schema for %s", table.fully_qualified_name)
            return None

        # 2. Hash for O(1) drift detection
        columns_json = json.dumps(current_columns, sort_keys=True)
        current_hash = hashlib.sha256(columns_json.encode()).hexdigest()

        # 3. Get latest snapshot
        stmt = (
            select(SchemaSnapshotModel)
            .where(SchemaSnapshotModel.table_id == table.id)
            .order_by(SchemaSnapshotModel.captured_at.desc())
            .limit(1)
        )
        last_snapshot = db.execute(stmt).scalar_one_or_none()

        # 4. Store new snapshot
        new_snapshot = SchemaSnapshotModel(
            table_id=table.id,
            columns=columns_json,
            snapshot_hash=current_hash,
            captured_at=datetime.now(timezone.utc),
        )
        db.add(new_snapshot)
        db.flush()

        # 5. Compare
        if last_snapshot is None:
            logger.info("First snapshot for %s — no baseline to compare", table.fully_qualified_name)
            return None

        if last_snapshot.snapshot_hash == current_hash:
            return None  # No drift

        # 6. Compute diff
        old_columns = json.loads(last_snapshot.columns)
        changes = self._diff_schemas(old_columns, current_columns)
        severity = self._classify_severity(changes)

        logger.warning(
            "Schema drift detected on %s: %s (severity=%s)",
            table.fully_qualified_name,
            changes,
            severity,
        )

        anomaly = AnomalyModel(
            table_id=table.id,
            type="schema_drift",
            severity=severity,
            detail=json.dumps(changes),
            detected_at=datetime.now(timezone.utc),
        )
        db.add(anomaly)
        db.flush()
        return anomaly

    def _diff_schemas(
        self, old: list[dict], new: list[dict]
    ) -> list[dict]:
        """Compute specific changes between two column lists."""
        old_by_name = {c["name"]: c for c in old}
        new_by_name = {c["name"]: c for c in new}
        changes = []

        # Deleted columns
        for name in old_by_name:
            if name not in new_by_name:
                changes.append({"change": "column_deleted", "column": name, "old": old_by_name[name]})

        # Added columns
        for name in new_by_name:
            if name not in old_by_name:
                changes.append({
                    "change": "column_added",
                    "column": name,
                    "nullable": new_by_name[name].get("nullable", True),
                    "new": new_by_name[name],
                })

        # Type changes
        for name in old_by_name:
            if name in new_by_name:
                old_type = old_by_name[name].get("type")
                new_type = new_by_name[name].get("type")
                if old_type != new_type:
                    changes.append({
                        "change": "type_changed",
                        "column": name,
                        "old_type": old_type,
                        "new_type": new_type,
                    })

        return changes

    def _classify_severity(self, changes: list[dict]) -> str:
        """Classify overall severity from the most severe change."""
        severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        max_severity = "low"

        for change in changes:
            kind = change["change"]
            if kind == "column_deleted":
                sev = "critical"
            elif kind == "type_changed":
                sev = "critical"
            elif kind == "column_added":
                sev = "low" if change.get("nullable", True) else "medium"
            else:
                sev = "medium"

            if severity_rank.get(sev, 0) > severity_rank.get(max_severity, 0):
                max_severity = sev

        return max_severity


class FreshnessSentinel:
    """Detects when tables are not updated within their expected SLA."""

    def inspect(
        self, table: MonitoredTableModel, connector: WarehouseConnector, db: Session
    ) -> AnomalyModel | None:
        if not table.freshness_sla_minutes:
            return None

        try:
            last_update = connector.fetch_last_update_time(table.schema_name, table.table_name)
        except Exception:
            logger.exception("Failed to check freshness for %s", table.fully_qualified_name)
            return None

        if last_update is None:
            logger.warning("No timestamp found for %s", table.fully_qualified_name)
            return None

        now = datetime.now(timezone.utc)
        if last_update.tzinfo is None:
            last_update = last_update.replace(tzinfo=timezone.utc)

        minutes_since = (now - last_update).total_seconds() / 60

        if minutes_since <= table.freshness_sla_minutes:
            return None

        minutes_overdue = minutes_since - table.freshness_sla_minutes
        severity = self._classify_severity(minutes_since, table.freshness_sla_minutes)

        logger.warning(
            "Freshness violation on %s: %.0f min overdue (severity=%s)",
            table.fully_qualified_name,
            minutes_overdue,
            severity,
        )

        detail = {
            "last_update": last_update.isoformat(),
            "sla_minutes": table.freshness_sla_minutes,
            "minutes_overdue": round(minutes_overdue, 1),
        }

        anomaly = AnomalyModel(
            table_id=table.id,
            type="freshness_violation",
            severity=severity,
            detail=json.dumps(detail),
            detected_at=datetime.now(timezone.utc),
        )
        db.add(anomaly)
        db.flush()
        return anomaly

    def _classify_severity(self, minutes_since: float, sla: int) -> str:
        ratio = minutes_since / sla
        if ratio > 5:
            return "critical"
        elif ratio > 2:
            return "high"
        else:
            return "medium"
