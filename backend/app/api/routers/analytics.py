"""Analytics and monitoring router."""

from fastapi import APIRouter

from app.core.analytics import get_counters_snapshot

router = APIRouter(prefix="/admin", tags=["analytics"])


@router.get("/stats", summary="Get system analytics and tool metrics")
async def get_stats() -> dict[str, object]:
    """Return aggregated tool success/failure counts, error breakdown, and latencies."""
    return get_counters_snapshot()
