"""Ties extraction, guardrails, deterministic search/relaxation, ranking, and
explanation together into a single query -> SearchResponse flow (US-004).

extract_fn/clarify_fn are injectable so this can be unit-tested without a
live LLM call (see tests/test_orchestrator.py) while production code (the
FastAPI server) uses the real Strands-agent-backed defaults.
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from car_search.agent import ask_clarifying_question, extract_filters, needs_clarification
from car_search.config import TOP_K
from car_search.dataset import search_full_dataset
from car_search.explanation import build_explanation
from car_search.guardrails import detect_contradiction
from car_search.models import Listing, SearchFilters
from car_search.relaxation import SearchFn, relax_and_search

ExtractFn = Callable[[str], SearchFilters]
ClarifyFn = Callable[[str], str]


class SearchResponse(BaseModel):
    filters: SearchFilters
    results: list[Listing]
    explanation: str
    relaxed_fields: list[str] | None = None
    clarifying_question: str | None = None


def rank_and_cap(listings: list[Listing], top_k: int = TOP_K) -> list[Listing]:
    """Deterministic ranking: ascending price, then mileage, then newer year first.

    No LLM is involved in ranking (FR-8).
    """
    return sorted(listings, key=lambda listing: (listing.price, listing.mileage, -listing.year))[:top_k]


def run_search(
    query: str,
    *,
    extract_fn: ExtractFn = extract_filters,
    clarify_fn: ClarifyFn = ask_clarifying_question,
    search_fn: SearchFn = search_full_dataset,
    skip_clarify: bool = False,
) -> SearchResponse:
    """Run the full query -> results pipeline.

    skip_clarify=True represents a follow-up call after a clarifying
    question went unanswered (US-007): the clarify path is skipped and a
    best-effort search runs on whatever filters were extracted.
    """
    filters = extract_fn(query)
    contradiction_note = detect_contradiction(query)

    if not skip_clarify and needs_clarification(filters):
        question = clarify_fn(query)
        return SearchResponse(
            filters=filters,
            results=[],
            explanation="This query is too vague to search meaningfully; asked a clarifying question instead.",
            relaxed_fields=None,
            clarifying_question=question,
        )

    result, _final_filters, steps = relax_and_search(filters, search_fn)
    ranked = rank_and_cap(result.matches)
    explanation = build_explanation(filters, ranked, steps, contradiction_note)

    return SearchResponse(
        filters=filters,
        results=ranked,
        explanation=explanation,
        relaxed_fields=[step.describe() for step in steps] or None,
        clarifying_question=None,
    )
