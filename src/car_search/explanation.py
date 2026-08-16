"""Deterministic, grounded explanation generation (US-005).

The explanation is built from a plain-Python template over the *actual*
extracted SearchFilters, result count, relaxation history, and any detected
contradiction -- never freely invented by an LLM.
"""

from __future__ import annotations

from car_search.models import Listing, SearchFilters
from car_search.relaxation import RelaxationStep


def _describe_filters(filters: SearchFilters) -> list[str]:
    parts: list[str] = []
    if filters.body_type is not None:
        parts.append(filters.body_type.value)
    if filters.make is not None:
        parts.append(filters.make)
    if filters.model is not None:
        parts.append(filters.model)
    if filters.fuel_type is not None:
        parts.append(f"{filters.fuel_type.value} fuel")
    if filters.year_min is not None:
        parts.append(f"{filters.year_min} or newer")
    if filters.mileage_max is not None:
        parts.append(f"under {filters.mileage_max:,} mi")
    if filters.price_max is not None:
        parts.append(f"under ${filters.price_max:,.0f}")
    if filters.location is not None:
        radius = filters.radius_mi
        parts.append(f"near {filters.location}" + (f" (within {radius}mi)" if radius else ""))
    return parts


def build_explanation(
    filters: SearchFilters,
    results: list[Listing],
    relaxed_steps: list[RelaxationStep] | None = None,
    contradiction_note: str | None = None,
) -> str:
    relaxed_steps = relaxed_steps or []
    criteria = _describe_filters(filters)
    criteria_str = ", ".join(criteria) if criteria else "no specific criteria"
    count = len(results)

    if count == 0:
        sentence = f"No listings matched {criteria_str}"
        if relaxed_steps:
            sentence += " even after relaxing " + ", ".join(s.field for s in relaxed_steps)
        sentence += "."
    else:
        noun = "listing" if count == 1 else "listings"
        sentence = f"Found {count} {noun} matching {criteria_str}."
        if relaxed_steps:
            relaxed_desc = "; ".join(s.describe() for s in relaxed_steps)
            sentence += f" Some constraints were relaxed to find these: {relaxed_desc}."

    if contradiction_note:
        sentence += f" Note: {contradiction_note}"

    return sentence
