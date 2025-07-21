"""
Unit tests for BaseMCPClient
"""

import types
import pytest
from unittest.mock import AsyncMock

from oxygent.oxy.mcp_tools.base_mcp_client import BaseMCPClient
from oxygent.schemas import OxyRequest, OxyState
from oxygent.oxy.mcp_tools.mcp_tool import MCPTool


# ──────────────────────────────────────────────────────────────────────────────
# Dummy MAS
# ──────────────────────────────────────────────────────────────────────────────
class DummyMAS:
    def __init__(self):
        self.oxy_name_to_oxy = {}
        self.add_oxy_calls = []

    def add_oxy(self, oxy):
        self.oxy_name_to_oxy[oxy.name] = oxy
        self.add_oxy_calls.append(oxy.name)


# ──────────────────────────────────────────────────────────────────────────────
# Mock Objects (ClientSession / ToolResponse / Content)
# ──────────────────────────────────────────────────────────────────────────────
class MockContent:
    def __init__(self, text):
        self.text = text


class MockMCPToolInfo:
    def __init__(self, name):
        self.name = name
        self.description = f"{name}-desc"
        self.inputSchema = {}


class MockSession:
    def __init__(self):
        self.list_tools = AsyncMock(
            return_value=[("tools", [MockMCPToolInfo("dummy_tool")])]
        )
        self.call_tool = AsyncMock(
            return_value=types.SimpleNamespace(
                content=[MockContent("hello-world")]
            )
        )


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def mas_env():
    return DummyMAS()


@pytest.fixture
def client(mas_env):
    c = BaseMCPClient(name="remote_server", desc="UT MCP client")
    c.set_mas(mas_env)
    # 注入 MockSession
    c._session = MockSession()
    return c


@pytest.fixture
def oxy_request(mas_env):
    req = OxyRequest(
        arguments={},
        caller="tester",
        caller_category="agent",
        current_trace_id="trace123",
    )
    req.mas = mas_env
    return req


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_list_tools_registers_mcp_tools(client, mas_env):
    await client.list_tools()
    assert client.included_tool_name_list == ["dummy_tool"]
    assert isinstance(mas_env.oxy_name_to_oxy["dummy_tool"], MCPTool)
    assert mas_env.add_oxy_calls == ["dummy_tool"]


@pytest.mark.asyncio
async def test_execute_success(client, oxy_request):
    oxy_request.callee = "dummy_tool"
    resp = await client._execute(oxy_request)

    client._session.call_tool.assert_awaited_once_with("dummy_tool", {})
    assert resp.state is OxyState.COMPLETED
    assert resp.output == "hello-world"


@pytest.mark.asyncio
async def test_execute_without_session_raises(mas_env, oxy_request):
    c = BaseMCPClient(name="no_session", desc="bad")
    c.set_mas(mas_env)
    oxy_request.callee = "xxx"
    with pytest.raises(RuntimeError):
        await c._execute(oxy_request)


@pytest.mark.asyncio
async def test_cleanup_resets_session(client):
    client._stdio_context = object()
    await client.cleanup()
    assert client._session is None
    assert client._stdio_context is None
