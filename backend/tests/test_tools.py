"""Comprehensive unit and integration tests for LLM tool layer."""

import uuid

import pytest
from pydantic import ValidationError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.chat_message import ChatMessage, ChatRole
from app.models.feed_post import FeedPost
from app.models.onboarding_answers import OnboardingAnswer
from app.models.subject import Subject
from app.models.subject_profile import (
    PacePreference,
    SubjectProfile,
    SubjectProfileStatus,
)
from app.models.topic import Topic, TopicStatus
from app.tools.dispatcher import (
    TOOL_REGISTRY,
    ToolRetryTracker,
    execute_tool,
    get_tool_definitions,
)
from app.tools.exceptions import (
    MaxQuestionsExceededError,
    ToolNotFoundError,
    ToolValidationError,
)
from app.tools.handlers import (
    execute_ask_question,
    execute_create_roadmap,
    execute_finalize_profile,
    execute_generate_feed_batch,
    execute_log_chat_message,
    execute_mark_topic_complete,
    execute_save_answer,
    execute_update_profile_slots,
)
from app.tools.schemas import (
    AskQuestionInput,
    CreateRoadmapInput,
    FeedPostItem,
    FinalizeProfileInput,
    GenerateFeedBatchInput,
    LogChatMessageInput,
    MarkTopicCompleteInput,
    RoadmapTopicItem,
    SaveAnswerInput,
    UpdateProfileSlotsInput,
)

# ============================================================================
# Helpers
# ============================================================================


async def _create_test_subject(
    session: AsyncSession, title: str = "Test Subject"
) -> Subject:
    """Helper to create a persisted subject."""
    subject = Subject(title=title, description="Subject for testing tools")
    session.add(subject)
    await session.commit()
    await session.refresh(subject)
    return subject


async def _create_test_topic(
    session: AsyncSession,
    subject_id: uuid.UUID,
    title: str = "Test Topic",
    order_index: int = 1,
    status: TopicStatus = TopicStatus.ACTIVE,
) -> Topic:
    """Helper to create a persisted topic."""
    topic = Topic(
        subject_id=subject_id,
        title=title,
        order_index=order_index,
        prerequisite_ids=[],
        status=status,
    )
    session.add(topic)
    await session.commit()
    await session.refresh(topic)
    return topic


# ============================================================================
# 1. ask_question Tests
# ============================================================================


def test_ask_question_schema_validation() -> None:
    """Validate AskQuestionInput pydantic model constraints."""
    # Valid input
    valid = AskQuestionInput(question="What is your goal?", why="To personalize pace")
    assert valid.question == "What is your goal?"
    assert valid.why == "To personalize pace"

    # Empty question should fail validation
    with pytest.raises(ValidationError):
        AskQuestionInput(question="")

    with pytest.raises(ValidationError):
        AskQuestionInput(question="   ")


@pytest.mark.asyncio
async def test_ask_question_execution_without_subject(session: AsyncSession) -> None:
    """ask_question without subject_id returns formatted output without DB check."""
    params = AskQuestionInput(
        question="What programming languages do you know?", why="Assess background"
    )
    res = await execute_ask_question(session, params)
    assert res.question == "What programming languages do you know?"
    assert res.why == "Assess background"
    assert res.question_count is None
    assert res.is_cap_reached is False


@pytest.mark.asyncio
async def test_ask_question_execution_with_subject(session: AsyncSession) -> None:
    """ask_question with subject_id computes question count against DB."""
    subject = await _create_test_subject(session, "Python Concurrency")

    # Add 2 answers
    session.add(OnboardingAnswer(subject_id=subject.id, question="Q1", answer="A1"))
    session.add(OnboardingAnswer(subject_id=subject.id, question="Q2", answer="A2"))
    await session.commit()

    params = AskQuestionInput(
        question="What is your asyncio experience?",
        subject_id=subject.id,
    )
    res = await execute_ask_question(session, params)
    assert res.question_count == 3
    assert res.is_cap_reached is False


@pytest.mark.asyncio
async def test_ask_question_non_existent_subject(session: AsyncSession) -> None:
    """ask_question with non-existent subject_id raises ToolNotFoundError."""
    params = AskQuestionInput(
        question="Any question?",
        subject_id=uuid.uuid4(),
    )
    with pytest.raises(ToolNotFoundError):
        await execute_ask_question(session, params)


@pytest.mark.asyncio
async def test_ask_question_max_cap_exceeded(session: AsyncSession) -> None:
    """ask_question raises MaxQuestionsExceededError when 10 answers already exist."""
    subject = await _create_test_subject(session, "Capped Subject")
    for i in range(10):
        session.add(
            OnboardingAnswer(
                subject_id=subject.id,
                question=f"Q{i + 1}",
                answer=f"A{i + 1}",
            )
        )
    await session.commit()

    params = AskQuestionInput(
        question="11th Question?",
        subject_id=subject.id,
    )
    with pytest.raises(MaxQuestionsExceededError) as exc_info:
        await execute_ask_question(session, params)

    assert "maximum onboarding limit of 10 questions" in exc_info.value.message


# ============================================================================
# 2. save_answer Tests
# ============================================================================


def test_save_answer_schema_validation() -> None:
    """Validate SaveAnswerInput constraints."""
    sub_id = uuid.uuid4()
    valid = SaveAnswerInput(
        subject_id=sub_id,
        question="What is your goal?",
        answer="Learn Rust",
    )
    assert valid.question == "What is your goal?"
    assert valid.answer == "Learn Rust"

    # Empty answer should fail
    with pytest.raises(ValidationError):
        SaveAnswerInput(subject_id=sub_id, question="Q", answer="")

    # Empty question should fail
    with pytest.raises(ValidationError):
        SaveAnswerInput(subject_id=sub_id, question="   ", answer="A")


@pytest.mark.asyncio
async def test_save_answer_execution(session: AsyncSession) -> None:
    """save_answer persists answer record and increments count."""
    subject = await _create_test_subject(session, "Rust Foundations")

    params1 = SaveAnswerInput(
        subject_id=subject.id,
        question="What is your goal?",
        answer="Build web services with Axum",
    )
    res1 = await execute_save_answer(session, params1)
    assert res1.id is not None
    assert res1.answer_count == 1
    assert res1.question == "What is your goal?"
    assert res1.answer == "Build web services with Axum"

    params2 = SaveAnswerInput(
        subject_id=subject.id,
        question="Current programming level?",
        answer="Proficient in Python and TypeScript",
    )
    res2 = await execute_save_answer(session, params2)
    assert res2.answer_count == 2

    # Verify rows in DB
    stmt = (
        select(OnboardingAnswer)
        .where(OnboardingAnswer.subject_id == subject.id)
        .order_by(OnboardingAnswer.created_at.asc())
    )
    records = (await session.exec(stmt)).all()
    assert len(records) == 2


@pytest.mark.asyncio
async def test_save_answer_non_existent_subject(session: AsyncSession) -> None:
    """save_answer for non-existent subject raises ToolNotFoundError."""
    params = SaveAnswerInput(
        subject_id=uuid.uuid4(),
        question="Q",
        answer="A",
    )
    with pytest.raises(ToolNotFoundError):
        await execute_save_answer(session, params)


@pytest.mark.asyncio
async def test_save_answer_max_cap_exceeded(session: AsyncSession) -> None:
    """save_answer raises MaxQuestionsExceededError when 10 answers already exist."""
    subject = await _create_test_subject(session, "Max Answer Subject")
    for i in range(10):
        session.add(
            OnboardingAnswer(
                subject_id=subject.id,
                question=f"Q{i}",
                answer=f"A{i}",
            )
        )
    await session.commit()

    params = SaveAnswerInput(
        subject_id=subject.id,
        question="11th Question",
        answer="11th Answer",
    )
    with pytest.raises(MaxQuestionsExceededError):
        await execute_save_answer(session, params)


# ============================================================================
# 3. finalize_profile Tests
# ============================================================================


def test_finalize_profile_schema_validation() -> None:
    """Validate FinalizeProfileInput constraints."""
    sub_id = uuid.uuid4()
    valid = FinalizeProfileInput(
        subject_id=sub_id,
        goal="Pass coding interview",
        current_level="Junior",
        background="CS Degree",
        motivation="New job",
        pace_preference=PacePreference.INTENSE,
    )
    assert valid.pace_preference == PacePreference.INTENSE

    # Blank field should fail
    with pytest.raises(ValidationError):
        FinalizeProfileInput(
            subject_id=sub_id,
            goal="",
            current_level="Junior",
            background="CS",
            motivation="Job",
        )


@pytest.mark.asyncio
async def test_finalize_profile_create_new(session: AsyncSession) -> None:
    """finalize_profile creates profile and sets status to READY."""
    subject = await _create_test_subject(session, "System Architecture")

    params = FinalizeProfileInput(
        subject_id=subject.id,
        goal="Design scalable distributed systems",
        current_level="Mid-level backend dev",
        background="5 years with relational DBs and microservices",
        motivation="Staff engineer promotion",
        pace_preference=PacePreference.STEADY,
    )
    res = await execute_finalize_profile(session, params)

    assert res.subject_id == subject.id
    assert res.status == SubjectProfileStatus.READY
    assert res.ready_for_roadmap is True
    assert res.pace_preference == PacePreference.STEADY

    # Verify in DB
    profile = await session.get(SubjectProfile, subject.id)
    assert profile is not None
    assert profile.status == SubjectProfileStatus.READY
    assert profile.goal == "Design scalable distributed systems"


@pytest.mark.asyncio
async def test_finalize_profile_update_existing(session: AsyncSession) -> None:
    """finalize_profile updates existing profile from onboarding to ready."""
    subject = await _create_test_subject(session, "Kubernetes")
    init_profile = SubjectProfile(
        subject_id=subject.id,
        goal="Old goal",
        current_level="Beginner",
        background="DevOps",
        motivation="Curiosity",
        status=SubjectProfileStatus.ONBOARDING,
    )
    session.add(init_profile)
    await session.commit()

    params = FinalizeProfileInput(
        subject_id=subject.id,
        goal="Pass CKA exam",
        current_level="Intermediate",
        background="DevOps 3 years",
        motivation="Certification",
        pace_preference=PacePreference.CHILL,
    )
    res = await execute_finalize_profile(session, params)
    assert res.goal == "Pass CKA exam"
    assert res.status == SubjectProfileStatus.READY
    assert res.pace_preference == PacePreference.CHILL


@pytest.mark.asyncio
async def test_finalize_profile_non_existent_subject(session: AsyncSession) -> None:
    """finalize_profile for non-existent subject raises ToolNotFoundError."""
    params = FinalizeProfileInput(
        subject_id=uuid.uuid4(),
        goal="Goal",
        current_level="Level",
        background="BG",
        motivation="Motiv",
    )
    with pytest.raises(ToolNotFoundError):
        await execute_finalize_profile(session, params)


# ============================================================================
# 4. create_roadmap Tests
# ============================================================================


def test_create_roadmap_schema_validation() -> None:
    """Validate CreateRoadmapInput constraints."""
    sub_id = uuid.uuid4()
    valid = CreateRoadmapInput(
        subject_id=sub_id,
        topics=[
            RoadmapTopicItem(title="Basics", order_index=1),
            RoadmapTopicItem(title="Advanced", order_index=2, prerequisite_indices=[1]),
        ],
    )
    assert len(valid.topics) == 2

    # Duplicate order_index should fail
    with pytest.raises(ValidationError):
        CreateRoadmapInput(
            subject_id=sub_id,
            topics=[
                RoadmapTopicItem(title="T1", order_index=1),
                RoadmapTopicItem(title="T2", order_index=1),
            ],
        )

    # Empty topics list should fail
    with pytest.raises(ValidationError):
        CreateRoadmapInput(subject_id=sub_id, topics=[])


@pytest.mark.asyncio
async def test_create_roadmap_execution(session: AsyncSession) -> None:
    """create_roadmap bulk inserts topics and maps prerequisite indices."""
    subject = await _create_test_subject(session, "Data Structures")

    params = CreateRoadmapInput(
        subject_id=subject.id,
        topics=[
            RoadmapTopicItem(
                title="Arrays & Hash Maps",
                order_index=1,
                prerequisite_indices=[],
            ),
            RoadmapTopicItem(
                title="Two Pointers & Sliding Window",
                order_index=2,
                prerequisite_indices=[1],
            ),
            RoadmapTopicItem(
                title="Trees & Graphs",
                order_index=3,
                prerequisite_indices=[1, 2],
            ),
        ],
    )

    res = await execute_create_roadmap(session, params)
    assert len(res.topics) == 3
    assert res.subject_id == subject.id

    t1, t2, t3 = res.topics
    assert t1.title == "Arrays & Hash Maps"
    assert t1.order_index == 1
    assert t1.status == TopicStatus.ACTIVE
    assert t1.prerequisite_ids == []
    assert res.active_topic_id == t1.id

    assert t2.title == "Two Pointers & Sliding Window"
    assert t2.order_index == 2
    assert t2.status == TopicStatus.PENDING
    assert t2.prerequisite_ids == [t1.id]

    assert t3.title == "Trees & Graphs"
    assert t3.order_index == 3
    assert t3.status == TopicStatus.PENDING
    assert sorted(t3.prerequisite_ids) == sorted([t1.id, t2.id])

    # Verify in DB
    stmt = (
        select(Topic)
        .where(Topic.subject_id == subject.id)
        .order_by(Topic.order_index.asc())
    )
    db_topics = (await session.exec(stmt)).all()
    assert len(db_topics) == 3
    assert db_topics[0].status == TopicStatus.ACTIVE


@pytest.mark.asyncio
async def test_create_roadmap_invalid_prerequisite_index(
    session: AsyncSession,
) -> None:
    """create_roadmap with bad prerequisite index raises ToolValidationError."""
    subject = await _create_test_subject(session, "Invalid Roadmap")

    params = CreateRoadmapInput(
        subject_id=subject.id,
        topics=[
            RoadmapTopicItem(title="T1", order_index=1),
            RoadmapTopicItem(title="T2", order_index=2, prerequisite_indices=[99]),
        ],
    )
    with pytest.raises(ToolValidationError) as exc_info:
        await execute_create_roadmap(session, params)

    assert "non-existent prerequisite order_index 99" in exc_info.value.message


@pytest.mark.asyncio
async def test_create_roadmap_non_existent_subject(session: AsyncSession) -> None:
    """create_roadmap for non-existent subject raises ToolNotFoundError."""
    params = CreateRoadmapInput(
        subject_id=uuid.uuid4(),
        topics=[RoadmapTopicItem(title="T1", order_index=1)],
    )
    with pytest.raises(ToolNotFoundError):
        await execute_create_roadmap(session, params)


# ============================================================================
# 5. generate_feed_batch Tests
# ============================================================================


def test_generate_feed_batch_schema_validation() -> None:
    """Validate GenerateFeedBatchInput constraints (5-10 posts, defense in depth)."""
    valid = GenerateFeedBatchInput(
        topic_id=1,
        posts=[
            FeedPostItem(content="Post 1", order_index=0),
            FeedPostItem(content="Post 2", order_index=1),
            FeedPostItem(content="Post 3", order_index=2),
            FeedPostItem(content="Post 4", order_index=3),
            FeedPostItem(content="Post 5", order_index=4),
        ],
    )
    assert len(valid.posts) == 5

    # Fewer than 5 posts should fail (schema enforces 5-10, service layer also checks)
    with pytest.raises(ValidationError):
        GenerateFeedBatchInput(
            topic_id=1,
            posts=[
                FeedPostItem(content="Post 1", order_index=0),
                FeedPostItem(content="Post 2", order_index=1),
            ],
        )

    # More than 10 posts should fail
    with pytest.raises(ValidationError):
        GenerateFeedBatchInput(
            topic_id=1,
            posts=[FeedPostItem(content=f"Post {i}", order_index=i) for i in range(11)],
        )

    # Duplicate order_index should fail
    with pytest.raises(ValidationError):
        GenerateFeedBatchInput(
            topic_id=1,
            posts=[
                FeedPostItem(content="Post 1", order_index=0),
                FeedPostItem(content="Post 2", order_index=0),
                FeedPostItem(content="Post 3", order_index=2),
                FeedPostItem(content="Post 4", order_index=3),
                FeedPostItem(content="Post 5", order_index=4),
            ],
        )

    # Empty content should fail
    with pytest.raises(ValidationError):
        GenerateFeedBatchInput(
            topic_id=1,
            posts=[FeedPostItem(content="", order_index=0)],
        )


@pytest.mark.asyncio
async def test_generate_feed_batch_execution(session: AsyncSession) -> None:
    """generate_feed_batch bulk inserts posts attached to a topic (5-10 required)."""
    subject = await _create_test_subject(session, "Async Python")
    topic = await _create_test_topic(session, subject.id, "Event Loop")

    params = GenerateFeedBatchInput(
        topic_id=topic.id,  # type: ignore[arg-type]
        posts=[
            FeedPostItem(
                content="The event loop is the core of every asyncio application.",
                order_index=0,
            ),
            FeedPostItem(
                content="Never run blocking CPU-bound code inside the event loop.",
                order_index=1,
            ),
            FeedPostItem(
                content="Use asyncio.to_thread for blocking sync calls.",
                order_index=2,
            ),
            FeedPostItem(
                content="Gather and create_task schedule coroutines concurrently.",
                order_index=3,
            ),
            FeedPostItem(
                content="Always handle cancellation and timeouts gracefully.",
                order_index=4,
            ),
        ],
    )

    res = await execute_generate_feed_batch(session, params)
    assert res.topic_id == topic.id
    assert res.post_count == 5
    assert len(res.posts) == 5
    assert res.posts[0].order_index == 0
    assert res.posts[1].order_index == 1
    assert res.posts[2].order_index == 2

    # Verify DB persistence
    stmt = (
        select(FeedPost)
        .where(FeedPost.topic_id == topic.id)
        .order_by(FeedPost.order_index.asc())
    )
    db_posts = (await session.exec(stmt)).all()
    assert len(db_posts) == 5
    assert db_posts[0].content.startswith("The event loop")


@pytest.mark.asyncio
async def test_generate_feed_batch_non_existent_topic(
    session: AsyncSession,
) -> None:
    """generate_feed_batch for non-existent topic raises ToolNotFoundError."""
    params = GenerateFeedBatchInput(
        topic_id=99999,
        posts=[FeedPostItem(content=f"Post {i}", order_index=i) for i in range(5)],
    )
    with pytest.raises(ToolNotFoundError):
        await execute_generate_feed_batch(session, params)


# ============================================================================
# 6. mark_topic_complete Tests
# ============================================================================


@pytest.mark.asyncio
async def test_mark_topic_complete_execution(session: AsyncSession) -> None:
    """mark_topic_complete purges posts and activates the next topic atomically."""
    subject = await _create_test_subject(session, "Go Concurrency")
    topic1 = await _create_test_topic(
        session, subject.id, "Goroutines", order_index=1, status=TopicStatus.ACTIVE
    )
    topic2 = await _create_test_topic(
        session, subject.id, "Channels", order_index=2, status=TopicStatus.PENDING
    )

    # Insert feed posts for topic 1
    feed1 = FeedPost(
        topic_id=topic1.id,
        content="Goroutines are lightweight.",
        order_index=0,  # type: ignore[arg-type]
    )
    feed2 = FeedPost(
        topic_id=topic1.id,
        content="Start with 'go f()'.",
        order_index=1,  # type: ignore[arg-type]
    )
    session.add_all([feed1, feed2])
    await session.commit()

    params = MarkTopicCompleteInput(topic_id=topic1.id)  # type: ignore[arg-type]
    res = await execute_mark_topic_complete(session, params)

    assert res.completed_topic_id == topic1.id
    assert res.status == TopicStatus.DONE
    assert res.deleted_feed_posts_count == 2
    assert res.next_topic_id == topic2.id
    assert res.next_topic_title == "Channels"
    assert res.all_topics_completed is False

    # Check topic 1 status
    await session.refresh(topic1)
    assert topic1.status == TopicStatus.DONE

    # Check topic 2 status
    await session.refresh(topic2)
    assert topic2.status == TopicStatus.ACTIVE

    # Check old feed posts deleted
    posts_res = (
        await session.exec(select(FeedPost).where(FeedPost.topic_id == topic1.id))
    ).all()
    assert len(posts_res) == 0


@pytest.mark.asyncio
async def test_mark_last_topic_complete(session: AsyncSession) -> None:
    """mark_topic_complete on final topic reports all_topics_completed=True."""
    subject = await _create_test_subject(session, "Short Track")
    topic = await _create_test_topic(
        session, subject.id, "Final Topic", order_index=1, status=TopicStatus.ACTIVE
    )

    params = MarkTopicCompleteInput(topic_id=topic.id)  # type: ignore[arg-type]
    res = await execute_mark_topic_complete(session, params)

    assert res.completed_topic_id == topic.id
    assert res.status == TopicStatus.DONE
    assert res.next_topic_id is None
    assert res.all_topics_completed is True


@pytest.mark.asyncio
async def test_mark_topic_complete_non_existent_topic(
    session: AsyncSession,
) -> None:
    """mark_topic_complete for non-existent topic raises ToolNotFoundError."""
    params = MarkTopicCompleteInput(topic_id=99999)
    with pytest.raises(ToolNotFoundError):
        await execute_mark_topic_complete(session, params)


# ============================================================================
# 7. log_chat_message Tests
# ============================================================================


def test_log_chat_message_schema_validation() -> None:
    """Validate LogChatMessageInput constraints."""
    valid = LogChatMessageInput(
        topic_id=1,
        role=ChatRole.USER,
        content="How does select work in Go?",
    )
    assert valid.role == ChatRole.USER

    # Blank content should fail
    with pytest.raises(ValidationError):
        LogChatMessageInput(topic_id=1, role=ChatRole.USER, content="")


@pytest.mark.asyncio
async def test_log_chat_message_execution(session: AsyncSession) -> None:
    """log_chat_message persists user and assistant chat turns."""
    subject = await _create_test_subject(session, "Database Internals")
    topic = await _create_test_topic(session, subject.id, "B-Trees")

    # Log user turn
    user_param = LogChatMessageInput(
        topic_id=topic.id,  # type: ignore[arg-type]
        role=ChatRole.USER,
        content="What is the branching factor?",
    )
    user_res = await execute_log_chat_message(session, user_param)
    assert user_res.id is not None
    assert user_res.role == ChatRole.USER
    assert user_res.content == "What is the branching factor?"

    # Log assistant turn
    ai_param = LogChatMessageInput(
        topic_id=topic.id,  # type: ignore[arg-type]
        role=ChatRole.ASSISTANT,
        content="Branching factor is the number of children each node can have.",
    )
    ai_res = await execute_log_chat_message(session, ai_param)
    assert ai_res.role == ChatRole.ASSISTANT

    # Verify DB records
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.topic_id == topic.id)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = (await session.exec(stmt)).all()
    assert len(messages) == 2
    assert messages[0].role == ChatRole.USER
    assert messages[1].role == ChatRole.ASSISTANT


@pytest.mark.asyncio
async def test_log_chat_message_non_existent_topic(session: AsyncSession) -> None:
    """log_chat_message for non-existent topic raises ToolNotFoundError."""
    params = LogChatMessageInput(
        topic_id=88888,
        role=ChatRole.USER,
        content="Hello?",
    )
    with pytest.raises(ToolNotFoundError):
        await execute_log_chat_message(session, params)


# ============================================================================
# 8. Tool Dispatcher & Error Handling Tests
# ============================================================================


@pytest.mark.asyncio
async def test_dispatcher_success_flow(session: AsyncSession) -> None:
    """execute_tool successfully dispatches valid tool call and returns ToolResult."""
    subject = await _create_test_subject(session, "Dispatcher Test")

    result = await execute_tool(
        session=session,
        name="save_answer",
        arguments={
            "subject_id": str(subject.id),
            "question": "What is your background?",
            "answer": "Computer Science student",
        },
    )

    assert result.success is True
    assert result.tool_name == "save_answer"
    assert result.data is not None
    assert result.data["question"] == "What is your background?"
    assert result.data["answer_count"] == 1
    assert result.error is None


@pytest.mark.asyncio
async def test_dispatcher_unregistered_tool(session: AsyncSession) -> None:
    """execute_tool returns structured TOOL_NOT_FOUND for unregistered tool."""
    result = await execute_tool(
        session=session,
        name="non_existent_tool",
        arguments={"foo": "bar"},
    )
    assert result.success is False
    assert result.error_code == "TOOL_NOT_FOUND"
    assert "is not registered" in str(result.error)
    assert result.details is not None
    assert "available_tools" in result.details


@pytest.mark.asyncio
async def test_dispatcher_validation_error_handling(session: AsyncSession) -> None:
    """execute_tool returns structured VALIDATION_ERROR with field details."""
    result = await execute_tool(
        session=session,
        name="save_answer",
        arguments={
            "subject_id": "not-a-valid-uuid",
            "question": "",
            "answer": "",
        },
    )
    assert result.success is False
    assert result.error_code == "VALIDATION_ERROR"
    assert "Validation failed for tool 'save_answer'" in str(result.error)
    assert result.details is not None
    assert "validation_errors" in result.details
    assert len(result.details["validation_errors"]) > 0


@pytest.mark.asyncio
async def test_dispatcher_not_found_error_handling(session: AsyncSession) -> None:
    """execute_tool returns structured NOT_FOUND for missing DB entity."""
    fake_id = str(uuid.uuid4())
    result = await execute_tool(
        session=session,
        name="save_answer",
        arguments={
            "subject_id": fake_id,
            "question": "Valid Q",
            "answer": "Valid A",
        },
    )
    assert result.success is False
    assert result.error_code == "NOT_FOUND"
    assert fake_id in str(result.error)


@pytest.mark.asyncio
async def test_dispatcher_max_questions_exceeded(session: AsyncSession) -> None:
    """execute_tool returns structured MAX_QUESTIONS_EXCEEDED error."""
    subject = await _create_test_subject(session, "Max Q Test")
    for i in range(10):
        session.add(
            OnboardingAnswer(
                subject_id=subject.id,
                question=f"Q{i}",
                answer=f"A{i}",
            )
        )
    await session.commit()

    result = await execute_tool(
        session=session,
        name="save_answer",
        arguments={
            "subject_id": str(subject.id),
            "question": "Q11",
            "answer": "A11",
        },
    )
    assert result.success is False
    assert result.error_code == "MAX_QUESTIONS_EXCEEDED"
    assert "maximum onboarding limit" in str(result.error)


def test_get_tool_definitions() -> None:
    """get_tool_definitions returns valid OpenAI/Groq function schemas."""
    definitions = get_tool_definitions()
    assert len(definitions) == len(TOOL_REGISTRY)

    names = {d["function"]["name"] for d in definitions}
    expected_names = {
        "ask_question",
        "save_answer",
        "finalize_profile",
        "update_profile_slots",
        "create_roadmap",
        "generate_feed_batch",
        "mark_topic_complete",
        "log_chat_message",
    }
    assert names == expected_names

    for item in definitions:
        assert item["type"] == "function"
        fn = item["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn
        assert fn["parameters"]["type"] == "object"


def test_tool_retry_tracker() -> None:
    """ToolRetryTracker manages consecutive retry counts and cap enforcement."""
    tracker = ToolRetryTracker(max_retries=3)
    assert tracker.is_exhausted("create_roadmap") is False

    tracker.record_failure("create_roadmap")
    assert tracker.get_failure_count("create_roadmap") == 1
    assert tracker.is_exhausted("create_roadmap") is False

    tracker.record_failure("create_roadmap")
    tracker.record_failure("create_roadmap")
    assert tracker.get_failure_count("create_roadmap") == 3
    assert tracker.is_exhausted("create_roadmap") is True

    # Reset on success
    tracker.record_success("create_roadmap")
    assert tracker.get_failure_count("create_roadmap") == 0
    assert tracker.is_exhausted("create_roadmap") is False


# ============================================================================
# 9. update_profile_slots Tests
# ============================================================================


def test_update_profile_slots_schema_validation() -> None:
    """Validate UpdateProfileSlotsInput partial-update constraints."""
    sub_id = uuid.uuid4()

    valid = UpdateProfileSlotsInput(subject_id=sub_id, goal="Learn Rust")
    assert valid.goal == "Learn Rust"
    assert valid.current_level is None
    assert valid.pace_preference is None

    # Empty-string writes are rejected (must omit to leave unchanged)
    with pytest.raises(ValidationError):
        UpdateProfileSlotsInput(subject_id=sub_id, goal="")

    with pytest.raises(ValidationError):
        UpdateProfileSlotsInput(subject_id=sub_id, background="   ")


@pytest.mark.asyncio
async def test_update_profile_slots_upsert_on_missing_profile(
    session: AsyncSession,
) -> None:
    """update_profile_slots creates an ONBOARDING profile row when absent."""
    subject = await _create_test_subject(session, "Fresh Subject")

    params = UpdateProfileSlotsInput(
        subject_id=subject.id,
        goal="Master async patterns",
        pace_preference=PacePreference.CHILL,
    )
    res = await execute_update_profile_slots(session, params)

    assert res.subject_id == subject.id
    assert res.goal == "Master async patterns"
    assert res.current_level == ""
    assert res.pace_preference == PacePreference.CHILL
    assert res.score == 40
    assert res.filled_slots == ["goal", "pace_preference"]
    assert res.missing_slots == ["current_level", "background", "motivation"]

    profile = await session.get(SubjectProfile, subject.id)
    assert profile is not None
    assert profile.status == SubjectProfileStatus.ONBOARDING


@pytest.mark.asyncio
async def test_update_profile_slots_partial_update_semantics(
    session: AsyncSession,
) -> None:
    """update_profile_slots leaves omitted slots untouched on existing rows."""
    subject = await _create_test_subject(session, "Partial Update Subject")
    session.add(
        SubjectProfile(
            subject_id=subject.id,
            goal="Existing goal",
            current_level="Intermediate",
            motivation="Curiosity",
            status=SubjectProfileStatus.ONBOARDING,
        )
    )
    await session.commit()

    params = UpdateProfileSlotsInput(
        subject_id=subject.id,
        background="5 years of Go",
        pace_preference=PacePreference.INTENSE,
    )
    res = await execute_update_profile_slots(session, params)

    # Updated slots
    assert res.background == "5 years of Go"
    assert res.pace_preference == PacePreference.INTENSE
    # Untouched slots keep prior values
    assert res.goal == "Existing goal"
    assert res.current_level == "Intermediate"
    assert res.motivation == "Curiosity"
    assert res.score == 100
    assert res.missing_slots == []


@pytest.mark.asyncio
async def test_update_profile_slots_values_are_stripped(
    session: AsyncSession,
) -> None:
    """update_profile_slots strips surrounding whitespace before persisting."""
    subject = await _create_test_subject(session, "Strip Subject")

    params = UpdateProfileSlotsInput(
        subject_id=subject.id,
        goal="  Build a compiler  ",
    )
    res = await execute_update_profile_slots(session, params)
    assert res.goal == "Build a compiler"


@pytest.mark.asyncio
async def test_update_profile_slots_no_values_provided(
    session: AsyncSession,
) -> None:
    """update_profile_slots with only null slots raises ToolValidationError."""
    subject = await _create_test_subject(session, "No-op Subject")

    params = UpdateProfileSlotsInput(subject_id=subject.id)
    with pytest.raises(ToolValidationError):
        await execute_update_profile_slots(session, params)


@pytest.mark.asyncio
async def test_update_profile_slots_non_existent_subject(
    session: AsyncSession,
) -> None:
    """update_profile_slots for non-existent subject raises ToolNotFoundError."""
    params = UpdateProfileSlotsInput(subject_id=uuid.uuid4(), goal="Some goal")
    with pytest.raises(ToolNotFoundError):
        await execute_update_profile_slots(session, params)


@pytest.mark.asyncio
async def test_dispatcher_routes_update_profile_slots(
    session: AsyncSession,
) -> None:
    """execute_tool dispatches update_profile_slots end-to-end."""
    subject = await _create_test_subject(session, "Dispatcher Slots")

    result = await execute_tool(
        session=session,
        name="update_profile_slots",
        arguments={
            "subject_id": str(subject.id),
            "motivation": "Ship a side project",
        },
    )
    assert result.success is True
    assert result.data is not None
    assert result.data["motivation"] == "Ship a side project"
    assert result.data["score"] == 40
