"""
Unit tests for EmbeddingCache & get_embedding
"""

import base64
import json
import numpy as np
import pytest
from unittest.mock import AsyncMock, patch

import oxygent.embedding_cache as ec


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def cache(tmp_path, monkeypatch):
    """Use tmp_path to isolate .pkl files"""
    # patch Config.get_cache_save_dir to tmp_path
    monkeypatch.setattr("oxygent.embedding_cache.Config.get_cache_save_dir", lambda: str(tmp_path))
    c = ec.EmbeddingCache(save_batch=2)  # small batch for testing
    yield c
    c.save()  # ensure persistence


# ──────────────────────────────────────────────────────────────────────────────
# Tests for EmbeddingCache class
# ──────────────────────────────────────────────────────────────────────────────
def test_md5_and_set_get(cache):
    """Basic MD5, set, is_in behaviour"""
    key = "hello"
    vec = np.array([1, 2, 3])

    md5 = cache.get_md5(key)
    assert isinstance(md5, str) and len(md5) == 32

    assert not cache.is_in(key)
    cache.set(key, vec)
    assert cache.is_in(key)
    # Internal data uses md5 keys
    assert (cache.data[md5] == vec).all()


def test_save_and_load(cache):
    """save() writes pickle, load() restores"""
    key = "persist"
    vec = np.array([9, 9, 9])
    cache.set(key, vec)
    cache.save()

    # Create new cache instance pointing to same file
    c2 = ec.EmbeddingCache()
    assert c2.is_in(key)
    md5 = c2.get_md5(key)
    assert (c2.data[md5] == vec).all()



@pytest.mark.asyncio
async def test_get_batch_mixed(monkeypatch, cache):
    """get batch with some keys cached, others not"""

    # Pre-cache one key
    cache.set("cached", np.array([1, 0, 0]))

    async def fake_embed(texts):
        return [np.array([0.5] * 3) for _ in texts]

    monkeypatch.setattr(ec, "get_embedding", fake_embed)

    keys = ["cached", "uncached1", "uncached2"]
    arr = await cache.get(keys)
    assert arr.shape == (3, 3)
    assert (arr[0] == np.array([1, 0, 0])).all()


# ──────────────────────────────────────────────────────────────────────────────
# Tests for get_embedding function
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_get_embedding_success(monkeypatch):
    """Mock httpx post to return base64 encoded array"""

    class FakeResponse:
        def json(self):
            arr = np.array([[1.0, 2.0, 3.0]])
            b64 = base64.b64encode(json.dumps(arr.tolist()).encode()).decode()
            return {"outputs": [{"data": [b64]}]}

    # patch Config.get_vearch_embedding_model_url
    monkeypatch.setattr("oxygent.embedding_cache.Config.get_vearch_embedding_model_url",
                        lambda: "http://fake_url")

    with patch("oxygent.embedding_cache.httpx.AsyncClient") as client_cls:
        client = client_cls.return_value.__aenter__.return_value
        client.post = AsyncMock(return_value=FakeResponse())

        result = await ec.get_embedding(["hello"])
        assert isinstance(result, np.ndarray)
        assert result.shape[1] == 3  # embedding_dim


@pytest.mark.asyncio
async def test_get_embedding_invalid_input():
    """Passing non-list raises error (prints message and returns None)"""
    result = await ec.get_embedding("not_a_list")
    assert result is None
