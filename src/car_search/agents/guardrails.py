"""Deterministic guardrails around LLM filter extraction.

These are pure-Python, regex-based safety nets that run alongside/after the
LLM extraction step (see agent.py::extract_filters). They exist so that
synonym mapping, unit normalization, contradiction detection, and
enum-hallucination handling are correct and unit-testable *without* needing
a live LLM call for every case -- the LLM is still the primary extractor,
but these fallbacks make the pipeline robust even when it misses something.
"""

from __future__ import annotations

import re
from typing import Any

from car_search.core import BodyType, FuelType, SearchFilters

# Natural-language synonym -> real enum code (US-008).
BODY_TYPE_SYNONYMS: dict[str, BodyType] = {
    "hatchback": BodyType.HATCH,
    "hatch": BodyType.HATCH,
    "truck": BodyType.TRUCKS,
    "pickup": BodyType.TRUCKS,
    "pick-up": BodyType.TRUCKS,
    "convertible": BodyType.CONVERT,
    "cabriolet": BodyType.CONVERT,
    "minivan": BodyType.VANS,
    "van": BodyType.VANS,
    "suv": BodyType.SUV,
    "sedan": BodyType.SEDAN,
    "coupe": BodyType.COUPE,
    "wagon": BodyType.WAGON,
    "estate": BodyType.WAGON,
}

FUEL_TYPE_SYNONYMS: dict[str, FuelType] = {
    "hybrid": FuelType.HYBRID,
    "gas-electric hybrid": FuelType.HYBRID,
    "electric": FuelType.ELECTRIC,
    "ev": FuelType.ELECTRIC,
    "diesel": FuelType.DIESEL,
    "flex fuel": FuelType.FLEXIBLE_FUEL,
    "flexible fuel": FuelType.FLEXIBLE_FUEL,
    "flex-fuel": FuelType.FLEXIBLE_FUEL,
    "gas": FuelType.GASOLINE,
    "gasoline": FuelType.GASOLINE,
    "petrol": FuelType.GASOLINE,
}

# Longer phrases must be matched before shorter substrings (e.g. "flex fuel"
# before "fuel" alone would never match, but this ordering keeps intent
# explicit and avoids "gas" matching inside "gas-electric").
_BODY_TYPE_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in sorted(BODY_TYPE_SYNONYMS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_FUEL_TYPE_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in sorted(FUEL_TYPE_SYNONYMS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

# "under 30k", "under $30,000", "less than 30k", "below $30k", "$30000 or less"
_PRICE_SHORTHAND_PATTERN = re.compile(
    r"(?:under|below|less than|no more than|<=?)\s*\$?\s*(\d[\d,]*)\s*(k)?",
    re.IGNORECASE,
)


def _parse_price_token(digits: str, k_suffix: str | None) -> float:
    value = float(digits.replace(",", ""))
    if k_suffix:
        value *= 1000
    return value


def apply_price_shorthand_fallback(query: str, filters: SearchFilters) -> SearchFilters:
    """Fill in price_max from shorthand phrasing if the LLM left it null."""
    if filters.price_max is not None:
        return filters
    match = _PRICE_SHORTHAND_PATTERN.search(query)
    if not match:
        return filters
    price = _parse_price_token(match.group(1), match.group(2))
    return filters.model_copy(update={"price_max": price})


def apply_synonym_fallback(query: str, filters: SearchFilters) -> SearchFilters:
    """Fill in body_type/fuel_type from known synonyms if the LLM left them null."""
    updates: dict[str, Any] = {}
    if filters.body_type is None:
        match = _BODY_TYPE_PATTERN.search(query)
        if match:
            updates["body_type"] = BODY_TYPE_SYNONYMS[match.group(1).lower()]
    if filters.fuel_type is None:
        match = _FUEL_TYPE_PATTERN.search(query)
        if match:
            updates["fuel_type"] = FUEL_TYPE_SYNONYMS[match.group(1).lower()]
    return filters.model_copy(update=updates) if updates else filters


def safe_parse_search_filters(data: dict[str, Any]) -> SearchFilters:
    """Parse a raw dict into SearchFilters, nulling out invalid enum values
    instead of raising -- a defensive layer for filter data that didn't come
    through the schema-constrained LLM structured-output path (US-008)."""
    cleaned = dict(data)
    if "body_type" in cleaned and cleaned["body_type"] is not None:
        try:
            BodyType(cleaned["body_type"])
        except ValueError:
            cleaned["body_type"] = None
    if "fuel_type" in cleaned and cleaned["fuel_type"] is not None:
        try:
            FuelType(cleaned["fuel_type"])
        except ValueError:
            cleaned["fuel_type"] = None
    return SearchFilters.model_validate(cleaned)


def detect_contradiction(query: str) -> str | None:
    """Detect contradictory body_type/fuel_type mentions in free text (US-009).

    Returns a human-readable note naming the conflicting values and which
    one wins (the last-mentioned/most specific one), or None if there's no
    contradiction.
    """
    for pattern, synonyms, label in (
        (_FUEL_TYPE_PATTERN, FUEL_TYPE_SYNONYMS, "fuel type"),
        (_BODY_TYPE_PATTERN, BODY_TYPE_SYNONYMS, "body type"),
    ):
        matches = list(pattern.finditer(query))
        # Distinct enum values mentioned, in order of first appearance.
        seen: dict[object, str] = {}
        for m in matches:
            token = m.group(1).lower()
            value = synonyms[token]
            seen.setdefault(value, token)
        if len(seen) > 1:
            values = list(seen.items())
            _winner_value, winner_token = values[-1]
            mentioned = ", ".join(token for _, token in values)
            return (
                f"Query mentioned conflicting {label}s ({mentioned}); "
                f"using the last-mentioned value ({winner_token})."
            )
    return None
