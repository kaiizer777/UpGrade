"""Pydantic schemas for SubjectProfile."""

import uuid

from pydantic import BaseModel, ConfigDict

from app.models.subject_profile import PacePreference, SubjectProfileStatus


class SubjectProfileBase(BaseModel):
    """Base schema for SubjectProfile."""

    goal: str = ""
    current_level: str = ""
    background: str = ""
    motivation: str = ""
    pace_preference: PacePreference = PacePreference.STEADY
    status: SubjectProfileStatus = SubjectProfileStatus.ONBOARDING


class SubjectProfileCreate(SubjectProfileBase):
    """Schema for creating/initializing a subject profile."""

    subject_id: uuid.UUID | None = None


class SubjectProfileUpdate(BaseModel):
    """Schema for updating a subject profile."""

    goal: str | None = None
    current_level: str | None = None
    background: str | None = None
    motivation: str | None = None
    pace_preference: PacePreference | None = None
    status: SubjectProfileStatus | None = None


class SubjectProfileRead(SubjectProfileBase):
    """Schema for reading a subject profile."""

    model_config = ConfigDict(from_attributes=True)

    subject_id: uuid.UUID
