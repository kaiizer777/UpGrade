"""Pydantic schemas for roadmap endpoints."""

import uuid

from pydantic import BaseModel, ConfigDict

from app.models.topic import TopicStatus


class RoadmapTopicRead(BaseModel):
    """Single topic in a roadmap response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    order_index: int
    prerequisite_ids: list[int]
    status: TopicStatus


class RoadmapRead(BaseModel):
    """Full roadmap response for a subject."""

    subject_id: uuid.UUID
    topics: list[RoadmapTopicRead]
    active_topic_id: int | None = None
