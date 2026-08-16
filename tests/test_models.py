import pytest
from pydantic import ValidationError

from car_search.core import BodyType, FuelType, SearchFilters


def test_all_fields_optional() -> None:
    filters = SearchFilters()
    assert filters.make is None
    assert filters.body_type is None
    assert filters.radius_mi is None


def test_valid_values_pass() -> None:
    filters = SearchFilters(
        make="Hyundai",
        model="Tucson",
        body_type=BodyType.SUV,
        price_max=30000,
        mileage_max=25000,
        year_min=2020,
        fuel_type=FuelType.GASOLINE,
        location="Chicago",
        radius_mi=50,
    )
    assert filters.body_type is BodyType.SUV
    assert filters.fuel_type is FuelType.GASOLINE


def test_valid_values_pass_as_raw_strings() -> None:
    filters = SearchFilters.model_validate({"body_type": "SUV", "fuel_type": "Hybrid Gas/Electric"})
    assert filters.body_type is BodyType.SUV
    assert filters.fuel_type is FuelType.HYBRID


def test_invalid_body_type_rejected() -> None:
    with pytest.raises(ValidationError):
        SearchFilters.model_validate({"body_type": "SPORTSCAR"})


def test_invalid_fuel_type_rejected() -> None:
    with pytest.raises(ValidationError):
        SearchFilters.model_validate({"fuel_type": "Unobtanium"})


def test_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError):
        SearchFilters.model_validate({"color": "red"})
