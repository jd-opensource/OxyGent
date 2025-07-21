"""
Unit tests for JesEs (extends BaseEs -> BaseDatabase)
"""

import pytest
from unittest.mock import AsyncMock, patch

from oxygent.databases.db_es.jes_es import JesEs


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.indices.exists.return_value = False
    client.indices.create.return_value = {"acknowledged": True}
    client.index.return_value = {"result": "created"}
    client.update.return_value = {"result": "updated"}
    client.search.return_value = {"hits": {"total": {"value": 1}, "hits": []}}
    client.exists.return_value = True
    client.close.return_value = None
    return client


@pytest.fixture
def jes_es(monkeypatch, mock_client):
    # patch AsyncElasticsearch constructor to return mock_client
    with patch("oxygent.databases.db_es.jes_es.AsyncElasticsearch", return_value=mock_client):
        es = JesEs(hosts=["localhost:9200"], user="user", password="pass")
        yield es


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_create_index_new(jes_es, mock_client):
    body = {"mappings": {"properties": {"title": {"type": "text"}}}}
    res = await jes_es.create_index("new_index", body)
    assert res == {"acknowledged": True}
    mock_client.indices.create.assert_awaited_once_with(index="new_index", body=body)


@pytest.mark.asyncio
async def test_create_index_existing(jes_es, mock_client):
    mock_client.indices.exists.return_value = True
    body = {"mappings": {}}
    res = await jes_es.create_index("exist_index", body)
    assert res is None


@pytest.mark.asyncio
async def test_index_doc(jes_es, mock_client):
    res = await jes_es.index("idx", "1", {"field": "val"})
    assert res["result"] == "created"
    mock_client.index.assert_awaited_once_with(index="idx", id="1", body={"field": "val"})


@pytest.mark.asyncio
async def test_update_doc(jes_es, mock_client):
    res = await jes_es.update("idx", "1", {"field": "new"})
    assert res["result"] == "updated"
    mock_client.update.assert_awaited_once_with(index="idx", id="1", body={"doc": {"field": "new"}})


@pytest.mark.asyncio
async def test_search_doc(jes_es, mock_client):
    query = {"query": {"match_all": {}}}
    res = await jes_es.search("idx", query)
    assert "hits" in res
    mock_client.search.assert_awaited_once_with(index="idx", body=query)


@pytest.mark.asyncio
async def test_exists_doc(jes_es, mock_client):
    res = await jes_es.exists("idx", "1")
    assert res is True
    mock_client.exists.assert_awaited_once_with(index="idx", id="1")


@pytest.mark.asyncio
async def test_close_client(jes_es, mock_client):
    res = await jes_es.close()
    assert res is None
    mock_client.close.assert_awaited_once()
