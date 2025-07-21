"""
Unit tests for base_oxy.py (Oxy Base Class)

This test suite verifies the core behaviors of the Oxy abstract base class, including:
- Attribute initialization
- Permission and tool management
- Lifecycle hooks callable structure

Because Oxy is abstract, we define a DummyOxy subclass for testing.
"""

import pytest
import asyncio
from oxygent.oxy.base_oxy import Oxy
from oxygent.schemas import OxyRequest, OxyResponse, OxyState

# Define a dummy subclass to implement the abstract method _execute
class DummyOxy(Oxy):
    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        return OxyResponse(state=OxyState.COMPLETED, output="dummy_output", oxy_request=oxy_request)

@pytest.mark.asyncio
class TestBaseOxy:
    @pytest.fixture
    def dummy_oxy(self):
        return DummyOxy(name="dummy", desc="dummy desc", category="tool")

    async def test_initialization(self, dummy_oxy):
        """Test attribute initialization of DummyOxy."""
        assert dummy_oxy.name == "dummy"
        assert dummy_oxy.desc == "dummy desc"
        assert dummy_oxy.category == "tool"
        assert isinstance(dummy_oxy._semaphore, asyncio.Semaphore)

    def test_add_permitted_tool(self, dummy_oxy):
        """Test adding permitted tools."""
        dummy_oxy.add_permitted_tool("tool_a")
        assert "tool_a" in dummy_oxy.permitted_tool_name_list

    def test_add_duplicate_permitted_tool(self, dummy_oxy, caplog):
        """Test adding duplicate tool logs warning."""
        dummy_oxy.add_permitted_tool("tool_a")
        dummy_oxy.add_permitted_tool("tool_a")
        assert dummy_oxy.permitted_tool_name_list.count("tool_a") == 1
        assert "already exists" in caplog.text

    def test_add_permitted_tools(self, dummy_oxy):
        """Test adding multiple permitted tools."""
        dummy_oxy.add_permitted_tools(["tool_b", "tool_c"])
        assert "tool_b" in dummy_oxy.permitted_tool_name_list
        assert "tool_c" in dummy_oxy.permitted_tool_name_list

    async def test_execute_runs_lifecycle(self, dummy_oxy):
        """Test that the execute method runs end-to-end returning OxyResponse."""
        oxy_request = OxyRequest(arguments={}, caller="test", current_trace_id="trace123")
        response = await dummy_oxy.execute(oxy_request)
        assert isinstance(response, OxyResponse)
        assert response.state == OxyState.COMPLETED
        assert response.output == "dummy_output"
        assert response.oxy_request == oxy_request
