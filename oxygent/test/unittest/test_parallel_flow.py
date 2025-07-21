"""
Unit tests for ParallelFlow
"""

import pytest
from unittest.mock import AsyncMock

from oxygent.oxy.flows.parallel_flow import ParallelFlow
from oxygent.schemas import OxyRequest, OxyResponse, OxyState


# ──────────────────────────────────────────────────────────────────────────────
# Dummy MAS  
# ──────────────────────────────────────────────────────────────────────────────
class DummyMAS:
    def __init__(self):
        self.oxy_name_to_oxy = {}
        self.background_tasks = set()
        self.message_prefix = "msg"
        self.name = "test_mas"
        self.send_message = AsyncMock()


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def mas_env():
    return DummyMAS()


@pytest.fixture
def flow(mas_env):
    f = ParallelFlow(name="pflow", desc="UT Parallel Flow")
    f.set_mas(mas_env)
    f.add_permitted_tools(["tool_a", "tool_b"])
    return f


@pytest.fixture
def oxy_request(monkeypatch, mas_env):
    req = OxyRequest(
        arguments={"query": "hello"},
        caller="tester",
        caller_category="agent",
        current_trace_id="trace123",
    )
    req.mas = mas_env

    async def _fake_call(self, *, callee: str, arguments: dict, **kwargs):
        return OxyResponse(
            state=OxyState.COMPLETED,
            output=f"{callee}-ok",
            oxy_request=self,
        )

    monkeypatch.setattr("oxygent.schemas.OxyRequest.call", _fake_call, raising=True)
    return req


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_execute_aggregates_outputs(flow, oxy_request):
    resp = await flow.execute(oxy_request)

    assert resp.state is OxyState.COMPLETED
    assert "tool_a-ok" in resp.output and "tool_b-ok" in resp.output
    assert resp.oxy_request.call_stack[-1] == "pflow"


@pytest.mark.asyncio
async def test_execute_no_tools(monkeypatch, mas_env, oxy_request):
    empty_flow = ParallelFlow(name="empty", desc="no tools")
    empty_flow.set_mas(mas_env)

    call_spy = AsyncMock()
    monkeypatch.setattr("oxygent.schemas.OxyRequest.call", call_spy, raising=True)

    resp = await empty_flow.execute(oxy_request)
    call_spy.assert_not_awaited()
    assert resp.state is OxyState.COMPLETED
    assert resp.output.endswith(":") 
