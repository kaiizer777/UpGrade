"""Pydantic schemas for OnboardingAnswer."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OnboardingAnswerBase(BaseModel):
    """Base schema for OnboardingAnswer."""

    question: str
    answer: str


class OnboardingAnswerCreate(OnboardingAnswerBase):
    """Schema for recording a single Q&A answer."""

    subject_id: uuid.UUID


class OnboardingAnswerRead(OnboardingAnswerBase):
    """Schema for reading an onboarding answer record."""

    model_config = ConfigDict(from_attributes=True)

    created_at: datetime
