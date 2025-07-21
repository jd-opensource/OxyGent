"""
Unit tests for WorkflowAgent
"""

import pytest
from unittest.mock import AsyncMock

from oxygent.oxy.agents.workflow_agent import WorkflowAgent
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


# ——— FunctionTool Stub ————————————————————————————————————————————————
async def echo_exec() -> str:
    return "echo-result"


class EchoTool(FunctionTool):
    name: str = "echo_tool"
    desc: str = "Echo FunctionTool"
    is_multimodal_supported: bool = False
    func_process = staticmethod(echo_exec)


# ——— LLM Stub ————————————————————————————————————————————————
class MockLLMTool(BaseTool):
    name: str = "mock_llm"
    desc: str = "Stub LLM"
    category: str = "llm"
    is_multimodal_supported: bool = False

    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:  # pragma: no cover
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
    mas.oxy_name_to_oxy["echo_tool"] = EchoTool()
    mas.oxy_name_to_oxy["mock_llm"] = MockLLMTool()
    return mas


async def workflow_fn(req: OxyRequest) -> str:
    tool_resp = await req.call(callee="echo_tool", arguments={})
    return f"workflow({tool_resp.output})"


@pytest.fixture
def workflow_agent(patched_config, mas_env):
    agent = WorkflowAgent(
        name="workflow_agent",
        desc="UT Workflow Agent",
        tools=["echo_tool"],
        func_workflow=workflow_fn,
        llm_model="mock_llm",
    )
    agent.set_mas(mas_env)
    return agent


@pytest.fixture
def oxy_request(monkeypatch, mas_env):
    req = OxyRequest(
        arguments={"query": "test"},
        caller="user",
        caller_category="user",
        current_trace_id="trace123",
    )
    req.mas = mas_env 

    async def _fake_call(self, *, callee: str, arguments: dict, **kwargs):
        if callee == "echo_tool":
            return OxyResponse(
                state=OxyState.COMPLETED, output="echo-result", oxy_request=self
            )
        if callee == "mock_llm":
            return OxyResponse(
                state=OxyState.COMPLETED, output="llm-output", oxy_request=self
            )
        return OxyResponse(state=OxyState.FAILED, output="bad callee", oxy_request=self)

    monkeypatch.setattr("oxygent.schemas.OxyRequest.call", _fake_call, raising=True)
    return req


# ──────────────────────────────────────────────────────────────────────────────
# ❸ test
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_init_collect_tools(workflow_agent):
    await workflow_agent.init()
    assert "echo_tool" in workflow_agent.permitted_tool_name_list


@pytest.mark.asyncio
async def test_execute_workflow(workflow_agent, oxy_request):
    await workflow_agent.init()
    resp = await workflow_agent.execute(oxy_request)
    assert resp.state is OxyState.COMPLETED
    assert resp.output == "workflow(echo-result)"
