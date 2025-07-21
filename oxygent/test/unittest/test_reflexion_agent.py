"""
Unit tests for ReflexionAgent
"""

import pytest
from unittest.mock import AsyncMock

from oxygent.oxy.agents.reflexion_agent import ReflexionAgent
from oxygent.schemas import (
    OxyRequest,
    OxyResponse,
    OxyState,
    LLMResponse,
    LLMState,
)
from oxygent.oxy.base_tool import BaseTool

# ──────────────────────────────────────────────────────────────────────────────
# ❶ Dummy MAS
# ──────────────────────────────────────────────────────────────────────────────
class DummyMAS:
    def __init__(self):
        self.oxy_name_to_oxy = {}
        self.es_client = AsyncMock()
        self.vearch_client = AsyncMock()
        self.background_tasks = set()
        self.message_prefix = "msg"
        self.name = "test_mas"
        self.send_message = AsyncMock()


# ──────────────────────────────────────────────────────────────────────────────
# ❷ Parser stub
# ──────────────────────────────────────────────────────────────────────────────
def parse_llm_answer(text: str) -> LLMResponse:
    return LLMResponse(state=LLMState.ANSWER, output=text, ori_response=text)


def parse_eval_ok(text: str) -> LLMResponse:
    return LLMResponse(state=LLMState.SUCCESS, output=text, ori_response=text)


def parse_reflect(text: str) -> LLMResponse:
    return LLMResponse(state=LLMState.SUCCESS, output="reflect", ori_response=text)



class StubTool(BaseTool):
    is_multimodal_supported: bool = False


# ──────────────────────────────────────────────────────────────────────────────
# ❸ Fixtures
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def mas_env():
    mas = DummyMAS()

    for name in ("evaluator_agent", "self_reflection_agent", "mock_llm"):
        mas.oxy_name_to_oxy[name] = StubTool(
            name=name,
            desc="stub",
            category="agent" if "agent" in name else "llm",
            is_permission_required=False,
            is_multimodal_supported=False,
        )
    return mas


@pytest.fixture
def reflex_agent(mas_env):
    """使用最简 ReAct 执行器实现，直接返回 ANSWER。"""
    class DummyReflexionAgent(ReflexionAgent):
        async def react_execute(self, oxy_request, self_refletion_memory):
            return OxyResponse(
                state=OxyState.COMPLETED,
                output="final-answer",
                extra={"react_memory": []},
            )

        func_parse_llm_response = staticmethod(parse_llm_answer)

    agent = DummyReflexionAgent(
        name="reflex_agent",
        desc="UT ReflexionAgent",
        tools=[],
        llm_model="mock_llm",
        evaluator_agent_name="evaluator_agent",
        self_reflection_agent_name="self_reflection_agent",
        func_parse_evaluator_response=parse_eval_ok,
        func_parse_self_reflection_response=parse_reflect,
    )
    agent.set_mas(mas_env)
    return agent


@pytest.fixture
def oxy_request(monkeypatch, mas_env):
    req = OxyRequest(
        arguments={"query": "How to test?"},
        caller="user",
        caller_category="user",
        current_trace_id="trace123",
    )
    req.mas = mas_env 

    async def _fake_call(self, *, callee: str, arguments: dict, **kwargs):
        return OxyResponse(
            state=OxyState.COMPLETED,
            output="OK",
            oxy_request=self,
        )

    monkeypatch.setattr("oxygent.schemas.OxyRequest.call", _fake_call, raising=True)
    return req


# ──────────────────────────────────────────────────────────────────────────────
# ❹ Tests
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_init_adds_extra_tools(reflex_agent):
    await reflex_agent.init()


@pytest.mark.asyncio
async def test_execute_success_first_round(reflex_agent, oxy_request):
    await reflex_agent.init()
    resp = await reflex_agent.execute(oxy_request)

    assert resp.state is OxyState.COMPLETED
    assert resp.output == "final-answer"
    assert "self_reflection_memory" in resp.extra
