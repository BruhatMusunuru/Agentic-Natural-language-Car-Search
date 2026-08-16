from car_search.inventory import load_listings
from car_search.models import BodyType, FuelType, Listing, SearchFilters
from car_search.search import filter_listings, search_listings


def all_listings() -> list[Listing]:
    return list(load_listings())


def test_no_filters_matches_everything() -> None:
    result = filter_listings(all_listings(), SearchFilters())
    assert len(result.matches) == len(all_listings())
    assert all(count == 0 for count in result.excluded_by.values())


def test_price_max_filters_independently() -> None:
    result = filter_listings(all_listings(), SearchFilters(price_max=10_000))
    assert all(listing.price <= 10_000 for listing in result.matches)
    assert result.excluded_by["price_max"] == sum(
        1 for listing in all_listings() if listing.price > 10_000
    )
    assert result.excluded_by["mileage_max"] == 0


def test_mileage_max_filters_independently() -> None:
    result = filter_listings(all_listings(), SearchFilters(mileage_max=20_000))
    assert all(listing.mileage <= 20_000 for listing in result.matches)
    assert result.excluded_by["mileage_max"] == sum(
        1 for listing in all_listings() if listing.mileage > 20_000
    )


def test_year_min_filters_independently() -> None:
    result = filter_listings(all_listings(), SearchFilters(year_min=2023))
    assert all(listing.year >= 2023 for listing in result.matches)


def test_make_filter_is_case_insensitive() -> None:
    result = filter_listings(all_listings(), SearchFilters(make="hyundai"))
    assert result.matches
    assert all(listing.make.lower() == "hyundai" for listing in result.matches)


def test_model_filter() -> None:
    result = filter_listings(all_listings(), SearchFilters(model="Tucson"))
    assert result.matches
    assert all(listing.model == "Tucson" for listing in result.matches)


def test_body_type_filter() -> None:
    result = filter_listings(all_listings(), SearchFilters(body_type=BodyType.WAGON))
    assert result.matches
    assert all(listing.body_type is BodyType.WAGON for listing in result.matches)


def test_fuel_type_filter() -> None:
    result = filter_listings(all_listings(), SearchFilters(fuel_type=FuelType.ELECTRIC))
    assert result.matches
    assert all(listing.fuel_type is FuelType.ELECTRIC for listing in result.matches)


def test_radius_filter_chicago_area() -> None:
    # Aurora, IL (60504) is a curated Chicago-metro listing within 50mi;
    # far-away listings (e.g. Linden, NJ 07036) must be excluded.
    result = filter_listings(
        all_listings(), SearchFilters(location="Chicago", radius_mi=50)
    )
    matched_zips = {listing.zip for listing in result.matches}
    assert "60504" in matched_zips
    assert "07036" not in matched_zips
    assert result.excluded_by["radius_mi"] > 0


def test_radius_filter_excludes_just_outside_boundary() -> None:
    # Rockford, IL (61107) is ~75mi from Chicago -- outside the default 50mi.
    result = filter_listings(all_listings(), SearchFilters(location="Chicago", radius_mi=50))
    matched_zips = {listing.zip for listing in result.matches}
    assert "61107" not in matched_zips

    wider = filter_listings(all_listings(), SearchFilters(location="Chicago", radius_mi=100))
    wider_zips = {listing.zip for listing in wider.matches}
    assert "61107" in wider_zips


def test_combined_filters_flagship_query() -> None:
    filters = SearchFilters(
        body_type=BodyType.SUV,
        price_max=30_000,
        mileage_max=25_000,
        location="Chicago",
        radius_mi=50,
    )
    result = filter_listings(all_listings(), filters)
    assert result.matches
    for listing in result.matches:
        assert listing.body_type is BodyType.SUV
        assert listing.price <= 30_000
        assert listing.mileage <= 25_000


def test_search_listings_tool_returns_matches() -> None:
    matches = search_listings(SearchFilters(body_type=BodyType.SUV, price_max=30_000))
    assert matches
    assert all(listing.body_type is BodyType.SUV and listing.price <= 30_000 for listing in matches)
