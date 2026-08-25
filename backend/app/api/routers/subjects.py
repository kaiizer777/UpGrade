"""Subjects and onboarding flow router."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.database import get_session
from app.models.subject import Subject
from app.models.subject_profile import SubjectProfile
from app.schemas.onboarding import (
    OnboardingMessageCreate,
    OnboardingMessageRead,
    OnboardingStateRead,
)
from app.schemas.subject import SubjectCreate, SubjectListItemRead, SubjectRead
from app.services.ai import AiConfigError, AiGenerationError
from app.services.onboarding import (
    OnboardingAlreadyFinalizedError,
    SubjectNotFoundError,
    build_onboarding_state,
    process_onboarding_message,
)

router = APIRouter(tags=["subjects"])


@router.post(
    "/subjects",
    response_model=SubjectRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a subject",
)
async def create_subject(
    payload: SubjectCreate,
    session: AsyncSession = Depends(get_session),
) -> Subject:
    """Persist and return a newly created learning subject."""
    subject = Subject(title=payload.title, description=payload.description)
    session.add(subject)
    await session.commit()
    await session.refresh(subject)
    return subject


@router.get(
    "/subjects",
    response_model=list[SubjectListItemRead],
    summary="List subjects with onboarding status",
)
async def list_subjects(
    session: AsyncSession = Depends(get_session),
) -> list[SubjectListItemRead]:
    """List all subjects; onboarding_status defaults to 'onboarding'."""
    stmt = (
        select(Subject, SubjectProfile)
        .join(
            SubjectProfile,
            SubjectProfile.subject_id == Subject.id,  # type: ignore[arg-type]
            isouter=True,
        )
        .order_by(Subject.created_at.desc())  # type: ignore[attr-defined]
    )
    rows = (await session.exec(stmt)).all()

    items: list[SubjectListItemRead] = []
    for subject_row, profile_row in rows:
        items.append(
            SubjectListItemRead(
                id=subject_row.id,
                title=subject_row.title,
                description=subject_row.description,
                created_at=subject_row.created_at,
                onboarding_status=(
                    profile_row.status.value if profile_row else "onboarding"
                ),
            )
        )
    return items


@router.get(
    "/subjects/{subject_id}/onboarding/state",
    response_model=OnboardingStateRead,
    summary="Get onboarding state for a subject",
)
async def get_onboarding_state(
    subject_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> OnboardingStateRead:
    """Return the full onboarding state snapshot for a subject."""
    subject = await session.get(Subject, subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject '{subject_id}' not found.",
        )
    return await build_onboarding_state(session, subject)


@router.post(
    "/subjects/{subject_id}/onboarding/messages",
    response_model=OnboardingMessageRead,
    summary="Send an onboarding message (full AI turn)",
)
async def post_onboarding_message(
    subject_id: uuid.UUID,
    payload: OnboardingMessageCreate,
    session: AsyncSession = Depends(get_session),
) -> OnboardingMessageRead:
    """Run one full AI onboarding turn for the given user message."""
    try:
        return await process_onboarding_message(session, subject_id, payload.content)
    except SubjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject '{subject_id}' not found.",
        ) from None
    except OnboardingAlreadyFinalizedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Onboarding already finalized",
        ) from None
    except AiConfigError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI provider not configured",
        ) from None
    except AiGenerationError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI generation failed",
        ) from None
