"""Pytest fixtures for database session and test execution."""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import app.models  # noqa: F401 - ensure models are registered
from app.core.config import settings


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession]:
    """Provide an async database session for testing."""
    test_engine = create_async_engine(
        settings.async_database_url,
        echo=False,
        future=True,
    )
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    test_session_maker = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with test_session_maker() as sess:
        yield sess

    await test_engine.dispose()
