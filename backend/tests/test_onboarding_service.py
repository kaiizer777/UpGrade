"""Onboarding turn-loop tests using a scripted fake LLM (no real API calls)."""

import json
import uuid
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.models.onboarding_answers import OnboardingAnswer
from app.models.subject import Subject
from app.models.subject_profile import (
    PacePreference,
    SubjectProfile,
    SubjectProfileStatus,
)
from app.services import ai as ai_module
from app.services.ai import (
    AiGenerationError,
    OnboardingTurnResult,
    run_onboarding_turn,
)
from app.tools.dispatcher import TOOL_REGISTRY

# ============================================================================
# Fake LLM plumbing
# ============================================================================


def _tool_call(call_id: str, name: str, args: dict[str, Any]) -> SimpleNamespace:
    """Build an OpenAI-shaped tool_call object."""
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
        raise ValueError(f"Unknown script step: {step!r}")


async def _create_subject(session: AsyncSession, title: str) -> Subject:
    """Helper to create a persisted subject."""
    subject = Subject(title=title, description="Onboarding service test")
    session.add(subject)
    await session.commit()
    await session.refresh(subject)
    return subject


async def _get_profile(
    session: AsyncSession, subject_id: uuid.UUID
) -> SubjectProfile | None:
    """Re-fetch a profile via SELECT so rollback-expired state is refreshed."""
    stmt = select(SubjectProfile).where(SubjectProfile.subject_id == subject_id)
    return (await session.exec(stmt)).first()


async def _load_answers(session: AsyncSession, subject_id: uuid.UUID) -> list:
    stmt = (
        select(OnboardingAnswer)
        .where(OnboardingAnswer.subject_id == subject_id)
        .order_by(OnboardingAnswer.created_at.asc())  # type: ignore[union-attr]
    )
    return list((await session.exec(stmt)).all())


def _user_msg(content: str) -> list[dict[str, str]]:
    return [{"role": "user", "content": content}]


@pytest.fixture(autouse=True)
def _reset_pending_questions() -> Iterator[None]:
    """Isolate the module-level pending-question registry between tests."""
    ai_module._pending_questions.clear()
    yield
    ai_module._pending_questions.clear()


# ============================================================================
# Pending-question tracking & transcript pairing
# ============================================================================


@pytest.mark.asyncio
async def test_pending_question_pairs_followup_answer(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession
) -> None:
    """Turn 1 asks Q; turn 2's answer is persisted against exactly that Q."""
    subject = await _create_subject(session, "Pairing Subject")
    question = "What's your programming background?"
    llm_ask = ScriptedLLM(
        [
            (
                "tools",
                [
                    (
                        "ask_question",
                        {"question": question, "subject_id": str(subject.id)},
                    )
                ],
            ),
            ("text", ""),
        ]
    )
    monkeypatch.setattr(ai_module, "_chat_completions_create", llm_ask)

    await run_onboarding_turn(
        messages=_user_msg("I want to learn DSA"),
        system_context="ctx",
        session=session,
        subject_id=subject.id,
    )
    assert ai_module._get_pending_question(subject.id) == question

    # Turn 2: model only produces text (no save_answer) - the fallback must
    # pair the user's reply with the tracked open question.
    llm_text = ScriptedLLM(
        [("tools", [("ask_question", {"question": "Pace?"})]), ("text", "")]
    )
    monkeypatch.setattr(ai_module, "_chat_completions_create", llm_text)

    await run_onboarding_turn(
        messages=[
            {
                "role": "assistant",
                "content": question,
            },
            _user_msg("Beginner with basic Python")[0],
        ],
        system_context="ctx",
        session=session,
        subject_id=subject.id,
    )

    answers = await _load_answers(session, subject.id)
    assert len(answers) == 2
    assert answers[0].question == "seed intent"
    assert answers[1].question == question
    assert answers[1].answer == "Beginner with basic Python"

    # The follow-up question asked this turn replaced the consumed one.
    assert ai_module._get_pending_question(subject.id) == "Pace?"

    # The provider received the system context plus replayed transcript
    # (assistant question then user answer) ahead of the current message.
    second_call_messages = llm_text.calls[0]["messages"]
    roles = [m["role"] for m in second_call_messages]
    assert roles[:3] == ["system", "assistant", "user"]


@pytest.mark.asyncio
async def test_finalize_clears_pending_question(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession
) -> None:
    """Finalization consumes the open question - nothing stays pending."""
    subject = await _create_subject(session, "Finalize Clear Subject")
    ai_module._set_pending_question(subject.id, "Any last thoughts?")
    session.add(
        SubjectProfile(
            subject_id=subject.id,
            goal="g",
            current_level="l",
            background="b",
            motivation="m",
            pace_preference=PacePreference.STEADY,
            status=SubjectProfileStatus.ONBOARDING,
        )
    )
    await session.commit()

    llm = ScriptedLLM(
        [
            (
                "tools",
                [
                    (
                        "finalize_profile",
                        {
                            "subject_id": str(subject.id),
                            "goal": "g",
                            "current_level": "l",
                            "background": "b",
                            "motivation": "m",
                            "pace_preference": "steady",
                        },
                    )
                ],
            ),
            ("text", "All set!"),
        ]
    )
    monkeypatch.setattr(ai_module, "_chat_completions_create", llm)

    result = await run_onboarding_turn(
        messages=_user_msg("nope done"),
        system_context="ctx",
        session=session,
        subject_id=subject.id,
    )

    assert result.finalized is True
    assert ai_module._get_pending_question(subject.id) is None


# ============================================================================
# Happy path Q&A turns
# ============================================================================


@pytest.mark.asyncio
async def test_happy_path_question_then_final_text(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession
) -> None:
    """Model asks a question then replies with final text; seed message persisted."""
    subject = await _create_subject(session, "DSA Journey")
    llm = ScriptedLLM(
        [
            (
                "tools",
                [
                    (
                        "ask_question",
                        {
                            "question": "What's your programming background?",
                            "why": "To calibrate depth",
                            "subject_id": str(subject.id),
                        },
                    )
                ],
            ),
            ("text", "Got it — what's your weekly time budget?"),
        ]
    )
    monkeypatch.setattr(ai_module, "_chat_completions_create", llm)

    result: OnboardingTurnResult = await run_onboarding_turn(
        messages=_user_msg("I want to learn DSA"),
        system_context="You are the onboarding coach.",
        session=session,
        subject_id=subject.id,
    )

    assert result.finalized is False
    assert "weekly time budget" in result.reply
    assert result.questions_asked == 1

    # Persistence guarantee: user message paired with the seed label.
    answers = await _load_answers(session, subject.id)
    assert len(answers) == 1
    assert answers[0].question == "seed intent"
    assert answers[0].answer == "I want to learn DSA"

    # Tools payload passed to the provider includes the whole registry.
    assert len(llm.calls[0]["tools"]) == len(TOOL_REGISTRY)
    assert llm.calls[0]["tool_choice"] == "auto"
    assert llm.calls[0]["messages"][0]["role"] == "system"


@pytest.mark.asyncio
async def test_model_save_answer_prevents_fallback_persistence(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession
) -> None:
    """When the model persists the answer itself, no duplicate row is written."""
    subject = await _create_subject(session, "Rust Track")
    llm = ScriptedLLM(
        [
            (
                "tools",
                [
                    (
                        "save_answer",
                        {
                            "subject_id": str(subject.id),
                            "question": "What do you want to build?",
                            "answer": "CLI tools in Rust",
                        },
                    )
                ],
            ),
            ("text", "Nice choice — how many hours per week can you study?"),
        ]
    )
    monkeypatch.setattr(ai_module, "_chat_completions_create", llm)

    result = await run_onboarding_turn(
        messages=_user_msg("I want to build CLI tools"),
        system_context="ctx",
        session=session,
        subject_id=subject.id,
    )

    answers = await _load_answers(session, subject.id)
    assert result.questions_asked == 1
    assert len(answers) == 1
    assert answers[0].question == "What do you want to build?"
    assert answers[0].answer == "CLI tools in Rust"


@pytest.mark.asyncio
async def test_subject_id_override_scopes_tool_calls(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession
) -> None:
    """Model-supplied subject_id values are overridden server-side."""
    subject = await _create_subject(session, "Override Subject")
    other = await _create_subject(session, "Other Subject")
    llm = ScriptedLLM(
        [
            (
                "tools",
                [
                    (
                        "update_profile_slots",
                        {
                            "subject_id": str(other.id),  # model targets wrongly
                            "goal": "Build a CLI in Rust",
                        },
                    )
                ],
            ),
            ("text", "Noted your goal!"),
        ]
    )
    monkeypatch.setattr(ai_module, "_chat_completions_create", llm)

    await run_onboarding_turn(
        messages=_user_msg("I want to build CLI tools"),
        system_context="ctx",
        session=session,
        subject_id=subject.id,
    )

    stmt = select(SubjectProfile).where(
        SubjectProfile.subject_id == subject.id  # type: ignore[arg-type]
    )
    profile = (await session.exec(stmt)).first()
    assert profile is not None
    assert profile.goal == "Build a CLI in Rust"


# ============================================================================
# Cap enforcement
# ============================================================================


@pytest.mark.asyncio
async def test_cap_reached_forces_finalize_directive_and_fallback(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession
) -> None:
    """At 10 answers the loop injects MANDATORY finalize and falls back server-side."""
    subject = await _create_subject(session, "Capped Subject")
    for i in range(10):
        session.add(
            OnboardingAnswer(
                subject_id=subject.id,
                question=f"Q{i}",
                answer=f"A{i}",
            )
        )
    await session.commit()

    llm = ScriptedLLM([("text", "Maybe I should ask about deadlines...")])
    monkeypatch.setattr(ai_module, "_chat_completions_create", llm)

    # Capture before the turn: a mid-turn rollback expires ORM instances.
    sid = subject.id
    result = await run_onboarding_turn(
        messages=_user_msg("just wrap it up please"),
        system_context="You are the onboarding coach.",
        session=session,
        subject_id=sid,
    )

    assert result.finalized is True
    # Directive injected into the system prompt sent to the provider.
    system_msgs = [
        m
        for m in llm.calls[0]["messages"]
        if m["role"] == "system" and "MANDATORY" in m["content"]
    ]
    assert system_msgs

    # Deterministic fallback finalized the profile with assumptions.
    profile = await _get_profile(session, sid)
    assert profile is not None
    assert profile.status == SubjectProfileStatus.READY
    assert "assumptions for:" in result.reply.lower()
    assert "not specified" in profile.goal.lower()
    assert result.questions_asked >= 10


# ============================================================================
# Score-threshold enforcement
# ============================================================================


@pytest.mark.asyncio
async def test_score_100_triggers_server_side_finalize(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession
) -> None:
    """A fully-complete profile forces finalize even when the model refuses."""
    subject = await _create_subject(session, "Full Slots Subject")
    session.add(
        SubjectProfile(
            subject_id=subject.id,
            goal="Pass CKA",
            current_level="Intermediate",
            background="DevOps",
            motivation="Certification",
            pace_preference=PacePreference.CHILL,
            status=SubjectProfileStatus.ONBOARDING,
        )
    )
    await session.commit()

    llm = ScriptedLLM([("text", "Anything else you'd like to share?")])
    monkeypatch.setattr(ai_module, "_chat_completions_create", llm)

    result = await run_onboarding_turn(
        messages=_user_msg("nope that's everything"),
        system_context="ctx",
        session=session,
        subject_id=subject.id,
    )

    assert result.finalized is True
    profile = await _get_profile(session, subject.id)
    assert profile is not None
    assert profile.status == SubjectProfileStatus.READY
    # Real slot values survive - no assumption strings overwrote them.
    assert profile.goal == "Pass CKA"
    assert profile.pace_preference == PacePreference.CHILL
    assert "assumed" not in result.reply.lower()


@pytest.mark.asyncio
async def test_midturn_full_slots_inject_directive_next_round(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession
) -> None:
    """Filling the last slot mid-turn injects the directive before the next round."""
    subject = await _create_subject(session, "Midturn Subject")
    session.add(
        SubjectProfile(
            subject_id=subject.id,
            goal="Get promoted",
            current_level="Senior dev",
            background="Backend Go services",
            motivation="",  # last missing text slot
            status=SubjectProfileStatus.ONBOARDING,
        )
    )
    await session.commit()

    llm = ScriptedLLM(
        [
            (
                "tools",
                [
                    (
                        "update_profile_slots",
                        {
                            "subject_id": str(subject.id),
                            "motivation": "Staff promotion cycle",
                        },
                    )
                ],
            ),
            (
                "tools",
                [
                    (
                        "finalize_profile",
                        {
                            "subject_id": str(subject.id),
                            "goal": "Get promoted",
                            "current_level": "Senior dev",
                            "background": "Backend Go services",
                            "motivation": "Staff promotion cycle",
                            "pace_preference": "steady",
                        },
                    )
                ],
            ),
            ("text", "You're all set — roadmap incoming!"),
        ]
    )
    monkeypatch.setattr(ai_module, "_chat_completions_create", llm)

    result = await run_onboarding_turn(
        messages=_user_msg("promotion is my driver"),
        system_context="ctx",
        session=session,
        subject_id=subject.id,
    )

    assert result.finalized is True
    profile = await _get_profile(session, subject.id)
    assert profile is not None
    assert profile.motivation == "Staff promotion cycle"
    assert profile.status == SubjectProfileStatus.READY

    # Second provider call already carried the mandatory directive.
    second_system = [
        m["content"] for m in llm.calls[1]["messages"] if m["role"] == "system"
    ]
    assert any("MANDATORY" in c for c in second_system)


# ============================================================================
# Fallback persistence & retry tracker hard-stop
# ============================================================================


@pytest.mark.asyncio
async def test_retry_tracker_hard_stops_failing_tool(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession
) -> None:
    """After 3 consecutive failures the loop stops issuing that tool."""
    subject = await _create_subject(session, "Retry Subject")

    # Empty question fails schema validation every time regardless of the
    # server-side subject_id override.
    fail_step = (
        "tools",
        [
            (
                "save_answer",
                {
                    "question": "",
                    "answer": "A",
                },
            )
        ],
    )
    llm = ScriptedLLM([fail_step] * 8)
    monkeypatch.setattr(ai_module, "_chat_completions_create", llm)

    result = await run_onboarding_turn(
        messages=_user_msg("hello"),
        system_context="ctx",
        session=session,
        subject_id=subject.id,
    )

    # Loop consumed its full round budget without crashing.
    assert len(llm.calls) == 8
    assert result.finalized is False

    # Later rounds received the retry-limit error fed back as tool output.
    last_conversation = llm.calls[-1]["messages"]
    tool_msgs = [m for m in last_conversation if m.get("role") == "tool"]
    assert any("TOOL_RETRY_LIMIT_REACHED" in m["content"] for m in tool_msgs)


@pytest.mark.asyncio
async def test_unparseable_tool_arguments_count_as_failure(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession
) -> None:
    """Non-JSON arguments produce a validation feedback message."""
    subject = await _create_subject(session, "Bad Args Subject")

    broken_call = SimpleNamespace(
        id="call_broken",
        function=SimpleNamespace(name="ask_question", arguments="{not json"),
    )
    bad_step = ("__raw_tools__", [broken_call])
    llm = ScriptedLLM([bad_step, ("text", "Let me rephrase.")])
    monkeypatch.setattr(ai_module, "_chat_completions_create", llm)

    result = await run_onboarding_turn(
        messages=_user_msg("hi"),
        system_context="ctx",
        session=session,
        subject_id=subject.id,
    )

    assert "rephrase" in result.reply
    tool_msgs = [m for m in llm.calls[1]["messages"] if m.get("role") == "tool"]
    assert any("VALIDATION_ERROR" in m["content"] for m in tool_msgs)


# ============================================================================
# Provider failure mapping
# ============================================================================


@pytest.mark.asyncio
async def test_provider_exception_wrapped_as_generation_error(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession
) -> None:
    """Raw SDK/network exceptions never escape; they chain into AiGenerationError."""

    async def boom(**kwargs: Any) -> Any:
        raise RuntimeError("connection reset by peer")

    monkeypatch.setattr(ai_module, "_chat_completions_create", boom)
    subject = await _create_subject(session, "Boom Subject")

    with pytest.raises(AiGenerationError) as exc_info:
        await run_onboarding_turn(
            messages=_user_msg("hello"),
            system_context="ctx",
            session=session,
            subject_id=subject.id,
        )

    assert isinstance(exc_info.value.__cause__, RuntimeError)


@pytest.mark.asyncio
async def test_unknown_provider_raises_config_error(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession
) -> None:
    """An unrecognized ai_provider maps to AiConfigError."""
    monkeypatch.setattr(settings, "ai_provider", "bogus-provider")
    subject = await _create_subject(session, "Config Subject")

    from app.services.ai import AiConfigError

    with pytest.raises(AiConfigError):
        await run_onboarding_turn(
            messages=_user_msg("hello"),
            system_context="ctx",
            session=session,
            subject_id=subject.id,
        )


@pytest.mark.asyncio
async def test_missing_api_key_raises_config_error(
    monkeypatch: pytest.MonkeyPatch, session: AsyncSession
) -> None:
    """An empty provider API key maps to AiConfigError."""
    monkeypatch.setattr(settings, "ai_provider", "groq")
    monkeypatch.setattr(settings, "groq_api_key", "")
    subject = await _create_subject(session, "No Key Subject")

    from app.services.ai import AiConfigError

    with pytest.raises(AiConfigError):
        await run_onboarding_turn(
            messages=_user_msg("hello"),
            system_context="ctx",
            session=session,
            subject_id=subject.id,
        )
