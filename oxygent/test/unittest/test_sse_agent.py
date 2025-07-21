"""
Unit tests for SSEOxyAgent
"""

import json
import pytest
import respx
from aioresponses import aioresponses
from pydantic import ValidationError
import httpx
from unittest.mock import AsyncMock

from oxygent.oxy.agents.sse_oxy_agent import SSEOxyGent
from oxygent.schemas import OxyRequest, OxyState


# ──────────────────────────────────────────────────────────────────────────────
# Dummy MAS 
# ──────────────────────────────────────────────────────────────────────────────
class DummyMAS:
    def __init__(self):
        self.oxy_name_to_oxy = {}
        self.message_prefix = "msg"
        self.name = "test_mas"
        self.background_tasks = set()
        self.send_message = AsyncMock()
        


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def sse_agent():
    return SSEOxyGent(
        name="sse_agent",
        desc="UT SSE Agent",
        server_url="https://remote-mas.example.com",
    )


@pytest.fixture
def oxy_request():
    req = OxyRequest(
        arguments={"query": "ping"},
        caller="user",
        caller_category="user",
        current_trace_id="trace123",
    )
    req.mas = DummyMAS()
    return req


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────
def test_url_validation():
    with pytest.raises(ValidationError):
        SSEOxyGent(name="bad", desc="bad", server_url="ftp://foo.com")


@pytest.mark.asyncio
async def test_init_fetch_org(sse_agent):
    """init() 会调用 httpx GET /get_organization 并填充 .org"""
    with respx.mock(assert_all_called=True) as router:
        router.get(
            httpx.URL("https://remote-mas.example.com/get_organization")
        ).mock(
            return_value=httpx.Response(
                200,
                json={"data": {"organization": [{"id": 1, "is_remote": False}]}},
            )
        )
        await sse_agent.init()
        assert sse_agent.org[0]["id"] == 1
        assert sse_agent.org[0]["is_remote"] is False


@pytest.mark.asyncio
async def test_execute_sse_flow(sse_agent, oxy_request):
    with respx.mock() as router:
        router.get(
            httpx.URL("https://remote-mas.example.com/get_organization")
        ).mock(
            return_value=httpx.Response(
                200, json={"data": {"organization": []}}
            )
        )
        await sse_agent.init()

    sse_payloads = [
        {"type": "tool_call", "content": {"caller_category": "agent", "callee_category": "agent"}},
        {"type": "observation", "content": {"caller_category": "agent", "callee_category": "agent"}},
        {"type": "answer", "content": "pong"},
    ]
    
    sse_bytes = b"".join(
        f"data: {json.dumps(evt)}\n\n".encode()
        for evt in sse_payloads
    ) + b"data: done\n\n"

    with aioresponses() as mocked_aio:
        mocked_aio.post(
            "https://remote-mas.example.com/sse/chat",
            status=200,
            body=sse_bytes,                       
            headers={"Content-Type": "text/event-stream"},
        )
        resp = await sse_agent.execute(oxy_request)

        assert resp.state is OxyState.COMPLETED
        assert resp.output == "pong"
