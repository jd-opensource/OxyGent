"""
Unit tests for OxyRequest & OxyResponse
"""

import asyncio
import pytest

from oxygent.schemas.oxy import (
    OxyRequest,
    OxyResponse,
    OxyState,
)


# ──────────────────────────────────────────────────────────────────────────────
# ❶ Dummy MAS / Oxy
# ──────────────────────────────────────────────────────────────────────────────
class DummyMAS:
    def __init__(self):
        self.oxy_name_to_oxy = {}
        self.background_tasks = set()
        self.message_prefix = "msg"
        self.name = "ut_mas"

    async def send_message(self, message, redis_key):
        self.last_msg = (redis_key, message)


class DummyOxy:
    def __init__(self, name, succeed=True, delay=0.0):
        self.name = name
        self.category = "tool"
        self.is_permission_required = True
        self.permitted_tool_name_list = []
        self.extra_permitted_tool_name_list = []
        self.timeout = 5
        self.delay = 0.0
        self._succeed = succeed
        self._delay = delay
        self.retries = 3

    async def execute(self, req: OxyRequest):
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._succeed:
            return OxyResponse(state=OxyState.COMPLETED, output=f"{self.name}-ok")
        raise RuntimeError("fail")


# ──────────────────────────────────────────────────────────────────────────────
# ❷ Fixtures
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def mas_env():
    return DummyMAS()


@pytest.fixture
def base_request(mas_env):
    req = OxyRequest(arguments={}, caller="user", caller_category="user")
    req.set_mas(mas_env)
    return req


# ──────────────────────────────────────────────────────────────────────────────
# ❸ Tests － clone_with / property / deepcopy
# ──────────────────────────────────────────────────────────────────────────────
def test_clone_with_independence(base_request):
    new_req = base_request.clone_with(arguments={"x": 1}, callee="dummy")
    assert new_req.arguments == {"x": 1}
    assert base_request.arguments == {}          
    with pytest.raises(AttributeError):
        base_request.clone_with(no_field=1)      


def test_deepcopy_resets_parallel_ids(base_request):
    dup = base_request.__deepcopy__({})
    assert dup.parallel_id == ""
    assert dup.latest_node_ids == []


# ──────────────────────────────────────────────────────────────────────────────
# ❹ retry_execute
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_retry_execute_success(base_request):
    oxy = DummyOxy("ok_tool")
    resp = await base_request.retry_execute(oxy)
    assert resp.state is OxyState.COMPLETED


@pytest.mark.asyncio
async def test_retry_execute_failure(base_request):
    oxy = DummyOxy("bad_tool", succeed=False)
    oxy.retries = 2
    oxy.delay = 0.01
    resp = await base_request.retry_execute(oxy)
    assert resp.state is OxyState.FAILED


# ──────────────────────────────────────────────────────────────────────────────
# ❺ call() 
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_call_permission_ok(mas_env):
    agentA = DummyOxy("agentA")
    toolX = DummyOxy("toolX")
    agentA.permitted_tool_name_list = ["toolX"]

    mas_env.oxy_name_to_oxy.update({"agentA": agentA, "toolX": toolX})

    req = OxyRequest(caller="agentA", callee="agentA",
                     caller_category="agent", callee_category="agent")
    req.set_mas(mas_env)

    resp = await req.call(callee="toolX", arguments={})
    assert resp.state is OxyState.COMPLETED
    assert resp.output == "toolX-ok"


@pytest.mark.asyncio
async def test_call_permission_denied(mas_env):
    agentA = DummyOxy("agentA")                 
    toolX = DummyOxy("toolX")
    mas_env.oxy_name_to_oxy.update({"agentA": agentA, "toolX": toolX})

    req = OxyRequest(caller="agentA", callee="agentA",
                     caller_category="agent", callee_category="agent")
    req.set_mas(mas_env)

    resp = await req.call(callee="toolX", arguments={})
    assert resp.state is OxyState.SKIPPED
    assert "No permission" in resp.output


@pytest.mark.asyncio
async def test_call_timeout(mas_env):
    agentA = DummyOxy("agentA", succeed=True)
    slow_tool = DummyOxy("slow", delay=0.2)
    slow_tool.timeout = 0.05                     
    agentA.permitted_tool_name_list = ["slow"]

    mas_env.oxy_name_to_oxy.update({"agentA": agentA, "slow": slow_tool})

    req = OxyRequest(caller="agentA", callee="agentA",
                     caller_category="agent", callee_category="agent")
    req.set_mas(mas_env)

    resp = await req.call(callee="slow", arguments={})
    assert resp.state is OxyState.FAILED
    assert "timed out" in resp.output


# ──────────────────────────────────────────────────────────────────────────────
# ❻ send_message
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_send_message(mas_env, base_request):
    await base_request.send_message({"type": "ping"})
    redis_key, message = mas_env.last_msg
    assert redis_key.endswith(base_request.current_trace_id)
    assert message["type"] == "ping"


# ──────────────────────────────────────────────────────────────────────────────
# ❼ OxyResponse basics
# ──────────────────────────────────────────────────────────────────────────────
def test_oxyresponse_fields(base_request):
    resp = OxyResponse(state=OxyState.COMPLETED, output="ok", oxy_request=base_request)
    assert resp.state is OxyState.COMPLETED
    assert resp.output == "ok"
    assert resp.oxy_request is base_request
