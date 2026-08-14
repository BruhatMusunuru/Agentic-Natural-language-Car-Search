"""Tests for the retrieval layer against the real sample data in data/data.

These exercise data_store.py directly (no network, no API key needed) so
they can run in CI or before every deploy.
"""

from __future__ import annotations

import concurrent.futures

from rag_assistant import data_store


def test_row_count_loads_data():
    assert data_store.row_count() > 0


def test_dataset_summary_reports_coverage():
    summary = data_store.dataset_summary()
    assert summary["listing_count"] == data_store.row_count()
    assert summary["first_seen"] <= summary["last_seen"]


def test_search_filters_by_make_and_model():
    result = data_store.search_listings(make="Toyota", model="Camry", limit=5)
    assert result["returned"] <= 5
    assert result["returned"] <= result["total_matches"]
    assert result["total_matches"] > 0
    for listing in result["listings"]:
        assert listing["makeName"] == "Toyota"
        assert listing["modelName"] == "Camry"


def test_search_year_range_is_respected():
    result = data_store.search_listings(year_min=2023, year_max=2024, limit=10)
    for listing in result["listings"]:
        assert 2023 <= listing["year"] <= 2024


def test_search_limit_is_clamped_to_max():
    result = data_store.search_listings(limit=10_000)
    assert result["returned"] <= data_store.config.MAX_SEARCH_LIMIT


def test_search_with_no_matches_returns_empty_not_error():
    result = data_store.search_listings(make="NotARealMakeXYZ")
    assert result["total_matches"] == 0
    assert result["listings"] == []


def test_search_keyword_requires_all_tokens():
    result = data_store.search_listings(keywords="sunroof leather", limit=5)
    for listing in result["listings"]:
        full = data_store.get_listing(listing["listingId"])
        blob = " ".join(
            str(full.get(c, "")) for c in data_store._SEARCH_TEXT_COLUMNS
        ).lower()
        assert "sunroof" in blob
        assert "leather" in blob


def test_premium_masked_fields_are_nulled_not_literal_string():
    result = data_store.search_listings(limit=20)
    for listing in result["listings"]:
        full = data_store.get_listing(listing["listingId"])
        for col in data_store._PREMIUM_COLUMNS:
            assert full.get(col) != "[PREMIUM]"


def test_get_listing_returns_none_for_unknown_id():
    assert data_store.get_listing("not-a-real-listing-id") is None


def test_get_listing_round_trips_a_search_result():
    result = data_store.search_listings(limit=1)
    listing_id = result["listings"][0]["listingId"]
    full = data_store.get_listing(listing_id)
    assert full is not None
    assert str(full["listingId"]) == str(listing_id)
    assert "searchBlob" not in full


def test_market_stats_counts_match_search_total():
    stats = data_store.market_stats(make="Honda", model="CR-V")
    search = data_store.search_listings(make="Honda", model="CR-V", limit=1)
    assert stats["count"] == search["total_matches"]


def test_market_stats_deal_mix_sums_to_count():
    stats = data_store.market_stats(make="Ford")
    assert sum(stats["deal_indicator_mix"].values()) == stats["count"]


def test_concurrent_queries_do_not_interfere():
    # FastAPI runs sync endpoints in a thread pool, so concurrent tool calls
    # against the shared in-memory database are the normal case, not an edge
    # case. Each call should get correct, independent results.
    makes = ["Toyota", "Honda", "Ford", "BMW", "Kia", "Nissan", "Chevrolet", "Jeep"]

    def run(make: str) -> bool:
        for _ in range(15):
            result = data_store.search_listings(make=make, limit=5)
            if not all(listing["makeName"] == make for listing in result["listings"]):
                return False
            stats = data_store.market_stats(make=make)
            if stats["count"] != result["total_matches"]:
                return False
        return True

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(makes)) as pool:
        outcomes = list(pool.map(run, makes * 3))

    assert all(outcomes)
