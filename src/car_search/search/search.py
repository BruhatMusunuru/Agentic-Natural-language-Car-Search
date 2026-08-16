"""Deterministic filtering against SearchFilters.

`filter_listings` is the pure, plain-Python matching logic (no LLM
involvement) over an explicit in-memory list of Listing objects -- it
applies each provided filter field as an AND condition and reports, per
field, how many listings that single field alone would exclude. It's kept
around as a fast, dependency-light reference implementation, used against
the small curated test fixture (see inventory.py) in unit tests.

`search_listings` is the `@tool`-wrapped entry point an Agent calls; in
production it delegates to dataset.py's DuckDB-backed
`search_full_dataset`, which applies the exact same filtering semantics
but against the *entire* real dataset (data/*.parquet) without loading it
into Python memory (see dataset.py for why/how).
"""

from __future__ import annotations

from collections.abc import Callable

from strands import tool

from car_search.core import FilterResult, Listing, SearchFilters
from car_search.geo import DEFAULT_RADIUS_MI, haversine_miles, resolve_location, zip_to_coords
from car_search.search.dataset import search_full_dataset

# Order matches the relaxation order used elsewhere (US-006): radius_mi is
# grouped with location since they're a single filter dimension.
FILTER_FIELDS = (
    "make",
    "model",
    "body_type",
    "price_max",
    "mileage_max",
    "year_min",
    "fuel_type",
    "radius_mi",
)


def _passes_make(listing: Listing, filters: SearchFilters) -> bool:
    return filters.make is None or listing.make.strip().lower() == filters.make.strip().lower()


def _passes_model(listing: Listing, filters: SearchFilters) -> bool:
    return filters.model is None or listing.model.strip().lower() == filters.model.strip().lower()


def _passes_body_type(listing: Listing, filters: SearchFilters) -> bool:
    return filters.body_type is None or listing.body_type == filters.body_type


def _passes_price_max(listing: Listing, filters: SearchFilters) -> bool:
    return filters.price_max is None or listing.price <= filters.price_max


def _passes_mileage_max(listing: Listing, filters: SearchFilters) -> bool:
    return filters.mileage_max is None or listing.mileage <= filters.mileage_max


def _passes_year_min(listing: Listing, filters: SearchFilters) -> bool:
    return filters.year_min is None or listing.year >= filters.year_min


def _passes_fuel_type(listing: Listing, filters: SearchFilters) -> bool:
    return filters.fuel_type is None or listing.fuel_type == filters.fuel_type


def _passes_radius(
    listing: Listing, filters: SearchFilters, origin: tuple[float, float] | None
) -> bool:
    if filters.location is None or origin is None:
        return True
    listing_coords = zip_to_coords(listing.zip)
    if listing_coords is None:
        # Can't evaluate distance for a listing whose zip isn't a
        # recognized US zip; don't silently exclude it.
        return True
    radius = filters.radius_mi if filters.radius_mi is not None else DEFAULT_RADIUS_MI
    return haversine_miles(origin, listing_coords) <= radius


def filter_listings(listings: list[Listing], filters: SearchFilters) -> FilterResult:
    """Apply every provided filter field as an AND condition, in memory.

    Returns the AND-combined matches plus, for each field independently,
    the count of listings that field alone would exclude (regardless of
    the other filters).
    """
    origin = resolve_location(filters.location) if filters.location else None

    predicates: dict[str, Callable[[Listing, SearchFilters], bool]] = {
        "make": _passes_make,
        "model": _passes_model,
        "body_type": _passes_body_type,
        "price_max": _passes_price_max,
        "mileage_max": _passes_mileage_max,
        "year_min": _passes_year_min,
        "fuel_type": _passes_fuel_type,
    }

    excluded_by: dict[str, int] = {}
    for name, predicate in predicates.items():
        excluded_by[name] = sum(1 for listing in listings if not predicate(listing, filters))
    excluded_by["radius_mi"] = sum(
        1 for listing in listings if not _passes_radius(listing, filters, origin)
    )

    matches = [
        listing
        for listing in listings
        if all(predicate(listing, filters) for predicate in predicates.values())
        and _passes_radius(listing, filters, origin)
    ]

    return FilterResult(matches=matches, excluded_by=excluded_by)


@tool
def search_listings(filters: SearchFilters) -> list[Listing]:
    """Deterministically filter the real car inventory against SearchFilters.

    Applies each provided field (make, model, body_type, price_max,
    mileage_max, year_min, fuel_type, location+radius_mi) as an AND
    condition against the full dataset (data/*.parquet). No LLM calls
    happen inside this tool -- matching is plain SQL executed by DuckDB.
    """
    return search_full_dataset(filters).matches
