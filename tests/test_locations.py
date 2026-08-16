from car_search.locations import resolve_location, zip_to_coords


def test_zip_to_coords_resolves_known_zip() -> None:
    coords = zip_to_coords("60504")  # Aurora, IL
    assert coords is not None
    lat, lon = coords
    assert 41.0 < lat < 43.0
    assert -89.0 < lon < -87.0


def test_zip_to_coords_rejects_bad_input() -> None:
    assert zip_to_coords("not-a-zip") is None
    assert zip_to_coords("") is None


def test_resolve_location_exact_zip() -> None:
    assert resolve_location("60504") == zip_to_coords("60504")


def test_resolve_location_city_name() -> None:
    coords = resolve_location("Chicago")
    assert coords is not None
    lat, lon = coords
    assert 41.5 < lat < 42.2
    assert -88.0 < lon < -87.4


def test_resolve_location_city_state() -> None:
    coords = resolve_location("Aurora, IL")
    assert coords is not None
    lat, _lon = coords
    assert 41.5 < lat < 42.0


def test_resolve_location_disambiguates_ambiguous_city_by_state_size() -> None:
    # "Beverly Hills" exists in both CA (5 zips) and FL (2 zips); without a
    # state, resolve to the more prominent (larger-zip-count) match rather
    # than averaging across unrelated regions.
    coords = resolve_location("Beverly Hills")
    assert coords is not None
    lat, lon = coords
    assert 33.5 < lat < 34.5
    assert -119.0 < lon < -117.5


def test_resolve_location_unresolvable_returns_none() -> None:
    assert resolve_location("Nonexistentville, ZZ") is None


def test_resolve_location_empty_string() -> None:
    assert resolve_location("") is None
    assert resolve_location("   ") is None
