"""
Unit tests for PlanAndSolve Flow
"""

import json
import pytest
from unittest.mock import AsyncMock

from oxygent.oxy.flows.plan_and_solve import PlanAndSolve, Plan, Response
from oxygent.schemas import LLMResponse, OxyRequest, OxyResponse, OxyState


# ──────────────────────────────────────────────────────────────────────────────
# Dummy MAS
# ──────────────────────────────────────────────────────────────────────────────
class DummyMAS:

    def __init__(self):
        self.oxy_name_to_oxy = {}
        self.background_tasks = set()   
        self.message_prefix = "msg"
        self.name = "test_mas"
        self.send_message = AsyncMock()

    def add_oxy(self, oxy):
        self.oxy_name_to_oxy[oxy.name] = oxy


# ──────────────────────────────────────────────────────────────────────────────
# Helper parsers
# ──────────────────────────────────────────────────────────────────────────────
def parse_planner(resp: str) -> LLMResponse:
    """把 JSON -> Plan"""
    plan_dict = json.loads(resp)
    return LLMResponse(state=None, output=None, ori_response=resp, steps=plan_dict["steps"])


def parse_replanner(resp: str) -> LLMResponse:
    data = json.loads(resp)
    if "response" in data:
        return LLMResponse(
            state=None, output=None, ori_response=resp,
            action=Response(response=data["response"])
        )
    return LLMResponse(
        state=None, output=None, ori_response=resp,
        action=Plan(steps=data["steps"])
    )


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def mas_env():
    return DummyMAS()


@pytest.fixture
def flow_preplan(mas_env):
    f = PlanAndSolve(
        name="ps_flow",
        desc="UT plan solve",
        pre_plan_steps=["step1", "step2"],
        executor_agent_name="executor_agent",
        llm_model="mock_llm",
    )
    f.set_mas(mas_env)
    return f


@pytest.fixture
def flow_full(mas_env):
    f = PlanAndSolve(
        name="ps_flow",
        desc="UT planner first",
        executor_agent_name="executor_agent",
        planner_agent_name="planner_agent",
        func_parse_planner_response=parse_planner,
        llm_model="mock_llm",
    )
    f.set_mas(mas_env)
    return f


@pytest.fixture
def flow_replanner(mas_env):
    f = PlanAndSolve(
        name="ps_flow",
        desc="UT replanner",
        executor_agent_name="executor_agent",
        planner_agent_name="planner_agent",
        enable_replanner=True,
        func_parse_planner_response=parse_planner,
        func_parse_replanner_response=parse_replanner,
        llm_model="mock_llm",
        max_replan_rounds=5,
    )
    f.set_mas(mas_env)
    return f


@pytest.fixture
def oxy_request(monkeypatch, mas_env):
    req = OxyRequest(
        arguments={"query": "What is the plan?"},
        caller="user",
        caller_category="user",
        current_trace_id="trace123",
    )
    req.mas = mas_env

    async def _fake_call(self, *, callee: str, arguments: dict, **kwargs):
        if callee == "executor_agent":
            return OxyResponse(
                state=OxyState.COMPLETED,
                output=f"done({arguments['query']})",
                oxy_request=self,
            )
        if callee == "planner_agent":
            return OxyResponse(
                state=OxyState.COMPLETED,
                output=json.dumps({"steps": ["step1", "step2"]}),
                oxy_request=self,
            )
        if callee == "replanner_agent":
            return OxyResponse(
                state=OxyState.COMPLETED,
                output=json.dumps({"response": "final-answer"}),
                oxy_request=self,
            )
        if callee == "mock_llm": 
            return OxyResponse(
                state=OxyState.COMPLETED, output="llm-fallback", oxy_request=self
            )

    monkeypatch.setattr("oxygent.schemas.OxyRequest.call", _fake_call, raising=True)
    return req


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_execute_with_preplan(flow_preplan, oxy_request):
    resp = await flow_preplan.execute(oxy_request)
    assert resp.state is OxyState.COMPLETED
    assert "step2" in resp.output       


@pytest.mark.asyncio
async def test_execute_with_planner(flow_full, oxy_request):
    resp = await flow_full.execute(oxy_request)
    assert resp.state is OxyState.COMPLETED
    assert "step2" in resp.output       

