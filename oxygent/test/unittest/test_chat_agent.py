"""
Unit tests for ChatAgent (_execute flow)

"""

import pytest
from unittest.mock import AsyncMock

from oxygent.oxy.agents.chat_agent import ChatAgent
from oxygent.schemas import OxyRequest, OxyResponse, OxyState

# ────────────────────────────────────────────────────────────────────────────────
# Dummy stubs used to patch Memory / Message inside chat_agent.py
# ────────────────────────────────────────────────────────────────────────────────
class DummyMemory:
    def __init__(self):
        self._messages = []

    def add_message(self, msg):
        self._messages.append(msg)

    def add_messages(self, msgs):
        self._messages.extend(msgs)

    def to_dict_list(self):
        return self._messages


class DummyMessage:
    """Return bare-bones dicts compatible with LLM Chat API"""
    @staticmethod
    def system_message(content):
        return {"role": "system", "content": content}

    @staticmethod
    def user_message(content):
        return {"role": "user", "content": content}

    @staticmethod
    def dict_list_to_messages(lst):
        return lst


# ────────────────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def chat_agent(monkeypatch):
    """Instantiate ChatAgent and patch dependencies"""
    # Patch Memory & Message inside module
    monkeypatch.setattr("oxygent.oxy.agents.chat_agent.Memory", DummyMemory, raising=True)
    monkeypatch.setattr("oxygent.oxy.agents.chat_agent.Message", DummyMessage, raising=True)

    agent = ChatAgent(name="chat_agent", desc="UT Chat Agent", llm_model="mock_llm")
    agent._build_instruction = lambda args: "You are a helpful AI assistant."
    return agent


@pytest.fixture
def oxy_request(monkeypatch):
    """Provide an OxyRequest with minimal viable fields"""
    req = OxyRequest(
        arguments={
            "query": "Hello!",
            "llm_params": {"temperature": 0.3},
        },
        caller="user",
        caller_category="user",
        current_trace_id="trace123",
        short_memory = [{"role": "assistant", "content": "Prev answer"}],
        query = "hello!"
    )
    mocked_resp = OxyResponse(
        state=OxyState.COMPLETED,
        output="Hi there!",
        oxy_request=req,
    )
    async_mock = AsyncMock(return_value=mocked_resp)
    monkeypatch.setattr(
        "oxygent.schemas.OxyRequest.call",
        async_mock,
        raising=True,
    )
    return req


# ────────────────────────────────────────────────────────────────────────────────
# Tests
# ────────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_initialization(chat_agent):
    assert chat_agent.name == "chat_agent"
    assert chat_agent.category == "agent"
    assert chat_agent._build_instruction({}) == "You are a helpful AI assistant."


@pytest.mark.asyncio
async def test_execute_builds_messages_and_calls_llm(chat_agent, oxy_request):
    response = await chat_agent._execute(oxy_request)

    assert response.output == "Hi there!"
    assert response.state == OxyState.COMPLETED

    oxy_request.call.assert_awaited_once()

    _, kwargs = oxy_request.call.call_args
    assert kwargs["callee"] == chat_agent.llm_model

    arguments = kwargs["arguments"]
    assert isinstance(arguments["messages"], list)

    assert arguments["messages"][0]["role"] == "system"
    assert arguments["messages"][-1]["role"] == "user"
    assert arguments["messages"][-1]["content"] == "Hello!"

    assert arguments["temperature"] == 0.3
