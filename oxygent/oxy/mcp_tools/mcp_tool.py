"""MCP Tool implementation for Model Context Protocol tools.

This module provides the MCPTool class, which represents individual tools discovered
from MCP servers. Each MCPTool acts as a proxy that delegates execution to its parent
MCP client while providing a standardized tool interface.
"""

from typing import Any

from pydantic import Field

from ...schemas import OxyRequest, OxyResponse
from ..base_tool import BaseTool


class MCPTool(BaseTool):
    """Individual tool proxy for MCP server tools.

    This class represents a specific tool discovered from an MCP server.
    It acts as a lightweight proxy that delegates actual execution to the
    parent MCP client while providing the standard BaseTool interface.

    Attributes:
        is_permission_required: Whether the tool requires explicit permission before execution.
        mcp_client: Reference to the parent MCP client that handles actual execution.
        server_name: Name of the MCP server that provides this tool.
    """

    is_permission_required: bool = Field(True, description="")

    mcp_client: Any = Field(None, exclude=True)
    server_name: str = Field("")

    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        """Execute the MCP tool by delegating to the parent MCP client."""
        return await self.mcp_client._execute(oxy_request)
