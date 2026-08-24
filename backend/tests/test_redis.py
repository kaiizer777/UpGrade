"""Redis client and health check unit tests."""

from unittest.mock import AsyncMock, patch

import pytest
from redis.asyncio import ConnectionPool, Redis

from app.db.redis import (
    check_redis_health,
    close_redis,
    get_redis,
    get_redis_client,
    get_redis_pool,
)


@pytest.mark.asyncio
async def test_get_redis_pool() -> None:
    """get_redis_pool should return a ConnectionPool instance."""
    pool = get_redis_pool()
    assert isinstance(pool, ConnectionPool)


@pytest.mark.asyncio
async def test_get_redis_client() -> None:
    """get_redis_client should return a Redis client."""
    client = get_redis_client()
    assert isinstance(client, Redis)


@pytest.mark.asyncio
async def test_get_redis_dependency() -> None:
    """get_redis generator should yield a Redis client and close it."""
    gen = get_redis()
    client = await anext(gen)
    assert isinstance(client, Redis)
    # Complete generator
    try:
        await anext(gen)
    except StopAsyncIteration:
        pass


@pytest.mark.asyncio
async def test_check_redis_health_success() -> None:
    """check_redis_health should return True when ping succeeds."""
    with patch("app.db.redis.get_redis_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.ping.return_value = True
        mock_get_client.return_value = mock_client

        healthy = await check_redis_health()
        assert healthy is True
        mock_client.ping.assert_awaited_once()


@pytest.mark.asyncio
async def test_check_redis_health_failure() -> None:
    """check_redis_health should return False when ping raises an exception."""
    with patch("app.db.redis.get_redis_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.ping.side_effect = ConnectionError("Connection refused")
        mock_get_client.return_value = mock_client

        healthy = await check_redis_health()
        assert healthy is False


@pytest.mark.asyncio
async def test_close_redis() -> None:
    """close_redis should close and reset the connection pool."""
    get_redis_pool()
    await close_redis()
