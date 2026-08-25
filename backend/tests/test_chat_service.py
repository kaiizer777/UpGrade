"""Chat service tests using scripted fake LLM (no real API calls)."""

import json
import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.chat_message import ChatMessage
from app.models.subject import Subject
from app.models.subject_profile import PacePreference, SubjectProfile, SubjectProfileStatus
from app.models.topic import Topic, TopicStatus
from app.services import chat as chat_module
from app.services.ai import AiConfigError, AiGenerationError
from app.services.chat import SubjectNotFoundError, TopicNotFoundError, chat_turn, get_chat_history


def _tool_call(call_id: str, name: str, args: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(args)))


class ScriptedLLM:
    def __init__(self, steps: list[Any]) -> None:
        self.steps = list(steps)
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        step = self.steps.pop(0)
        if step[0] == "text":
            content = step[1]
            message = SimpleNamespace(content=content, tool_calls=None)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])
        if step[0] == "tools":
            tool_calls = [_tool_call(f"call_{i}", name, args) for i, (name, args) in enumerate(step[1])]
            message = SimpleNamespace(content="", tool_calls=tool_calls)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])
        if step[0] == "error":
            raise step[1]
        raise ValueError(f"Unknown step {step!r}")


async def _create_subject(session: AsyncSession, title: str = "Chat Subject") -> Subject:
    s = Subject(title=title, description="chat test")
    session.add(s)
    await session.commit()
    await session.refresh(s)
    return s


async def _make_ready_profile(session: AsyncSession, subject_id: uuid.UUID) -> SubjectProfile:
    p = SubjectProfile(
        subject_id=subject_id,
        goal="Master DSA for FAANG",
        current_level="Intermediate",
        background="CS grad with Python",
        motivation="Career growth",
        pace_preference=PacePreference.STEADY,
        status=SubjectProfileStatus.READY,
    )
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return p


async def _create_topic(session: AsyncSession, subject_id: uuid.UUID, title: str = "Recursion", order: int = 1) -> Topic:
    t = Topic(subject_id=subject_id, title=title, order_index=order, prerequisite_ids=[], status=TopicStatus.ACTIVE)
    session.add(t)
    await session.commit()
    await session.refresh(t)
    return t


@pytest.mark.asyncio
async def test_chat_turn_happy_path_persists_both(monkeypatch: pytest.MonkeyPatch, session: AsyncSession) -> None:
    subject = await _create_subject(session)
    await _make_ready_profile(session, subject.id)
    topic = await _create_topic(session, subject.id)

    llm = ScriptedLLM([("text", "Recursion is a function calling itself with a base case.")])
    monkeypatch.setattr(chat_module, "_chat_completions_create", llm)
    monkeypatch.setattr(chat_module.asyncio, "sleep", lambda *_a, **_k: __import__("asyncio").sleep(0))  # type: ignore

    result = await chat_turn(session, subject.id, topic.id, "explain recursion")  # type: ignore[arg-type]

    assert result["reply"] == "Recursion is a function calling itself with a base case."
    assert len(result["messages"]) == 2
    assert result["messages"][0]["role"] == "user"
    assert result["messages"][0]["content"] == "explain recursion"
    assert result["messages"][1]["role"] == "assistant"
    assert "Recursion" in result["messages"][1]["content"]

    # DB persistence check
    stmt = select(ChatMessage).where(ChatMessage.topic_id == topic.id).order_by(ChatMessage.id)  # type: ignore[attr-defined]
    rows = list((await session.exec(stmt)).all())
    assert len(rows) == 2
    assert rows[0].role.value == "user"
    assert rows[1].role.value == "assistant"

    # System prompt contains profile context
    sys_contents = [m["content"] for m in llm.calls[0]["messages"] if m["role"] == "system"]
    assert any("Master DSA" in c for c in sys_contents)
    assert any("Recursion" in c for c in sys_contents)


@pytest.mark.asyncio
async def test_chat_history_used_in_second_turn(monkeypatch: pytest.MonkeyPatch, session: AsyncSession) -> None:
    subject = await _create_subject(session)
    await _make_ready_profile(session, subject.id)
    topic = await _create_topic(session, subject.id)

    llm1 = ScriptedLLM([("text", "First reply")])
    monkeypatch.setattr(chat_module, "_chat_completions_create", llm1)
    await chat_turn(session, subject.id, topic.id, "first question")  # type: ignore[arg-type]

    llm2 = ScriptedLLM([("text", "Second reply")])
    monkeypatch.setattr(chat_module, "_chat_completions_create", llm2)

    result2 = await chat_turn(session, subject.id, topic.id, "second question")  # type: ignore[arg-type]

    assert len(result2["messages"]) == 4
    # Second call's messages should include history of 2 prior + new user
    msgs = llm2.calls[0]["messages"]
    # Roles sequence: system, user(first), assistant(first reply), user(second)
    roles = [m["role"] for m in msgs]
    assert roles[0] == "system"
    assert roles[1] == "user"
    assert msgs[1]["content"] == "first question"
    assert roles[2] == "assistant"
    assert msgs[2]["content"] == "First reply"
    assert roles[3] == "user"
    assert msgs[3]["content"] == "second question"


@pytest.mark.asyncio
async def test_get_chat_history_ordered(session: AsyncSession) -> None:
    subject = await _create_subject(session)
    topic = await _create_topic(session, subject.id)
    # Insert out of order? created_at same but id order defines
    for role, content in [("user", "hi"), ("assistant", "hello"), ("user", "bye")]:
        session.add(ChatMessage(topic_id=topic.id, role=role, content=content))  # type: ignore[arg-type]
    await session.commit()

    history = await get_chat_history(session, subject.id, topic.id)  # type: ignore[arg-type]
    assert [h.content for h in history] == ["hi", "hello", "bye"]
    assert [h.role.value for h in history] == ["user", "assistant", "user"]


@pytest.mark.asyncio
async def test_topic_scoping_isolated(monkeypatch: pytest.MonkeyPatch, session: AsyncSession) -> None:
    subject = await _create_subject(session)
    await _make_ready_profile(session, subject.id)
    t1 = await _create_topic(session, subject.id, "Topic A", 1)
    # second topic
    t2 = Topic(subject_id=subject.id, title="Topic B", order_index=2, prerequisite_ids=[t1.id], status=TopicStatus.PENDING)  # type: ignore[arg-type]
    session.add(t2)
    await session.commit()
    await session.refresh(t2)
    assert t2.id is not None

    llm = ScriptedLLM([("text", "reply A")])
    monkeypatch.setattr(chat_module, "_chat_completions_create", llm)
    await chat_turn(session, subject.id, t1.id, "question A")  # type: ignore[arg-type]

    # History for t2 should be empty
    history_t2 = await get_chat_history(session, subject.id, t2.id)  # type: ignore[arg-type]
    assert history_t2 == []

    # And t1 history still only its own messages
    history_t1 = await get_chat_history(session, subject.id, t1.id)  # type: ignore[arg-type]
    assert len(history_t1) == 2


@pytest.mark.asyncio
async def test_prerequisite_context_injected(monkeypatch: pytest.MonkeyPatch, session: AsyncSession) -> None:
    subject = await _create_subject(session)
    await _make_ready_profile(session, subject.id)
    t1 = await _create_topic(session, subject.id, "Arrays", 1)
    t2 = Topic(subject_id=subject.id, title="Recursion", order_index=2, prerequisite_ids=[t1.id], status=TopicStatus.ACTIVE)  # type: ignore[arg-type]
    session.add(t2)
    await session.commit()
    await session.refresh(t2)
    assert t2.id is not None

    llm = ScriptedLLM([("text", "reply")])
    monkeypatch.setattr(chat_module, "_chat_completions_create", llm)
    await chat_turn(session, subject.id, t2.id, "explain recursion")  # type: ignore[arg-type]

    sys = [m["content"] for m in llm.calls[0]["messages"] if m["role"] == "system"][0]
    assert "Arrays" in sys
    assert "Recursion" in sys


@pytest.mark.asyncio
async def test_chat_404_subject(session: AsyncSession) -> None:
    fake_topic = 999
    # Use random subject
    with pytest.raises(SubjectNotFoundError):
        await chat_turn(session, uuid.uuid4(), fake_topic, "hi")


@pytest.mark.asyncio
async def test_chat_404_topic_mismatch(session: AsyncSession) -> None:
    s1 = await _create_subject(session, "S1")
    s2 = await _create_subject(session, "S2")
    t = await _create_topic(session, s1.id)
    with pytest.raises(TopicNotFoundError):
        await chat_turn(session, s2.id, t.id, "hi")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_chat_empty_message_raises(session: AsyncSession) -> None:
    s = await _create_subject(session)
    t = await _create_topic(session, s.id)
    with pytest.raises(ValueError):
        await chat_turn(session, s.id, t.id, "   ")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_chat_503_on_missing_key(monkeypatch: pytest.MonkeyPatch, session: AsyncSession) -> None:
    s = await _create_subject(session)
    await _make_ready_profile(session, s.id)
    t = await _create_topic(session, s.id)
    # Force provider to have no key
    monkeypatch.setattr(chat_module.settings, "groq_api_key", "")
    monkeypatch.setattr(chat_module.settings, "ai_provider", "groq")
    # Also ensure _chat_completions_create would raise config if called; but chat_turn resolves provider first
    with pytest.raises(AiConfigError):
        await chat_turn(session, s.id, t.id, "hi")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_chat_502_on_provider_failure(monkeypatch: pytest.MonkeyPatch, session: AsyncSession) -> None:
    s = await _create_subject(session)
    await _make_ready_profile(session, s.id)
    t = await _create_topic(session, s.id)

    async def boom(**_k: Any) -> Any:
        raise RuntimeError("provider down")

    monkeypatch.setattr(chat_module, "_chat_completions_create", boom)
    with pytest.raises(AiGenerationError):
        await chat_turn(session, s.id, t.id, "hi")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_tool_call_reply_extracted(monkeypatch: pytest.MonkeyPatch, session: AsyncSession) -> None:
    """Model returns log_chat_message tool call; service extracts content."""
    s = await _create_subject(session)
    await _make_ready_profile(session, s.id)
    t = await _create_topic(session, s.id)

    llm = ScriptedLLM([("tools", [("log_chat_message", {"topic_id": t.id, "role": "assistant", "content": "Tool reply content"})])])
    monkeypatch.setattr(chat_module, "_chat_completions_create", llm)
    result = await chat_turn(session, s.id, t.id, "hi")  # type: ignore[arg-type]
    assert result["reply"] == "Tool reply content"
    # Still persisted as assistant
    history = await get_chat_history(session, s.id, t.id)  # type: ignore[arg-type]
    assert history[-1].content == "Tool reply content"
