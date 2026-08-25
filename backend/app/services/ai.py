"""LLM client for the onboarding conversation loop (Groq / OpenCode Zen).

Talks to any OpenAI-compatible endpoint via ``base_url`` override. The actual
chat-completion callable lives behind a module-level seam
(:func:`_chat_completions_create`) so tests can monkeypatch it instead of
hitting a real provider.
"""

import asyncio
import json
import logging
import uuid
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.models.onboarding_answers import OnboardingAnswer
from app.models.subject_profile import SubjectProfile
from app.services.completeness import compute_completeness
from app.tools.dispatcher import ToolRetryTracker, execute_tool, get_tool_definitions
from app.tools.handlers import MAX_ONBOARDING_QUESTIONS

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 8
MAX_TOOL_RETRIES = 3

# Tools whose input schema carries a subject_id — the server overrides it so
# model-supplied values can never target another subject (or an invalid one).
_SUBJECT_SCOPED_TOOLS = frozenset(
    {"ask_question", "save_answer", "update_profile_slots", "finalize_profile"}
)

SEED_QUESTION_LABEL = "seed intent"

# Pending-question registry: Redis-backed with in-memory fallback.
# The question the assistant asked most recently and the user's next message
# will answer. Redis gives cross-worker consistency; fallback keeps single-
# process dev working when Redis is down.
_pending_questions: dict[uuid.UUID, str] = {}
_pending_locks: dict[uuid.UUID, asyncio.Lock] = {}
_PENDING_TTL_SECONDS = 24 * 3600
_PENDING_KEY_PREFIX = "pending_question:"


def _get_pending_question(subject_id: uuid.UUID) -> str | None:
    """Sync in-memory fallback — used by tests and as Redis fallback."""
    return _pending_questions.get(subject_id)


def _set_pending_question(subject_id: uuid.UUID, question: str) -> None:
    """Sync in-memory fallback."""
    _pending_questions[subject_id] = question


def _clear_pending_question(subject_id: uuid.UUID) -> None:
    """Sync in-memory fallback."""
    _pending_questions.pop(subject_id, None)


def _pending_key(subject_id: uuid.UUID) -> str:
    """Redis key for a subject's open question."""
    return f"{_PENDING_KEY_PREFIX}{subject_id}"


async def _get_pending_question_async(subject_id: uuid.UUID) -> str | None:
    """Redis-first get with in-memory fallback."""
    try:
        from app.db.redis import get_redis_client

        client = get_redis_client()
        val = await client.get(_pending_key(subject_id))
        if val is not None:
            # Keep memory in sync for fallback reads
            str_val = val.decode() if isinstance(val, bytes) else val
            _pending_questions[subject_id] = str_val
            return str_val
    except Exception as exc:  # noqa: BLE001
        logger.debug("Redis pending get fallback for %s: %s", subject_id, exc)
    return _pending_questions.get(subject_id)


async def _set_pending_question_async(subject_id: uuid.UUID, question: str) -> None:
    """Redis-first set with TTL + in-memory fallback."""
    _pending_questions[subject_id] = question
    try:
        from app.db.redis import get_redis_client

        client = get_redis_client()
        await client.set(_pending_key(subject_id), question, ex=_PENDING_TTL_SECONDS)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Redis pending set fallback for %s: %s", subject_id, exc)


async def _clear_pending_question_async(subject_id: uuid.UUID) -> None:
    """Redis-first delete + in-memory fallback."""
    _pending_questions.pop(subject_id, None)
    try:
        from app.db.redis import get_redis_client

        client = get_redis_client()
        await client.delete(_pending_key(subject_id))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Redis pending clear fallback for %s: %s", subject_id, exc)


FINALIZE_DIRECTIVE = (
    "MANDATORY: you must call finalize_profile NOW and state remaining "
    "assumptions in plain words; do NOT call ask_question."
)

_ASSUMPTION_VALUES: dict[str, str] = {
    "goal": "not specified — assume general proficiency building in this subject",
    "current_level": "not specified — assume beginner",
    "background": "not specified — assume no prior experience",
    "motivation": "not specified — assume personal growth",
}


class AiConfigError(Exception):
    """Raised when the configured AI provider lacks credentials/base URL."""


class AiGenerationError(Exception):
    """Raised when the provider call or tool loop fails irrecoverably."""


class OnboardingTurnResult(BaseModel):
    """Outcome of a single onboarding conversational turn."""

    reply: str
    finalized: bool
    questions_asked: int


# ============================================================================
# Provider plumbing
# ============================================================================

_client_cache: dict[tuple[str, str], AsyncOpenAI] = {}


def _resolve_provider() -> tuple[str, str, str]:
    """Resolve (base_url, api_key, model) for the configured provider."""
    provider = settings.ai_provider.strip().lower()
    if provider == "groq":
        return (
            settings.ai_base_url_groq,
            settings.groq_api_key,
            settings.ai_model_groq,
        )
    if provider == "opencode":
        return (
            settings.ai_base_url_opencode,
            settings.opencode_api_key,
            settings.ai_model_opencode,
        )
    raise AiConfigError(
        f"Unknown ai_provider '{settings.ai_provider}' (expected 'groq' or 'opencode')."
    )


def get_client() -> AsyncOpenAI:
    """Build (or reuse) the AsyncOpenAI client for the configured provider."""
    base_url, api_key, _model = _resolve_provider()
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


async def _chat_completions_create(**kwargs: Any) -> Any:
    """Seam around the SDK call - monkeypatch this in tests."""
    client = get_client()
    return await client.chat.completions.create(**kwargs)


# ============================================================================
# State helpers
# ============================================================================


async def _load_profile(
    session: AsyncSession, subject_id: uuid.UUID
) -> SubjectProfile | None:
    """Load a subject profile via select so expired instances are refreshed.

    ``session.get`` can return a stale identity-map instance left expired by
    an earlier rollback; a fresh SELECT hydrates it safely.
    """
    stmt = select(SubjectProfile).where(SubjectProfile.subject_id == subject_id)
    return (await session.exec(stmt)).first()


async def _count_answers(session: AsyncSession, subject_id: uuid.UUID) -> int:
    """Count persisted onboarding answers for a subject."""
    stmt = select(OnboardingAnswer).where(OnboardingAnswer.subject_id == subject_id)
    results = (await session.exec(stmt)).all()
    return len(results)


def _extract_user_content(messages: list[dict[str, Any]]) -> str:
    """Return the most recent non-empty user message content."""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
    return ""


async def _persist_fallback_answer(
    session: AsyncSession,
    subject_id: uuid.UUID,
    user_content: str,
    pairing_question: str,
) -> bool:
    """Server-side guarantee that the user's message lands in onboarding_answers."""
    result = await execute_tool(
        session,
        "save_answer",
        {
            "subject_id": str(subject_id),
            "question": pairing_question,
            "answer": user_content,
        },
    )
    if not result.success:
        logger.warning(
            "Fallback save_answer failed for subject %s: %s (%s)",
            subject_id,
            result.error,
            result.error_code,
        )
        return False
    return True


async def _deterministic_finalize(
    session: AsyncSession,
    subject_id: uuid.UUID,
    profile: SubjectProfile | None,
) -> str:
    """Finalize the profile server-side, filling missing slots with assumptions.

    Returns a plain-language reply describing what was assumed.
    """
    assumed_slots: list[str] = []
    args: dict[str, Any] = {
        "subject_id": str(subject_id),
        "pace_preference": profile.pace_preference.value if profile else "steady",
    }
    for slot, assumption in _ASSUMPTION_VALUES.items():
        existing = getattr(profile, slot, "") if profile else ""
        if existing and existing.strip():
            args[slot] = existing.strip()
        else:
            args[slot] = assumption
            assumed_slots.append(slot)

    result = await execute_tool(session, "finalize_profile", args)
    if not result.success:
        raise AiGenerationError(
            f"Deterministic finalize_profile failed: {result.error} "
            f"(code={result.error_code})"
        )

    if assumed_slots:
        listed = ", ".join(assumed_slots)
        return (
            "Your learning profile is ready! Because our question budget ran out, "
            f"I made reasonable assumptions for: {listed}. "
            "You can update these anytime and I'll adapt your roadmap."
        )
    return "Your learning profile is ready — let's start your personalized roadmap!"


# ============================================================================
# Main turn loop
# ============================================================================


async def run_onboarding_turn(
    messages: list[dict[str, Any]],
    system_context: str,
    session: AsyncSession,
    subject_id: uuid.UUID,
) -> OnboardingTurnResult:
    """Run one full onboarding turn against the LLM with server-side tool execution.

    Enforcement (never trusting the model):
    - Pre-computes answer count / completeness; appends a mandatory-finalize
      directive to the system prompt when the question cap is reached or the
      completeness score hits 100.
    - Hard-stops any tool after ``MAX_TOOL_RETRIES`` consecutive failures.
    - Deterministically finalizes the profile if the model refuses while stop
      conditions are met.
    - Guarantees the user's message is persisted via ``save_answer``, paired
      with the subject's tracked open question (server-side pending-question
      registry, not model memory).
    """
    _, _, model = _resolve_provider()

    profile = await _load_profile(session, subject_id)
    answers_count = await _count_answers(session, subject_id)
    pending = await _get_pending_question_async(subject_id)
    pairing_question = pending or SEED_QUESTION_LABEL

    completeness = compute_completeness(profile)
    enforce_finalize = (
        answers_count >= MAX_ONBOARDING_QUESTIONS or completeness.score >= 100
    )

    system_content = system_context
    if enforce_finalize:
        system_content = f"{system_context}\n\n{FINALIZE_DIRECTIVE}"

    conversation: list[dict[str, Any]] = [
        {"role": "system", "content": system_content},
        *messages,
    ]

    tracker = ToolRetryTracker(max_retries=MAX_TOOL_RETRIES)
    finalize_executed = False
    save_answer_executed = False
    asked_questions: list[str] = []
    reply = ""
    finalized = False

    for _round in range(MAX_TOOL_ROUNDS):
        # Retry provider calls on rate limits (429) with exponential backoff
        response = None
        last_err: Exception | None = None
        for _attempt in range(4):  # 1 initial + 3 retries
            try:
                response = await _chat_completions_create(
                    model=model,
                    messages=conversation,
                    tools=get_tool_definitions(),
                    tool_choice="auto",
                )
                last_err = None
                break
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
                # Log provider error for live debugging (no secrets)
                logger.warning(
                    "AI provider error (attempt %s/4) %s: %s",
                    _attempt + 1,
                    err_name,
                    err,
                )
                if is_rate_limit and _attempt < 3:
                    backoff = (2**_attempt) * 1.5  # 1.5, 3, 6 seconds
                    # respect Retry-After if present
                    try:
                        retry_after = getattr(err, "response", None)  # type: ignore[attr-defined]
                        if retry_after is not None and hasattr(retry_after, "headers"):
                            hdr = retry_after.headers.get(
                                "retry-after"
                            ) or retry_after.headers.get("Retry-After")  # type: ignore[attr-defined]
                            if hdr:
                                backoff = max(backoff, float(hdr))
                    except Exception:
                        pass
                    await asyncio.sleep(backoff)
                    continue
                raise AiGenerationError(
                    f"AI provider call failed: {err_name}: {err}"
                ) from err
        if last_err is not None:
            # Should have raised already, but ensure we surface it
            raise AiGenerationError(
                f"AI provider call failed: {type(last_err).__name__}: {last_err}"
            ) from last_err
        assert response is not None

        choice_message = response.choices[0].message
        tool_calls = getattr(choice_message, "tool_calls", None)

        if not tool_calls:
            reply = choice_message.content or ""
            finalized = finalize_executed
            break

        conversation.append(
            {
                "role": "assistant",
                "content": choice_message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )

        for tool_call in tool_calls:
            name = tool_call.function.name

            if tracker.is_exhausted(name):
                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(
                            {
                                "success": False,
                                "error_code": "TOOL_RETRY_LIMIT_REACHED",
                                "error": (
                                    f"Tool '{name}' is disabled for this turn "
                                    f"after {MAX_TOOL_RETRIES} consecutive failures."
                                ),
                            }
                        ),
                    }
                )
                continue

            try:
                arguments = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError as err:
                tracker.record_failure(name)
                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(
                            {
                                "success": False,
                                "error_code": "VALIDATION_ERROR",
                                "error": f"Arguments were not valid JSON ({err}); "
                                "resend valid JSON matching the tool schema.",
                            }
                        ),
                    }
                )
                continue

            # The model never knows the subject's UUID; scope every
            # subject-scoped tool call to the subject this turn belongs to.
            if name in _SUBJECT_SCOPED_TOOLS:
                arguments["subject_id"] = str(subject_id)

            result = await execute_tool(session, name, arguments)

            if result.success:
                tracker.record_success(name)
                if name == "finalize_profile":
                    finalize_executed = True
                    finalized = True
                elif name == "save_answer":
                    save_answer_executed = True
                    answers_count += 1
                elif name == "ask_question" and result.data:
                    question_text = str(result.data.get("question") or "").strip()
                    if question_text:
                        asked_questions.append(question_text)
                elif name == "update_profile_slots" and result.data:
                    if result.data.get("score") == 100:
                        enforce_finalize = True
            else:
                tracker.record_failure(name)

            conversation.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result.model_dump_json(),
                }
            )

        if enforce_finalize and not finalize_executed:
            conversation.append(
                {
                    "role": "system",
                    "content": FINALIZE_DIRECTIVE,
                }
            )

    # ------------------------------------------------------------------
    # Post-loop enforcement
    # ------------------------------------------------------------------
    cap_reached_now = answers_count >= MAX_ONBOARDING_QUESTIONS
    if not finalized and (enforce_finalize or cap_reached_now):
        refreshed_profile = await _load_profile(session, subject_id)
        reply = await _deterministic_finalize(session, subject_id, refreshed_profile)
        finalized = True

    # Persistence guarantee: make sure the user's message lands in the DB,
    # paired with the open question it answers (or the seed label).
    if not save_answer_executed:
        user_content = _extract_user_content(messages)
        if user_content:
            persisted = await _persist_fallback_answer(
                session,
                subject_id,
                user_content,
                pairing_question,
            )
            if persisted:
                answers_count += 1

    # The open question is now consumed: either its answer was just persisted
    # or the onboarding finished. If this turn asked a fresh question (and the
    # conversation is still live), it becomes the next open question.
    await _clear_pending_question_async(subject_id)
    if not finalized and asked_questions:
        await _set_pending_question_async(subject_id, asked_questions[-1])

    if not reply:
        reply = (
            "Thanks — tell me a bit more about your goal so I can tailor your roadmap."
        )

    questions_asked = await _count_answers(session, subject_id)
    return OnboardingTurnResult(
        reply=reply, finalized=finalized, questions_asked=questions_asked
    )
