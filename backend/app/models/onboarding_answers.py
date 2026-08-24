"""OnboardingAnswer model."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.subject import Subject


class OnboardingAnswer(SQLModel, table=True):
    """Onboarding answer record representing a single Q&A turn per subject."""

    __tablename__ = "onboarding_answers"

    id: int | None = Field(default=None, primary_key=True)
    subject_id: uuid.UUID = Field(
        foreign_key="subjects.id",
        ondelete="CASCADE",
        index=True,
        nullable=False,
    )
    question: str = Field(nullable=False)
    answer: str = Field(nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # Relationships
    subject: Optional["Subject"] = Relationship(back_populates="onboarding_answers")
