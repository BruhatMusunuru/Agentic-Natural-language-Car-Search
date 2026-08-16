"""Tests for the DuckDB-backed, out-of-core full-dataset query engine.

These read the real data/*.parquet files (checked into the repo) via
DuckDB -- no network calls, no full in-memory materialization of the
dataset, and no LLM involved.
"""

from car_search.dataset import dataset_row_count, search_full_dataset
from car_search.models import BodyType, FuelType, SearchFilters


def test_dataset_row_count_covers_the_whole_export() -> None:
    # 30 daily files, ~1000 rows each before quality filtering.
    count = dataset_row_count()
    assert count > 15_000


def test_no_filters_returns_the_full_qualifying_set_capped_by_nothing() -> None:
    result = search_full_dataset(SearchFilters())
    assert len(result.matches) == dataset_row_count()
    assert all(count == 0 for count in result.excluded_by.values())


def test_price_max_pushed_down_correctly() -> None:
    result = search_full_dataset(SearchFilters(price_max=10_000))
    assert result.matches
    assert all(listing.price <= 10_000 for listing in result.matches)
    assert result.excluded_by["price_max"] > 0


def test_every_matched_listing_has_a_genuinely_positive_price() -> None:
    # kbbFairPriceHigh <= 0 is a "missing price" sentinel, not a real price.
    result = search_full_dataset(SearchFilters())
    assert all(listing.price > 0 for listing in result.matches)


def test_body_type_and_fuel_type_pushed_down() -> None:
    result = search_full_dataset(SearchFilters(body_type=BodyType.WAGON, fuel_type=FuelType.GASOLINE))
    assert result.matches
    assert all(listing.body_type is BodyType.WAGON for listing in result.matches)
    assert all(listing.fuel_type is FuelType.GASOLINE for listing in result.matches)


def test_flagship_query_returns_many_real_chicago_suvs() -> None:
    # The whole point of using the full dataset instead of a ~26-row
    # curated subset: many more real matches than before.
    result = search_full_dataset(
        SearchFilters(body_type=BodyType.SUV, price_max=30_000, mileage_max=25_000, location="Chicago", radius_mi=50)
    )
    assert len(result.matches) > 20
    for listing in result.matches:
        assert listing.body_type is BodyType.SUV
        assert listing.price <= 30_000
        assert listing.mileage <= 25_000


def test_radius_filter_excludes_far_away_listings() -> None:
    tight = search_full_dataset(SearchFilters(location="Chicago", radius_mi=10))
    wide = search_full_dataset(SearchFilters(location="Chicago", radius_mi=500))
    assert len(tight.matches) < len(wide.matches)
    tight_zips = {listing.zip for listing in tight.matches}
    wide_zips = {listing.zip for listing in wide.matches}
    assert tight_zips <= wide_zips


def test_hydrogen_fuel_type_is_supported() -> None:
    # Rare (3 rows) but real -- present across the full dataset even
    # though it never showed up in the single-day MVP sample.
    result = search_full_dataset(SearchFilters(fuel_type=FuelType.HYDROGEN))
    assert all(listing.fuel_type is FuelType.HYDROGEN for listing in result.matches)


def test_excluded_by_counts_are_independent_per_field() -> None:
    result = search_full_dataset(SearchFilters(price_max=5_000, mileage_max=1_000))
    baseline = dataset_row_count()
    assert 0 < result.excluded_by["price_max"] < baseline
    assert 0 < result.excluded_by["mileage_max"] < baseline
    # combined matches should be <= either individual field's pass count
    assert len(result.matches) <= baseline - result.excluded_by["price_max"]
    assert len(result.matches) <= baseline - result.excluded_by["mileage_max"]
