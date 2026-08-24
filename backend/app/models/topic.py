"""Topic model."""

import enum
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, Index
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.chat_message import ChatMessage
    from app.models.feed_post import FeedPost
    from app.models.subject import Subject


class TopicStatus(enum.StrEnum):
    """Status options for a roadmap topic."""

    PENDING = "pending"
    ACTIVE = "active"
    DONE = "done"


class Topic(SQLModel, table=True):
    """Topic table representing ordered learning topics in a roadmap."""

    __tablename__ = "topics"
    __table_args__ = (
        Index("ix_topics_subject_id_order_index", "subject_id", "order_index"),
    )

    id: int | None = Field(default=None, primary_key=True)
    subject_id: uuid.UUID = Field(
        foreign_key="subjects.id",
        ondelete="CASCADE",
        nullable=False,
    )
    title: str = Field(nullable=False)
    order_index: int = Field(nullable=False)
    prerequisite_ids: list[int] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, default=list),
    )
    status: TopicStatus = Field(
        default=TopicStatus.PENDING,
        sa_column=Column(
            SAEnum(
                TopicStatus,
                name="topic_status",
                values_callable=lambda x: [e.value for e in x],
            ),
            nullable=False,
            default=TopicStatus.PENDING.value,
        ),
    )

    # Relationships
    subject: Optional["Subject"] = Relationship(back_populates="topics")
    feed_posts: list["FeedPost"] = Relationship(
        back_populates="topic",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    chat_messages: list["ChatMessage"] = Relationship(
        back_populates="topic",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
