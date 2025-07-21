"""
Unit tests for FunctionTool
"""

import pytest
from pydantic import Field

from oxygent.oxy.function_tools.function_tool import FunctionTool
from oxygent.schemas import OxyRequest, OxyState


# ──────────────────────────────────────────────────────────────────────────────
# ❶ Function
# ──────────────────────────────────────────────────────────────────────────────
async def add(
    a: int = Field(..., description="first"), b: int = Field(..., description="second")
):
    return a + b


async def explode():
    raise ValueError("boom")


# ──────────────────────────────────────────────────────────────────────────────
# ❷ Fixtures
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def add_tool():
    return FunctionTool(name="add_tool", desc="add two numbers", func_process=add)


@pytest.fixture
def error_tool():
    return FunctionTool(name="err_tool", desc="raise error", func_process=explode)


@pytest.fixture
def oxy_request():
    return OxyRequest(
        arguments={"a": 2, "b": 3},
        caller="tester",
        caller_category="agent",
        current_trace_id="trace123",
    )


# ──────────────────────────────────────────────────────────────────────────────
# ❸ Tests
# ──────────────────────────────────────────────────────────────────────────────
def test_input_schema(add_tool):
    schema = add_tool.input_schema
    assert schema["required"] == ["a", "b"]
    assert schema["properties"]["a"]["type"] == "int"
    assert schema["properties"]["a"]["description"] == "first"
    assert schema["properties"]["b"]["description"] == "second"


@pytest.mark.asyncio
async def test_execute_success(add_tool, oxy_request):
    resp = await add_tool._execute(oxy_request)
    assert resp.state is OxyState.COMPLETED
    assert resp.output == 5


@pytest.mark.asyncio
async def test_execute_failure(error_tool):
    req = OxyRequest(
        arguments={}, caller="tester", caller_category="agent", current_trace_id="id2"
    )
    resp = await error_tool._execute(req)
    assert resp.state is OxyState.FAILED
    assert "boom" in resp.output
