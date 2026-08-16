from car_search.inventory import load_listings
from car_search.models import BodyType, FilterResult, Listing, SearchFilters
from car_search.relaxation import relax_and_search
from car_search.search import filter_listings


def all_listings() -> list[Listing]:
    return list(load_listings())


def fixture_search(filters: SearchFilters) -> FilterResult:
    """search_fn backed by the small in-memory curated fixture, for fast
    offline tests (no DuckDB/parquet I/O needed)."""
    return filter_listings(all_listings(), filters)


def test_no_relaxation_needed_when_results_exist() -> None:
    filters = SearchFilters(body_type=BodyType.SUV, price_max=30_000)
    result, final_filters, steps = relax_and_search(filters, fixture_search)
    assert result.matches
    assert steps == []
    assert final_filters == filters


def test_relaxation_kicks_in_on_zero_results_and_stops_at_first_success() -> None:
    # Engineered to return zero results initially (the only curated WAGON
    # is in Barrington, IL 60010, ~32mi from Chicago -- just outside a
    # 20mi radius) and find it once radius_mi is doubled to 40 by the
    # first relaxation step.
    filters = SearchFilters(
        body_type=BodyType.WAGON,
        location="Chicago",
        radius_mi=20,
    )
    baseline = relax_and_search(SearchFilters(body_type=BodyType.WAGON), fixture_search)
    assert baseline[0].matches, "sanity check: WAGON exists at all in curated set"

    result, final_filters, steps = relax_and_search(filters, fixture_search)
    assert result.matches
    assert steps  # at least one relaxation happened
    assert steps[0].field == "radius_mi"  # radius_mi is relaxed first
    # make/model/body_type/fuel_type are never relaxed
    assert final_filters.body_type is BodyType.WAGON


def test_never_relaxes_body_type_make_model_fuel_type() -> None:
    filters = SearchFilters(body_type=BodyType.WAGON, make="Nonexistent Make Inc")
    result, final_filters, steps = relax_and_search(filters, fixture_search)
    assert result.matches == []
    assert final_filters.make == "Nonexistent Make Inc"
    assert final_filters.body_type is BodyType.WAGON
    # every relaxable field was None, so no steps could be taken
    assert steps == []


def test_relaxation_order_is_radius_then_mileage_then_price_then_year() -> None:
    filters = SearchFilters(
        location="Chicago",
        radius_mi=1,
        mileage_max=1,
        price_max=1,
        year_min=2999,
    )
    _result, _final_filters, steps = relax_and_search(filters, fixture_search)
    fields_in_order = [s.field for s in steps]
    full_order = ["radius_mi", "mileage_max", "price_max", "year_min"]
    assert fields_in_order == full_order[: len(fields_in_order)]
