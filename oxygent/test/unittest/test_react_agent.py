"""
Unit tests for ReActAgent
"""

import json
from unittest.mock import AsyncMock

import pytest

from oxygent.oxy.agents.react_agent import LLMState, ReActAgent
from oxygent.oxy.base_tool import BaseTool
from oxygent.oxy.function_tools.function_tool import FunctionTool
from oxygent.schemas import (
    OxyRequest,
    OxyResponse,
    OxyState,
)


# ──────────────────────────────────────────────────────────────────────────────
# ❶ Dummy MAS
# ──────────────────────────────────────────────────────────────────────────────
class DummyMAS:
    def __init__(self):
        self.oxy_name_to_oxy = {}
        self.vearch_client = AsyncMock()
        self.es_client = AsyncMock()
        self.background_tasks = set()

    @staticmethod
    def is_agent(name: str) -> bool:
        return name.startswith("agent_")


# —— FunctionTool Stub  ————————————————————————————————————
async def dummy_exec() -> str:
    return "dummy result"


class DummyFunctionTool(FunctionTool):
    name: str = "dummy_tool"
    desc: str = "Unit-Test FunctionTool"
    is_multimodal_supported: bool = False
    func_process = staticmethod(dummy_exec)


# —— LLM Stub ——————————————————————————————————————————————
class MockLLMTool(BaseTool):
    name: str = "mock_llm"
    desc: str = "Stub LLM"
    category: str = "llm"
    is_multimodal_supported: bool = False

    async def _execute(
        self, oxy_request: OxyRequest
    ) -> OxyResponse:  
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
def react_agent(patched_config, mas_env):
    agent = ReActAgent(
        name="react_agent",
        desc="UT ReAct Agent",
        tools=["dummy_tool"],
        trust_mode=True, 
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

    async def _fake_call(self, *, callee: str, arguments: dict, **kwargs):
        if callee == "mock_llm":
            llm_output = json.dumps({"tool_name": "dummy_tool", "arguments": {}})
            return OxyResponse(
                state=OxyState.COMPLETED, output=llm_output, oxy_request=self
            )
        elif callee == "dummy_tool":
            return OxyResponse(
                state=OxyState.COMPLETED,  
                output="tool-exec-ok",
                oxy_request=self,
            )
        else:
            return OxyResponse(
                state=OxyState.FAILED, output="unknown tool", oxy_request=self
            )

    monkeypatch.setattr("oxygent.schemas.OxyRequest.call", _fake_call, raising=True)
    return req


# ──────────────────────────────────────────────────────────────────────────────
# ❸ test
# ──────────────────────────────────────────────────────────────────────────────
def test_parse_llm_response(react_agent):
    resp = react_agent._parse_llm_response('{"tool_name":"dummy_tool","arguments":{}}')
    assert resp.state is LLMState.TOOL_CALL
    assert resp.output["tool_name"] == "dummy_tool"


@pytest.mark.asyncio
async def test_execute_trust_mode(react_agent, oxy_request):
    result = await react_agent.execute(oxy_request)
    assert result.state is OxyState.COMPLETED
    assert "dummy_tool" in result.output


@pytest.mark.asyncio
async def test_permitted_tool_list(react_agent):
    await react_agent.init()
    assert "dummy_tool" in react_agent.permitted_tool_name_list
