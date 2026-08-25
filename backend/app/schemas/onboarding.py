"""Pydantic schemas for the onboarding flow API."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.subject_profile import PacePreference, SubjectProfileStatus
from app.schemas.onboarding_answers import OnboardingAnswerRead


class OnboardingMessageCreate(BaseModel):
    """Schema for submitting a user message during onboarding."""

    content: str = Field(..., min_length=1)


class CompletenessRead(BaseModel):
    """Deterministic completeness snapshot for a subject profile."""

    score: int
    filled_slots: list[str]
    missing_slots: list[str]


class SubjectProfileSlotRead(BaseModel):
    """Profile slot values exposed to onboarding consumers."""

    model_config = ConfigDict(from_attributes=True)

    goal: str
    current_level: str
    background: str
    motivation: str
    pace_preference: PacePreference
    status: SubjectProfileStatus


class OnboardingMessageRead(BaseModel):
    """Response schema for a single onboarding conversational turn."""

    reply: str
    status: str
    questions_asked: int
    max_questions: int
    completeness: CompletenessRead
    profile: SubjectProfileSlotRead | None


class OnboardingStateRead(BaseModel):
    """Full onboarding state snapshot for a subject."""

    subject_id: uuid.UUID
    status: str
    questions_asked: int
    max_questions: int
    completeness: CompletenessRead
    answers: list[OnboardingAnswerRead]
    profile: SubjectProfileSlotRead | None
