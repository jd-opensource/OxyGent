"""Tool Retrieval Module.

This file demonstrates the structure of the 'retrieve_tools', which can select
appropriate functions for an agent based on specific circumstances and requirements.
"""

from typing import Any

from pydantic import Field

from oxygent.oxy.function_tools.function_hub import FunctionHub

fh = FunctionHub(name="core_tools")


@fh.tool(
    description="Retrieve tools based on query and filter by app_name and agent_name"
)
async def retrieve_tools(
    query: str = Field(description="The usage of tools"),
    app_name: str = Field(description="SystemArg"),
    agent_name: str = Field(description="SystemArg"),
    top_k: int = Field(description="SystemArg", default=10),
    vearch_client: Any = Field(description="SystemArg"),
) -> str:
    """Retrieve relevant tools based on query and filter by app_name and agent_name.

    This function performs semantic search to find tools that match the given query,
    while applying filters based on the application and agent context.

    Args:
        query: Description of the tool functionality or use case to search for
        app_name: Name of the application to filter tools by
        agent_name: Name of the agent to filter tools by
        top_k: Maximum number of most relevant tools to return (default: 10)
        vearch_client: Vector search client used for tool retrieval operations

    Returns:
        A string containing the retrieved tool information

    Example:
        The query format example:
        query = {
            'query': query,
            'app_name': 'app_test1',
            'agent_name': 'agent_test1'
        }
    """
    # Perform tool retrieval using the vector search client
    # Filter results by app_name and agent_name, then return top_k most relevant tools
    return await vearch_client.tool_retrieval(query, app_name, agent_name, top_k)
