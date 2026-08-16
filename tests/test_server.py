from fastapi.testclient import TestClient

import car_search.api.server as server_module
from car_search.api.server import app
from car_search.core import BodyType, SearchFilters
from car_search.orchestrator import run_search

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


def test_internal_runtime_error_returns_502_not_a_raw_500(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def failing_run_search(query: str) -> object:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    monkeypatch.setattr(server_module, "run_search", failing_run_search)
    response = client.post("/search", json={"query": "reliable family SUV under $30k"})
    assert response.status_code == 502
    assert response.json()["detail"] == "ANTHROPIC_API_KEY is not set"


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
