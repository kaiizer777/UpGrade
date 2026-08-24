"""Pydantic schemas for FeedPost."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FeedPostBase(BaseModel):
    """Base schema for FeedPost."""

    content: str
    order_index: int


class FeedPostCreate(FeedPostBase):
    """Schema for creating a feed post."""

    topic_id: int


class FeedPostRead(FeedPostBase):
    """Schema for reading a feed post."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    topic_id: int
    created_at: datetime
