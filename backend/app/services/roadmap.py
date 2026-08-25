"""Roadmap generation service: subject_profile → ordered topic DAG."""

import asyncio
import json
import logging
import uuid
from typing import Any

from fastapi import BackgroundTasks
from openai import AsyncOpenAI
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.models.subject import Subject
from app.models.subject_profile import SubjectProfile, SubjectProfileStatus
from app.models.topic import Topic, TopicStatus
from app.services.ai import AiConfigError, AiGenerationError
from app.tools.dispatcher import TOOL_REGISTRY, ToolRetryTracker, execute_tool

logger = logging.getLogger(__name__)

# Keep strong references to asyncio Tasks scheduled outside request context so they
# are not garbage-collected before completion. Tasks are removed via done callback.
_background_tasks: set[asyncio.Task[Any]] = set()


def _background_task_done_callback(task: asyncio.Task[Any]) -> None:
    """Remove completed task from set and log any error."""
    _background_tasks.discard(task)
    if task.cancelled():
        logger.warning("Roadmap background feed prefetch task was cancelled")
        return
    exc = task.exception()
    if exc is not None:
        logger.warning("Roadmap background feed prefetch task failed: %s", exc)
    else:
        logger.debug("Roadmap background feed prefetch task completed")


async def _prefetch_first_feed(subject_id: uuid.UUID, topic_id: int) -> None:
    """Attempt arq enqueue for feed generation, falling back to direct generation.

    Durable via Redis/arq when available; direct DB generation is the fallback if
    Redis is down so request does not lose work after worker recycle.
    """
    # Try arq enqueue first (durable across worker restarts)
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        from app.core.config import settings as _settings

        redis_settings = RedisSettings.from_dsn(_settings.redis_url)
        pool = await create_pool(redis_settings)
        try:
            await pool.enqueue_job(
                "generate_feed_batch", str(subject_id), int(topic_id)
            )
            logger.info(
                "Enqueued first feed generation via arq for subject %s topic %s",
                subject_id,
                topic_id,
            )
            return
        finally:
            await pool.close()
    except Exception as exc:
        logger.debug(
            "arq enqueue failed for first feed prefetch, falling back: %s", exc
        )

    # Fallback: direct generation with fresh session
    try:
        from app.db.database import async_session_maker as _maker
        from app.services.feed import generate_feed_batch as _gen_feed

        async with _maker() as _sess:
            await _gen_feed(_sess, subject_id, int(topic_id))
        logger.info(
            "Direct fallback feed generation succeeded for subject %s topic %s",
            subject_id,
            topic_id,
        )
    except Exception as exc:
        logger.warning(
            "First feed background generation failed for subject %s topic %s: %s",
            subject_id,
            topic_id,
            exc,
        )


def _schedule_first_feed(
    subject_id: uuid.UUID,
    topic_id: int,
    background_tasks: BackgroundTasks | None = None,
) -> None:
    """Schedule first-feed generation via BackgroundTasks or tracked asyncio Task."""
    try:
        if background_tasks is not None:
            background_tasks.add_task(_prefetch_first_feed, subject_id, int(topic_id))
            logger.info(
                "Scheduled first feed generation via BackgroundTasks for subject %s topic %s",
                subject_id,
                topic_id,
            )
            return
        task: asyncio.Task[Any] = asyncio.create_task(
            _prefetch_first_feed(subject_id, int(topic_id))
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_task_done_callback)
        logger.info(
            "Scheduled first feed generation via tracked asyncio task for subject %s topic %s",
            subject_id,
            topic_id,
        )
    except Exception as exc:
        logger.warning("Failed to schedule first feed generation: %s", exc)


MAX_TOOL_ROUNDS = 8
MAX_TOOL_RETRIES = 3

_SUBJECT_SCOPED_TOOLS = frozenset({"create_roadmap"})

_client_cache: dict[tuple[str, str], AsyncOpenAI] = {}


class SubjectNotFoundError(Exception):
    """Raised when the referenced subject does not exist."""


class RoadmapNotReadyError(Exception):
    """Raised when onboarding is not finalized (profile missing or not ready)."""


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


def _build_roadmap_system_prompt(profile: SubjectProfile, subject: Subject) -> str:
    """Build the system prompt for roadmap generation from a profile + subject.

    Pure function - no IO, easy to unit test.
    """
    lines = [
        "You are UpGrade's curriculum architect. Your job is to generate a "
        "personalized, prerequisite-ordered roadmap for the learner's subject.",
        f"Subject title: {subject.title}",
    ]
    if subject.description:
        lines.append(f"Subject description: {subject.description}")
    lines.extend(
        [
            f"Learner goal: {profile.goal}",
            f"Current level: {profile.current_level}",
            f"Background: {profile.background}",
            f"Motivation: {profile.motivation}",
            f"Pace preference: {profile.pace_preference.value}",
            "",
            "Rules:",
            "- NO dates, deadlines, hours, or calendar estimates. "
            "Sequence only via prerequisites.",
            "- Produce 6-12 topics, ordered 1..N contiguous. "
            "Each topic has a concise title (3-6 words).",
            "- Each topic MUST include order_index (1..N contiguous, first topic=1; "
            "server will auto-assign if omitted).",
            "- Each topic after the first must list prerequisite_indices = "
            "order_indices of earlier topics it depends on. No forward refs, "
            "no cycles (DAG only).",
            "- Tailor depth and ordering to the learner's current_level and goal. "
            "A beginner needs foundations first; an advanced learner can skip basics.",
            "- Example for DSA: Arrays → Strings → Hashing → Two Pointers → "
            "Stack/Queue → Linked List → ... but you MUST personalize to this learner.",
            "- Call exactly one tool: create_roadmap with subject_id "
            "(system will scope it) and the ordered topics list.",
            "- Do NOT return roadmap as plain text - you MUST call the tool.",
        ]
    )
    return "\n".join(lines)


def _validate_create_roadmap_args(args: dict[str, Any]) -> str | None:
    """Validate create_roadmap args before persistence.

    Returns an error message if invalid, None if valid.
    """
    topics = args.get("topics")
    if not isinstance(topics, list) or len(topics) == 0:
        return "topics must be a non-empty list (6-12 items required)."
    if len(topics) < 6 or len(topics) > 12:
        return f"topics length {len(topics)} is invalid: must be 6-12 topics."
    # Extract order_index values
    order_indices: list[int] = []
    for t in topics:
        if not isinstance(t, dict):
            return (
                "Each topic must be an object with title, "
                "order_index, prerequisite_indices."
            )
        oi = t.get("order_index")
        title = t.get("title")
        if not isinstance(oi, int) or oi < 1:
            return f"Topic '{title}' has invalid order_index {oi!r} (must be int >=1)."
        if not isinstance(title, str) or not title.strip():
            return f"Topic with order_index {oi} has empty title."
        order_indices.append(oi)
    if len(order_indices) != len(set(order_indices)):
        return "Topic order_index values must be unique."
    sorted_indices = sorted(order_indices)
    expected = list(range(1, len(topics) + 1))
    if sorted_indices != expected:
        return (
            f"order_index must be contiguous 1..{len(topics)} without gaps; "
            f"got {sorted_indices}."
        )
    # Build order_index -> topic map
    index_set = set(order_indices)
    # Validate prerequisites forward-only
    # Build adjacency for cycle check: prereq -> topic
    adjacency: dict[int, list[int]] = {oi: [] for oi in order_indices}
    for t in topics:
        oi = t["order_index"]
        prereqs = t.get("prerequisite_indices") or []
        if prereqs is None:
            prereqs = []
        if not isinstance(prereqs, list):
            return f"Topic {oi} prerequisite_indices must be a list."
        for p in prereqs:
            if not isinstance(p, int):
                return f"Topic {oi} has non-int prerequisite {p!r}."
            if p not in index_set:
                return (
                    f"Topic {oi} references non-existent prerequisite order_index {p}."
                )
            if p >= oi:
                return (
                    f"Topic {oi} has forward prerequisite {p}: prerequisites must "
                    "reference earlier topics only (DAG, no forward refs)."
                )
            adjacency[p].append(oi)
    # Cycle detection via DFS (forward-only already ensures acyclic, check anyway)
    visiting: set[int] = set()
    visited: set[int] = set()

    def dfs(node: int) -> bool:
        visiting.add(node)
        for neighbor in adjacency.get(node, []):
            if neighbor in visiting:
                return True
            if neighbor not in visited and dfs(neighbor):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    for node in order_indices:
        if node not in visited and dfs(node):
            return "Cycle detected in prerequisite graph - roadmap must be a DAG."
    return None


async def _load_profile(
    session: AsyncSession, subject_id: uuid.UUID
) -> SubjectProfile | None:
    stmt = select(SubjectProfile).where(SubjectProfile.subject_id == subject_id)
    return (await session.exec(stmt)).first()


async def _load_topics(session: AsyncSession, subject_id: uuid.UUID) -> list[Topic]:
    stmt = (
        select(Topic)
        .where(Topic.subject_id == subject_id)
        .order_by(Topic.order_index.asc())  # type: ignore[attr-defined]
    )
    return list((await session.exec(stmt)).all())


def _to_roadmap_output(subject_id: uuid.UUID, topics: list[Topic]) -> dict[str, Any]:
    """Convert persisted topics to a serializable roadmap dict."""
    active_id = next((t.id for t in topics if t.status == TopicStatus.ACTIVE), None)
    return {
        "subject_id": subject_id,
        "topics": [
            {
                "id": t.id,
                "subject_id": t.subject_id,
                "title": t.title,
                "order_index": t.order_index,
                "prerequisite_ids": t.prerequisite_ids,
                "status": t.status.value
                if hasattr(t.status, "value")
                else str(t.status),
            }
            for t in topics
        ],
        "active_topic_id": active_id,
    }


async def generate_roadmap(
    session: AsyncSession,
    subject_id: uuid.UUID,
    background_tasks: BackgroundTasks | None = None,
) -> dict[str, Any]:
    """Generate a roadmap for a subject via a single LLM tool call.

    Raises:
        SubjectNotFoundError: if subject does not exist.
        RoadmapNotReadyError: if profile missing or status != ready.
        AiConfigError: if provider not configured.
        AiGenerationError: if LLM fails to produce a valid roadmap.
    """
    subject = await session.get(Subject, subject_id)
    if not subject:
        raise SubjectNotFoundError(f"Subject '{subject_id}' not found.")

    profile = await _load_profile(session, subject_id)
    if not profile or profile.status != SubjectProfileStatus.READY:
        raise RoadmapNotReadyError("Onboarding not finalized")

    existing = await _load_topics(session, subject_id)
    if existing:
        return _to_roadmap_output(subject_id, existing)

    _, _, model = _resolve_provider()
    system_prompt = _build_roadmap_system_prompt(profile, subject)

    # Only expose create_roadmap to the model for this turn
    tool_def = TOOL_REGISTRY["create_roadmap"]
    tool_definitions = [
        {
            "type": "function",
            "function": {
                "name": tool_def.name,
                "description": tool_def.description,
                "parameters": tool_def.input_schema.model_json_schema(),
            },
        }
    ]

    conversation: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"Generate the personalized roadmap for '{subject.title}' now.",
        },
    ]

    tracker = ToolRetryTracker(max_retries=MAX_TOOL_RETRIES)
    last_validation_error: str | None = None

    for _round in range(MAX_TOOL_ROUNDS):
        # Provider call with 429 retry
        response = None
        last_err: Exception | None = None
        for _attempt in range(4):
            try:
                response = await _chat_completions_create(
                    model=model,
                    messages=conversation,
                    tools=tool_definitions,
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
                logger.warning(
                    "Roadmap AI provider error (attempt %s/4) %s: %s",
                    _attempt + 1,
                    err_name,
                    err,
                )
                if is_rate_limit and _attempt < 3:
                    backoff = (2**_attempt) * 1.5
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
            raise AiGenerationError(
                f"AI provider call failed: {type(last_err).__name__}: {last_err}"
            ) from last_err
        assert response is not None

        choice_message = response.choices[0].message
        tool_calls = getattr(choice_message, "tool_calls", None)

        if not tool_calls:
            # Model returned text without tool call - feed error back, retry
            reply_text = choice_message.content or ""
            logger.warning(
                "Roadmap model returned text without tool call: %s", reply_text[:200]
            )
            # Push assistant text and a system nudge, let model retry
            conversation.append(
                {"role": "assistant", "content": reply_text or "(no content)"}
            )
            conversation.append(
                {
                    "role": "system",
                    "content": (
                        "You must call create_roadmap with 6-12 ordered topics and "
                        "prerequisite_indices. Plain text is not acceptable."
                    ),
                }
            )
            # If this was the last round, we will raise after loop
            continue

        # Attach assistant tool_calls to history
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

            if name != "create_roadmap":
                # Only create_roadmap is expected; inform model
                tracker.record_failure(name)
                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(
                            {
                                "success": False,
                                "error_code": "TOOL_NOT_FOUND",
                                "error": (
                                    f"Tool '{name}' is not available for "
                                    "roadmap generation. Use create_roadmap."
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
                                "error": (
                                    f"Arguments were not valid JSON ({err}); "
                                    "resend valid JSON matching the tool schema."
                                ),
                            }
                        ),
                    }
                )
                continue

            # Scope to this subject
            if name in _SUBJECT_SCOPED_TOOLS:
                arguments["subject_id"] = str(subject_id)

            validation_error = _validate_create_roadmap_args(arguments)
            if validation_error:
                tracker.record_failure(name)
                last_validation_error = validation_error
                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(
                            {
                                "success": False,
                                "error_code": "VALIDATION_ERROR",
                                "error": validation_error,
                                "details": {"validation_error": validation_error},
                            }
                        ),
                    }
                )
                continue

            result = await execute_tool(session, name, arguments)
            if result.success:
                tracker.record_success(name)
                data = result.data or {}
                active_id = data.get("active_topic_id")
                logger.info(
                    "Roadmap generated for subject %s: %s topics, active_topic_id=%s. "
                    "Triggering first generate_feed_batch job.",
                    subject_id,
                    len(data.get("topics", [])),
                    active_id,
                )
                # Trigger first feed generation via BackgroundTasks or tracked asyncio task
                # (durable via arq/Redis; fallback to direct generation if Redis down)
                if active_id is not None:
                    _schedule_first_feed(subject_id, int(active_id), background_tasks)
                return {
                    "subject_id": data.get("subject_id", str(subject_id)),
                    "topics": data.get("topics", []),
                    "active_topic_id": active_id,
                }
            else:
                tracker.record_failure(name)
                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result.model_dump_json(),
                    }
                )
                continue

    # Exhausted rounds without success
    detail = (
        last_validation_error
        or "Model did not call create_roadmap with a valid roadmap"
    )
    raise AiGenerationError(
        f"Roadmap generation failed: {detail} after {MAX_TOOL_ROUNDS} tool rounds."
    )
