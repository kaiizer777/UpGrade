"""FeedPost model."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime, Index
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.topic import Topic


class FeedPost(SQLModel, table=True):
    """Feed post table representing ephemeral JIT lesson bites for the active topic."""

    __tablename__ = "feed_posts"
    __table_args__ = (
        Index("ix_feed_posts_topic_id_order_index", "topic_id", "order_index"),
    )

    id: int | None = Field(default=None, primary_key=True)
    topic_id: int = Field(
        foreign_key="topics.id",
        ondelete="CASCADE",
        nullable=False,
    )
    content: str = Field(nullable=False)
    order_index: int = Field(nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # Relationships
    topic: Optional["Topic"] = Relationship(back_populates="feed_posts")
