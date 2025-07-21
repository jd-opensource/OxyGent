"""
Unit tests for LocalAgent (tool & memory management)
pytest – pytest-asyncio
"""

import copy
import pytest
from unittest.mock import AsyncMock

from oxygent.oxy.agents.local_agent import LocalAgent
from oxygent.oxy.function_tools.function_tool import FunctionTool
from oxygent.oxy.base_tool import BaseTool
from oxygent.schemas import OxyRequest, OxyResponse, OxyState


# ──────────────────────────────────────────────────────────────────────────────
# ❶ Dummy MAS & Tools
# ──────────────────────────────────────────────────────────────────────────────
class DummyMAS:
    def __init__(self):
        self.oxy_name_to_oxy = {}
        self.es_client = AsyncMock()
        self.vearch_client = AsyncMock()
        self.background_tasks = set()

    @staticmethod
    def is_agent(name: str) -> bool:
        return name.startswith("agent_")


# -- FunctionTool Stub ---------------------------------------------------------
async def dummy_exec() -> str:
    return "dummy result"


class DummyFunctionTool(FunctionTool):
    name: str = "dummy_tool"
    desc: str = "Unit-Test FunctionTool"
    is_multimodal_supported: bool = False  

    func_process = staticmethod(dummy_exec)


# -- LLM Stub ------------------------------------------------------------------
class MockLLMTool(BaseTool):
    name: str = "mock_llm"
    desc: str = "Stub LLM"
    category: str = "llm"
    is_multimodal_supported: bool = False  

    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:  
        return OxyResponse(
            state=OxyState.COMPLETED, output="llm-output", oxy_request=oxy_request
        )


# ──────────────────────────────────────────────────────────────────────────────
# ❷ Fixtures
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def patched_config(monkeypatch):
    monkeypatch.setattr(
        "oxygent.oxy.agents.local_agent.Config.get_agent_llm_model",
        lambda: "mock_llm",
        raising=True,
    )
    monkeypatch.setattr(
        "oxygent.oxy.agents.local_agent.Config.get_agent_prompt",
        lambda: "SYSTEM_PROMPT",
        raising=True,
    )
    monkeypatch.setattr(
        "oxygent.oxy.agents.local_agent.Config.get_vearch_config",
        lambda: None,
        raising=True,
    )


@pytest.fixture
def mas_env():
    mas = DummyMAS()
    mas.oxy_name_to_oxy["dummy_tool"] = DummyFunctionTool()
    mas.oxy_name_to_oxy["mock_llm"] = MockLLMTool()
    return mas


@pytest.fixture
def dummy_local_agent(patched_config, mas_env):
    class DummyLocalAgent(LocalAgent):
        async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
            return OxyResponse(
                state=OxyState.COMPLETED,
                output=oxy_request.get_query(),
                oxy_request=oxy_request,
            )

    agent = DummyLocalAgent(
        name="agent_tester",
        desc="Unit-Test Local Agent",
        tools=["dummy_tool"],
        sub_agents=[],
        llm_model="mock_llm",
    )
    agent.set_mas(mas_env)
    return agent


@pytest.fixture
def oxy_request(monkeypatch):
    req = OxyRequest(
        arguments={"query": "hello"},
        caller="user",
        caller_category="user",
        current_trace_id="trace123",
    )

    async def _fake_call(self, **kwargs):
        return OxyResponse(
            state=OxyState.COMPLETED,
            output="tool-output",
            oxy_request=self,
        )

    monkeypatch.setattr("oxygent.schemas.OxyRequest.call", _fake_call, raising=True)
    return req


# ──────────────────────────────────────────────────────────────────────────────
# ❸ Tests
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_initialization(dummy_local_agent):
    await dummy_local_agent.init()
    assert "dummy_tool" in dummy_local_agent.permitted_tool_name_list
    assert dummy_local_agent.is_multimodal_supported is False


@pytest.mark.asyncio
async def test_full_execute_cycle(dummy_local_agent, oxy_request):
    resp = await dummy_local_agent.execute(copy.deepcopy(oxy_request))
    assert resp.state == OxyState.COMPLETED
    assert resp.output == "hello"
