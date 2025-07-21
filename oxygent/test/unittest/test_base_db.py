"""
Unit tests for BaseDB
"""

import pytest

from oxygent.databases.base_db import BaseDB


# ──────────────────────────────────────────────────────────────────────────────
# Dummy subclass for testing
# ──────────────────────────────────────────────────────────────────────────────
class MyDB(BaseDB):
    def __init__(self):
        self.count = 0

    async def succeed(self):
        """Always succeed and increment count."""
        self.count += 1
        return "ok"

    async def fail_once_then_succeed(self):
        """Fail the first time, succeed the second time."""
        self.count += 1
        if self.count == 1:
            raise ValueError("fail")
        return "recovered"

    async def always_fail(self):
        """Always raise exception."""
        self.count += 1
        raise RuntimeError("fail")


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_try_decorator_direct():

    calls = {"n": 0}

    @BaseDB.try_decorator(max_retries=3, delay_between_retries=0.01)
    async def sometimes_fail():
        calls["n"] += 1
        if calls["n"] < 2:
            raise Exception("fail")
        return "success"

    result = await sometimes_fail()
    assert result == "success"
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_initsubclass_applies_decorator():
    db = MyDB()

    # succeed should work and increment count once
    out = await db.succeed()
    assert out == "ok"
    assert db.count == 1

    # fail_once_then_succeed should retry and eventually succeed
    result = await db.fail_once_then_succeed()
    assert result == "recovered"
    assert db.count == 2  

    # always_fail should retry default (1 attempt) and return None
    res = await db.always_fail()
    assert res is None
    assert db.count == 3


@pytest.mark.asyncio
async def test_retry_limit_respected():
    calls = {"n": 0}

    @BaseDB.try_decorator(max_retries=2, delay_between_retries=0.01)
    async def fail_twice():
        calls["n"] += 1
        raise Exception("fail")

    result = await fail_twice()
    assert result is None
    assert calls["n"] == 2
