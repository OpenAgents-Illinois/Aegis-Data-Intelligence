"""Tests for Investigator prompt templates."""

from aegis.agents.investigator_prompts import INVESTIGATOR_SYSTEM, investigator_prompt


def test_system_prompt_contains_classification_rules():
    assert "fact" in INVESTIGATOR_SYSTEM
    assert "dimension" in INVESTIGATOR_SYSTEM
    assert "staging" in INVESTIGATOR_SYSTEM
    assert "skip" in INVESTIGATOR_SYSTEM


def test_prompt_template_formats_correctly():
    messages = investigator_prompt.format_messages(
        connection_name="test-warehouse",
        dialect="postgresql",
        connection_id=1,
        agent_scratchpad=[],
    )
    assert len(messages) >= 2
    assert "test-warehouse" in messages[1].content
    assert "postgresql" in messages[1].content
