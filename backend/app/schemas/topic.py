"""Pydantic schemas for Topic."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.topic import TopicStatus


class TopicBase(BaseModel):
    """Base schema for Topic."""

    title: str
    order_index: int
    prerequisite_ids: list[int] = Field(default_factory=list)
    status: TopicStatus = TopicStatus.PENDING


class TopicCreate(TopicBase):
    """Schema for creating a topic in a roadmap."""

    subject_id: uuid.UUID


class TopicUpdate(BaseModel):
    """Schema for updating topic state or order."""

    title: str | None = None
    order_index: int | None = None
    prerequisite_ids: list[int] | None = None
    status: TopicStatus | None = None


class TopicRead(TopicBase):
    """Schema for reading a topic."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    subject_id: uuid.UUID
