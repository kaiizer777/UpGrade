"""Unit tests for centralized LLM orchestration and OpenCode fallback."""

from types import SimpleNamespace
from typing import Any

import pytest

from app.core.config import settings
from app.services.llm import (
    AiConfigError,
    AiGenerationError,
    _resolve_provider,
    _resolve_provider_for,
    chat_completions_create_with_opencode_fallback,
    get_client,
    get_client_for,
)


class RateLimitError(Exception):
    """Simulated 429 error."""


@pytest.fixture(autouse=True)
def _reset_llm_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure tests run with clean default settings."""
    monkeypatch.setattr(settings, "ai_provider", "groq")
    monkeypatch.setattr(settings, "groq_api_key", "test-groq-key")
    monkeypatch.setattr(settings, "opencode_api_key", "test-opencode-key")
    monkeypatch.setattr(settings, "ai_model_groq", "openai/gpt-oss-120b")
    monkeypatch.setattr(settings, "ai_model_opencode", "hy3-free")
    monkeypatch.setattr(settings, "ai_model_opencode_fallback", "nemotron-3-ultra-free")
    monkeypatch.setattr(settings, "ai_base_url_groq", "https://api.groq.com/openai/v1")
    monkeypatch.setattr(settings, "ai_base_url_opencode", "https://opencode.ai/zen/v1")


def test_resolve_provider_groq() -> None:
    base_url, api_key, models = _resolve_provider_for("groq")
    assert base_url == "https://api.groq.com/openai/v1"
    assert api_key == "test-groq-key"
    assert models == ["openai/gpt-oss-120b"]

    b, k, m = _resolve_provider()
    assert b == base_url
    assert k == api_key
    assert m == "openai/gpt-oss-120b"


def test_resolve_provider_opencode_with_fallback() -> None:
    base_url, api_key, models = _resolve_provider_for("opencode")
    assert base_url == "https://opencode.ai/zen/v1"
    assert api_key == "test-opencode-key"
    assert models == ["hy3-free", "nemotron-3-ultra-free"]


def test_resolve_provider_opencode_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ai_model_opencode_fallback", "")
    _, _, models = _resolve_provider_for("opencode")
    assert models == ["hy3-free"]


def test_resolve_provider_unknown_raises() -> None:
    with pytest.raises(AiConfigError, match="Unknown ai_provider 'invalid'"):
        _resolve_provider_for("invalid")


def test_get_client_missing_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "groq_api_key", "")
    with pytest.raises(AiConfigError, match="has no API key configured"):
        get_client()


def test_get_client_caching() -> None:
    client1 = get_client_for("https://test.com", "key1")
    client2 = get_client_for("https://test.com", "key1")
    assert client1 is client2


@pytest.mark.asyncio
async def test_groq_single_model_call(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    async def mock_create(**kwargs: Any) -> Any:
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="groq response"))])

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=mock_create)))
    monkeypatch.setattr("app.services.llm.get_client_for", lambda *_a, **_k: fake_client)

    resp = await chat_completions_create_with_opencode_fallback(messages=[{"role": "user", "content": "hi"}])
    assert resp.choices[0].message.content == "groq response"
    assert len(calls) == 1
    assert calls[0]["model"] == "openai/gpt-oss-120b"


@pytest.mark.asyncio
async def test_opencode_primary_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_provider", "opencode")
    calls: list[dict[str, Any]] = []

    async def mock_create(**kwargs: Any) -> Any:
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="opencode primary response"))])

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=mock_create)))
    monkeypatch.setattr("app.services.llm.get_client_for", lambda *_a, **_k: fake_client)

    resp = await chat_completions_create_with_opencode_fallback(messages=[{"role": "user", "content": "hi"}])
    assert resp.choices[0].message.content == "opencode primary response"
    assert len(calls) == 1
    assert calls[0]["model"] == "hy3-free"


@pytest.mark.asyncio
async def test_opencode_fallback_on_500(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_provider", "opencode")
    calls: list[dict[str, Any]] = []
    events: list[tuple[str, dict[str, Any]]] = []

    def mock_record_event(event: str, **fields: Any) -> None:
        events.append((event, fields))

    monkeypatch.setattr("app.services.llm.record_event", mock_record_event)

    async def mock_create(**kwargs: Any) -> Any:
        calls.append(kwargs)
        if kwargs.get("model") == "hy3-free":
            raise RuntimeError("500 Internal Server Error from OpenCode")
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="fallback success"))])

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=mock_create)))
    monkeypatch.setattr("app.services.llm.get_client_for", lambda *_a, **_k: fake_client)

    resp = await chat_completions_create_with_opencode_fallback(messages=[{"role": "user", "content": "hi"}])
    assert resp.choices[0].message.content == "fallback success"
    assert len(calls) == 2
    assert calls[0]["model"] == "hy3-free"
    assert calls[1]["model"] == "nemotron-3-ultra-free"

    # Verify telemetry event
    assert len(events) == 1
    assert events[0][0] == "opencode_fallback"
    assert events[0][1]["from_model"] == "hy3-free"
    assert events[0][1]["to_model"] == "nemotron-3-ultra-free"


@pytest.mark.asyncio
async def test_opencode_all_models_fail_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_provider", "opencode")
    calls: list[dict[str, Any]] = []

    async def mock_create(**kwargs: Any) -> Any:
        calls.append(kwargs)
        raise RuntimeError("Model unavailable")

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=mock_create)))
    monkeypatch.setattr("app.services.llm.get_client_for", lambda *_a, **_k: fake_client)

    with pytest.raises(AiGenerationError) as exc_info:
        await chat_completions_create_with_opencode_fallback(messages=[{"role": "user", "content": "hi"}])

    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert len(calls) == 2
    assert calls[0]["model"] == "hy3-free"
    assert calls[1]["model"] == "nemotron-3-ultra-free"


@pytest.mark.asyncio
async def test_rate_limit_retry_and_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ai_provider", "groq")
    call_count = 0
    sleeps: list[float] = []

    async def mock_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("app.services.llm.asyncio.sleep", mock_sleep)

    async def mock_create(**_kwargs: Any) -> Any:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            err = RateLimitError("429 rate limit exceeded")
            err.response = SimpleNamespace(headers={"retry-after": "5"})  # type: ignore[attr-defined]
            raise err
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok after 429"))])

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=mock_create)))
    monkeypatch.setattr("app.services.llm.get_client_for", lambda *_a, **_k: fake_client)

    resp = await chat_completions_create_with_opencode_fallback(messages=[{"role": "user", "content": "hi"}])
    assert resp.choices[0].message.content == "ok after 429"
    assert call_count == 3
    assert len(sleeps) == 2
    assert sleeps[0] == 5.0
    assert sleeps[1] == 5.0
