"""Unit and integration tests for SQLModel core data models."""

import uuid

import pytest
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


@pytest.mark.asyncio
async def test_create_subject_read_back(session: AsyncSession) -> None:
    """Create a subject and verify read back by id."""
    subject = Subject(
        title="Distributed Systems in Go",
        description="Master distributed consensus and Raft",
    )
    session.add(subject)
    await session.commit()
    await session.refresh(subject)

    assert subject.id is not None
    assert isinstance(subject.id, uuid.UUID)
    assert subject.title == "Distributed Systems in Go"
    assert subject.description == "Master distributed consensus and Raft"
    assert subject.created_at is not None

    # Read back via select
    stmt = select(Subject).where(Subject.id == subject.id)
    result = await session.exec(stmt)
    fetched = result.first()
    assert fetched is not None
    assert fetched.id == subject.id
    assert fetched.title == "Distributed Systems in Go"


@pytest.mark.asyncio
async def test_create_subject_profile_linked(session: AsyncSession) -> None:
    """Create a subject profile linked 1:1 to a subject."""
    subject = Subject(title="Rust for Systems Programming")
    session.add(subject)
    await session.commit()
    await session.refresh(subject)

    profile = SubjectProfile(
        subject_id=subject.id,
        goal="Build a high performance database engine",
        current_level="Intermediate in C++, beginner in Rust",
        background="5 years backend engineering",
        motivation="Switch to systems engineering roles",
        pace_preference=PacePreference.INTENSE,
        status=SubjectProfileStatus.ONBOARDING,
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)

    assert profile.subject_id == subject.id
    assert profile.pace_preference == PacePreference.INTENSE
    assert profile.status == SubjectProfileStatus.ONBOARDING

    # Read back
    stmt = select(SubjectProfile).where(SubjectProfile.subject_id == subject.id)
    res = await session.exec(stmt)
    fetched_profile = res.first()
    assert fetched_profile is not None
    assert fetched_profile.goal == "Build a high performance database engine"


@pytest.mark.asyncio
async def test_create_ordered_topics(session: AsyncSession) -> None:
    """Create 3 topics for a subject with order_index and prerequisite list."""
    subject = Subject(title="Data Structures & Algorithms")
    session.add(subject)
    await session.commit()
    await session.refresh(subject)

    topic_1 = Topic(
        subject_id=subject.id,
        title="Arrays & Hashing",
        order_index=1,
        prerequisite_ids=[],
        status=TopicStatus.DONE,
    )
    session.add(topic_1)
    await session.commit()
    await session.refresh(topic_1)
    assert topic_1.id is not None

    topic_2 = Topic(
        subject_id=subject.id,
        title="Two Pointers",
        order_index=2,
        prerequisite_ids=[topic_1.id],
        status=TopicStatus.ACTIVE,
    )
    topic_3 = Topic(
        subject_id=subject.id,
        title="Sliding Window",
        order_index=3,
        prerequisite_ids=[topic_1.id, topic_2.id],
        status=TopicStatus.PENDING,
    )
    session.add_all([topic_2, topic_3])
    await session.commit()

    # Query ordered by order_index
    stmt = (
        select(Topic).where(Topic.subject_id == subject.id).order_by(Topic.order_index)
    )
    res = await session.exec(stmt)
    topics = res.all()

    assert len(topics) == 3
    assert [t.order_index for t in topics] == [1, 2, 3]
    assert topics[0].status == TopicStatus.DONE
    assert topics[1].status == TopicStatus.ACTIVE
    assert topics[2].status == TopicStatus.PENDING
    assert topics[1].prerequisite_ids == [topic_1.id]


@pytest.mark.asyncio
async def test_create_feed_posts_for_active_topic(session: AsyncSession) -> None:
    """Create feed posts for an active topic and read them back in order."""
    subject = Subject(title="FastAPI Internals")
    session.add(subject)
    await session.commit()
    await session.refresh(subject)

    topic = Topic(
        subject_id=subject.id,
        title="ASGI Middleware Pipeline",
        order_index=1,
        status=TopicStatus.ACTIVE,
    )
    session.add(topic)
    await session.commit()
    await session.refresh(topic)
    assert topic.id is not None

    posts = [
        FeedPost(
            topic_id=topic.id,
            content="ASGI stands for Asynchronous Server Gateway Interface.",
            order_index=0,
        ),
        FeedPost(
            topic_id=topic.id,
            content=(
                "Middleware intercepts every request before it hits the route handler."
            ),
            order_index=1,
        ),
        FeedPost(
            topic_id=topic.id,
            content="Always ensure async middleware doesn't block the event loop!",
            order_index=2,
        ),
    ]
    session.add_all(posts)
    await session.commit()

    stmt = (
        select(FeedPost)
        .where(FeedPost.topic_id == topic.id)
        .order_by(FeedPost.order_index.asc())
    )
    res = await session.exec(stmt)
    fetched_posts = res.all()

    assert len(fetched_posts) == 3
    assert fetched_posts[0].content.startswith("ASGI stands for")
    assert fetched_posts[1].order_index == 1
    assert fetched_posts[2].order_index == 2


@pytest.mark.asyncio
async def test_create_chat_messages(session: AsyncSession) -> None:
    """Create chat messages attached to a topic for Open Chat."""
    subject = Subject(title="Operating Systems")
    session.add(subject)
    await session.commit()
    await session.refresh(subject)

    topic = Topic(
        subject_id=subject.id,
        title="Virtual Memory & Paging",
        order_index=1,
    )
    session.add(topic)
    await session.commit()
    await session.refresh(topic)
    assert topic.id is not None

    user_msg = ChatMessage(
        topic_id=topic.id,
        role=ChatRole.USER,
        content="What is a TLB miss?",
    )
    ai_msg = ChatMessage(
        topic_id=topic.id,
        role=ChatRole.ASSISTANT,
        content=(
            "A Translation Lookaside Buffer (TLB) miss occurs when "
            "a virtual page number is not found in the cache."
        ),
    )
    session.add_all([user_msg, ai_msg])
    await session.commit()

    stmt = (
        select(ChatMessage)
        .where(ChatMessage.topic_id == topic.id)
        .order_by(ChatMessage.created_at.asc())
    )
    res = await session.exec(stmt)
    messages = res.all()

    assert len(messages) == 2
    assert messages[0].role == ChatRole.USER
    assert messages[0].content == "What is a TLB miss?"
    assert messages[1].role == ChatRole.ASSISTANT


@pytest.mark.asyncio
async def test_onboarding_answers_row_per_answer(session: AsyncSession) -> None:
    """Insert onboarding answers row-per-answer and read them back."""
    subject = Subject(title="Deep Learning")
    session.add(subject)
    await session.commit()
    await session.refresh(subject)

    answers = [
        OnboardingAnswer(
            subject_id=subject.id,
            question="What is your primary goal?",
            answer="Understand attention mechanisms and Transformers.",
        ),
        OnboardingAnswer(
            subject_id=subject.id,
            question="How many hours per week can you study?",
            answer="10 hours per week.",
        ),
        OnboardingAnswer(
            subject_id=subject.id,
            question="What is your current math background?",
            answer="Comfortable with linear algebra and calculus.",
        ),
    ]
    session.add_all(answers)
    await session.commit()

    stmt = (
        select(OnboardingAnswer)
        .where(OnboardingAnswer.subject_id == subject.id)
        .order_by(OnboardingAnswer.created_at.asc())
    )
    res = await session.exec(stmt)
    saved_answers = res.all()

    assert len(saved_answers) == 3
    assert saved_answers[0].question == "What is your primary goal?"
    assert saved_answers[1].answer == "10 hours per week."
