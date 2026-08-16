from fastapi.testclient import TestClient

from car_search.models import BodyType, SearchFilters
from car_search.orchestrator import run_search
from car_search.server import app

client = TestClient(app)


def test_missing_query_returns_4xx() -> None:
    response = client.post("/search", json={})
    assert 400 <= response.status_code < 500


def test_empty_query_returns_4xx() -> None:
    response = client.post("/search", json={"query": ""})
    assert 400 <= response.status_code < 500


def test_whitespace_only_query_returns_4xx() -> None:
    response = client.post("/search", json={"query": "   "})
    assert 400 <= response.status_code < 500


def test_valid_query_shape_via_orchestrator_directly() -> None:
    # Exercises the same response shape /search returns, without a live
    # LLM call (see tests/test_orchestrator.py for extract_fn injection).
    filters = SearchFilters(body_type=BodyType.SUV, price_max=30_000, location="Chicago")
    response = run_search(
        "reliable family SUV under $30k, low mileage, near Chicago",
        extract_fn=lambda query: filters,
        clarify_fn=lambda query: "unused",
    )
    body = response.model_dump(mode="json")
    assert set(body.keys()) == {"filters", "results", "explanation", "relaxed_fields", "clarifying_question"}
