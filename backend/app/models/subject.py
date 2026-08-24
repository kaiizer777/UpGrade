"""Subject model."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime, Index
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.chat_message import ChatMessage  # noqa: F401
    from app.models.feed_post import FeedPost  # noqa: F401
    from app.models.onboarding_answers import OnboardingAnswer
    from app.models.subject_profile import SubjectProfile
    from app.models.topic import Topic


# TODO(auth): add user_id FK when auth lands at end
class Subject(SQLModel, table=True):
    """Subject table representing a learning track."""

    __tablename__ = "subjects"
    __table_args__ = (Index("ix_subjects_created_at", "created_at"),)

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )
    title: str = Field(nullable=False)
    description: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # Relationships
    profile: Optional["SubjectProfile"] = Relationship(
        back_populates="subject",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "uselist": False,
        },
    )
    onboarding_answers: list["OnboardingAnswer"] = Relationship(
        back_populates="subject",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    topics: list["Topic"] = Relationship(
        back_populates="subject",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
