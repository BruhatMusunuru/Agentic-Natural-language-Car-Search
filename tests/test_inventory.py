from car_search.data import load_listings
from car_search.geo import zip_to_coords


def test_loads_curated_fixture() -> None:
    listings = load_listings()
    assert 20 <= len(listings) <= 30


def test_covers_multiple_body_and_fuel_types() -> None:
    listings = load_listings()
    assert len({listing.body_type for listing in listings}) >= 5
    assert len({listing.fuel_type for listing in listings}) >= 4


def test_wide_price_spread() -> None:
    listings = load_listings()
    prices = [listing.price for listing in listings]
    assert min(prices) < 5_000
    assert max(prices) > 50_000


def test_every_listing_zip_has_a_coordinate() -> None:
    listings = load_listings()
    for listing in listings:
        assert zip_to_coords(listing.zip) is not None


def test_chicago_area_low_mileage_affordable_suv_cluster_exists() -> None:
    chicago_metro_zips = {"60201", "60453", "60173", "60126", "60610", "60540", "60504"}
    listings = load_listings()
    matches = [
        listing
        for listing in listings
        if listing.zip in chicago_metro_zips
        and listing.body_type.value == "SUV"
        and listing.mileage < 25_000
        and listing.price < 30_000
    ]
    assert len(matches) >= 3
