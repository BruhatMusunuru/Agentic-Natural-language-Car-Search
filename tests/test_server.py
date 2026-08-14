"""Tests for the FastAPI app that don't require a real Anthropic API key:
health/static wiring and input validation. The agent<->Anthropic call path
itself is exercised manually against the live API (see README).
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from strands.types.exceptions import ConcurrencyException

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-fake-key-for-import-only")

import rag_assistant.server as server_module
from rag_assistant.server import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["listings_loaded"] > 0


def test_index_serves_chat_ui(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]


def test_chat_rejects_empty_message(client):
    res = client.post("/chat", json={"message": "   "})
    assert res.status_code == 400


def test_chat_rejects_missing_message_field(client):
    res = client.post("/chat", json={})
    assert res.status_code == 422


def test_chat_maps_concurrency_exception_to_409(client, monkeypatch):
    # A Strands Agent raises ConcurrencyException rather than corrupting
    # state if the same session is invoked twice at once; the API should
    # surface that as a clean 409, not the generic 502.
    class _StubAgent:
        def __call__(self, message):
            raise ConcurrencyException("busy")

    monkeypatch.setattr(
        server_module, "_get_or_create_agent", lambda session_id: ("sid", _StubAgent())
    )
    res = client.post("/chat", json={"message": "hi"})
    assert res.status_code == 409
