"""FastAPI application entrypoint - lifespan pattern (2026)."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers.chat import router as chat_router
from app.api.routers.feed import router as feed_router
from app.api.routers.health import router as health_router
from app.api.routers.roadmap import router as roadmap_router
from app.api.routers.subjects import router as subjects_router
from app.core.config import settings
from app.db.redis import close_redis


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan - replaces deprecated on_event handlers."""
    # Startup
    print(f"Starting {settings.app_name} in '{settings.env}' mode")
    yield
    # Shutdown
    print("Shutting down...")
    await close_redis()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="UpGrade backend API",
    lifespan=lifespan,
)

# CORS - permissive for development, restrict in production via env
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health_router)
app.include_router(subjects_router)
app.include_router(roadmap_router)
app.include_router(feed_router)
app.include_router(chat_router)


@app.get("/", tags=["root"], summary="Root")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": f"Welcome to {settings.app_name}", "env": settings.env}
