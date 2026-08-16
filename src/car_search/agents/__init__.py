"""Agents: the Strands agent wiring and the extraction guardrails that make
agent output trustworthy.
"""

from car_search.agents.agent import (
    ask_clarifying_question,
    build_clarify_agent,
    build_extraction_agent,
    build_model,
    extract_filters,
    needs_clarification,
)
from car_search.agents.guardrails import (
    apply_price_shorthand_fallback,
    apply_synonym_fallback,
    detect_contradiction,
    safe_parse_search_filters,
)

__all__ = [
    "apply_price_shorthand_fallback",
    "apply_synonym_fallback",
    "ask_clarifying_question",
    "build_clarify_agent",
    "build_extraction_agent",
    "build_model",
    "detect_contradiction",
    "extract_filters",
    "needs_clarification",
    "safe_parse_search_filters",
]
