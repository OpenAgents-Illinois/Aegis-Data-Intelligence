"""Tests for Architect agent — prompt construction, parsing, fallback."""

import json
from unittest.mock import MagicMock, patch

from aegis.agents.architect import Architect
from aegis.core.models import AnomalyModel


class TestArchitect:
    def test_fallback_when_llm_unavailable(self, db, sample_anomaly):
        """When LLM returns None, rule-based fallback is used."""
        with patch("aegis.agents.architect.llm_client") as mock_llm:
            mock_llm.diagnose.return_value = None

            architect = Architect(lineage_graph=None)
            diagnosis = architect.analyze(sample_anomaly, db)

            assert diagnosis.confidence == 0.0
            assert "Manual investigation" in diagnosis.root_cause
            assert len(diagnosis.recommendations) == 1
            assert diagnosis.recommendations[0].action == "investigate"

    def test_parses_valid_llm_response(self, db, sample_anomaly):
        """Valid LLM JSON is parsed into a Diagnosis."""
        llm_response = {
            "root_cause": "Upstream ETL schema change in staging_orders",
            "root_cause_table": "staging.orders",
            "blast_radius": ["analytics.daily_revenue", "analytics.customer_ltv"],
            "severity": "critical",
            "confidence": 0.85,
            "recommendations": [
                {
                    "action": "revert_schema",
                    "description": "Revert column type change",
                    "sql": "ALTER TABLE orders ALTER COLUMN price TYPE FLOAT",
                    "priority": 1,
                }
            ],
        }

        with patch("aegis.agents.architect.llm_client") as mock_llm:
            mock_llm.diagnose.return_value = llm_response

            architect = Architect(lineage_graph=None)
            diagnosis = architect.analyze(sample_anomaly, db)

            assert diagnosis.root_cause == "Upstream ETL schema change in staging_orders"
            assert diagnosis.confidence == 0.85
            assert len(diagnosis.blast_radius) == 2
            assert diagnosis.recommendations[0].sql is not None

    def test_prompt_includes_anomaly_details(self, db, sample_anomaly):
        """Prompt construction includes anomaly type and table info."""
        with patch("aegis.agents.architect.llm_client") as mock_llm:
            mock_llm.diagnose.return_value = None

            architect = Architect(lineage_graph=None)
            architect.analyze(sample_anomaly, db)

            # Check the prompt that was passed to LLM
            call_args = mock_llm.diagnose.call_args
            prompt = call_args[0][0]
            assert "schema_drift" in prompt
            assert "public.orders" in prompt

    def test_fallback_includes_blast_radius_from_lineage(self, db, sample_anomaly):
        """Rule-based fallback uses lineage graph for blast radius."""
        mock_lineage = MagicMock()
        mock_lineage.get_downstream.return_value = [
            {"table": "analytics.daily_revenue", "depth": 1, "confidence": 1.0},
        ]

        with patch("aegis.agents.architect.llm_client") as mock_llm:
            mock_llm.diagnose.return_value = None

            architect = Architect(lineage_graph=mock_lineage)
            diagnosis = architect.analyze(sample_anomaly, db)

            assert "analytics.daily_revenue" in diagnosis.blast_radius
