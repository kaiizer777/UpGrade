"""LLM client and fallback orchestration (Groq / OpenCode Zen).

Provides centralized provider resolution, client caching, rate-limit exponential
backoff, and OpenCode model fallback (hy3-free -> nemotron-3-ultra-free).
"""

import asyncio
import logging
from typing import Any

from openai import AsyncOpenAI

from app.core.analytics import record_event
from app.core.config import settings

logger = logging.getLogger(__name__)

_client_cache: dict[tuple[str, str], AsyncOpenAI] = {}


class AiConfigError(Exception):
    """Raised when the configured AI provider lacks credentials/base URL."""


class AiGenerationError(Exception):
    """Raised when the provider call or tool loop fails irrecoverably."""


def _resolve_provider_for(provider: str | None = None) -> tuple[str, str, list[str]]:
    """Resolve (base_url, api_key, model_list) for the configured or given provider."""
    p = (provider or settings.ai_provider).strip().lower()
    if p == "groq":
        return (
            settings.ai_base_url_groq,
            settings.groq_api_key,
            [settings.ai_model_groq],
        )
    if p == "opencode":
        models = [settings.ai_model_opencode]
        if (
            settings.ai_model_opencode_fallback
            and settings.ai_model_opencode_fallback.strip()
        ):
            models.append(settings.ai_model_opencode_fallback.strip())
        return (
            settings.ai_base_url_opencode,
            settings.opencode_api_key,
            models,
        )
    raise AiConfigError(
        f"Unknown ai_provider '{provider or settings.ai_provider}' (expected 'groq' or 'opencode')."
    )


def _resolve_provider() -> tuple[str, str, str]:
    """Resolve (base_url, api_key, primary_model) - convenience for single-model callers."""
    base_url, api_key, models = _resolve_provider_for()
    return (base_url, api_key, models[0])


def get_client_for(base_url: str, api_key: str) -> AsyncOpenAI:
    """Build (or reuse) the AsyncOpenAI client for the given base_url and api_key."""
    if not api_key:
        raise AiConfigError(
            f"AI provider '{settings.ai_provider}' has no API key configured."
        )
    cache_key = (base_url, api_key)
    client = _client_cache.get(cache_key)
    if client is None:
        client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        _client_cache[cache_key] = client
    return client


def get_client() -> AsyncOpenAI:
    """Build (or reuse) the AsyncOpenAI client for the default configured provider."""
    base_url, api_key, _ = _resolve_provider_for()
    return get_client_for(base_url, api_key)


async def chat_completions_create_with_opencode_fallback(**kwargs: Any) -> Any:
    """Perform chat completion with 429 backoff and OpenCode model fallback.

    For Groq: single model try with 4x rate limit retry.
    For OpenCode: tries primary model (hy3-free) with 4x retry, on failure falls back
    to fallback model (nemotron-3-ultra-free) with 4x retry.
    """
    base_url, api_key, models = _resolve_provider_for()
    client = get_client_for(base_url, api_key)

    provider = settings.ai_provider.strip().lower()

    # Determine models to attempt
    if provider == "opencode":
        kwargs.pop("model", None)
        models_to_try = list(models)
    else:
        explicit_model = kwargs.pop("model", None)
        models_to_try = [explicit_model] if explicit_model else list(models)

    last_err: Exception | None = None

    for model_idx, model in enumerate(models_to_try):
        for attempt in range(4):  # 1 initial + 3 retries
            try:
                return await client.chat.completions.create(model=model, **kwargs)
            except AiConfigError:
                raise
            except Exception as err:
                last_err = err
                err_name = type(err).__name__
                err_str = str(err)
                is_rate_limit = (
                    "RateLimitError" in err_name
                    or "rate_limit" in err_str.lower()
                    or "429" in err_str
                )
                logger.warning(
                    "AI provider error (provider=%s, model=%s, attempt=%s/4) %s: %s",
                    provider,
                    model,
                    attempt + 1,
                    err_name,
                    err,
                )
                if is_rate_limit and attempt < 3:
                    backoff = (2**attempt) * 1.5
                    try:
                        retry_after = getattr(err, "response", None)
                        if retry_after is not None and hasattr(retry_after, "headers"):
                            hdr = retry_after.headers.get(
                                "retry-after"
                            ) or retry_after.headers.get("Retry-After")
                            if hdr:
                                backoff = max(backoff, float(hdr))
                    except Exception:
                        pass
                    await asyncio.sleep(backoff)
                    continue
                # Non-rate-limit error (e.g. 500, 502, 503) or exhausted retries: break to fallback
                break

        # If more models exist, log fallback and record event
        if model_idx + 1 < len(models_to_try):
            next_model = models_to_try[model_idx + 1]
            logger.warning(
                "AI model '%s' failed (%s: %s). Falling back to '%s'.",
                model,
                type(last_err).__name__,
                last_err,
                next_model,
            )
            record_event(
                "opencode_fallback",
                from_model=model,
                to_model=next_model,
                error=type(last_err).__name__,
            )

    if last_err is not None:
        raise AiGenerationError(
            f"AI provider call failed: {type(last_err).__name__}: {last_err}"
        ) from last_err

    raise AiGenerationError("AI provider call failed: no models configured")
