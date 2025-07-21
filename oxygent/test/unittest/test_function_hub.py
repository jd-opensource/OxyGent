"""
Unit tests for FunctionHub
"""

import asyncio
import pytest

from oxygent.oxy.function_tools.function_hub import FunctionHub
from oxygent.oxy.function_tools.function_tool import FunctionTool
from oxygent.schemas import OxyResponse, OxyState


# ────────────────────────────────────────────────────────────────────────────
# Dummy MAS
# ────────────────────────────────────────────────────────────────────────────
class DummyMAS:
    def __init__(self):
        self.oxy_name_to_oxy = {}

    def add_oxy(self, oxy):
        self.oxy_name_to_oxy[oxy.name] = oxy


# ────────────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def mas_env():
    return DummyMAS()


@pytest.fixture
def func_hub(mas_env):
    hub = FunctionHub(name="hub", desc="UT FunctionHub")
    hub.set_mas(mas_env)
    return hub


# ────────────────────────────────────────────────────────────────────────────
# Tests
# ────────────────────────────────────────────────────────────────────────────
def test_decorator_registers_functions(func_hub):
    @func_hub.tool("sync add")
    def add(a: int, b: int):
        return a + b

    @func_hub.tool("async mul")
    async def mul(a: int, b: int):
        return a * b

    assert "add" in func_hub.func_dict
    assert "mul" in func_hub.func_dict
    desc, async_fn = func_hub.func_dict["add"]
    assert asyncio.iscoroutinefunction(async_fn)
    assert desc == "sync add"


@pytest.mark.asyncio
async def test_init_converts_to_function_tools(func_hub, mas_env):
    @func_hub.tool("echo")
    def echo(msg: str):
        return msg

    await func_hub.init()

    assert "echo" in mas_env.oxy_name_to_oxy
    tool = mas_env.oxy_name_to_oxy["echo"]
    assert isinstance(tool, FunctionTool)
    assert tool.desc == "echo"
    from oxygent.schemas import OxyRequest
    oxy_req = OxyRequest(
        arguments={"msg": "hello"},
        caller="tester",
        caller_category="agent",
        current_trace_id="trace123",
    )

    resp: OxyResponse = await tool._execute(oxy_req)
    assert resp.state is OxyState.COMPLETED
    assert resp.output == "hello"


def test_sync_function_wrapped_async(func_hub):
    @func_hub.tool("inc")
    def inc(x: int):
        return x + 1

    _, async_inc = func_hub.func_dict["inc"]
    assert asyncio.iscoroutinefunction(async_inc)

    result = asyncio.run(async_inc(41))
    assert result == 42
