"""
Unit tests for RemoteAgent
"""

import pytest
from pydantic import ValidationError

from oxygent.oxy.agents.remote_agent import RemoteAgent
from oxygent.schemas import OxyRequest, OxyResponse, OxyState


# ──────────────────────────────────────────────────────────────────────────────
# ❶ Dummy 
# ──────────────────────────────────────────────────────────────────────────────
class DummyRemoteAgent(RemoteAgent):
    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        return OxyResponse(
            state=OxyState.COMPLETED,
            output=f"pong({oxy_request.arguments.get('query')})",
            oxy_request=oxy_request,
        )


# ──────────────────────────────────────────────────────────────────────────────
# ❷ Fixtures
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def dummy_agent():
    org_tree = {
        "id": 0,
        "name": "root",
        "children": [
            {"id": 1, "name": "dep1", "children": []},
            {"id": 2, "name": "dep2", "children": []},
        ],
    }
    return DummyRemoteAgent(
        name="remote_dummy",
        desc="UT Remote Agent",
        server_url="https://example.com/api",
        org=org_tree,
    )


@pytest.fixture
def oxy_request():
    return OxyRequest(
        arguments={"query": "ping"},
        caller="user",
        caller_category="user",
        current_trace_id="trace123",
    )


# ──────────────────────────────────────────────────────────────────────────────
# ❸ Tests
# ──────────────────────────────────────────────────────────────────────────────
def test_server_url_validation():
    """不合法协议应触发 ValidationError"""
    with pytest.raises(ValidationError):
        DummyRemoteAgent(
            name="bad_remote",
            desc="bad",
            server_url="ftp://foo.com",  
        )


def test_get_org_returns_marked_copy(dummy_agent):
    """get_org 应深拷贝并标记 is_remote=True"""
    org_copy = dummy_agent.get_org()

    assert all(node["is_remote"] for node in org_copy)

    org_copy[0]["name"] = "changed"
    assert dummy_agent.org["children"][0]["name"] == "dep1"


@pytest.mark.asyncio
async def test_execute_lifecycle(dummy_agent, oxy_request):
    resp = await dummy_agent.execute(oxy_request)

    assert resp.state == OxyState.COMPLETED
    assert resp.output == "pong(ping)"
    assert resp.oxy_request.call_stack[-1] == "remote_dummy"
