"""
Unit tests for LocalRedis
"""

import time
import asyncio
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

@pytest.fixture
def redis():
    """Create a LocalRedis instance for each test."""
    return LocalRedis(yield_on_ops=True)


@pytest.mark.asyncio
async def test_zadd_new_members(redis):
    """Test adding new members to a sorted set."""
    result = await redis.zadd("myzset", {"one": 1, "two": 2, "three": 3})
    assert result == 3  # 3 new members added
    
    # Verify members are in correct order
    members = await redis.zrange("myzset", 0, -1)
    assert members == ["one", "two", "three"]


@pytest.mark.asyncio
async def test_zadd_update_existing_members(redis):
    """Test updating existing members in a sorted set."""
    # Add initial members
    await redis.zadd("myzset", {"one": 1, "two": 2, "three": 3})
    
    # Update a member's score
    result = await redis.zadd("myzset", {"two": 5})
    assert result == 0  # No new members added, only updated
    
    # Verify order is updated
    members = await redis.zrange("myzset", 0, -1)
    assert members == ["one", "three", "two"]


@pytest.mark.asyncio
async def test_zadd_with_withscores(redis):
    """Test zadd with scores returned."""
    await redis.zadd("myzset", {"a": 10.5, "b": 20.3, "c": 5.1})
    
    result = await redis.zrange("myzset", 0, -1, withscores=True)
    assert result == [("c", 5.1), ("a", 10.5), ("b", 20.3)]


@pytest.mark.asyncio
async def test_zrange_with_indices(redis):
    """Test zrange with different index ranges."""
    await redis.zadd("myzset", {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5})
    
    # Range from 0 to 2
    result = await redis.zrange("myzset", 0, 2)
    assert result == ["a", "b", "c"]
    
    # Range with negative indices
    result = await redis.zrange("myzset", -2, -1)
    assert result == ["d", "e"]
    
    # Single element
    result = await redis.zrange("myzset", 0, 0)
    assert result == ["a"]


@pytest.mark.asyncio
async def test_zrange_nonexistent_key(redis):
    """Test zrange on non-existent key returns empty list."""
    result = await redis.zrange("nonexistent", 0, -1)
    assert result == []


@pytest.mark.asyncio
async def test_zrem_single_member(redis):
    """Test removing a single member from sorted set."""
    await redis.zadd("myzset", {"a": 1, "b": 2, "c": 3})
    
    removed = await redis.zrem("myzset", "b")
    assert removed == 1
    
    members = await redis.zrange("myzset", 0, -1)
    assert members == ["a", "c"]


@pytest.mark.asyncio
async def test_zrem_multiple_members(redis):
    """Test removing multiple members from sorted set."""
    await redis.zadd("myzset", {"a": 1, "b": 2, "c": 3, "d": 4})
    
    removed = await redis.zrem("myzset", "b", "d")
    assert removed == 2
    
    members = await redis.zrange("myzset", 0, -1)
    assert members == ["a", "c"]


@pytest.mark.asyncio
async def test_zrem_nonexistent_member(redis):
    """Test removing non-existent member."""
    await redis.zadd("myzset", {"a": 1, "b": 2})
    
    removed = await redis.zrem("myzset", "nonexistent")
    assert removed == 0
    
    members = await redis.zrange("myzset", 0, -1)
    assert members == ["a", "b"]


@pytest.mark.asyncio
async def test_zrem_cleans_empty_set(redis):
    """Test that zrem removes empty sets from storage."""
    await redis.zadd("myzset", {"a": 1})
    
    await redis.zrem("myzset", "a")
    
    # Verify key is completely removed
    assert "myzset" not in redis.zsets
    assert "myzset" not in redis.expiry


@pytest.mark.asyncio
async def test_zincrby_existing_member(redis):
    """Test incrementing score of existing member."""
    await redis.zadd("myzset", {"a": 10, "b": 20, "c": 30})
    
    new_score = await redis.zincrby("myzset", 5, "b")
    assert new_score == 25
    
    # Verify order is updated: b's score changes from 20 to 25
    # So order should be a(10), b(25), c(30)
    members = await redis.zrange("myzset", 0, -1)
    assert members == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_zincrby_new_member(redis):
    """Test incrementing score of non-existent member (creates it)."""
    await redis.zadd("myzset", {"a": 10})
    
    new_score = await redis.zincrby("myzset", 15, "b")
    assert new_score == 15
    
    members = await redis.zrange("myzset", 0, -1)
    assert members == ["a", "b"]


@pytest.mark.asyncio
async def test_zincrby_negative_increment(redis):
    """Test decrementing score with negative increment."""
    await redis.zadd("myzset", {"a": 10, "b": 20, "c": 30})
    
    new_score = await redis.zincrby("myzset", -5, "b")
    assert new_score == 15
    
    members = await redis.zrange("myzset", 0, -1)
    assert members == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_zincrby_on_empty_set(redis):
    """Test zincrby on non-existent key creates the set."""
    new_score = await redis.zincrby("myzset", 42, "member")
    assert new_score == 42
    
    members = await redis.zrange("myzset", 0, -1, withscores=True)
    assert members == [("member", 42)]


@pytest.mark.asyncio
async def test_zincrby_maintains_order(redis):
    """Test that zincrby properly maintains sorted order."""
    await redis.zadd("myzset", {"a": 1, "b": 2, "c": 3, "d": 4})
    
    # Move 'a' to become the largest
    await redis.zincrby("myzset", 10, "a")
    
    members = await redis.zrange("myzset", 0, -1, withscores=True)
    assert members == [("b", 2), ("c", 3), ("d", 4), ("a", 11)]


@pytest.mark.asyncio
async def test_zincrby_multiple_operations(redis):
    """Test multiple zincrby operations in sequence."""
    await redis.zadd("myzset", {"a": 0, "b": 0})
    
    # Simulate API key pool: increment on task start, decrement on task end
    await redis.zincrby("myzset", 1, "a")  # a: 1, b: 0
    assert (await redis.zrange("myzset", 0, 0))[0] == "b"  # b is least loaded
    
    await redis.zincrby("myzset", 2, "b")  # a: 1, b: 2
    assert (await redis.zrange("myzset", 0, 0))[0] == "a"  # a is least loaded
    
    await redis.zincrby("myzset", -1, "a")  # a: 0, b: 2
    assert (await redis.zrange("myzset", 0, 0))[0] == "a"  # a is least loaded


@pytest.mark.asyncio
async def test_api_key_pool_simulation(redis):
    """Test a realistic API key pool load balancing scenario."""
    # Initialize pool with 3 API keys
    api_keys = {"key1", "key2", "key3"}
    await redis.zadd("api_pool", {key: 0 for key in api_keys})
    
    # Simulate task assignments
    # Get least loaded key
    least_loaded = (await redis.zrange("api_pool", 0, 0))[0]
    assert least_loaded in api_keys
    
    # Increment when task starts
    await redis.zincrby("api_pool", 1, least_loaded)
    
    # Get new least loaded key
    new_least = (await redis.zrange("api_pool", 0, 0))[0]
    assert new_least in api_keys
    assert new_least != least_loaded  # Should be different
    
    # Increment again
    await redis.zincrby("api_pool", 1, new_least)
    
    # Get state with scores
    state = await redis.zrange("api_pool", 0, -1, withscores=True)
    assert len(state) == 3
    
    # Verify scores are correct
    scores = {member: score for member, score in state}
    assert scores[least_loaded] == 1
    assert scores[new_least] == 1


@pytest.mark.asyncio
async def test_expiry_in_zadd(redis):
    """Test expiry setting in zadd."""
    import time
    
    await redis.zadd("myzset", {"a": 1}, ex=1)
    
    # Should exist
    members = await redis.zrange("myzset", 0, -1)
    assert len(members) == 1
    
    # Wait for expiry
    await asyncio.sleep(1.1)
    
    # Should be expired, get empty result
    members = await redis.zrange("myzset", 0, -1)
    assert len(members) == 0

@pytest.mark.asyncio
async def test_negative_scores(redis):
    """Test sorted set with negative scores."""
    await redis.zadd("myzset", {"a": -10, "b": 0, "c": 10, "d": -5})
    
    members = await redis.zrange("myzset", 0, -1, withscores=True)
    assert members == [("a", -10), ("d", -5), ("b", 0), ("c", 10)]


@pytest.mark.asyncio
async def test_float_scores(redis):
    """Test sorted set with floating point scores."""
    await redis.zadd("myzset", {
        "a": 1.5,
        "b": 2.7,
        "c": 1.2,
        "d": 3.1
    })
    
    members = await redis.zrange("myzset", 0, -1, withscores=True)
    assert members == [("c", 1.2), ("a", 1.5), ("b", 2.7), ("d", 3.1)]


@pytest.mark.asyncio
async def test_score_equality_update(redis):
    """Test that updating with same score doesn't change order."""
    await redis.zadd("myzset", {"a": 1, "b": 2, "c": 3})
    
    # Update 'b' with same score
    await redis.zadd("myzset", {"b": 2})
    
    members = await redis.zrange("myzset", 0, -1)
    assert members == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_large_sorted_set(redis):
    """Test performance with larger sorted set."""
    # Add 1000 members
    members_dict = {f"member_{i}": float(i) for i in range(1000)}
    added = await redis.zadd("large_set", members_dict)
    assert added == 1000
    
    # Get all members
    all_members = await redis.zrange("large_set", 0, -1)
    assert len(all_members) == 1000
    
    # Verify they're sorted
    for i, member in enumerate(all_members):
        assert member == f"member_{i}"
