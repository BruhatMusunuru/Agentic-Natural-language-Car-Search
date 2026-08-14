"""Tests for agent construction that don't require a real Anthropic API key."""

from __future__ import annotations

from rag_assistant import agent, data_store


def test_system_prompt_grounds_dataset_facts():
    prompt = agent.build_system_prompt()
    summary = data_store.dataset_summary()
    assert str(summary["listing_count"]) in prompt
    assert summary["first_seen"] in prompt
    assert summary["last_seen"] in prompt


def test_build_agent_requires_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    try:
        agent.build_agent()
    except RuntimeError as exc:
        assert "ANTHROPIC_API_KEY" in str(exc)
    else:
        raise AssertionError("expected RuntimeError when no API key is configured")
