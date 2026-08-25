"""Roadmap generation router."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.database import get_session
from app.models.subject import Subject
from app.models.topic import Topic
from app.schemas.roadmap import RoadmapRead, RoadmapTopicRead
from app.services.ai import AiConfigError, AiGenerationError
from app.services.roadmap import (
    RoadmapNotReadyError,
    SubjectNotFoundError,
    generate_roadmap,
)

router = APIRouter(tags=["roadmap"])


def _topics_to_response(subject_id: uuid.UUID, topics: list[Topic]) -> RoadmapRead:
    active_id = next((t.id for t in topics if t.status.value == "active"), None)  # type: ignore[union-attr]
    return RoadmapRead(
        subject_id=subject_id,
        topics=[
            RoadmapTopicRead(
                id=t.id,  # type: ignore[arg-type]
                title=t.title,
                order_index=t.order_index,
                prerequisite_ids=t.prerequisite_ids,
                status=t.status,
            )
            for t in topics
        ],
        active_topic_id=active_id,
    )


@router.post(
    "/subjects/{subject_id}/roadmap",
    response_model=RoadmapRead,
    summary="Generate or fetch roadmap for a subject",
)
async def post_roadmap(
    subject_id: uuid.UUID,
    response: Response,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> RoadmapRead:
    """Generate a roadmap; idempotent - returns existing with 200 if already present.

    The HTTP status code differs by creation freshness; we return the same body
    shape in both cases. FastAPI's response_model will serialize it.
    """
    # Fast check for idempotency to decide status code
    subject = await session.get(Subject, subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject '{subject_id}' not found.",
        )
    existing_stmt = (
        select(Topic)
        .where(Topic.subject_id == subject_id)
        .order_by(Topic.order_index.asc())  # type: ignore[attr-defined]
    )
    existing = list((await session.exec(existing_stmt)).all())
    if existing:
        response.status_code = status.HTTP_200_OK
        return _topics_to_response(subject_id, existing)

    try:
        result = await generate_roadmap(session, subject_id, background_tasks)
    except SubjectNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject '{subject_id}' not found.",
        ) from None
    except RoadmapNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc) or "Onboarding not finalized",
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

    # After generation, topics are persisted; reload to ensure ordered status
    # But we can also build from result dict directly
    topics_data = result.get("topics", [])
    # Convert dict topics to RoadmapRead via manual mapping to avoid re-query
    # Ensure ordering by order_index
    sorted_topics = sorted(topics_data, key=lambda t: t.get("order_index", 0))
    response.status_code = status.HTTP_201_CREATED
    return RoadmapRead(
        subject_id=uuid.UUID(str(result["subject_id"])),
        topics=[
            RoadmapTopicRead(
                id=t["id"],
                title=t["title"],
                order_index=t["order_index"],
                prerequisite_ids=t.get("prerequisite_ids", []),
                status=t["status"],
            )
            for t in sorted_topics
        ],
        active_topic_id=result.get("active_topic_id"),
    )


@router.get(
    "/subjects/{subject_id}/roadmap",
    response_model=RoadmapRead,
    summary="Get roadmap for a subject",
)
async def get_roadmap(
    subject_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> RoadmapRead:
    """Fetch the roadmap for a subject; empty list if not yet generated."""
    subject = await session.get(Subject, subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject '{subject_id}' not found.",
        )
    stmt = (
        select(Topic)
        .where(Topic.subject_id == subject_id)
        .order_by(Topic.order_index.asc())  # type: ignore[attr-defined]
    )
    topics = list((await session.exec(stmt)).all())
    return _topics_to_response(subject_id, topics)
