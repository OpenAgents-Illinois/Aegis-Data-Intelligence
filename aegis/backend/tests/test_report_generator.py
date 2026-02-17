"""Tests for ReportGenerator — incident report assembly."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

from aegis.agents.report_generator import ReportGenerator
from aegis.core.models import (
    AnomalyModel,
    Diagnosis,
    IncidentModel,
    MonitoredTableModel,
    Recommendation,
    Remediation,
)


def _make_anomaly(table_id=1, anomaly_type="schema_drift"):
    anomaly = MagicMock(spec=AnomalyModel)
    anomaly.id = 10
    anomaly.table_id = table_id
    anomaly.type = anomaly_type
    anomaly.severity = "critical"
    anomaly.detected_at = datetime(2026, 2, 17, 15, 0, tzinfo=timezone.utc)
    if anomaly_type == "schema_drift":
        anomaly.detail = json.dumps([{"change": "column_deleted", "column": "price"}])
    else:
        anomaly.detail = json.dumps({"sla_minutes": 60, "minutes_overdue": 30})
    return anomaly


def _make_table():
    table = MagicMock(spec=MonitoredTableModel)
    table.id = 1
    table.fully_qualified_name = "public.orders"
    table.schema_name = "public"
    table.table_name = "orders"
    return table


def _make_incident(anomaly_id=10):
    incident = MagicMock(spec=IncidentModel)
    incident.id = 42
    incident.anomaly_id = anomaly_id
    incident.status = "pending_review"
    incident.severity = "critical"
    incident.created_at = datetime(2026, 2, 17, 15, 0, 1, tzinfo=timezone.utc)
    return incident


def _make_diagnosis():
    return Diagnosis(
        root_cause="Column deleted upstream",
        root_cause_table="staging.orders",
        blast_radius=["analytics.daily_revenue", "analytics.customer_ltv"],
        severity="critical",
        confidence=0.85,
        recommendations=[
            Recommendation(
                action="revert_schema",
                description="Revert column deletion",
                priority=1,
            ),
        ],
    )


def _make_remediation():
    return Remediation(
        actions=[
            {
                "type": "revert_schema",
                "description": "Revert column deletion",
                "priority": 1,
                "status": "pending_approval",
            }
        ],
        summary="Incident: Schema Drift\nSeverity: CRITICAL",
        generated_at=datetime(2026, 2, 17, 15, 0, 2, tzinfo=timezone.utc),
    )


class TestReportGenerator:
    def test_generates_report_with_all_sections(self):
        gen = ReportGenerator()
        report = gen.generate(
            incident=_make_incident(),
            anomaly=_make_anomaly(),
            table=_make_table(),
            diagnosis=_make_diagnosis(),
            remediation=_make_remediation(),
        )
        assert report.incident_id == 42
        assert "Schema Drift" in report.title
        assert "public.orders" in report.title
        assert report.severity == "critical"
        assert report.anomaly_details.type == "schema_drift"
        assert report.root_cause.confidence == 0.85
        assert report.blast_radius.total_affected == 2
        assert len(report.recommended_actions) == 1
        assert len(report.timeline) >= 3  # detected, created, diagnosed at minimum

    def test_generates_report_without_diagnosis(self):
        gen = ReportGenerator()
        report = gen.generate(
            incident=_make_incident(),
            anomaly=_make_anomaly(),
            table=_make_table(),
            diagnosis=None,
            remediation=None,
        )
        assert report.root_cause.explanation == "Analysis unavailable"
        assert report.root_cause.confidence == 0.0
        assert report.blast_radius.total_affected == 0
        assert report.recommended_actions == []

    def test_generates_report_for_freshness_breach(self):
        gen = ReportGenerator()
        report = gen.generate(
            incident=_make_incident(),
            anomaly=_make_anomaly(anomaly_type="freshness_breach"),
            table=_make_table(),
            diagnosis=_make_diagnosis(),
            remediation=_make_remediation(),
        )
        assert "Freshness Breach" in report.title
        assert report.anomaly_details.type == "freshness_breach"

    def test_summary_mentions_key_facts(self):
        gen = ReportGenerator()
        report = gen.generate(
            incident=_make_incident(),
            anomaly=_make_anomaly(),
            table=_make_table(),
            diagnosis=_make_diagnosis(),
            remediation=_make_remediation(),
        )
        assert "public.orders" in report.summary
        assert "critical" in report.summary.lower()
