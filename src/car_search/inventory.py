"""Loads the curated seed inventory fixture at startup.

The service never re-reads the raw CSV/parquet files at runtime -- only the
checked-in JSON fixture produced by scripts/curate_seed_listings.py.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from car_search.models import Listing

SEED_LISTINGS_PATH = Path(__file__).resolve().parent / "data" / "seed_listings.json"


@lru_cache(maxsize=1)
def load_listings(path: Path = SEED_LISTINGS_PATH) -> tuple[Listing, ...]:
    """Load and validate the curated inventory fixture. Cached after first call."""
    raw = json.loads(path.read_text())
    return tuple(Listing.model_validate(row) for row in raw)
