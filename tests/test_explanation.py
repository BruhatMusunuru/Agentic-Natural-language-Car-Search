from car_search.core import BodyType, Listing, SearchFilters
from car_search.data import load_listings
from car_search.search import RelaxationStep, build_explanation


def sample_listings() -> list[Listing]:
    return list(load_listings())[:2]


def test_explanation_grounded_in_real_filters_and_results() -> None:
    filters = SearchFilters(body_type=BodyType.SUV, price_max=30_000, location="Chicago")
    results = sample_listings()
    explanation = build_explanation(filters, results)
    assert str(len(results)) in explanation
    assert "SUV" in explanation
    assert "30,000" in explanation
    assert "Chicago" in explanation


def test_explanation_zero_results_no_relaxation() -> None:
    filters = SearchFilters(make="Nonexistent Make Inc")
    explanation = build_explanation(filters, [])
    assert "No listings matched" in explanation
    assert "Nonexistent Make Inc" in explanation


def test_explanation_surfaces_relaxation_history() -> None:
    filters = SearchFilters(location="Chicago", radius_mi=100)
    steps = [RelaxationStep(field="radius_mi", from_value=50, to_value=100)]
    explanation = build_explanation(filters, sample_listings(), relaxed_steps=steps)
    assert "relaxed" in explanation.lower()
    assert "radius_mi" in explanation


def test_explanation_surfaces_contradiction_note() -> None:
    filters = SearchFilters()
    note = "Query mentioned conflicting fuel types (electric, diesel); using the last-mentioned value (diesel)."
    explanation = build_explanation(filters, [], contradiction_note=note)
    assert note in explanation


def test_explanation_does_not_invent_fields_not_in_filters() -> None:
    filters = SearchFilters(price_max=10_000)
    explanation = build_explanation(filters, [])
    # only the fields actually set on filters should be described
    assert "SUV" not in explanation
    assert "Chicago" not in explanation
