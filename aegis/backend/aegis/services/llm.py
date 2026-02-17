"""OpenAI client wrapper with retry logic and fallback."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from openai import OpenAI, APIError, APITimeoutError, RateLimitError

from aegis.config import settings

logger = logging.getLogger("aegis.llm")

DIAGNOSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "root_cause": {"type": "string"},
        "root_cause_table": {"type": "string"},
        "blast_radius": {"type": "array", "items": {"type": "string"}},
        "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "description": {"type": "string"},
                    "sql": {"type": ["string", "null"]},
                    "priority": {"type": "integer"},
                },
                "required": ["action", "description", "priority"],
            },
        },
    },
    "required": [
        "root_cause",
        "root_cause_table",
        "blast_radius",
        "severity",
        "confidence",
        "recommendations",
    ],
}

SYSTEM_PROMPT = """You are Aegis Architect, a data reliability agent. You analyze data \
anomalies and perform root-cause analysis. You have access to the table's \
lineage graph and historical anomaly data.

Always respond with structured JSON matching the Diagnosis schema.
Consider: What upstream change could have caused this? How far does the \
impact reach downstream? What's the simplest fix?"""


class LLMClient:
    """Wrapper around OpenAI with retry and structured output."""

    def __init__(self):
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            api_key = settings.openai_api_key
            if not api_key:
                raise ValueError("OPENAI_API_KEY is not configured")
            self._client = OpenAI(api_key=api_key)
        return self._client

    def diagnose(self, prompt: str) -> dict[str, Any] | None:
        """Call GPT-4 with structured output for root-cause analysis.

        Returns parsed diagnosis dict or None if all retries fail.
        """
        backoff_delays = [2, 4, 8]

        for attempt, delay in enumerate(backoff_delays):
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    timeout=30,
                )

                content = response.choices[0].message.content
                if content is None:
                    logger.warning("Empty response from LLM (attempt %d)", attempt + 1)
                    continue

                parsed = json.loads(content)
                return parsed

            except (APITimeoutError, APIError) as exc:
                logger.warning(
                    "LLM call failed (attempt %d/%d): %s",
                    attempt + 1,
                    len(backoff_delays),
                    exc,
                )
                if attempt < len(backoff_delays) - 1:
                    time.sleep(delay)

            except RateLimitError as exc:
                retry_after = getattr(exc, "retry_after", delay)
                logger.warning("Rate limited, waiting %s seconds", retry_after)
                time.sleep(float(retry_after))

            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning("Invalid LLM response (attempt %d): %s", attempt + 1, exc)
                if attempt < len(backoff_delays) - 1:
                    time.sleep(delay)

        logger.error("All LLM retries exhausted")
        return None


llm_client = LLMClient()
