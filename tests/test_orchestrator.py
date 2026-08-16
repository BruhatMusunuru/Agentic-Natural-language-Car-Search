from car_search.inventory import load_listings
from car_search.models import BodyType, SearchFilters
from car_search.orchestrator import ClarifyFn, ExtractFn, rank_and_cap, run_search


def fake_extract(filters: SearchFilters) -> ExtractFn:
    def _extract(query: str) -> SearchFilters:
        return filters

    return _extract


def fake_clarify(question: str = "What's your budget?") -> ClarifyFn:
    def _clarify(query: str) -> str:
        return question

    return _clarify


def unreachable_extract(query: str) -> SearchFilters:
    raise AssertionError("extract_fn should not be called")


def unreachable_clarify(query: str) -> str:
    raise AssertionError("clarify_fn should not be called for a well-specified query")


def test_flagship_query_returns_ranked_chicago_suvs() -> None:
    filters = SearchFilters(body_type=BodyType.SUV, price_max=30_000, location="Chicago")
    response = run_search(
        "reliable family SUV under $30k, low mileage, near Chicago",
        extract_fn=fake_extract(filters),
        clarify_fn=unreachable_clarify,
    )
    assert response.clarifying_question is None
    assert response.results
    assert len(response.results) <= 5
    prices = [r.price for r in response.results]
    assert prices == sorted(prices)
    assert all(r.body_type is BodyType.SUV for r in response.results)


def test_results_capped_at_five() -> None:
    listings = list(load_listings())
    ranked = rank_and_cap(listings, top_k=5)
    assert len(ranked) == min(5, len(listings))


def test_ranking_is_ascending_price_deterministic() -> None:
    listings = list(load_listings())
    ranked_once = rank_and_cap(listings)
    ranked_twice = rank_and_cap(listings)
    assert ranked_once == ranked_twice
    prices = [listing.price for listing in ranked_once]
    assert prices == sorted(prices)


def test_vague_query_triggers_clarify_and_skips_search() -> None:
    response = run_search(
        "find me a car",
        extract_fn=fake_extract(SearchFilters()),
        clarify_fn=fake_clarify("What's your budget and preferred body type?"),
    )
    assert response.clarifying_question == "What's your budget and preferred body type?"
    assert response.results == []


def test_well_specified_query_never_triggers_clarify() -> None:
    filters = SearchFilters(body_type=BodyType.SUV, price_max=30_000, location="Chicago")
    response = run_search(
        "reliable family SUV under $30k, low mileage, near Chicago",
        extract_fn=fake_extract(filters),
        clarify_fn=unreachable_clarify,
    )
    assert response.clarifying_question is None


def test_skip_clarify_forces_best_effort_search_on_followup() -> None:
    response = run_search(
        "find me a car",
        extract_fn=fake_extract(SearchFilters()),
        clarify_fn=unreachable_clarify,
        skip_clarify=True,
    )
    assert response.clarifying_question is None
    # best-effort search on empty filters just returns everything, capped
    assert len(response.results) <= 5


def test_zero_result_query_triggers_relaxation_via_orchestrator() -> None:
    filters = SearchFilters(body_type=BodyType.WAGON, location="Chicago", radius_mi=20)
    response = run_search(
        "wagon near chicago",
        extract_fn=fake_extract(filters),
        clarify_fn=unreachable_clarify,
    )
    assert response.results
    assert response.relaxed_fields is not None
    assert any("radius_mi" in field for field in response.relaxed_fields)


def test_contradiction_note_surfaces_in_explanation() -> None:
    filters = SearchFilters(body_type=BodyType.SUV)
    response = run_search(
        "electric diesel SUV",
        extract_fn=fake_extract(filters),
        clarify_fn=unreachable_clarify,
    )
    assert "conflicting fuel types" in response.explanation
