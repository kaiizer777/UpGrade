"""JIT Feed generation service: profile+topic+prereqs -> Groq -> 5-10 posts."""

import json
import logging
import uuid
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.analytics import record_event, record_latency
from app.models.feed_post import FeedPost
from app.models.subject import Subject
from app.models.subject_profile import SubjectProfile, SubjectProfileStatus
from app.models.topic import Topic, TopicStatus
from app.services.llm import (
    AiConfigError,
    AiGenerationError,
    _resolve_provider,
    chat_completions_create_with_opencode_fallback,
    get_client,
)
from app.tools.dispatcher import TOOL_REGISTRY, ToolRetryTracker, execute_tool

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 6
MAX_TOOL_RETRIES = 3


class SubjectNotFoundError(Exception):
    """Raised when referenced subject does not exist."""


class TopicNotFoundError(Exception):
    """Raised when referenced topic does not exist."""


class FeedNotReadyError(Exception):
    """Raised when profile not ready or topic not active."""


# ============================================================================
# Provider plumbing (delegated to app.services.llm)
# ============================================================================

_chat_completions_create = chat_completions_create_with_opencode_fallback
_resolve_provider = _resolve_provider
get_client = get_client


def _build_feed_system_prompt(
    profile: SubjectProfile,
    subject: Subject,
    topic: Topic,
    prereq_topics: list[Topic],
) -> str:
    """Build personalized system prompt for feed generation."""
    prereq_titles = (
        ", ".join(t.title for t in prereq_topics)
        if prereq_topics
        else "None (first topic)"
    )
    pace = (
        profile.pace_preference.value
        if hasattr(profile.pace_preference, "value")
        else str(profile.pace_preference)
    )
    lines = [
        "You are UpGrade's JIT feed tutor. Generate a personalized, bite-sized Twitter-style feed for ONE topic.",
        f"Subject: {subject.title}",
    ]
    if subject.description:
        lines.append(f"Subject description: {subject.description}")
    lines.extend(
        [
            f"Learner goal: {profile.goal}",
            f"Current level: {profile.current_level}",
            f"Background: {profile.background}",
            f"Motivation: {profile.motivation}",
            f"Pace preference: {pace}",
            f"Current topic: {topic.title} (order {topic.order_index})",
            f"Prerequisite topics already covered: {prereq_titles}",
            "",
            "Rules:",
            "- Call exactly one tool: generate_feed_batch with topic_id (system scopes it) and posts list.",
            "- Generate 5-10 posts, each 280 characters MAX (strict). Concise, punchy, lesson bite.",
            "- Each post: one micro-lesson, code/visual snippet, or mini-exercise. Sequential order (0..N-1).",
            "- Personalize deeply: goal/level/background/pace must change tone, depth, examples. Beginner needs foundations; advanced skips basics.",
            "- Do NOT be generic. Tailor examples to the learner's goal (e.g. FAANG vs building product).",
            "- No dates, deadlines, or calendars.",
            "- Do NOT return posts as plain text - you MUST call the tool.",
            "- Posts ordered by order_index 0..N-1 contiguous, unique.",
        ]
    )
    return "\n".join(lines)


def _validate_feed_args(args: dict[str, Any]) -> str | None:
    """Validate generate_feed_batch args for count and content constraints."""
    posts = args.get("posts")
    if not isinstance(posts, list) or len(posts) == 0:
        return "posts must be a non-empty list (5-10 items required)."
    if len(posts) < 5 or len(posts) > 10:
        return f"posts length {len(posts)} is invalid: must be 5-10 posts."
    seen: set[int] = set()
    for p in posts:
        if not isinstance(p, dict):
            return "Each post must be an object with content and order_index."
        content = p.get("content")
        oi = p.get("order_index")
        if not isinstance(content, str) or not content.strip():
            return f"Post with order_index {oi!r} has empty content."
        if len(content.strip()) > 280:
            return f"Post {oi!r} exceeds 280 characters ({len(content.strip())} chars)."
        if not isinstance(oi, int) or oi < 0:
            return f"Post '{content[:30]}' has invalid order_index {oi!r} (must be int >=0)."
        if oi in seen:
            return "Post order_index values must be unique."
        seen.add(oi)
    if sorted(seen) != list(range(len(posts))):
        return f"order_index must be contiguous 0..{len(posts) - 1} without gaps; got {sorted(seen)}."
    return None


async def _load_profile(
    session: AsyncSession, subject_id: uuid.UUID
) -> SubjectProfile | None:
    stmt = select(SubjectProfile).where(SubjectProfile.subject_id == subject_id)
    return (await session.exec(stmt)).first()


async def _load_topic(
    session: AsyncSession, topic_id: int, subject_id: uuid.UUID | None = None
) -> Topic | None:
    topic = await session.get(Topic, topic_id)
    if topic and subject_id and topic.subject_id != subject_id:
        return None
    return topic


async def _load_prereqs(session: AsyncSession, topic: Topic) -> list[Topic]:
    if not topic.prerequisite_ids:
        return []
    stmt = select(Topic).where(Topic.id.in_(topic.prerequisite_ids))  # type: ignore[attr-defined,union-attr]
    res = await session.exec(stmt)
    return list(res.all())


async def _load_existing_posts(session: AsyncSession, topic_id: int) -> list[FeedPost]:
    stmt = (
        select(FeedPost)
        .where(FeedPost.topic_id == topic_id)
        .order_by(FeedPost.order_index.asc())  # type: ignore[attr-defined]
    )
    res = await session.exec(stmt)
    return list(res.all())


def _to_feed_output(topic_id: int, posts: list[FeedPost]) -> dict[str, Any]:
    return {
        "topic_id": topic_id,
        "post_count": len(posts),
        "posts": [
            {
                "id": p.id,
                "topic_id": p.topic_id,
                "content": p.content,
                "order_index": p.order_index,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in sorted(posts, key=lambda x: x.order_index)
        ],
    }


async def generate_feed_batch(
    session: AsyncSession,
    subject_id: uuid.UUID,
    topic_id: int,
) -> dict[str, Any]:
    """Generate JIT feed for a topic via single LLM tool call.

    Idempotent: if posts already exist for topic, returns them without LLM call.

    Raises:
        SubjectNotFoundError, TopicNotFoundError, FeedNotReadyError, AiGenerationError
    """
    import time

    _gen_start = time.perf_counter()
    subject = await session.get(Subject, subject_id)
    if not subject:
        raise SubjectNotFoundError(f"Subject '{subject_id}' not found.")

    topic = await session.get(Topic, topic_id)
    if not topic:
        raise TopicNotFoundError(f"Topic '{topic_id}' not found.")
    if topic.subject_id != subject_id:
        raise TopicNotFoundError(
            f"Topic '{topic_id}' does not belong to subject '{subject_id}'."
        )

    existing_posts = await _load_existing_posts(session, topic_id)
    if existing_posts:
        return _to_feed_output(topic_id, existing_posts)

    profile = await _load_profile(session, subject_id)
    if not profile or profile.status != SubjectProfileStatus.READY:
        raise FeedNotReadyError("Onboarding not finalized or profile not ready")

    # Optional: enforce topic status? Allow pending/active but not done? Keep loose for prefetch.
    # If topic is pending and not active, still allow generation for prefetch.
    # But if status done? That would be unexpected.
    if topic.status == TopicStatus.DONE:
        raise FeedNotReadyError(f"Topic {topic_id} already completed")

    prereq_topics = await _load_prereqs(session, topic)
    system_prompt = _build_feed_system_prompt(profile, subject, topic, prereq_topics)

    tool_def = TOOL_REGISTRY["generate_feed_batch"]
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
            "content": f"Generate the personalized feed for topic '{topic.title}' now (5-10 posts, 280 chars each).",
        },
    ]

    tracker = ToolRetryTracker(max_retries=MAX_TOOL_RETRIES)
    last_validation_error: str | None = None

    for _round in range(MAX_TOOL_ROUNDS):
        try:
            response = await _chat_completions_create(
                messages=conversation,
                tools=tool_definitions,
                tool_choice="auto",
            )
        except (AiConfigError, AiGenerationError):
            raise
        except Exception as err:
            raise AiGenerationError(
                f"AI provider call failed: {type(err).__name__}: {err}"
            ) from err
        assert response is not None

        choice_message = response.choices[0].message
        tool_calls = getattr(choice_message, "tool_calls", None)

        if not tool_calls:
            reply_text = choice_message.content or ""
            logger.warning(
                "Feed model returned text without tool call: %s", reply_text[:200]
            )
            conversation.append(
                {"role": "assistant", "content": reply_text or "(no content)"}
            )
            conversation.append(
                {
                    "role": "system",
                    "content": "You must call generate_feed_batch with 5-10 posts (280 chars each) and order_index 0..N-1. Plain text not acceptable.",
                }
            )
            continue

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
                                "error": f"Tool '{name}' disabled after {MAX_TOOL_RETRIES} failures.",
                            }
                        ),
                    }
                )
                continue

            if name != "generate_feed_batch":
                tracker.record_failure(name)
                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(
                            {
                                "success": False,
                                "error_code": "TOOL_NOT_FOUND",
                                "error": f"Tool '{name}' not available. Use generate_feed_batch.",
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
                                "error": f"Arguments not valid JSON ({err}); resend valid JSON.",
                            }
                        ),
                    }
                )
                continue

            # Scope to correct topic (override if model hallucinates)
            arguments["topic_id"] = topic_id

            # Pre-validate before hitting DB for friendly feedback
            validation_error = _validate_feed_args(arguments)
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
                # Return persisted posts shape
                posts = data.get("posts", [])
                elapsed_ms = int((time.perf_counter() - _gen_start) * 1000)
                record_latency("feed_generation", elapsed_ms)
                record_event(
                    "feed_generated",
                    topic_id=topic_id,
                    post_count=len(posts),
                    generation_ms=elapsed_ms,
                )
                logger.info(
                    "Feed generated for topic %s: %s posts in %sms",
                    topic_id,
                    len(posts),
                    elapsed_ms,
                )
                return {
                    "topic_id": data.get("topic_id", topic_id),
                    "post_count": data.get("post_count", len(posts)),
                    "posts": posts,
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

    detail = (
        last_validation_error
        or "Model did not call generate_feed_batch with valid posts"
    )
    elapsed_ms = int((time.perf_counter() - _gen_start) * 1000)
    record_latency("feed_generation", elapsed_ms)
    record_event(
        "feed_generation_failed",
        topic_id=topic_id,
        latency_ms=elapsed_ms,
        reason=detail,
    )
    logger.warning(
        "Feed generation failed for topic %s after %sms: %s",
        topic_id,
        elapsed_ms,
        detail,
    )
    raise AiGenerationError(
        f"Feed generation failed: {detail} after {MAX_TOOL_ROUNDS} tool rounds."
    )
