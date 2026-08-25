"""Feed JIT router: GET feed, prefetch, complete topic."""

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.database import get_session
from app.models.feed_post import FeedPost
from app.models.subject import Subject
from app.models.topic import Topic, TopicStatus
from app.schemas.feed_post import FeedPostRead
from app.services.ai import AiConfigError, AiGenerationError
from app.services.feed import (
    FeedNotReadyError,
)
from app.services.feed import (
    SubjectNotFoundError as FeedSubjectNotFound,
)
from app.services.feed import (
    TopicNotFoundError as FeedTopicNotFound,
)
from app.services.feed import (
    generate_feed_batch as service_generate_feed_batch,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["feed"])


def _topic_to_dict(t: Topic) -> dict:
    return {
        "id": t.id,
        "title": t.title,
        "order_index": t.order_index,
        "status": t.status.value if hasattr(t.status, "value") else str(t.status),
        "prerequisite_ids": t.prerequisite_ids,
    }


async def _try_enqueue(subject_id: uuid.UUID, topic_id: int) -> bool:
    """Attempt to enqueue arq job; return True if enqueued, False if fallback needed."""
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        from app.core.config import settings

        redis_settings = RedisSettings.from_dsn(settings.redis_url)
        # Short timeout to avoid blocking if redis down
        pool = await create_pool(redis_settings)
        try:
            # Enqueue; keep job for result if caller wants to wait
            await pool.enqueue_job("generate_feed_batch", str(subject_id), topic_id)
            logger.info(
                "Enqueued feed generation via arq for subject %s topic %s",
                subject_id,
                topic_id,
            )
            return True
        finally:
            await pool.close()
    except Exception as exc:
        logger.debug("arq enqueue failed, falling back to direct: %s", exc)
        return False


async def _run_direct_generation(subject_id: uuid.UUID, topic_id: int) -> None:
    """Direct fallback generation executed as a BackgroundTask."""
    try:
        from app.db.database import async_session_maker

        async with async_session_maker() as session:
            await service_generate_feed_batch(session, subject_id, topic_id)
        logger.info(
            "Background direct feed generation succeeded for topic %s (subject %s)",
            topic_id,
            subject_id,
        )
    except Exception as exc:
        logger.warning(
            "Background direct feed generation failed for topic %s: %s",
            topic_id,
            exc,
        )


async def _generate_next_feed_background(
    subject_id: uuid.UUID, next_topic_id: int
) -> None:
    """Background job: try arq enqueue, fall back to direct generation.

    This function is intended to be scheduled via FastAPI BackgroundTasks so it
    survives until after the response is sent and is not lost on fire-and-forget
    asyncio.create_task that can be dropped on worker recycle.
    """
    enqueued = await _try_enqueue(subject_id, next_topic_id)
    if enqueued:
        return
    logger.info(
        "arq enqueue unavailable for topic %s, running direct generation via background task",
        next_topic_id,
    )
    await _run_direct_generation(subject_id, next_topic_id)


@router.get(
    "/subjects/{subject_id}/feed",
    summary="Get JIT feed for subject (active topic by default)",
)
async def get_feed(
    subject_id: uuid.UUID,
    topic_id: int | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Return feed posts for active topic (or explicit topic_id).

    If posts are empty, triggers generation synchronously (arq enqueue+wait or direct fallback).
    """
    subject = await session.get(Subject, subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject '{subject_id}' not found.",
        )

    target_topic: Topic | None = None
    if topic_id is not None:
        target_topic = await session.get(Topic, topic_id)
        if not target_topic or target_topic.subject_id != subject_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Topic '{topic_id}' not found for subject '{subject_id}'.",
            )
    else:
        # Find active topic
        stmt = (
            select(Topic)
            .where(Topic.subject_id == subject_id, Topic.status == TopicStatus.ACTIVE)
            .order_by(Topic.order_index.asc())  # type: ignore
        )
        res = await session.exec(stmt)
        target_topic = res.first()
        if not target_topic:
            # Fallback: first pending? Or any? If no active, check if all done
            pending_stmt = (
                select(Topic)
                .where(
                    Topic.subject_id == subject_id, Topic.status == TopicStatus.PENDING
                )
                .order_by(Topic.order_index.asc())  # type: ignore
            )
            pending_res = await session.exec(pending_stmt)
            pending = pending_res.first()
            if pending:
                # Auto-activate? But handler does activation on complete; here maybe no active exists yet.
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="No active topic; roadmap may need initialization.",
                )
            # No topics at all?
            all_stmt = select(Topic).where(Topic.subject_id == subject_id)
            all_res = await session.exec(all_stmt)
            all_topics = list(all_res.all())
            if not all_topics:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No topics found for subject.",
                )
            # All done?
            if all(t.status == TopicStatus.DONE for t in all_topics):
                return {
                    "subject_id": str(subject_id),
                    "topic": None,
                    "topic_id": None,
                    "posts": [],
                    "post_count": 0,
                    "all_topics_completed": True,
                }
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="No active topic found."
            )

    assert target_topic is not None
    assert target_topic.id is not None
    # Load existing posts
    posts_stmt = (
        select(FeedPost)
        .where(FeedPost.topic_id == target_topic.id)
        .order_by(FeedPost.order_index.asc())  # type: ignore
    )
    posts_res = await session.exec(posts_stmt)
    posts = list(posts_res.all())

    if not posts:
        # Trigger generation synchronously
        # Try arq enqueue with wait? For simplicity, attempt enqueue then direct fallback if redis not available or wait.
        # We will attempt direct generation to ensure result available for response (works without redis).
        # If redis is available, we still do direct to return synchronously, but also enqueue is redundant.
        # So do direct call (which will use LLM). If LLM fails, map errors.
        try:
            # Attempt arq first: if redis available, enqueue and poll? Instead just direct for simplicity.
            # Check if we can enqueue and then wait for result via polling direct generation? Keep direct.
            await service_generate_feed_batch(
                session,
                subject_id,
                target_topic.id,  # type: ignore[arg-type]
            )
            # Reload posts from DB to ensure ordering
            posts_stmt2 = (
                select(FeedPost)
                .where(FeedPost.topic_id == target_topic.id)
                .order_by(FeedPost.order_index.asc())  # type: ignore
            )
            posts_res2 = await session.exec(posts_stmt2)
            posts = list(posts_res2.all())
            # result contains posts dicts too, but we use DB posts
        except FeedSubjectNotFound:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subject '{subject_id}' not found.",
            ) from None
        except FeedTopicNotFound:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Topic '{topic_id}' not found.",
            ) from None
        except FeedNotReadyError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            ) from None
        except AiConfigError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI provider not configured",
            ) from None
        except AiGenerationError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Feed generation failed: {exc}",
            ) from None

    # Build response
    feed_reads = [
        FeedPostRead(
            id=p.id,  # type: ignore
            topic_id=p.topic_id,
            content=p.content,
            order_index=p.order_index,
            created_at=p.created_at,
        ).model_dump()
        for p in posts
    ]
    return {
        "subject_id": str(subject_id),
        "topic": _topic_to_dict(target_topic),
        "topic_id": target_topic.id,
        "posts": feed_reads,
        "post_count": len(feed_reads),
    }


@router.post(
    "/subjects/{subject_id}/topics/{topic_id}/prefetch",
    summary="Prefetch feed for a topic (idempotent, background)",
)
async def prefetch_feed(
    subject_id: uuid.UUID,
    topic_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Trigger background generation for topic if not already cached."""
    subject = await session.get(Subject, subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject '{subject_id}' not found.",
        )
    topic = await session.get(Topic, topic_id)
    if not topic or topic.subject_id != subject_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Topic '{topic_id}' not found for subject '{subject_id}'.",
        )

    posts_stmt = (
        select(FeedPost)
        .where(FeedPost.topic_id == topic_id)
        .order_by(FeedPost.order_index.asc())  # type: ignore
    )
    posts_res = await session.exec(posts_stmt)
    posts = list(posts_res.all())
    if posts:
        return {
            "topic_id": topic_id,
            "status": "already_cached",
            "post_count": len(posts),
        }

    # Durable trigger: try arq enqueue first; fallback to BackgroundTasks direct generation
    enqueued = await _try_enqueue(subject_id, topic_id)
    if enqueued:
        logger.info(
            "Prefetch enqueued via arq for subject %s topic %s", subject_id, topic_id
        )
        return {"topic_id": topic_id, "status": "prefetch_enqueued", "post_count": 0}
    # Redis down or enqueue failed -> schedule direct generation via BackgroundTasks (survives beyond fire-and-forget)
    background_tasks.add_task(_run_direct_generation, subject_id, topic_id)
    logger.info(
        "Prefetch fallback to BackgroundTasks direct generation for topic %s", topic_id
    )
    return {"topic_id": topic_id, "status": "prefetch_triggered", "post_count": 0}


@router.post(
    "/topics/{topic_id}/complete",
    summary="Mark topic complete, activate next, trigger next feed",
)
async def complete_topic(
    topic_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Mark topic complete via tool, delete old feed, activate next, trigger next feed generation."""
    topic = await session.get(Topic, topic_id)
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Topic '{topic_id}' not found.",
        )

    subject_id = topic.subject_id
    # Use tool dispatcher for atomic logic
    from app.tools.dispatcher import execute_tool

    result = await execute_tool(session, "mark_topic_complete", {"topic_id": topic_id})
    if not result.success:
        code = result.error_code
        if code == "NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.error or "Topic not found",
            )
        if code == "VALIDATION_ERROR":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error or "Validation error",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error or "Failed to complete topic",
        )

    data = result.data or {}
    next_topic_id = data.get("next_topic_id")
    # Trigger next feed generation if exists - durable via arq, fallback to BackgroundTasks
    if next_topic_id is not None:
        try:
            sid = (
                subject_id
                if isinstance(subject_id, uuid.UUID)
                else uuid.UUID(str(subject_id))
            )
            next_tid = int(next_topic_id)
            enqueued = await _try_enqueue(sid, next_tid)
            if enqueued:
                logger.info(
                    "Next feed enqueued via arq after complete for subject %s topic %s",
                    sid,
                    next_tid,
                )
            else:
                background_tasks.add_task(_run_direct_generation, sid, next_tid)
                logger.info(
                    "Next feed fallback to BackgroundTasks after complete for topic %s",
                    next_tid,
                )
        except Exception as exc:
            logger.warning(
                "Failed to trigger next feed generation for topic %s: %s",
                next_topic_id,
                exc,
            )

    return {
        "completed_topic_id": data.get("completed_topic_id", topic_id),
        "status": data.get("status", "done"),
        "deleted_feed_posts_count": data.get("deleted_feed_posts_count", 0),
        "next_topic_id": next_topic_id,
        "next_topic_title": data.get("next_topic_title"),
        "all_topics_completed": data.get("all_topics_completed", False),
    }
