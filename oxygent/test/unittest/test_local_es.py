"""
Unit tests for LocalEs
"""

import os
import shutil
import pytest
from oxygent.databases.db_es.local_es import LocalEs


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def local_es(tmp_path, monkeypatch):
    """Use tmp_path as isolated data_dir for tests."""
    monkeypatch.setattr("oxygent.databases.db_es.local_es.Config.get_cache_save_dir", lambda: str(tmp_path))
    es = LocalEs()
    yield es
    shutil.rmtree(tmp_path)  # clean up


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_create_index(local_es):
    body = {"mappings": {"properties": {"f": {"type": "text"}}}}
    res = await local_es.create_index("testidx", body)
    assert res == {"acknowledged": True}
    assert os.path.exists(os.path.join(local_es.data_dir, "testidx_mapping.json"))
    assert os.path.exists(os.path.join(local_es.data_dir, "testidx.json"))


@pytest.mark.asyncio
async def test_index_update_exists(local_es):
    # index
    await local_es.create_index("idx", {"mappings": {}})
    r1 = await local_es.index("idx", "1", {"v": 10})
    assert r1["result"] == "created"

    # update
    r2 = await local_es.update("idx", "1", {"v": 20, "x": 5})
    assert r2["result"] == "updated"

    # exists
    exists = await local_es.exists("idx", "1")
    assert exists is True

    not_exist = await local_es.exists("idx", "999")
    assert not not_exist


@pytest.mark.asyncio
async def test_search_term_terms_bool_sort(local_es):
    await local_es.create_index("idx", {"mappings": {}})
    await local_es.index("idx", "a", {"k": "v1", "n": 2})
    await local_es.index("idx", "b", {"k": "v2", "n": 1})
    await local_es.index("idx", "c", {"k": "v2", "n": 3})

    # term query
    q1 = {"query": {"term": {"k": "v1"}}}
    res1 = await local_es.search("idx", q1)
    assert len(res1["hits"]["hits"]) == 1

    # terms query
    q2 = {"query": {"terms": {"k": ["v2"]}}}
    res2 = await local_es.search("idx", q2)
    assert len(res2["hits"]["hits"]) == 2

    # bool.must query
    q3 = {"query": {"bool": {"must": [{"term": {"k": "v2"}}, {"term": {"n": 3}}]}}}
    res3 = await local_es.search("idx", q3)
    assert len(res3["hits"]["hits"]) == 1
    assert res3["hits"]["hits"][0]["_id"] == "c"

    # sort desc
    q4 = {"sort": [{"n": {"order": "desc"}}]}
    res4 = await local_es.search("idx", q4)
    hits = res4["hits"]["hits"]
    assert hits[0]["_source"]["n"] == 3


@pytest.mark.asyncio
async def test_close(local_es):
    res = await local_es.close()
    assert res is True
