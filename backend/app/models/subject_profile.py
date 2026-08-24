"""SubjectProfile model."""

import enum
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.subject import Subject


class PacePreference(enum.StrEnum):
    """Pace preference options for a subject."""

    CHILL = "chill"
    STEADY = "steady"
    INTENSE = "intense"


class SubjectProfileStatus(enum.StrEnum):
    """Status options for onboarding / readiness of a subject."""

    ONBOARDING = "onboarding"
    READY = "ready"


class SubjectProfile(SQLModel, table=True):
    """Subject profile containing finalized personalization context."""

    __tablename__ = "subject_profile"

    subject_id: uuid.UUID = Field(
        foreign_key="subjects.id",
        primary_key=True,
        ondelete="CASCADE",
        nullable=False,
    )
    goal: str = Field(default="", nullable=False)
    current_level: str = Field(default="", nullable=False)
    background: str = Field(default="", nullable=False)
    motivation: str = Field(default="", nullable=False)
    pace_preference: PacePreference = Field(
        default=PacePreference.STEADY,
        sa_column=Column(
            SAEnum(
                PacePreference,
                name="pace_preference",
                values_callable=lambda x: [e.value for e in x],
            ),
            nullable=False,
            default=PacePreference.STEADY.value,
        ),
    )
    status: SubjectProfileStatus = Field(
        default=SubjectProfileStatus.ONBOARDING,
        sa_column=Column(
            SAEnum(
                SubjectProfileStatus,
                name="subject_profile_status",
                values_callable=lambda x: [e.value for e in x],
            ),
            nullable=False,
            default=SubjectProfileStatus.ONBOARDING.value,
        ),
    )

    # Relationships
    subject: Optional["Subject"] = Relationship(back_populates="profile")
