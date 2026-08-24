"""Pydantic schemas for Subject."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SubjectBase(BaseModel):
    """Base schema for Subject."""

    title: str
    description: str | None = None


class SubjectCreate(SubjectBase):
    """Schema for creating a subject."""

    pass


class SubjectUpdate(BaseModel):
    """Schema for updating a subject."""

    title: str | None = None
    description: str | None = None


class SubjectRead(SubjectBase):
    """Schema for reading a subject."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
