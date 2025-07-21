"""
Unit tests for base_agent.py (BaseAgent Class)

This test suite verifies core behaviors of the BaseAgent class, including:
- Attribute initialization
- Pre-process and post-process methods
- Trace management logic

Because BaseAgent is abstract (via BaseFlow -> BaseOxy), we define DummyAgent for testing.
"""

import pytest
from unittest.mock import AsyncMock

from oxygent.oxy.agents.base_agent import BaseAgent
from oxygent.schemas import OxyRequest, OxyResponse, OxyState

# Define a dummy subclass implementing required abstract methods
class DummyAgent(BaseAgent):
    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        return OxyResponse(state=OxyState.COMPLETED, output="dummy_output", oxy_request=oxy_request)

@pytest.mark.asyncio
class TestBaseAgent:
    @pytest.fixture
    def dummy_agent(self):
        agent = DummyAgent(name="dummy_agent", desc="Dummy Agent for testing")
        agent.mas = AsyncMock()
        agent.mas.es_client = AsyncMock()
        return agent

    async def test_initialization(self, dummy_agent):
        """Test attribute initialization of DummyAgent."""
        assert dummy_agent.name == "dummy_agent"
        assert dummy_agent.category == "agent"
        assert isinstance(dummy_agent.input_schema, dict)

    async def test_pre_process_user_request(self, dummy_agent):
        """Test _pre_process updates root_trace_ids for user requests with from_trace_id."""
        oxy_request = OxyRequest(arguments={}, caller="test", caller_category="user", from_trace_id="parent_trace")
        dummy_agent.mas.es_client.search.return_value = {
            "hits": {
                "hits": [{
                    "_source": {"root_trace_ids": "trace1|trace2"}
                }]
            }
        }
        result = await dummy_agent._pre_process(oxy_request)
        assert isinstance(result.root_trace_ids, list)
        assert "parent_trace" in result.root_trace_ids

    async def test_pre_save_data(self, dummy_agent):
        """Test _pre_save_data stores pre-trace data for user requests."""
        oxy_request = OxyRequest(arguments={}, caller="test", caller_category="user", current_trace_id="trace123")
        await dummy_agent._pre_save_data(oxy_request)
        dummy_agent.mas.es_client.index.assert_called()


    async def test_post_save_data(self, dummy_agent):
        """Test _post_save_data stores post-trace data and history."""
        oxy_request = OxyRequest(
            arguments={},
            caller="test",
            caller_category="user",
            current_trace_id="trace123",
            is_save_history=True,      
        )
        oxy_request.callee = dummy_agent.name  
        oxy_response = OxyResponse(
            state=OxyState.COMPLETED,
            output="test_output",
            oxy_request=oxy_request,
        )

        await dummy_agent._post_save_data(oxy_response)
        assert dummy_agent.mas.es_client.index.call_count >= 2

