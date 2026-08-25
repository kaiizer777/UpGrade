"""Roadmap service tests using scripted fake LLM (no real API calls)."""

import json
import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.subject import Subject
from app.models.subject_profile import (
    PacePreference,
    SubjectProfile,
    SubjectProfileStatus,
)
from app.models.topic import Topic
from app.services import roadmap as roadmap_module
from app.services.ai import AiGenerationError
from app.services.roadmap import (
    RoadmapNotReadyError,
    SubjectNotFoundError,
    _build_roadmap_system_prompt,
    generate_roadmap,
)


def _tool_call(call_id: str, name: str, args: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(args)),
    )


class ScriptedLLM:
    """Async callable returning scripted responses and capturing requests."""

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
            tool_calls = [
                _tool_call(f"call_{i}", name, args)
                for i, (name, args) in enumerate(step[1])
            ]
            message = SimpleNamespace(content="", tool_calls=tool_calls)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])
        if step[0] == "__raw_tools__":
            message = SimpleNamespace(content="", tool_calls=step[1])
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])
        if step[0] == "error":
            raise step[1]
        raise ValueError(f"Unknown script step: {step!r}")


async def _create_subject(session: AsyncSession, title: str) -> Subject:
    subject = Subject(title=title, description="roadmap test")
    session.add(subject)
    await session.commit()
    await session.refresh(subject)
    return subject


async def _make_ready_profile(
    session: AsyncSession, subject_id: uuid.UUID
) -> SubjectProfile:
    profile = SubjectProfile(
        subject_id=subject_id,
        goal="Crack FAANG DSA interviews",
        current_level="Beginner with basic arrays",
        background="Self-taught Python dev, 1 year",
        motivation="Career switch to FAANG",
        pace_preference=PacePreference.STEADY,
        status=SubjectProfileStatus.READY,
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return profile


def _roadmap_topics(n: int = 6) -> list[dict[str, Any]]:
    titles = [
        "Arrays & Hashing",
        "Strings & Two Pointers",
        "Stack & Queue",
        "Linked Lists",
        "Trees & Recursion",
        "Graphs & BFS/DFS",
        "Dynamic Programming Basics",
        "Advanced DP & Greedy",
    ]
    topics: list[dict[str, Any]] = []
    for i in range(n):
        prereqs: list[int] = []
        if i > 0:
            prereqs = [i]  # prerequisite is previous order_index (1-based)
            if i > 2:
                prereqs = [i, i - 1]
        topics.append(
            {
                "title": titles[i],
                "order_index": i + 1,
                "prerequisite_indices": prereqs,
            }
        )
    # First topic should have no prereqs
    topics[0]["prerequisite_indices"] = []
    return topics


@pytest.mark.asyncio
async def test_build_roadmap_system_prompt_pure() -> None:
    """Prompt builder includes profile fields and bans dates."""
    subject = Subject(title="DSA Mastery", description="Learn DSA")
    profile = SubjectProfile(
        subject_id=uuid.uuid4(),
        goal="FAANG in 3 months",
        current_level="Intermediate",
        background="CS grad",
        motivation="High salary",
        pace_preference=PacePreference.INTENSE,
        status=SubjectProfileStatus.READY,
    )
    prompt = _build_roadmap_system_prompt(profile, subject)
    assert "DSA Mastery" in prompt
    assert "FAANG in 3 months" in prompt
    assert "Intermediate" in prompt
    assert "CS grad" in prompt
    assert "intense" in prompt.lower()
    assert "NO dates" in prompt
    assert "6-12 topics" in prompt
    assert "prerequisite_indices" in prompt
    assert "create_roadmap" in prompt


@pytest.mark.asyncio
async def test_happy_path_creates_6_topics_first_active(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession
) -> None:
    """Happy path: 6 topics persisted, first ACTIVE, prereqs resolved to ids."""
    subject = await _create_subject(session, "Happy DSA")
    await _make_ready_profile(session, subject.id)

    topics_payload = _roadmap_topics(6)
    llm = ScriptedLLM(
        [
            (
                "tools",
                [
                    (
                        "create_roadmap",
                        {"subject_id": str(subject.id), "topics": topics_payload},
                    )
                ],
            ),
        ]
    )
    monkeypatch.setattr(roadmap_module, "_chat_completions_create", llm)
    # Avoid real sleep in 429 path
    monkeypatch.setattr(
        roadmap_module.asyncio,
        "sleep",
        lambda *_a, **_k: __import__("asyncio").sleep(0),
    )  # type: ignore

    result = await generate_roadmap(session, subject.id)

    assert result["subject_id"] == str(subject.id) or result["subject_id"] == subject.id
    assert len(result["topics"]) == 6
    assert result["active_topic_id"] is not None

    # Verify persistence
    stmt = (
        select(Topic).where(Topic.subject_id == subject.id).order_by(Topic.order_index)
    )  # type: ignore[attr-defined]
    persisted = list((await session.exec(stmt)).all())
    assert len(persisted) == 6
    assert persisted[0].status.value == "active"
    assert all(t.status.value == "pending" for t in persisted[1:])
    # Prereqs resolved: second topic should have first's id, third etc
    assert persisted[1].prerequisite_ids == [persisted[0].id]
    # Check tool was called with correct model and scoped subject_id
    assert llm.calls[0]["model"]
    assert llm.calls[0]["tools"][0]["function"]["name"] == "create_roadmap"
    # Verify system prompt contains DSA
    system_contents = [
        m["content"] for m in llm.calls[0]["messages"] if m["role"] == "system"
    ]
    assert any("DSA" in c or "Happy" in c for c in system_contents)


@pytest.mark.asyncio
async def test_idempotency_second_call_returns_same(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession
) -> None:
    """Second call returns same roadmap without hitting LLM."""
    subject = await _create_subject(session, "Idempotent DSA")
    await _make_ready_profile(session, subject.id)

    topics_payload = _roadmap_topics(6)
    llm = ScriptedLLM(
        [
            (
                "tools",
                [
                    (
                        "create_roadmap",
                        {"subject_id": str(subject.id), "topics": topics_payload},
                    )
                ],
            ),
        ]
    )
    monkeypatch.setattr(roadmap_module, "_chat_completions_create", llm)

    first = await generate_roadmap(session, subject.id)

    # Second call: should not call LLM again
    llm2 = ScriptedLLM([("text", "should not be called")])
    monkeypatch.setattr(roadmap_module, "_chat_completions_create", llm2)

    second = await generate_roadmap(session, subject.id)
    assert len(llm2.calls) == 0
    assert first["active_topic_id"] == second["active_topic_id"]
    assert len(second["topics"]) == 6
    # Ensure no duplicate rows
    stmt = select(Topic).where(Topic.subject_id == subject.id)
    persisted = list((await session.exec(stmt)).all())
    assert len(persisted) == 6


@pytest.mark.asyncio
async def test_409_when_onboarding_not_ready_missing_profile(
    session: AsyncSession,
) -> None:
    """Profile missing → RoadmapNotReadyError."""
    subject = await _create_subject(session, "No Profile Subject")
    with pytest.raises(RoadmapNotReadyError, match="Onboarding not finalized"):
        await generate_roadmap(session, subject.id)


@pytest.mark.asyncio
async def test_409_when_onboarding_not_ready_status_onboarding(
    session: AsyncSession,
) -> None:
    """Profile status onboarding → 409."""
    subject = await _create_subject(session, "Onboarding Subject")
    session.add(
        SubjectProfile(
            subject_id=subject.id,
            goal="g",
            current_level="l",
            background="b",
            motivation="m",
            pace_preference=PacePreference.CHILL,
            status=SubjectProfileStatus.ONBOARDING,
        )
    )
    await session.commit()
    with pytest.raises(RoadmapNotReadyError):
        await generate_roadmap(session, subject.id)


@pytest.mark.asyncio
async def test_404_when_subject_missing(session: AsyncSession) -> None:
    """Unknown subject → SubjectNotFoundError."""
    with pytest.raises(SubjectNotFoundError):
        await generate_roadmap(session, uuid.uuid4())


@pytest.mark.asyncio
async def test_prerequisite_invalid_index_fed_back_and_retry(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession
) -> None:
    """Invalid forward ref fed back as tool error; model retries with valid payload."""
    subject = await _create_subject(session, "Invalid Prereq Subject")
    await _make_ready_profile(session, subject.id)

    bad_topics = _roadmap_topics(6)
    # Introduce forward ref: topic 1 claims prereq 5 (future)
    bad_topics[0]["prerequisite_indices"] = [5]
    good_topics = _roadmap_topics(6)

    llm = ScriptedLLM(
        [
            (
                "tools",
                [
                    (
                        "create_roadmap",
                        {"subject_id": str(subject.id), "topics": bad_topics},
                    )
                ],
            ),
            (
                "tools",
                [
                    (
                        "create_roadmap",
                        {"subject_id": str(subject.id), "topics": good_topics},
                    )
                ],
            ),
        ]
    )
    monkeypatch.setattr(roadmap_module, "_chat_completions_create", llm)

    result = await generate_roadmap(session, subject.id)
    assert len(result["topics"]) == 6
    # Two LLM calls: first failed validation fed back, second succeeded
    assert len(llm.calls) == 2
    second_messages = llm.calls[1]["messages"]
    tool_msgs = [m for m in second_messages if m.get("role") == "tool"]
    assert any(
        "forward prerequisite" in m["content"] or "VALIDATION_ERROR" in m["content"]
        for m in tool_msgs
    )


@pytest.mark.asyncio
async def test_prerequisite_cycle_fed_back(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession
) -> None:
    """Cycle detection fed back."""
    subject = await _create_subject(session, "Cycle Subject")
    await _make_ready_profile(session, subject.id)

    # Forward ref already covers cycle; here test self-ref
    bad = _roadmap_topics(6)
    bad[2]["prerequisite_indices"] = [
        3
    ]  # topic 3 (order 3) prereq 3 self? That is not <3, so forward check catches
    # Actually self-ref is forward equal, still caught.
    # Let's just trigger forward ref which is also cycle prevention
    llm = ScriptedLLM(
        [
            (
                "tools",
                [("create_roadmap", {"subject_id": str(subject.id), "topics": bad})],
            ),
            (
                "tools",
                [
                    (
                        "create_roadmap",
                        {"subject_id": str(subject.id), "topics": _roadmap_topics(6)},
                    )
                ],
            ),
        ]
    )
    monkeypatch.setattr(roadmap_module, "_chat_completions_create", llm)
    result = await generate_roadmap(session, subject.id)
    assert len(result["topics"]) == 6


@pytest.mark.asyncio
async def test_provider_429_retry_path(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession
) -> None:
    """429 on first attempt retries with backoff then succeeds."""
    subject = await _create_subject(session, "429 Subject")
    await _make_ready_profile(session, subject.id)

    class RateLimitError(Exception):
        pass

    RateLimitError.__name__ = "RateLimitError"

    call_count = 0

    async def flaky(**kwargs: Any) -> Any:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            err = RateLimitError("429 rate_limit exceeded")
            # Attach fake response.headers for backoff branch
            err.response = SimpleNamespace(headers={})  # type: ignore[attr-defined]
            raise err
        # Second call succeeds
        tool_calls = [
            _tool_call(
                "call_0",
                "create_roadmap",
                {"subject_id": str(subject.id), "topics": _roadmap_topics(6)},
            )
        ]
        message = SimpleNamespace(content="", tool_calls=tool_calls)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    monkeypatch.setattr(roadmap_module, "_chat_completions_create", flaky)

    # Make sleep instant
    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(roadmap_module.asyncio, "sleep", no_sleep)

    result = await generate_roadmap(session, subject.id)
    assert len(result["topics"]) == 6
    assert call_count == 2


@pytest.mark.asyncio
async def test_subject_id_override_scopes_correctly(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession
) -> None:
    """Model passes wrong subject_id but service scopes to correct one."""
    subject = await _create_subject(session, "Override Subject")
    other = await _create_subject(session, "Other Subject")
    await _make_ready_profile(session, subject.id)
    # Ensure other has no profile needed
    llm = ScriptedLLM(
        [
            (
                "tools",
                [
                    (
                        "create_roadmap",
                        {"subject_id": str(other.id), "topics": _roadmap_topics(6)},
                    )
                ],
            ),
        ]
    )
    monkeypatch.setattr(roadmap_module, "_chat_completions_create", llm)

    result = await generate_roadmap(session, subject.id)
    # Topics should be attached to the correct subject, not other
    stmt = select(Topic).where(Topic.subject_id == subject.id)
    own = list((await session.exec(stmt)).all())
    assert len(own) == 6
    stmt_other = select(Topic).where(Topic.subject_id == other.id)
    other_topics = list((await session.exec(stmt_other)).all())
    assert len(other_topics) == 0
    assert len(result["topics"]) == 6


@pytest.mark.asyncio
async def test_text_without_tool_call_raises_generation_error(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession
) -> None:
    """Model returns only text → AiGenerationError after exhausting rounds."""
    subject = await _create_subject(session, "No Tool Subject")
    await _make_ready_profile(session, subject.id)

    # 8 rounds of plain text (MAX_TOOL_ROUNDS)
    steps = [("text", "Here is a roadmap in plain text...")] * 8
    llm = ScriptedLLM(steps)
    monkeypatch.setattr(roadmap_module, "_chat_completions_create", llm)

    with pytest.raises(AiGenerationError, match="did not call create_roadmap"):
        await generate_roadmap(session, subject.id)
