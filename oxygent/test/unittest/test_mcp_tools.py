"""
Unit tests for MCPTool
"""

import pytest
from unittest.mock import AsyncMock

from oxygent.oxy.mcp_tools.mcp_tool import MCPTool
from oxygent.schemas import OxyRequest, OxyResponse, OxyState


# ──────────────────────────────────────────────────────────────────────────────
# ❶ Dummy MCP-Client
# ──────────────────────────────────────────────────────────────────────────────
class DummyMCPClient:
    def __init__(self):
        self._execute = AsyncMock()

    async def execute_ok(self, req):
        return OxyResponse(state=OxyState.COMPLETED, output="ok", oxy_request=req)


# ──────────────────────────────────────────────────────────────────────────────
# ❷ Fixtures
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def mcp_client():
    cli = DummyMCPClient()
    cli._execute.side_effect = cli.execute_ok        
    return cli


@pytest.fixture
def mcp_tool(mcp_client):
    return MCPTool(
        name="remote_tool",
        desc="UT MCP Tool",
        mcp_client=mcp_client,
        server_name="remote_server",
    )


@pytest.fixture
def oxy_request():
    return OxyRequest(
        arguments={"x": 1},
        caller="tester",
        caller_category="agent",
        current_trace_id="trace123",
    )


# ──────────────────────────────────────────────────────────────────────────────
# ❸ Tests
# ──────────────────────────────────────────────────────────────────────────────
def test_default_flags(mcp_tool):
    assert mcp_tool.is_permission_required is True
    assert mcp_tool.server_name == "remote_server"


@pytest.mark.asyncio
async def test_execute_delegates_to_client(mcp_tool, mcp_client, oxy_request):
    resp = await mcp_tool._execute(oxy_request)

    mcp_client._execute.assert_awaited_once_with(oxy_request)
    assert resp.state is OxyState.COMPLETED
    assert resp.output == "ok"


@pytest.mark.asyncio
async def test_execute_without_client_raises(oxy_request):
    bare_tool = MCPTool(name="bare", desc="no client")
    with pytest.raises(AttributeError):
        await bare_tool._execute(oxy_request)
