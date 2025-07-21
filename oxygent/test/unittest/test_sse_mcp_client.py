"""
Unit tests for SSEMCPClient
"""

import pytest
from unittest.mock import AsyncMock, patch

from oxygent.oxy.mcp_tools.sse_mcp_client import SSEMCPClient
from oxygent.schemas import OxyRequest, OxyResponse, OxyState


# ──────────────────────────────────────────────────────────────────────────────
# Dummy MAS
# ──────────────────────────────────────────────────────────────────────────────
class DummyMAS:
    def __init__(self):
        self.oxy_name_to_oxy = {}
        self.message_prefix = "msg"
        self.name = "test_mas"


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def mas_env():
    return DummyMAS()


@pytest.fixture
def sse_client_patch():
    """patch mcp.client.sse.sse_client 为 AsyncMock"""
    with patch("oxygent.oxy.mcp_tools.sse_mcp_client.sse_client") as mock_cli:
        # 返回一个 async context manager -> (read, write)
        def _acm(*args, **kwargs):
            class _Ctx:
                async def __aenter__(self_inner):
                    return ("read", "write")

                async def __aexit__(self_inner, exc_type, exc, tb):
                    return False

            return _Ctx()

        mock_cli.side_effect = _acm
        yield mock_cli


@pytest.fixture
def session_patch():
    """patch mcp.ClientSession"""
    with patch("oxygent.oxy.mcp_tools.sse_mcp_client.ClientSession") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session_cls.return_value = mock_session
        yield mock_session


@pytest.fixture
def client(mas_env, sse_client_patch, session_patch):
    c = SSEMCPClient(
        name="remote_server",
        desc="UT SSE MCP",
        server_url="https://foo.com/rpc",
        sse_url="https://foo.com/sse",
    )
    c.set_mas(mas_env)
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
async def test_init_success(client, session_patch):
    await client.init()
    assert client._session is session_patch

@pytest.mark.asyncio
async def test_execute_delegates_call(client, oxy_request, session_patch):
    await client.init()
    oxy_request.callee = "tool_x"

    resp: OxyResponse = await client._execute(oxy_request)

    session_patch.call_tool.assert_awaited_once_with("tool_x", {})
    assert resp.state is OxyState.COMPLETED


@pytest.mark.asyncio
async def test_init_failure_cleanup(mas_env, sse_client_patch):
    sse_client_patch.side_effect = RuntimeError("connect fail")
    bad = SSEMCPClient(
        name="bad_server",
        desc="err",
        server_url="https://x",
        sse_url="https://x/sse",
    )
    bad.set_mas(mas_env)

    with pytest.raises(Exception):
        await bad.init()
    assert bad._session is None
