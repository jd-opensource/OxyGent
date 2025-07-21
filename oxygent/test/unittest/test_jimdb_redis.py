"""
Unit tests for JimdbApRedis
"""

import pytest
from unittest.mock import AsyncMock, patch

from oxygent.databases.db_redis.jimdb_ap_redis import JimdbApRedis


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def redis_client(monkeypatch):
    """Create JimdbApRedis with mocked redis_pool."""
    with patch("oxygent.databases.db_redis.jimdb_ap_redis.Redis.from_url") as mock_from_url:
        mock_pool = AsyncMock()
        mock_from_url.return_value = mock_pool

        client = JimdbApRedis("localhost", 6379, "pass")
        client.redis_pool = mock_pool
        yield client


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_set_get_exists_delete(redis_client):
    r = redis_client.redis_pool
    r.set.return_value = True
    r.get.return_value = b"val"
    r.exists.return_value = 1
    r.delete.return_value = 1

    assert await redis_client.set("k", "v") is True
    assert await redis_client.get("k") == b"val"
    assert await redis_client.exists("k") == 1
    assert await redis_client.delete("k") == 1


@pytest.mark.asyncio
async def test_mset_mget(redis_client):
    r = redis_client.redis_pool
    r.mset.return_value = True
    r.mget.return_value = [b"a", b"b"]

    items = {"x": "1", "y": "2"}
    assert await redis_client.mset(items) is True
    assert await redis_client.mget(["x", "y"]) == [b"a", b"b"]


@pytest.mark.asyncio
async def test_expire(redis_client):
    r = redis_client.redis_pool
    r.expire.return_value = True

    assert await redis_client.expire("k", 10) is True


@pytest.mark.asyncio
async def test_lpush_and_rpop(redis_client):
    r = redis_client.redis_pool
    pipe = AsyncMock()
    pipe.__aenter__.return_value = pipe
    pipe.execute.return_value = [3]
    r.pipeline
