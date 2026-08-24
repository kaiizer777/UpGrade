"""Redis connection factory and health checks using redis.asyncio."""

from collections.abc import AsyncGenerator

from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings

_redis_pool: ConnectionPool | None = None


def get_redis_pool() -> ConnectionPool:
    """Get or initialize singleton Redis connection pool."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
        )
    return _redis_pool


def get_redis_client() -> Redis:
    """Return an async Redis client instance configured with the connection pool."""
    pool = get_redis_pool()
    return Redis(connection_pool=pool)


async def get_redis() -> AsyncGenerator[Redis]:
    """FastAPI dependency yielding an async Redis client."""
    client = get_redis_client()
    try:
        yield client
    finally:
        await client.aclose()


async def check_redis_health() -> bool:
    """Perform health check ping against Redis.

    Returns True if Redis is reachable and responds to PING, False otherwise.
    """
    try:
        client = get_redis_client()
        result = await client.ping()
        return bool(result)
    except Exception:
        return False


async def close_redis() -> None:
    """Close the global Redis connection pool on application shutdown."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None
