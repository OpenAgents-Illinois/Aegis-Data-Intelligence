"""Architect agent — LLM-powered root-cause analysis with fallback."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from aegis.core.models import (
    AnomalyModel,
    Diagnosis,
    MonitoredTableModel,
    Recommendation,
)
from aegis.services.llm import llm_client

logger = logging.getLogger("aegis.architect")


class Architect:
    """Uses GPT-4 to diagnose root causes of data anomalies."""

    def __init__(self, lineage_graph=None):
        self.lineage = lineage_graph

    def analyze(self, anomaly: AnomalyModel, db: Session) -> Diagnosis:
        """Perform root-cause analysis on an anomaly."""
        # Build context for the LLM
        prompt = self._build_prompt(anomaly, db)

        # Try LLM diagnosis
        result = llm_client.diagnose(prompt)
        if result is not None:
            try:
                return self._parse_diagnosis(result)
            except Exception:
                logger.warning("Failed to parse LLM diagnosis, falling back to rules")

        # Fallback to rule-based
        return self._rule_based_fallback(anomaly, db)

    def _build_prompt(self, anomaly: AnomalyModel, db: Session) -> str:
        """Construct the LLM prompt with anomaly, lineage, and history context."""
        detail = json.loads(anomaly.detail)
        table = db.get(MonitoredTableModel, anomaly.table_id)
        table_name = table.fully_qualified_name if table else f"table_id={anomaly.table_id}"

        sections = []

        # Anomaly section
        sections.append(f"## Anomaly\nType: {anomaly.type}\nTable: {table_name}")
        if anomaly.type == "schema_drift":
            changes_str = "\n".join(
                f"- {c.get('change', 'unknown')}: column `{c.get('column', '?')}`"
                + (f" type {c.get('old_type')} → {c.get('new_type')}" if c.get("old_type") else "")
                for c in detail
            ) if isinstance(detail, list) else json.dumps(detail, indent=2)
            sections.append(f"Changes:\n{changes_str}")
        else:
            sections.append(f"Detail: {json.dumps(detail, indent=2)}")

        sections.append(f"Detected: {anomaly.detected_at.isoformat()}")

        # Lineage section
        if self.lineage:
            try:
                upstream = self.lineage.get_upstream(table_name, depth=3)
                downstream = self.lineage.get_downstream(table_name, depth=3)

                if upstream or downstream:
                    lineage_parts = []
                    if upstream:
                        lineage_parts.append(
                            "Upstream: " + " → ".join(n["table"] for n in upstream)
                        )
                    lineage_parts.append(table_name)
                    if downstream:
                        lineage_parts.append(
                            "Downstream: " + ", ".join(n["table"] for n in downstream)
                        )
                    sections.append(f"## Lineage\n" + " → ".join(lineage_parts))
            except Exception:
                logger.debug("Could not load lineage for prompt")

        # Recent history
        history_stmt = (
            select(AnomalyModel)
            .where(AnomalyModel.table_id == anomaly.table_id)
            .where(AnomalyModel.id != anomaly.id)
            .order_by(AnomalyModel.detected_at.desc())
            .limit(5)
        )
        recent = db.execute(history_stmt).scalars().all()
        if recent:
            history_lines = [
                f"- {a.type} ({a.severity}) at {a.detected_at.isoformat()}"
                for a in recent
            ]
            sections.append(f"## Recent History\n" + "\n".join(history_lines))

        return "\n\n".join(sections)

    def _parse_diagnosis(self, result: dict[str, Any]) -> Diagnosis:
        """Parse the LLM response into a Diagnosis object."""
        recommendations = [
            Recommendation(
                action=r["action"],
                description=r["description"],
                sql=r.get("sql"),
                priority=r.get("priority", 1),
            )
            for r in result.get("recommendations", [])
        ]

        return Diagnosis(
            root_cause=result["root_cause"],
            root_cause_table=result["root_cause_table"],
            blast_radius=result.get("blast_radius", []),
            severity=result.get("severity", "medium"),
            confidence=result.get("confidence", 0.5),
            recommendations=recommendations,
        )

    def _rule_based_fallback(self, anomaly: AnomalyModel, db: Session) -> Diagnosis:
        """Deterministic fallback when LLM is unavailable."""
        table = db.get(MonitoredTableModel, anomaly.table_id)
        table_name = table.fully_qualified_name if table else "unknown"

        blast_radius: list[str] = []
        if self.lineage:
            try:
                downstream = self.lineage.get_downstream(table_name, depth=10)
                blast_radius = [n["table"] for n in downstream]
            except Exception:
                pass

        return Diagnosis(
            root_cause="Automated analysis unavailable. Manual investigation required.",
            root_cause_table=table_name,
            blast_radius=blast_radius,
            severity=anomaly.severity,
            confidence=0.0,
            recommendations=[
                Recommendation(
                    action="investigate",
                    description="Check upstream tables for recent changes",
                    priority=1,
                )
            ],
        )
