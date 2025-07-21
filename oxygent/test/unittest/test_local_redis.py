"""
Unit tests for LocalRedis
"""

import time
import pytest

from oxygent.databases.db_redis.local_redis import LocalRedis


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def redis():
    return LocalRedis()


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_lpush_basic(redis):
    n = await redis.lpush("mylist", "a", "b", "c")
    assert n == 3
    assert list(redis.data["mylist"]) == ["a", "b", "c"]
    assert "mylist" in redis.expiry


@pytest.mark.asyncio
async def test_lpush_types_and_max_length(redis):
    long_str = "x" * 1000
    truncated = long_str[:81920]
    n = await redis.lpush("k", long_str, 123, 4.56, {"k": "v"})
    assert n == 4
    items = list(redis.data["k"])
    assert items[0] == truncated
    assert items[1] == 123
    assert items[2] == 4.56
    assert items[3] == '{"k": "v"}'


@pytest.mark.asyncio
async def test_lpush_invalid_type(redis):
    with pytest.raises(ValueError):
        await redis.lpush("k", object())


@pytest.mark.asyncio
async def test_lpush_max_size(redis):
    await redis.lpush("l", "a", "b", "c", max_size=2)
    items = list(redis.data["l"])
    assert len(items) == 2


@pytest.mark.asyncio
async def test_rpop(redis):
    await redis.lpush("poplist", "x", "y")
    val1 = await redis.rpop("poplist")
    val2 = await redis.rpop("poplist")
    val3 = await redis.rpop("poplist")
    assert val1 == "y"
    assert val2 == "x"
    assert val3 is None


@pytest.mark.asyncio
async def test_expiry(redis):
    await redis.lpush("exp", "v", ex=1)
    assert "exp" in redis.data
    time.sleep(1.1)
    redis._check_expiry("exp")
    assert "exp" not in redis.data


@pytest.mark.asyncio
async def test_close(redis):
    assert await redis.close() is None
