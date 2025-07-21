"""
Unit tests for oxygent.utils.common_utils
"""

import asyncio
import json
import hashlib

import pytest

import oxygent.utils.common_utils as cu


def test_chunk_list_and_timestamp():
    assert cu.chunk_list([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
    ts = float(cu.get_timestamp())
    assert ts > 0


def test_extract_json_functions():
    text = "```json\n{\"a\":1}\n```"
    assert cu.extract_first_json(text) == '{"a":1}'
    assert cu.extract_json_str("foo {\"x\":2}") == '{"x":2}'
    with pytest.raises(ValueError):
        cu.extract_json_str("no-json")


def test_url_helpers():
    assert cu.append_url_path("https://a.com/api", "/v1") == "https://a.com/api/v1"
    built = cu.build_url("https://a.com", "chat", {"q": "x", "q": ["y"]})  # noqa: F601
    assert built.startswith("https://a.com/chat")
    assert "q=y" in built


def test_filter_json_types_and_msgpack():
    res = cu.filter_json_types({"k": object()})
    assert res["k"] == "..."
    assert cu.msgpack_preprocess({"t": (1, 2)}) == {"t": [1, 2]}


def test_get_md5_and_to_json():
    s = "abc"
    assert cu.get_md5(s) == hashlib.md5(b"abc").hexdigest()
    assert cu.to_json({"x": 1}) == json.dumps({"x": 1}, ensure_ascii=False)


@pytest.fixture(autouse=True)
def patch_source_to_bytes(monkeypatch):
    monkeypatch.setattr(
        cu,
        "source_to_bytes",
        lambda src: asyncio.Future(),
        raising=True,
    )
    fut = cu.source_to_bytes(None)
    fut.set_result(b"\x89PNG\r\n\x1a\n")  
    yield





