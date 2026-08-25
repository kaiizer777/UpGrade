"""Onboarding orchestration: state snapshots and full conversational turns."""

import logging
import uuid

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.onboarding_answers import OnboardingAnswer
from app.models.subject import Subject
from app.models.subject_profile import SubjectProfile, SubjectProfileStatus
from app.schemas.onboarding import (
    CompletenessRead,
    OnboardingMessageRead,
    OnboardingStateRead,
    SubjectProfileSlotRead,
)
from app.schemas.onboarding_answers import OnboardingAnswerRead
from app.services.ai import run_onboarding_turn
from app.services.completeness import CompletenessInfo, compute_completeness
from app.tools.handlers import MAX_ONBOARDING_QUESTIONS

logger = logging.getLogger(__name__)


class SubjectNotFoundError(Exception):
    """Raised when the referenced subject does not exist."""


class OnboardingAlreadyFinalizedError(Exception):
    """Raised when onboarding was already finalized for the subject."""


def _status_string(profile: SubjectProfile | None) -> str:
    """Map a profile row to its public status string."""
    if profile and profile.status == SubjectProfileStatus.READY:
        return SubjectProfileStatus.READY.value
    return SubjectProfileStatus.ONBOARDING.value


async def _load_profile(
    session: AsyncSession, subject_id: uuid.UUID
) -> SubjectProfile | None:
    """Load a subject profile via select so expired instances are refreshed."""
    stmt = select(SubjectProfile).where(SubjectProfile.subject_id == subject_id)
    return (await session.exec(stmt)).first()


async def _load_answers(
    session: AsyncSession, subject_id: uuid.UUID
) -> list[OnboardingAnswer]:
    """Load all persisted onboarding answers for a subject, oldest first."""
    stmt = (
        select(OnboardingAnswer)
        .where(OnboardingAnswer.subject_id == subject_id)
        .order_by(OnboardingAnswer.created_at.asc())  # type: ignore[attr-defined]
    )
    return list((await session.exec(stmt)).all())


def build_system_context(
    subject: Subject,
    profile: SubjectProfile | None,
    completeness: CompletenessInfo,
    questions_asked: int,
) -> str:
    """Build the system prompt describing current onboarding progress."""
    lines = [
        (
            "You are UpGrade's onboarding coach. Your job is to personalize a "
            "learning roadmap by asking clarifying questions ONE AT A TIME."
        ),
        f"Subject title: {subject.title}",
    ]
    if subject.description:
        lines.append(f"Subject description: {subject.description}")

    known: dict[str, str] = {}
    for slot in completeness.filled_slots:
        raw = getattr(profile, slot) if profile else None
        if raw is None:
            continue
        # Enum values (pace) render as their string name for the model.
        value_str = getattr(raw, "value", raw)
        if isinstance(value_str, str) and value_str.strip():
            known[slot] = value_str.strip()
    if known:
        known_str = "; ".join(f"{slot}: {value}" for slot, value in known.items())
        lines.append(f"Known profile slots: {known_str}")
    else:
        lines.append("Known profile slots: none yet.")

    missing = ", ".join(completeness.missing_slots) or "none"
    remaining = MAX_ONBOARDING_QUESTIONS - questions_asked
    lines.extend(
        [
            f"Missing profile slots: {missing}.",
            (
                f"Completeness: {completeness.score}/100 "
                f"after {questions_asked} questions asked."
            ),
            (
                f"Question budget: {remaining} of {MAX_ONBOARDING_QUESTIONS} "
                "questions remain."
            ),
            (
                "Tool rules:\n"
                "- The system automatically persists the user's latest "
                "reply by pairing it with the previous assistant question "
                "(or 'seed intent' for the first turn) - you do NOT need to "
                "call save_answer. Focus your tool calls on profile slots "
                "and questions.\n"
                "- The instant you infer ANY slot value - goal (what they want to "
                "achieve), current_level (their present skill), background "
                "(education/experience), motivation (why they learn), "
                "pace_preference (chill|steady|intense) - immediately call "
                "update_profile_slots with exactly the slots you just learned "
                "(omit unknown ones). Do this EVERY turn you learn something, "
                "before you ask the next question.\n"
                "- Call ask_question to ask exactly ONE next question "
                "(never bundle).\n"
                "- When calling any tool, produce valid JSON: never escape "
                "single quotes as \\'; write I am instead of I'm.\n"
                "- When all 5 slots are filled (completeness 100) or the "
                "10-question budget runs out, call finalize_profile with concrete "
                "non-empty values for all slots and state any assumptions in your "
                "reply text."
            ),
        ]
    )
    return "\n".join(lines)


async def build_onboarding_state(
    session: AsyncSession, subject: Subject
) -> OnboardingStateRead:
    """Build the full onboarding state snapshot for a subject."""
    profile = await _load_profile(session, subject.id)
    answers = await _load_answers(session, subject.id)
    completeness = compute_completeness(profile)

    return OnboardingStateRead(
        subject_id=subject.id,
        status=_status_string(profile),
        questions_asked=len(answers),
        max_questions=MAX_ONBOARDING_QUESTIONS,
        completeness=CompletenessRead(
            score=completeness.score,
            filled_slots=completeness.filled_slots,
            missing_slots=completeness.missing_slots,
        ),
        answers=[OnboardingAnswerRead.model_validate(a) for a in answers],
        profile=(SubjectProfileSlotRead.model_validate(profile) if profile else None),
    )


def build_conversation_history(
    answers: list[OnboardingAnswer],
) -> list[dict[str, str]]:
    """Rebuild the Q&A transcript as alternating assistant/user messages.

    Each persisted answer row stores both halves of an exchange, so the
    assistant's prior questions and the user's replies can be replayed
    verbatim to keep the model grounded across turns.
    """
    history: list[dict[str, str]] = []
    for row in answers:
        history.append({"role": "assistant", "content": row.question})
        history.append({"role": "user", "content": row.answer})
    return history


async def process_onboarding_message(
    session: AsyncSession,
    subject_id: uuid.UUID,
    content: str,
) -> OnboardingMessageRead:
    """Run one full onboarding turn for a user message.

    Raises:
        SubjectNotFoundError: if the subject does not exist.
        OnboardingAlreadyFinalizedError: if onboarding is already complete.
    """
    subject = await session.get(Subject, subject_id)
    if not subject:
        raise SubjectNotFoundError(f"Subject '{subject_id}' not found.")

    profile = await _load_profile(session, subject_id)
    if profile and profile.status == SubjectProfileStatus.READY:
        raise OnboardingAlreadyFinalizedError("Onboarding already finalized.")

    answers_count = len(await _load_answers(session, subject_id))
    completeness = compute_completeness(profile)
    system_context = build_system_context(subject, profile, completeness, answers_count)

    prior_answers = await _load_answers(session, subject_id)
    turn = await run_onboarding_turn(
        messages=[
            *build_conversation_history(prior_answers),
            {"role": "user", "content": content},
        ],
        system_context=system_context,
        session=session,
        subject_id=subject_id,
    )

    fresh_profile = await _load_profile(session, subject_id)
    fresh_answers = await _load_answers(session, subject_id)
    fresh_completeness = compute_completeness(fresh_profile)

    return OnboardingMessageRead(
        reply=turn.reply,
        status=_status_string(fresh_profile),
        questions_asked=len(fresh_answers),
        max_questions=MAX_ONBOARDING_QUESTIONS,
        completeness=CompletenessRead(
            score=fresh_completeness.score,
            filled_slots=fresh_completeness.filled_slots,
            missing_slots=fresh_completeness.missing_slots,
        ),
        profile=(
            SubjectProfileSlotRead.model_validate(fresh_profile)
            if fresh_profile
            else None
        ),
    )
