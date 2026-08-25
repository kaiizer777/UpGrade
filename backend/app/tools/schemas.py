"""Pydantic schemas and validators for LLM tool layer."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.chat_message import ChatRole
from app.models.subject_profile import PacePreference, SubjectProfileStatus
from app.models.topic import TopicStatus

# ============================================================================
# ask_question Tool Schemas
# ============================================================================


class AskQuestionInput(BaseModel):
    """Input schema for the ask_question onboarding tool."""

    question: str = Field(
        ...,
        min_length=1,
        description="The clarifying question to ask the user during onboarding.",
    )
    why: str | None = Field(
        default=None,
        description="Optional rationale explaining why this question is being asked.",
    )
    subject_id: str | uuid.UUID | None = Field(
        default=None,
        description=(
            "Optional subject ID - the system fills it automatically; "
            "any string is accepted and will be overridden server-side."
        ),
    )

    @field_validator("question")
    @classmethod
    def validate_non_empty_question(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Question cannot be empty or whitespace only.")
        return stripped


class AskQuestionOutput(BaseModel):
    """Output schema for ask_question."""

    question: str
    why: str | None = None
    question_count: int | None = None
    is_cap_reached: bool = False


# ============================================================================
# save_answer Tool Schemas
# ============================================================================


class SaveAnswerInput(BaseModel):
    """Input schema for save_answer onboarding tool."""

    subject_id: str | uuid.UUID | None = Field(
        default=None,
        description=(
            "The subject ID associated with this onboarding turn. "
            "Any string is accepted; the system overrides it server-side."
        ),
    )
    question: str = Field(
        ...,
        min_length=1,
        description="The question that was asked.",
    )
    answer: str = Field(
        ...,
        min_length=1,
        description="The user's answer.",
    )

    @field_validator("question", "answer")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field cannot be empty or whitespace only.")
        return stripped


class SaveAnswerOutput(BaseModel):
    """Output schema for save_answer."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    subject_id: uuid.UUID
    question: str
    answer: str
    created_at: datetime
    answer_count: int


# ============================================================================
# update_profile_slots Tool Schemas
# ============================================================================


class UpdateProfileSlotsInput(BaseModel):
    """Input schema for the update_profile_slots onboarding tool.

    All slot fields are optional - ``None`` means "leave this slot unchanged".
    """

    subject_id: str | uuid.UUID | None = Field(
        default=None,
        description=(
            "The subject ID whose profile slots should be updated. "
            "Any string is accepted; the system overrides it server-side."
        ),
    )
    goal: str | None = Field(
        default=None,
        description="User's goal for learning this subject (None = don't change).",
    )
    current_level: str | None = Field(
        default=None,
        description="User's current knowledge/skill level (None = don't change).",
    )
    background: str | None = Field(
        default=None,
        description="User's relevant background or experience (None = don't change).",
    )
    motivation: str | None = Field(
        default=None,
        description="User's motivation for learning (None = don't change).",
    )
    pace_preference: PacePreference | None = Field(
        default=None,
        description="Pace preference: chill, steady, or intense (None = don't change).",
    )

    @field_validator("goal", "current_level", "background", "motivation")
    @classmethod
    def validate_non_empty_slots(cls, v: str | None) -> str | None:
        if v is None:
            return v
        stripped = v.strip()
        if not stripped:
            raise ValueError(
                "Slot cannot be set to an empty string; omit it to leave unchanged."
            )
        return stripped


class UpdateProfileSlotsOutput(BaseModel):
    """Output schema for update_profile_slots."""

    model_config = ConfigDict(from_attributes=True)

    subject_id: uuid.UUID
    goal: str
    current_level: str
    background: str
    motivation: str
    pace_preference: PacePreference
    score: int
    filled_slots: list[str]
    missing_slots: list[str]


# ============================================================================
# finalize_profile Tool Schemas
# ============================================================================


class FinalizeProfileInput(BaseModel):
    """Input schema for finalize_profile tool."""

    subject_id: str | uuid.UUID | None = Field(
        default=None,
        description=(
            "The subject ID to finalize the profile for. "
            "Any string is accepted; the system overrides it server-side."
        ),
    )
    goal: str = Field(
        ...,
        min_length=1,
        description="User's finalized goal for learning this subject.",
    )
    current_level: str = Field(
        ...,
        min_length=1,
        description="User's current knowledge and skill level.",
    )
    background: str = Field(
        ...,
        min_length=1,
        description="User's relevant background or experience.",
    )
    motivation: str = Field(
        ...,
        min_length=1,
        description="User's motivation or reason for learning.",
    )
    pace_preference: PacePreference = Field(
        default=PacePreference.STEADY,
        description="User's pace preference: chill, steady, or intense.",
    )

    @field_validator("goal", "current_level", "background", "motivation")
    @classmethod
    def validate_non_empty_profile_fields(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Profile field cannot be empty or whitespace only.")
        return stripped


class FinalizeProfileOutput(BaseModel):
    """Output schema for finalize_profile."""

    model_config = ConfigDict(from_attributes=True)

    subject_id: uuid.UUID
    goal: str
    current_level: str
    background: str
    motivation: str
    pace_preference: PacePreference
    status: SubjectProfileStatus
    ready_for_roadmap: bool = True


# ============================================================================
# create_roadmap Tool Schemas
# ============================================================================


class RoadmapTopicItem(BaseModel):
    """Single topic item within a roadmap."""

    title: str = Field(
        ...,
        min_length=1,
        description="Title of the learning topic.",
    )
    order_index: int | None = Field(
        default=None,
        ge=1,
        description=(
            "1-based sequence order index. If omitted, the server assigns "
            "it from array position (first topic = 1)."
        ),
    )
    prerequisite_indices: list[int] = Field(
        default_factory=list,
        description="Order indices of prerequisite topics (relative sequencing).",
    )
    prerequisite_ids: list[int] = Field(
        default_factory=list,
        description=(
            "Direct database topic IDs of prerequisite topics (if already known)."
        ),
    )
    status: TopicStatus | None = Field(
        default=None,
        description=(
            "Explicit status for the topic. If None, first topic is active and "
            "others are pending."
        ),
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Topic title cannot be empty.")
        return stripped


class CreateRoadmapInput(BaseModel):
    """Input schema for create_roadmap tool."""

    subject_id: str | uuid.UUID | None = Field(
        default=None,
        description=(
            "The subject ID to attach the roadmap to. "
            "Any string is accepted; the system overrides it server-side."
        ),
    )
    topics: list[RoadmapTopicItem] = Field(
        ...,
        min_length=1,
        description="Ordered list of roadmap topics.",
    )

    @field_validator("topics")
    @classmethod
    def validate_unique_order_indices(
        cls, v: list[RoadmapTopicItem]
    ) -> list[RoadmapTopicItem]:
        # Auto-assign missing order_index from array position (1-based)
        for idx, topic in enumerate(v):
            if topic.order_index is None:
                topic.order_index = idx + 1
        order_indices: list[int] = []
        for topic in v:
            assert topic.order_index is not None  # assigned above
            order_indices.append(topic.order_index)
        if len(order_indices) != len(set(order_indices)):
            raise ValueError("Topic order_index values must be unique.")
        n = len(v)
        if sorted(order_indices) != list(range(1, n + 1)):
            raise ValueError(
                f"Topic order_index values must be contiguous 1..{n} without gaps; "
                f"got {sorted(order_indices)}."
            )
        return v


class CreatedTopicItem(BaseModel):
    """Representation of a persisted topic."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    subject_id: uuid.UUID
    title: str
    order_index: int
    prerequisite_ids: list[int]
    status: TopicStatus


class CreateRoadmapOutput(BaseModel):
    """Output schema for create_roadmap."""

    subject_id: uuid.UUID
    topics: list[CreatedTopicItem]
    active_topic_id: int | None = None


# ============================================================================
# generate_feed_batch Tool Schemas
# ============================================================================


class FeedPostItem(BaseModel):
    """Single feed post item in a generated batch."""

    content: str = Field(
        ...,
        min_length=1,
        description="Post content (lesson bite, code snippet, or mini-exercise).",
    )
    order_index: int = Field(
        ...,
        ge=0,
        description="0-based sequence index within the topic's feed batch.",
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Feed post content cannot be empty.")
        return stripped


class GenerateFeedBatchInput(BaseModel):
    """Input schema for generate_feed_batch tool."""

    topic_id: int = Field(
        ...,
        description="The topic ID this feed batch belongs to.",
    )
    posts: list[FeedPostItem] = Field(
        ...,
        min_length=1,
        description="List of feed posts to persist.",
    )

    @field_validator("posts")
    @classmethod
    def validate_unique_order_indices(cls, v: list[FeedPostItem]) -> list[FeedPostItem]:
        indices = [p.order_index for p in v]
        if len(indices) != len(set(indices)):
            raise ValueError("Feed post order_index values must be unique.")
        return v


class CreatedFeedPostItem(BaseModel):
    """Representation of a persisted feed post."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    topic_id: int
    content: str
    order_index: int
    created_at: datetime


class GenerateFeedBatchOutput(BaseModel):
    """Output schema for generate_feed_batch."""

    topic_id: int
    post_count: int
    posts: list[CreatedFeedPostItem]


# ============================================================================
# mark_topic_complete Tool Schemas
# ============================================================================


class MarkTopicCompleteInput(BaseModel):
    """Input schema for mark_topic_complete tool."""

    topic_id: int = Field(
        ...,
        description="The ID of the topic to complete.",
    )


class MarkTopicCompleteOutput(BaseModel):
    """Output schema for mark_topic_complete."""

    completed_topic_id: int
    status: TopicStatus
    deleted_feed_posts_count: int
    next_topic_id: int | None = None
    next_topic_title: str | None = None
    all_topics_completed: bool = False


# ============================================================================
# log_chat_message Tool Schemas
# ============================================================================


class LogChatMessageInput(BaseModel):
    """Input schema for log_chat_message tool."""

    topic_id: int = Field(
        ...,
        description="The topic ID associated with the Open Chat conversation.",
    )
    role: ChatRole = Field(
        ...,
        description="Role of the message sender: 'user' or 'assistant'.",
    )
    content: str = Field(
        ...,
        min_length=1,
        description="The text content of the message.",
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Chat message content cannot be empty.")
        return stripped


class LogChatMessageOutput(BaseModel):
    """Output schema for log_chat_message."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    topic_id: int
    role: ChatRole
    content: str
    created_at: datetime


# ============================================================================
# Generic Tool Dispatcher & Result Schemas
# ============================================================================


class ToolResult(BaseModel):
    """Standardized response schema returned by the tool dispatcher."""

    success: bool
    tool_name: str
    data: Any | None = None
    error: str | None = None
    error_code: str | None = None
    details: dict[str, Any] | None = None


class ToolCallRequest(BaseModel):
    """Payload representing an incoming tool invocation from an LLM."""

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
