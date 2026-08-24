"""ChatMessage model."""

import enum
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.topic import Topic


class ChatRole(enum.StrEnum):
    """Role of the message sender in Open Chat."""

    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(SQLModel, table=True):
    """ChatMessage table persisting Open Chat turns scoped to a topic."""

    __tablename__ = "chat_messages"

    id: int | None = Field(default=None, primary_key=True)
    topic_id: int = Field(
        foreign_key="topics.id",
        ondelete="CASCADE",
        index=True,
        nullable=False,
    )
    role: ChatRole = Field(
        sa_column=Column(
            SAEnum(
                ChatRole,
                name="chat_role",
                values_callable=lambda x: [e.value for e in x],
            ),
            nullable=False,
        ),
    )
    content: str = Field(nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # Relationships
    topic: Optional["Topic"] = Relationship(back_populates="chat_messages")
