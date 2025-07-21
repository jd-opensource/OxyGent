"""
Unit tests for Workflow
"""

import pytest

from oxygent.oxy.flows.workflow import Workflow
from oxygent.schemas import OxyRequest, OxyResponse, OxyState


# ──────────────────────────────────────────────────────────────────────────────
# ❶ Dummy workflow 
# ──────────────────────────────────────────────────────────────────────────────
async def echo_workflow(req: OxyRequest) -> str:  
    return f"echo({req.arguments.get('query')})"


# ──────────────────────────────────────────────────────────────────────────────
# ❷ Fixtures
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def workflow():
    return Workflow(name="wf", desc="UT Workflow", func_workflow=echo_workflow)


@pytest.fixture
def oxy_request():
    return OxyRequest(
        arguments={"query": "hello"},
        caller="user",
        caller_category="user",
        current_trace_id="trace123",
    )


# ──────────────────────────────────────────────────────────────────────────────
# ❸ Tests
# ──────────────────────────────────────────────────────────────────────────────
def test_initialization(workflow):
    assert workflow.name == "wf"
    assert workflow.func_workflow is echo_workflow


@pytest.mark.asyncio
async def test_execute_success(workflow, oxy_request):
    resp: OxyResponse = await workflow.execute(oxy_request)

    assert resp.state is OxyState.COMPLETED
    assert resp.output == "echo(hello)"
    assert resp.oxy_request.call_stack[-1] == "wf"

# TODO: add error
# @pytest.mark.asyncio
# async def test_execute_without_func_raises(oxy_request):
#     bad_flow = Workflow(name="bad", desc="no func")
#     with pytest.raises(TypeError):
#         await bad_flow.execute(oxy_request)
