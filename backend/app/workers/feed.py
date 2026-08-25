"""arq worker for JIT feed generation."""

import logging
import uuid

from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.db.database import ASYNC_DATABASE_URL
from app.services.feed import generate_feed_batch as service_generate_feed_batch

logger = logging.getLogger(__name__)

# arq expects RedisSettings
redis_settings = RedisSettings.from_dsn(settings.redis_url)


async def generate_feed_batch(ctx: dict, subject_id: str, topic_id: int) -> dict:
    """arq job: generate feed for topic.

    Args:
        ctx: arq context (contains redis).
        subject_id: UUID string of the subject.
        topic_id: integer topic ID.

    Returns:
        dict with topic_id, post_count, posts.
    """
    logger.info(
        "arq generate_feed_batch start subject=%s topic=%s", subject_id, topic_id
    )
    try:
        subject_uuid = uuid.UUID(str(subject_id))
    except Exception as exc:
        logger.error("Invalid subject_id %s: %s", subject_id, exc)
        return {"error": f"Invalid subject_id: {subject_id}", "topic_id": topic_id}

    # Create ephemeral engine/session for worker (isolated from web process)
    engine = create_async_engine(ASYNC_DATABASE_URL, echo=False, future=True)
    session_maker = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    try:
        async with session_maker() as session:
            result = await service_generate_feed_batch(session, subject_uuid, topic_id)
            logger.info(
                "arq generate_feed_batch done topic=%s posts=%s",
                topic_id,
                result.get("post_count"),
            )
            return result
    except Exception as exc:
        logger.exception("arq generate_feed_batch failed topic=%s: %s", topic_id, exc)
        # Re-raise so arq can retry according to its retry mechanism
        raise
    finally:
        await engine.dispose()


# Allow arq to retry failures with exponential backoff (max 3 tries)
# arq retry is configured via function retry logic; we set max_tries via WorkerSettings
class WorkerSettings:
    """arq worker settings."""

    redis_settings = redis_settings
    functions = [generate_feed_batch]
    max_tries = 3
    # Allow health checks
    health_check_interval = 3600
    job_timeout = 120
