"""Execution handlers for LLM tools interacting with the database."""

import uuid

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.chat_message import ChatMessage
from app.models.feed_post import FeedPost
from app.models.onboarding_answers import OnboardingAnswer
from app.models.subject import Subject
from app.models.subject_profile import (
    PacePreference,
    SubjectProfile,
    SubjectProfileStatus,
)
from app.models.topic import Topic, TopicStatus
from app.services.completeness import compute_completeness
from app.tools.exceptions import (
    MaxQuestionsExceededError,
    ToolNotFoundError,
    ToolValidationError,
)
from app.tools.schemas import (
    AskQuestionInput,
    AskQuestionOutput,
    CreatedFeedPostItem,
    CreatedTopicItem,
    CreateRoadmapInput,
    CreateRoadmapOutput,
    FinalizeProfileInput,
    FinalizeProfileOutput,
    GenerateFeedBatchInput,
    GenerateFeedBatchOutput,
    LogChatMessageInput,
    LogChatMessageOutput,
    MarkTopicCompleteInput,
    MarkTopicCompleteOutput,
    SaveAnswerInput,
    SaveAnswerOutput,
    UpdateProfileSlotsInput,
    UpdateProfileSlotsOutput,
)

MAX_ONBOARDING_QUESTIONS = 10


def _parse_subject_id(
    value: str | uuid.UUID | None,
) -> uuid.UUID | None:
    """Parse a string/UUID subject_id into a UUID, raising validation on failure."""
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError) as exc:
        raise ToolValidationError(
            f"Invalid subject_id '{value}': must be a valid UUID.",
            details={"subject_id": str(value)},
        ) from exc


def _require_subject_id(value: str | uuid.UUID | None) -> uuid.UUID:
    """Parse a required string/UUID subject_id, raising validation error on failure."""
    parsed = _parse_subject_id(value)
    if parsed is None:
        raise ToolValidationError(
            "subject_id is required and must be a valid UUID.",
            details={"subject_id": str(value)},
        )
    return parsed


async def execute_ask_question(
    session: AsyncSession,
    params: AskQuestionInput,
) -> AskQuestionOutput:
    """Validate and process an onboarding question.

    If subject_id is supplied, verifies subject existence and checks the
    10-question onboarding hard cap against persisted answers.
    """
    parsed_sid = _parse_subject_id(params.subject_id)
    if parsed_sid is not None:
        subject = await session.get(Subject, parsed_sid)
        if not subject:
            raise ToolNotFoundError(f"Subject '{params.subject_id}' not found.")

        count_stmt = (
            select(func.count())
            .select_from(OnboardingAnswer)
            .where(OnboardingAnswer.subject_id == parsed_sid)
        )
        count_res = await session.exec(count_stmt)
        answer_count = count_res.one()

        if answer_count >= MAX_ONBOARDING_QUESTIONS:
            raise MaxQuestionsExceededError(
                f"Subject '{params.subject_id}' has already reached the maximum "
                f"onboarding limit of {MAX_ONBOARDING_QUESTIONS} questions "
                f"(current: {answer_count}). Profile must now be finalized.",
                details={
                    "subject_id": str(params.subject_id),
                    "current_count": answer_count,
                    "max_questions": MAX_ONBOARDING_QUESTIONS,
                },
            )

        new_count = answer_count + 1
        return AskQuestionOutput(
            question=params.question,
            why=params.why,
            question_count=new_count,
            is_cap_reached=(new_count >= MAX_ONBOARDING_QUESTIONS),
        )

    return AskQuestionOutput(
        question=params.question,
        why=params.why,
        question_count=None,
        is_cap_reached=False,
    )


async def execute_save_answer(
    session: AsyncSession,
    params: SaveAnswerInput,
) -> SaveAnswerOutput:
    """Persist a single Q&A turn into onboarding_answers."""
    parsed_sid = _require_subject_id(params.subject_id)
    subject = await session.get(Subject, parsed_sid)
    if not subject:
        raise ToolNotFoundError(f"Subject '{params.subject_id}' not found.")

    count_stmt = (
        select(func.count())
        .select_from(OnboardingAnswer)
        .where(OnboardingAnswer.subject_id == parsed_sid)
    )
    count_res = await session.exec(count_stmt)
    current_count = count_res.one()

    if current_count >= MAX_ONBOARDING_QUESTIONS:
        raise MaxQuestionsExceededError(
            f"Subject '{params.subject_id}' has already reached the maximum "
            f"onboarding limit of {MAX_ONBOARDING_QUESTIONS} answers.",
            details={
                "subject_id": str(params.subject_id),
                "current_count": current_count,
                "max_questions": MAX_ONBOARDING_QUESTIONS,
            },
        )

    answer_record = OnboardingAnswer(
        subject_id=parsed_sid,
        question=params.question,
        answer=params.answer,
    )
    session.add(answer_record)
    await session.commit()
    await session.refresh(answer_record)

    return SaveAnswerOutput(
        id=answer_record.id,  # type: ignore[arg-type]
        subject_id=answer_record.subject_id,
        question=answer_record.question,
        answer=answer_record.answer,
        created_at=answer_record.created_at,
        answer_count=current_count + 1,
    )


async def execute_update_profile_slots(
    session: AsyncSession,
    params: UpdateProfileSlotsInput,
) -> UpdateProfileSlotsOutput:
    """Upsert a subject profile, writing only the slots explicitly provided.

    Creates the profile row (status=ONBOARDING) if absent; ``None`` slot values
    mean "leave unchanged". Empty strings are rejected at schema level.
    """
    parsed_sid = _require_subject_id(params.subject_id)
    subject = await session.get(Subject, parsed_sid)
    if not subject:
        raise ToolNotFoundError(f"Subject '{params.subject_id}' not found.")

    profile = await session.get(SubjectProfile, parsed_sid)
    if profile is None:
        profile = SubjectProfile(
            subject_id=parsed_sid,
            status=SubjectProfileStatus.ONBOARDING,
        )

    updates: dict[str, str | PacePreference] = {}
    for slot in ("goal", "current_level", "background", "motivation"):
        value: str | None = getattr(params, slot)
        if value is None:
            continue
        stripped = value.strip()
        if not stripped:
            raise ToolValidationError(
                f"Slot '{slot}' cannot be set to an empty string.",
                details={"slot": slot},
            )
        updates[slot] = stripped
    if params.pace_preference is not None:
        updates["pace_preference"] = params.pace_preference

    if not updates:
        raise ToolValidationError(
            "No slot values provided; supply at least one non-null slot to update.",
            details={"subject_id": str(params.subject_id)},
        )

    for slot_name, slot_value in updates.items():
        setattr(profile, slot_name, slot_value)
    session.add(profile)
    await session.commit()
    await session.refresh(profile)

    completeness = compute_completeness(profile)

    return UpdateProfileSlotsOutput(
        subject_id=profile.subject_id,
        goal=profile.goal,
        current_level=profile.current_level,
        background=profile.background,
        motivation=profile.motivation,
        pace_preference=profile.pace_preference,
        score=completeness.score,
        filled_slots=completeness.filled_slots,
        missing_slots=completeness.missing_slots,
    )


# Sets status=ready + ready_for_roadmap=True. Roadmap generation is client-driven
# via POST /subjects/{id}/roadmap (gated on READY) — see mobile/lib/features/roadmap/presentation/screens/roadmap_screen.dart:29
async def execute_finalize_profile(
    session: AsyncSession,
    params: FinalizeProfileInput,
) -> FinalizeProfileOutput:
    """Lock subject profile, persist personalization slots, and set status to READY.

    Wiring note: this does NOT auto-generate the roadmap. After status becomes
    READY, the client triggers `POST /subjects/{id}/roadmap`
    (`app/api/routers/roadmap.py:post_roadmap` → `app/services/roadmap.py:generate_roadmap`).
    Keeping finalize and roadmap generation decoupled avoids implicit side-effects
    and makes the flow idempotent (see also `app/services/roadmap.py` header).
    """
    parsed_sid = _require_subject_id(params.subject_id)
    subject = await session.get(Subject, parsed_sid)
    if not subject:
        raise ToolNotFoundError(f"Subject '{params.subject_id}' not found.")

    profile = await session.get(SubjectProfile, parsed_sid)
    if profile:
        profile.goal = params.goal
        profile.current_level = params.current_level
        profile.background = params.background
        profile.motivation = params.motivation
        profile.pace_preference = params.pace_preference
        profile.status = SubjectProfileStatus.READY
        session.add(profile)
    else:
        profile = SubjectProfile(
            subject_id=parsed_sid,
            goal=params.goal,
            current_level=params.current_level,
            background=params.background,
            motivation=params.motivation,
            pace_preference=params.pace_preference,
            status=SubjectProfileStatus.READY,
        )
        session.add(profile)

    await session.commit()
    await session.refresh(profile)

    return FinalizeProfileOutput(
        subject_id=profile.subject_id,
        goal=profile.goal,
        current_level=profile.current_level,
        background=profile.background,
        motivation=profile.motivation,
        pace_preference=profile.pace_preference,
        status=profile.status,
        ready_for_roadmap=True,
    )


async def execute_create_roadmap(
    session: AsyncSession,
    params: CreateRoadmapInput,
) -> CreateRoadmapOutput:
    """Bulk insert roadmap topics with ordering, prerequisites, and status."""
    parsed_sid = _require_subject_id(params.subject_id)
    subject = await session.get(Subject, parsed_sid)
    if not subject:
        raise ToolNotFoundError(f"Subject '{params.subject_id}' not found.")

    # Fallback for None (validator already assigns, defensively handle direct calls)
    for idx, t in enumerate(params.topics):
        if t.order_index is None:
            t.order_index = idx + 1

    sorted_topics = sorted(
        params.topics, key=lambda t: t.order_index if t.order_index is not None else 0
    )

    order_to_topic: dict[int, Topic] = {}
    created_topic_entities: list[Topic] = []

    for idx, item in enumerate(sorted_topics):
        assert item.order_index is not None  # ensured above
        status = (
            item.status
            if item.status is not None
            else (TopicStatus.ACTIVE if idx == 0 else TopicStatus.PENDING)
        )
        topic_obj = Topic(
            subject_id=parsed_sid,
            title=item.title,
            order_index=item.order_index,
            prerequisite_ids=[],
            status=status,
        )
        session.add(topic_obj)
        created_topic_entities.append(topic_obj)
        order_to_topic[item.order_index] = topic_obj

    # Flush to generate autoincrement integer primary keys
    await session.flush()

    # Map prerequisite order_indices to actual generated topic IDs
    for item, topic_obj in zip(sorted_topics, created_topic_entities, strict=True):
        prereq_set: set[int] = set(item.prerequisite_ids)
        for req_order in item.prerequisite_indices:
            if req_order in order_to_topic:
                parent_topic = order_to_topic[req_order]
                if parent_topic.id is not None:
                    prereq_set.add(parent_topic.id)
            else:
                raise ToolValidationError(
                    f"Topic '{item.title}' references non-existent prerequisite "
                    f"order_index {req_order}.",
                    details={
                        "order_index": item.order_index,
                        "prerequisite": req_order,
                    },
                )
        topic_obj.prerequisite_ids = sorted(list(prereq_set))
        session.add(topic_obj)

    await session.commit()

    for topic_obj in created_topic_entities:
        await session.refresh(topic_obj)

    created_items = [
        CreatedTopicItem(
            id=t.id,  # type: ignore[arg-type]
            subject_id=t.subject_id,
            title=t.title,
            order_index=t.order_index,
            prerequisite_ids=t.prerequisite_ids,
            status=t.status,
        )
        for t in created_topic_entities
    ]

    active_topic_id = next(
        (t.id for t in created_topic_entities if t.status == TopicStatus.ACTIVE),
        None,
    )

    return CreateRoadmapOutput(
        subject_id=parsed_sid,
        topics=created_items,
        active_topic_id=active_topic_id,
    )


async def execute_generate_feed_batch(
    session: AsyncSession,
    params: GenerateFeedBatchInput,
) -> GenerateFeedBatchOutput:
    """Bulk insert generated feed posts for a topic."""
    topic = await session.get(Topic, params.topic_id)
    if not topic:
        raise ToolNotFoundError(f"Topic '{params.topic_id}' not found.")

    feed_post_objs = [
        FeedPost(
            topic_id=params.topic_id,
            content=p.content,
            order_index=p.order_index,
        )
        for p in params.posts
    ]
    session.add_all(feed_post_objs)
    await session.commit()

    for fp in feed_post_objs:
        await session.refresh(fp)

    return GenerateFeedBatchOutput(
        topic_id=params.topic_id,
        post_count=len(feed_post_objs),
        posts=[
            CreatedFeedPostItem(
                id=fp.id,  # type: ignore[arg-type]
                topic_id=fp.topic_id,
                content=fp.content,
                order_index=fp.order_index,
                created_at=fp.created_at,
            )
            for fp in feed_post_objs
        ],
    )


async def execute_mark_topic_complete(
    session: AsyncSession,
    params: MarkTopicCompleteInput,
) -> MarkTopicCompleteOutput:
    """Complete a topic in a single atomic transaction.

    1. Marks topic status as 'done'.
    2. Deletes old feed_posts for this topic.
    3. Finds and activates the next pending topic for the subject if available.
    """
    topic = await session.get(Topic, params.topic_id)
    if not topic:
        raise ToolNotFoundError(f"Topic '{params.topic_id}' not found.")

    # 1. Mark current topic done
    topic.status = TopicStatus.DONE
    session.add(topic)

    # 2. Delete existing feed posts for this completed topic
    posts_stmt = select(FeedPost).where(FeedPost.topic_id == params.topic_id)
    posts_res = await session.exec(posts_stmt)
    existing_posts = posts_res.all()
    deleted_count = len(existing_posts)
    for p in existing_posts:
        await session.delete(p)

    # 3. Find and activate next pending topic
    next_stmt = (
        select(Topic)
        .where(
            Topic.subject_id == topic.subject_id,
            Topic.order_index > topic.order_index,
            Topic.status == TopicStatus.PENDING,
        )
        .order_by(Topic.order_index.asc())  # type: ignore[attr-defined]
    )
    next_res = await session.exec(next_stmt)
    next_topic = next_res.first()

    next_id: int | None = None
    next_title: str | None = None
    if next_topic:
        next_topic.status = TopicStatus.ACTIVE
        session.add(next_topic)
        next_id = next_topic.id
        next_title = next_topic.title

    # 4. Check if all topics are completed
    remaining_stmt = (
        select(func.count())
        .select_from(Topic)
        .where(
            Topic.subject_id == topic.subject_id,
            Topic.status != TopicStatus.DONE,
            Topic.id != topic.id,
        )
    )
    remaining_res = await session.exec(remaining_stmt)
    remaining_count = remaining_res.one()
    all_completed = remaining_count == 0

    await session.commit()

    return MarkTopicCompleteOutput(
        completed_topic_id=params.topic_id,
        status=TopicStatus.DONE,
        deleted_feed_posts_count=deleted_count,
        next_topic_id=next_id,
        next_topic_title=next_title,
        all_topics_completed=all_completed,
    )


async def execute_log_chat_message(
    session: AsyncSession,
    params: LogChatMessageInput,
) -> LogChatMessageOutput:
    """Persist an Open Chat message turn associated with a topic."""
    topic = await session.get(Topic, params.topic_id)
    if not topic:
        raise ToolNotFoundError(f"Topic '{params.topic_id}' not found.")

    chat_obj = ChatMessage(
        topic_id=params.topic_id,
        role=params.role,
        content=params.content,
    )
    session.add(chat_obj)
    await session.commit()
    await session.refresh(chat_obj)

    return LogChatMessageOutput(
        id=chat_obj.id,  # type: ignore[arg-type]
        topic_id=chat_obj.topic_id,
        role=chat_obj.role,
        content=chat_obj.content,
        created_at=chat_obj.created_at,
    )
