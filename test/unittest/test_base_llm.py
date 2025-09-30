"""
Unit tests for BaseLLM
"""

from unittest.mock import AsyncMock

import pytest

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
