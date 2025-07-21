"""
Unit tests for ParallelAgent
"""

import pytest
from unittest.mock import AsyncMock

from oxygent.oxy.agents.parallel_agent import ParallelAgent
from oxygent.oxy.function_tools.function_tool import FunctionTool
from oxygent.oxy.base_tool import BaseTool
from oxygent.schemas import OxyRequest, OxyResponse, OxyState


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

    @staticmethod
    def is_agent(name: str) -> bool:
        return name.startswith("agent_")


async def exec_tool_a() -> str:
    return "result_a"


async def exec_tool_b() -> str:
    return "result_b"


class ToolA(FunctionTool):
    name: str = "tool_a"
    desc: str = "A FunctionTool"
    func_process = staticmethod(exec_tool_a)
    is_multimodal_supported: bool = False


class ToolB(FunctionTool):
    name: str = "tool_b"
    desc: str = "B FunctionTool"
    func_process = staticmethod(exec_tool_b)
    is_multimodal_supported: bool = False


class MockLLMTool(BaseTool):
    name: str = "mock_llm"
    desc: str = "Stub LLM"
    category: str = "llm"
    is_multimodal_supported: bool = False

    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:  # pragma: no cover
        return OxyResponse(
            state=OxyState.COMPLETED, output="stub-llm", oxy_request=oxy_request
        )


# ──────────────────────────────────────────────────────────────────────────────
# ❷ Fixtures
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def patched_config(monkeypatch):
    """修补 LocalAgent 依赖的 Config"""
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
    mas.oxy_name_to_oxy.update(
        {
            "tool_a": ToolA(),
            "tool_b": ToolB(),
            "mock_llm": MockLLMTool(),
        }
    )
    return mas


@pytest.fixture
def parallel_agent(patched_config, mas_env):
    agent = ParallelAgent(
        name="parallel_agent",
        desc="UT Parallel Agent",
        tools=["tool_a", "tool_b"],
        llm_model="mock_llm",
    )
    agent.set_mas(mas_env)
    return agent


@pytest.fixture
def oxy_request(monkeypatch, mas_env):
    req = OxyRequest(
        arguments={"query": "question"},
        caller="user",
        caller_category="user",
        current_trace_id="trace123",
    )
    req.mas = mas_env

    async def _fake_call(self, *, callee: str, arguments: dict, **kwargs):
        if callee == "tool_a":
            return OxyResponse(
                state=OxyState.COMPLETED, output="result_a", oxy_request=self
            )
        if callee == "tool_b":
            return OxyResponse(
                state=OxyState.COMPLETED, output="result_b", oxy_request=self
            )
        if callee == "mock_llm":
            outputs = [msg["content"] for msg in arguments["messages"] if msg["role"] == "user"]
            summary = f"summary({'+'.join(outputs)})"
            return OxyResponse(
                state=OxyState.COMPLETED, output=summary, oxy_request=self
            )
        return OxyResponse(state=OxyState.FAILED, output="unknown callee", oxy_request=self)

    monkeypatch.setattr("oxygent.schemas.OxyRequest.call", _fake_call, raising=True)
    return req


# ──────────────────────────────────────────────────────────────────────────────
# ❸ Tests
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_init_collect_tools(parallel_agent):
    await parallel_agent.init()
    assert set(parallel_agent.permitted_tool_name_list) == {"tool_a", "tool_b"}


@pytest.mark.asyncio
async def test_execute_parallel_flow(parallel_agent, oxy_request):
    await parallel_agent.init()
    resp = await parallel_agent.execute(oxy_request)
    assert resp.state is OxyState.COMPLETED
    assert "result_a" in resp.output and "result_b" in resp.output
