"""
Unit tests for BaseFlow
"""

import pytest

from oxygent.oxy.base_flow import BaseFlow
from oxygent.schemas import OxyRequest, OxyResponse, OxyState


# ──────────────────────────────────────────────────────────────────────────────
# ❶ Dummy Flow
# ──────────────────────────────────────────────────────────────────────────────
class DummyFlow(BaseFlow):
    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        return OxyResponse(
            state=OxyState.COMPLETED,
            output=oxy_request.arguments.get("query", ""),
            oxy_request=oxy_request,
        )


# ──────────────────────────────────────────────────────────────────────────────
# ❷ Fixtures
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def dummy_flow():
    return DummyFlow(name="dummy_flow", desc="Unit-Test Flow")


@pytest.fixture
def oxy_request():
    return OxyRequest(
        arguments={"query": "hello"},
        caller="user",
        caller_category="user",
        current_trace_id="trace123",
    )


# ──────────────────────────────────────────────────────────────────────────────
# ❸ Tests
# ──────────────────────────────────────────────────────────────────────────────
def test_initialization(dummy_flow):
    assert dummy_flow.is_permission_required is True
    assert dummy_flow.name == "dummy_flow"


@pytest.mark.asyncio
async def test_execute_lifecycle(dummy_flow, oxy_request):
    resp = await dummy_flow.execute(oxy_request)

    assert isinstance(resp, OxyResponse)
    assert resp.state is OxyState.COMPLETED
    assert resp.output == "hello"
    assert resp.oxy_request.call_stack[-1] == "dummy_flow"
