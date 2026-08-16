import pytest

from car_search.config import require_api_key


def test_require_api_key_returns_value_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-value")
    assert require_api_key() == "sk-ant-test-value"


def test_require_api_key_raises_clear_error_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY is not set"):
        require_api_key()
