"""
Unit tests for StdioMCPClient
"""

import types
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from oxygent.oxy.mcp_tools.stdio_mcp_client import StdioMCPClient
from oxygent.schemas import OxyRequest, OxyResponse, OxyState


# ──────────────────────────────────────────────────────────────────────────────
# Dummy MAS
# ──────────────────────────────────────────────────────────────────────────────
class DummyMAS:
    def __init__(self):
        self.oxy_name_to_oxy = {}
        self.message_prefix = "msg"
        self.name = "test_mas"
        self.add_oxy = MagicMock()


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def mas_env():
    return DummyMAS()


@pytest.fixture
def session_patch():
    """patch mcp.ClientSession"""
    with patch("oxygent.oxy.mcp_tools.stdio_mcp_client.ClientSession") as cls:
        sess = AsyncMock()
        sess.initialize = AsyncMock()
        sess.list_tools.return_value = [
            (
                "tools",
                [
                    types.SimpleNamespace(
                        name="stdio_tool",
                        description="desc",
                        inputSchema={},
                    )
                ],
            )
        ]
        sess.call_tool.return_value = types.SimpleNamespace(
            content=[types.SimpleNamespace(text="pong")]
        )
        sess.__aenter__.return_value = sess
        cls.return_value = sess
        yield sess


@pytest.fixture
def stdio_patch():
    with patch("oxygent.oxy.mcp_tools.stdio_mcp_client.stdio_client") as stdio_cli:

        class _Ctx:
            async def __aenter__(self):
                return ("read", "write")

            async def __aexit__(self, exc_type, exc, tb):
                return False

        def acm(*args, **kwargs):
            return _Ctx()

        stdio_cli.side_effect = acm
        yield stdio_cli


@pytest.fixture
def which_patch():
    """shutil.which('npx') → '/usr/bin/npx'"""
    with patch("oxygent.oxy.mcp_tools.stdio_mcp_client.shutil.which", return_value="/usr/bin/npx"):
        yield


@pytest.fixture
def stdio_client(mas_env, stdio_patch, session_patch, which_patch):
    client = StdioMCPClient(
        name="stdio_server",
        desc="UT Stdio MCP",
        params={
            "command": "npx",
            "args": ["--directory", "/tmp", "run", "index.js"],
            "env": {},
        },
    )
    client.set_mas(mas_env)
    return client


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
async def test_init_registers_tools(stdio_client, session_patch):
    with patch("oxygent.oxy.mcp_tools.stdio_mcp_client.os.path.exists", return_value=True):
        await stdio_client.init()

    assert stdio_client._session is session_patch
    assert "stdio_tool" in stdio_client.included_tool_name_list


@pytest.mark.asyncio
async def test_execute_success(stdio_client, session_patch, oxy_request):
    with patch("oxygent.oxy.mcp_tools.stdio_mcp_client.os.path.exists", return_value=True):
        await stdio_client.init()

    oxy_request.callee = "stdio_tool"
    resp: OxyResponse = await stdio_client._execute(oxy_request)

    session_patch.call_tool.assert_awaited_once_with("stdio_tool", {})
    assert resp.state is OxyState.COMPLETED
    assert resp.output == "pong"


@pytest.mark.asyncio
async def test_init_missing_file_raises(which_patch, mas_env):
    bad = StdioMCPClient(
        name="bad",
        desc="err",
        params={
            "command": "npx",
            "args": ["--directory", "/not/exist", "run", "main.js"],
            "env": {},
        },
    )
    bad.set_mas(mas_env)

    with patch("oxygent.oxy.mcp_tools.stdio_mcp_client.os.path.exists", return_value=False):
        with pytest.raises(FileNotFoundError):
            await bad.init()
