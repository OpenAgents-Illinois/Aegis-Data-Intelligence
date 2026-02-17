"""Executor agent — formats remediation plans for human review."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from aegis.core.models import AnomalyModel, Diagnosis, Remediation

logger = logging.getLogger("aegis.executor")


class Executor:
    """Generates actionable remediation plans from Architect diagnoses."""

    def prepare(self, anomaly: AnomalyModel, diagnosis: Diagnosis) -> Remediation:
        """Create a remediation plan from an anomaly and its diagnosis."""
        actions = []

        for rec in diagnosis.recommendations:
            action = {
                "type": rec.action,
                "description": rec.description,
                "priority": rec.priority,
            }
            if rec.sql:
                action["sql"] = rec.sql
                action["status"] = "pending_approval"
            else:
                action["status"] = "manual"
            actions.append(action)

        summary = self._format_summary(anomaly, diagnosis)

        return Remediation(
            actions=actions,
            summary=summary,
            generated_at=datetime.now(timezone.utc),
        )

    def _format_summary(self, anomaly: AnomalyModel, diagnosis: Diagnosis) -> str:
        """Build a human-readable incident summary."""
        detail = json.loads(anomaly.detail) if isinstance(anomaly.detail, str) else anomaly.detail

        lines = [
            f"**Incident: {anomaly.type.replace('_', ' ').title()}**",
            f"Severity: {diagnosis.severity.upper()}",
            f"Confidence: {diagnosis.confidence:.0%}",
            "",
            f"**Root Cause:** {diagnosis.root_cause}",
            f"**Source Table:** {diagnosis.root_cause_table}",
        ]

        if diagnosis.blast_radius:
            lines.append(f"**Blast Radius:** {len(diagnosis.blast_radius)} downstream tables affected")
            for table in diagnosis.blast_radius[:10]:
                lines.append(f"  - {table}")
            if len(diagnosis.blast_radius) > 10:
                lines.append(f"  ... and {len(diagnosis.blast_radius) - 10} more")

        lines.append("")
        lines.append(f"**Recommended Actions:** {len(diagnosis.recommendations)}")
        for i, rec in enumerate(diagnosis.recommendations, 1):
            lines.append(f"  {i}. [{rec.action}] {rec.description}")

        return "\n".join(lines)
