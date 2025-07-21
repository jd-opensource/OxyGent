"""
Unit tests for BaseLLM
"""

import pytest
from unittest.mock import AsyncMock, patch

from oxygent.oxy.llms.base_llm import BaseLLM
from oxygent.schemas import OxyRequest, OxyResponse, OxyState


# ───────────────────────────────────────────────────────────────────────────────
# ❶ DummyLLM 
# ───────────────────────────────────────────────────────────────────────────────
class DummyLLM(BaseLLM):
    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        last_msg = oxy_request.arguments["messages"][-1]["content"]
        return OxyResponse(
            state=OxyState.COMPLETED,
            output=f"<think>internal</think>\n{last_msg}",
            oxy_request=oxy_request,
        )


# ───────────────────────────────────────────────────────────────────────────────
# ❷ Fixtures
# ───────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def llm():
    return DummyLLM(name="dummy_llm", desc="UT LLM")


@pytest.fixture
def oxy_request(monkeypatch):
    req = OxyRequest(
        arguments={
            "messages": [
                {"role": "system", "content": "You are tester."},
                {"role": "user", "content": "Hello"},
            ]
        },
        caller="user",
        caller_category="user",
        current_trace_id="trace123",
    )
    monkeypatch.setattr(
        "oxygent.schemas.oxy.OxyRequest.send_message",   
        AsyncMock(),
        raising=True,
    )
    return req


# ───────────────────────────────────────────────────────────────────────────────
# ❸ Tests
# ───────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_execute_and_think(llm, oxy_request):
    resp = await llm.execute(oxy_request)

    assert resp.state is OxyState.COMPLETED
    assert resp.output.endswith("Hello")

    oxy_request.send_message.assert_any_await({"type": "think", "content": "internal"})


@pytest.mark.asyncio
async def test_get_messages_url_to_base64(monkeypatch, llm, oxy_request):

    oxy_request.arguments["messages"] = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "see"},
                {"type": "image_url", "image_url": {"url": "http://x/a.png"}},
                {"type": "video_url", "video_url": {"url": "http://x/v.mp4"}},
            ],
        }
    ]

    llm.is_convert_url_to_base64 = True

    with patch("oxygent.oxy.llms.base_llm.image_to_base64", AsyncMock(return_value="img64")), \
         patch("oxygent.oxy.llms.base_llm.video_to_base64", AsyncMock(return_value="vid64")):

        msgs = await llm._get_messages(oxy_request)
        blob = msgs[0]["content"]

        assert blob[1]["image_url"]["url"] == "img64"
        assert blob[2]["video_url"]["url"] == "vid64"
