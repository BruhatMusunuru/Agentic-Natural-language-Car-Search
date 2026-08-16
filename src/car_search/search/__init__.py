"""Search: the deterministic-search-related modules -- the DuckDB engine, the
in-memory reference filter, zero-result relaxation, and explanation generation.
"""

from car_search.search.dataset import dataset_row_count, search_full_dataset
from car_search.search.explanation import build_explanation
from car_search.search.relaxation import RelaxationStep, SearchFn, relax_and_search
from car_search.search.search import filter_listings, search_listings

__all__ = [
    "RelaxationStep",
    "SearchFn",
    "build_explanation",
    "dataset_row_count",
    "filter_listings",
    "relax_and_search",
    "search_full_dataset",
    "search_listings",
]
