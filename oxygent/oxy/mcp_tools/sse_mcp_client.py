"""Server-Sent Events MCP client implementation.

This module provides the SSEMCPClient class, which implements MCP communication over
Server-Sent Events (SSE). This allows for real-time, unidirectional communication from
MCP servers to clients, ideal for streaming responses and live updates.
"""

import logging

from mcp import ClientSession
from mcp.client.sse import sse_client
from pydantic import AnyUrl, Field

from ...utils.common_utils import build_url
from .base_mcp_client import BaseMCPClient

logger = logging.getLogger(__name__)


class SSEMCPClient(BaseMCPClient):
    """MCP client implementation using Server-Sent Events transport.

    This class extends BaseMCPClient to provide MCP communication over SSE. SSE enables
    real-time, unidirectional communication from servers to clients, making it suitable
    for streaming responses and live data updates.
    """

    sse_url: AnyUrl = Field("")

    async def init(self) -> None:
        """Initialize the SSE connection to the MCP server.

        Establishes a Server-Sent Events connection to the MCP server, creates a client
        session, initializes the MCP protocol, and discovers available tools from the
        server.
        """
        try:
            sse_transport = await self._exit_stack.enter_async_context(
                sse_client(build_url(self.sse_url))
            )
            read, write = sse_transport
            self._session = await self._exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await self._session.initialize()
            await self.list_tools()
        except Exception as e:
            logger.error(f"Error initializing server {self.name}: {e}")
            await self.cleanup()
            raise Exception(f"Server {self.name} error")
