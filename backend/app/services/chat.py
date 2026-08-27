"""Open Chat service: topic-scoped chat with profile+prereq context + persistence."""

import asyncio  # noqa: F401
import json
import logging
import uuid
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.analytics import record_event, record_latency
from app.core.config import settings  # noqa: F401
from app.models.chat_message import ChatMessage
from app.models.subject import Subject
from app.models.subject_profile import SubjectProfile
from app.models.topic import Topic
from app.services.llm import (
    AiConfigError,
    AiGenerationError,
    _resolve_provider,
    chat_completions_create_with_opencode_fallback,
    get_client,
)
from app.tools.dispatcher import TOOL_REGISTRY, execute_tool

logger = logging.getLogger(__name__)


class SubjectNotFoundError(Exception):
    """Raised when referenced subject does not exist."""


class TopicNotFoundError(Exception):
    """Raised when referenced topic does not exist or mismatched subject."""


# ============================================================================
# Provider plumbing (delegated to app.services.llm)
# ============================================================================

_chat_completions_create = chat_completions_create_with_opencode_fallback
_resolve_provider = _resolve_provider
get_client = get_client


def _build_chat_system_prompt(
    profile: SubjectProfile | None,
    subject: Subject,
    topic: Topic,
    prereq_topics: list[Topic],
) -> str:
    prereq_titles = (
        ", ".join(t.title for t in prereq_topics)
        if prereq_topics
        else "None (first topic)"
    )
    pace = "steady"
    if profile:
        raw = profile.pace_preference
        pace = raw.value if hasattr(raw, "value") else str(raw)
    lines = [
        "You are UpGrade's Open Chat tutor. Answer the learner's question scoped to the current topic.",
        f"Subject: {subject.title}",
    ]
    if subject.description:
        lines.append(f"Subject description: {subject.description}")
    if profile:
        lines.extend(
            [
                f"Learner goal: {profile.goal}",
                f"Current level: {profile.current_level}",
                f"Background: {profile.background}",
                f"Motivation: {profile.motivation}",
                f"Pace preference: {pace}",
            ]
        )
    lines.extend(
        [
            f"Current topic: {topic.title} (order {topic.order_index})",
            f"Prerequisite topics already covered: {prereq_titles}",
            "",
            "Rules:",
            "- Stay scoped to the current topic and its prerequisites. Don't teach future topics.",
            "- Personalize: adapt depth, tone, examples to goal/level/background/pace.",
            "- Be concise, helpful, and encourage learning. Use examples relevant to learner's goal.",
            "- You may optionally call the log_chat_message tool to persist your reply, but a plain text reply is also acceptable - it will be persisted server-side.",
        ]
    )
    return "\n".join(lines)


async def _load_prereqs(session: AsyncSession, topic: Topic) -> list[Topic]:
    if not topic.prerequisite_ids:
        return []
    stmt = select(Topic).where(Topic.id.in_(topic.prerequisite_ids))  # type: ignore[attr-defined,union-attr]
    res = await session.exec(stmt)
    return list(res.all())


async def _load_history(session: AsyncSession, topic_id: int) -> list[ChatMessage]:
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.topic_id == topic_id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())  # type: ignore[attr-defined,union-attr]
    )
    res = await session.exec(stmt)
    return list(res.all())


async def _load_profile(
    session: AsyncSession, subject_id: uuid.UUID
) -> SubjectProfile | None:
    stmt = select(SubjectProfile).where(SubjectProfile.subject_id == subject_id)
    return (await session.exec(stmt)).first()


def _history_to_llm_messages(history: list[ChatMessage]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for m in history:
        out.append(
            {
                "role": m.role.value if hasattr(m.role, "value") else str(m.role),
                "content": m.content,
            }
        )
    return out


async def get_chat_history(
    session: AsyncSession,
    subject_id: uuid.UUID,
    topic_id: int,
) -> list[ChatMessage]:
    """Load ordered chat history for a topic, validating subject/topic scoping."""
    subject = await session.get(Subject, subject_id)
    if not subject:
        raise SubjectNotFoundError(f"Subject '{subject_id}' not found.")
    topic = await session.get(Topic, topic_id)
    if not topic or topic.subject_id != subject_id:
        raise TopicNotFoundError(
            f"Topic '{topic_id}' not found for subject '{subject_id}'."
        )
    return await _load_history(session, topic_id)


async def chat_turn(
    session: AsyncSession,
    subject_id: uuid.UUID,
    topic_id: int,
    message: str,
) -> dict[str, Any]:
    """Run a single Open Chat turn: persist user+AI and return reply + history.

    Raises:
        SubjectNotFoundError, TopicNotFoundError, AiConfigError, AiGenerationError
        ValueError if message empty.
    """
    import time

    _chat_start = time.perf_counter()
    cleaned = message.strip() if isinstance(message, str) else ""
    if not cleaned:
        raise ValueError("message must be a non-empty string")

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

    profile = await _load_profile(session, subject_id)
    prereq_topics = await _load_prereqs(session, topic)
    history_before = await _load_history(session, topic_id)

    # Persist user turn via log_chat_message tool (ensures validation + FK check)
    user_result = await execute_tool(
        session,
        "log_chat_message",
        {"topic_id": topic_id, "role": "user", "content": cleaned},
    )
    if not user_result.success:
        # Should map to validation error but preserve as generation error for caller
        raise AiGenerationError(user_result.error or "Failed to persist user message")

    # Reload history for LLM context (including just-saved user message could be appended separately)
    # Build conversation: system + prior history + new user message
    system_prompt = _build_chat_system_prompt(profile, subject, topic, prereq_topics)

    conversation: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        *_history_to_llm_messages(history_before),
        {"role": "user", "content": cleaned},
    ]

    # Provide log_chat_message as optional tool + allow plain text reply
    tool_def = TOOL_REGISTRY["log_chat_message"]
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

    reply_text = ""
    # If model called log_chat_message tool, extract its content; otherwise use plain text
    if tool_calls:
        # Find first log_chat_message call
        for tc in tool_calls:
            if tc.function.name == "log_chat_message":
                try:
                    args = json.loads(tc.function.arguments or "{}")
                    cand = args.get("content")
                    if isinstance(cand, str) and cand.strip():
                        reply_text = cand.strip()
                        break
                except Exception:
                    continue
        if not reply_text:
            reply_text = (choice_message.content or "").strip()
    else:
        reply_text = (choice_message.content or "").strip()

    if not reply_text:
        # Fallback generic reply if model returned empty
        reply_text = (
            "I'm here to help — could you rephrase your question about this topic?"
        )

    # Persist assistant turn via log_chat_message tool
    ai_result = await execute_tool(
        session,
        "log_chat_message",
        {"topic_id": topic_id, "role": "assistant", "content": reply_text},
    )
    if not ai_result.success:
        raise AiGenerationError(ai_result.error or "Failed to persist AI message")
    elapsed_ms = int((time.perf_counter() - _chat_start) * 1000)
    record_latency("chat_turn", elapsed_ms)
    record_event("chat_turn_success", topic_id=topic_id, latency_ms=elapsed_ms)

    # Reload full history ordered
    full_history = await _load_history(session, topic_id)
    # Serialize messages for response
    messages_payload = [
        {
            "id": m.id,
            "topic_id": m.topic_id,
            "role": m.role.value if hasattr(m.role, "value") else str(m.role),
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in full_history
    ]
    return {"reply": reply_text, "messages": messages_payload}
