"""Zero-result auto-relaxation (US-006).

If a search returns zero results, constraints are relaxed one at a time, in
the fixed order radius_mi -> mileage_max -> price_max -> year_min, and the
search is re-run after each relaxation. Relaxation is cumulative (a
relaxed field stays relaxed for subsequent steps) and stops as soon as a
step produces at least one result. make/model/body_type/fuel_type are never
relaxed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from car_search.core import FilterResult, SearchFilters
from car_search.geo import DEFAULT_RADIUS_MI

SearchFn = Callable[[SearchFilters], FilterResult]

# (field name, relaxation multiplier/step description)
_RELAXATION_ORDER = ("radius_mi", "mileage_max", "price_max", "year_min")


@dataclass
class RelaxationStep:
    field: str
    from_value: float | int
    to_value: float | int

    def describe(self) -> str:
        unit = {"radius_mi": "mi", "mileage_max": "mi", "price_max": "$", "year_min": ""}[self.field]
        if unit == "$":
            return f"{self.field}: ${self.from_value:,.0f} → ${self.to_value:,.0f}"
        if unit == "mi":
            return f"{self.field}: {self.from_value:,.0f}mi → {self.to_value:,.0f}mi"
        return f"{self.field}: {self.from_value} → {self.to_value}"


def _relax_field(field: str, filters: SearchFilters) -> tuple[SearchFilters, RelaxationStep] | None:
    """Return (relaxed filters, step record), or None if this field can't be relaxed further."""
    if field == "radius_mi":
        if filters.location is None:
            return None
        current = filters.radius_mi if filters.radius_mi is not None else DEFAULT_RADIUS_MI
        new_value = current * 2
        return filters.model_copy(update={"radius_mi": new_value}), RelaxationStep(field, current, new_value)

    if field == "mileage_max":
        if filters.mileage_max is None:
            return None
        new_value = round(filters.mileage_max * 1.5)
        return filters.model_copy(update={"mileage_max": new_value}), RelaxationStep(
            field, filters.mileage_max, new_value
        )

    if field == "price_max":
        if filters.price_max is None:
            return None
        new_value = round(filters.price_max * 1.2)
        return filters.model_copy(update={"price_max": new_value}), RelaxationStep(
            field, filters.price_max, new_value
        )

    if field == "year_min":
        if filters.year_min is None:
            return None
        new_value = filters.year_min - 3
        return filters.model_copy(update={"year_min": new_value}), RelaxationStep(
            field, filters.year_min, new_value
        )

    raise ValueError(f"Unknown relaxable field: {field}")


def relax_and_search(
    filters: SearchFilters, search_fn: SearchFn
) -> tuple[FilterResult, SearchFilters, list[RelaxationStep]]:
    """Run search_fn, auto-relaxing on zero results per US-006.

    search_fn is injectable so relaxation works identically whether it's
    backed by the full out-of-core dataset (dataset.py::search_full_dataset,
    the production default) or the small in-memory curated fixture
    (search.py::filter_listings against inventory.py, used in fast offline
    tests) -- each relaxation step just re-invokes search_fn with
    progressively looser filters; it never needs a materialized listings
    list of its own.

    Returns the final FilterResult, the (possibly relaxed) SearchFilters
    used to produce it, and the ordered list of relaxation steps applied
    (empty if no relaxation was needed).
    """
    result = search_fn(filters)
    if result.matches:
        return result, filters, []

    current_filters = filters
    steps: list[RelaxationStep] = []
    for field in _RELAXATION_ORDER:
        relaxed = _relax_field(field, current_filters)
        if relaxed is None:
            continue
        current_filters, step = relaxed
        steps.append(step)
        result = search_fn(current_filters)
        if result.matches:
            return result, current_filters, steps

    # Exhausted every relaxable field with no matches; return the
    # (still-empty) result as-is along with whatever relaxation was tried.
    return result, current_filters, steps
