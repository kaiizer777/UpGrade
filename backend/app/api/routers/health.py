"""Health check router."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Health check")
async def health_check() -> dict[str, str]:
    """Return service health status."""
    return {"status": "ok"}


@router.get("/healthz", summary="Health check (k8s alias)", include_in_schema=False)
async def healthz() -> dict[str, str]:
    """Kubernetes-style alias."""
    return {"status": "ok"}
