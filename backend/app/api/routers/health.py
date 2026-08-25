"""Health check router."""

import logging

from fastapi import APIRouter

from app.core.analytics import get_counters_snapshot

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", summary="Health check")
async def health_check() -> dict[str, str]:
    """Return service health status."""
    return {"status": "ok"}


@router.get("/healthz", summary="Health check (k8s alias)", include_in_schema=False)
async def healthz() -> dict[str, str]:
    """Kubernetes-style alias."""
    return {"status": "ok"}


@router.get("/ready", summary="Readiness probe (DB + Redis)")
async def readiness() -> dict:
    """Readiness probe: checks DB and Redis connectivity plus analytics counters."""
    db_ok = False
    redis_ok = False
    db_error: str | None = None
    redis_error: str | None = None
    try:
        from sqlalchemy import text

        from app.db.database import engine

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        db_error = str(exc)[:200]
        logger.warning("Readiness DB check failed: %s", exc)
    try:
        from app.db.redis import check_redis_health

        redis_ok = await check_redis_health()
        if not redis_ok:
            redis_error = "ping failed"
    except Exception as exc:
        redis_error = str(exc)[:200]
        logger.warning("Readiness Redis check failed: %s", exc)

    # Ready if DB is ok; Redis is optional (fallback exists) but reported
    ready = db_ok
    counters = get_counters_snapshot()
    return {
        "ready": ready,
        "db": {"ok": db_ok, "error": db_error},
        "redis": {"ok": redis_ok, "error": redis_error},
        "analytics": counters,
    }
