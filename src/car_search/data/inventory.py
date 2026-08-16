"""Loads the small curated seed inventory fixture (26 hand-picked rows).

NOTE: this is no longer the production listings source. Real search
traffic is served from the *entire* dataset via dataset.py's DuckDB-backed
`search_full_dataset`, which queries data/*.parquet directly without
loading it into memory. This fixture (produced by
scripts/curate_seed_listings.py) is kept checked in purely so unit tests
have a small, fast, dependency-light dataset to exercise
search.py::filter_listings' reference implementation against, without
needing DuckDB/parquet I/O for every test.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from car_search.core import Listing

SEED_LISTINGS_PATH = Path(__file__).resolve().parent / "seed_listings.json"


@lru_cache(maxsize=1)
def load_listings(path: Path = SEED_LISTINGS_PATH) -> tuple[Listing, ...]:
    """Load and validate the curated inventory fixture. Cached after first call."""
    raw = json.loads(path.read_text())
    return tuple(Listing.model_validate(row) for row in raw)
