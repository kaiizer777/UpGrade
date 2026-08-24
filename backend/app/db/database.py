"""Database connection placeholder.

Replace with SQLAlchemy async engine / SQLModel when a real DB is added.

Example:
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.core.config import settings

    engine = create_async_engine(settings.database_url, echo=False)
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
"""

from app.core.config import settings

# Placeholder - no active connection yet
DATABASE_URL: str = settings.database_url


def get_database_url() -> str:
    """Return the configured database URL."""
    return DATABASE_URL
