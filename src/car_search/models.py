"""Pydantic models for the car-search service.

`SearchFilters` is the strict, validated shape the LLM extraction step must
produce. `Listing` is the shape of a curated inventory row (see
scripts/curate_seed_listings.py / src/car_search/data/seed_listings.json).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class BodyType(str, Enum):
    """Matches the source data's actual `bodyStyle` codes."""

    SUV = "SUV"
    TRUCKS = "TRUCKS"
    SEDAN = "SEDAN"
    COUPE = "COUPE"
    CONVERT = "CONVERT"
    HATCH = "HATCH"
    VANS = "VANS"
    WAGON = "WAGON"


class FuelType(str, Enum):
    """Matches the source data's actual `fuelType` values."""

    GASOLINE = "Gasoline"
    DIESEL = "Diesel"
    HYBRID = "Hybrid Gas/Electric"
    FLEXIBLE_FUEL = "Flexible Fuel"
    ELECTRIC = "Electric"


class SearchFilters(BaseModel):
    """Structured filters extracted from a free-text car search query.

    All fields are optional -- a query that only specifies some filters is
    valid. Enum fields (`body_type`, `fuel_type`) reject any value outside
    the real source-data codes at validation time rather than silently
    accepting nonsense.
    """

    model_config = ConfigDict(extra="forbid")

    make: str | None = None
    model: str | None = None
    body_type: BodyType | None = None
    price_max: float | None = None
    mileage_max: int | None = None
    year_min: int | None = None
    fuel_type: FuelType | None = None
    location: str | None = None
    radius_mi: int | None = None


class Listing(BaseModel):
    """A single curated inventory listing (see US-001)."""

    id: str
    make: str
    model: str
    body_type: BodyType
    price: float
    mileage: int
    year: int
    fuel_type: FuelType
    city: str
    state: str
    zip: str
