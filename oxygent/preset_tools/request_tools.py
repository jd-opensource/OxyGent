from oxygent.oxy import FunctionHub
from pydantic import Field
from oxygent.schemas import OxyRequest

request_tools = FunctionHub(name="request_tools")


@request_tools.tool(description="A tool that can access the request context.")
def advanced_tool(
    query: str = Field(description="The user query"),
    oxy_request: OxyRequest = Field(description="The request context"),
) -> str:
    trace_id = oxy_request.current_trace_id
    shared_data = oxy_request.shared_data
    caller = oxy_request.caller
    node_id = oxy_request.node_id

    result = {
        "message": f"Successfully accessed request context for query: '{query}'",
        "trace_id": trace_id,
        "node_id": node_id,
        "caller": caller,
        "shared_data": shared_data,
        "demo_status": "SUCCESS - OxyRequest parameter working correctly!",
    }

    return f"CONTEXT ACCESS DEMO RESULT:\n{result}"
