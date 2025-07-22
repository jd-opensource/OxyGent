"""Standard I/O MCP client implementation.

This module provides the StdioMCPClient class, which implements MCP communication over
standard input/output streams. This transport method is ideal for local process
communication, allowing MCP servers to run as separate processes that communicate
through stdin/stdout pipes.
"""

import logging
import os
import shutil
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import Field

from .base_mcp_client import BaseMCPClient

logger = logging.getLogger(__name__)


class StdioMCPClient(BaseMCPClient):
    """MCP client implementation using standard I/O transport.

    This class extends BaseMCPClient to provide MCP communication over stdio.
    It spawns and manages external processes (like Node.js scripts) that act
    as MCP servers, communicating through standard input/output streams.

    Attributes:
        params: Configuration parameters including command, arguments, and environment variables.
    """

    params: dict[str, Any] = Field(default_factory=dict)
    async def _ensure_directories_exist(self, args: list[str]) -> None:
        """Ensure required directories exist before starting MCP server."""
        if len(args) >= 2 and "server-filesystem" in " ".join(args):
            target_dir = args[-1]
            if not os.path.exists(target_dir):
                try:
                    os.makedirs(target_dir, exist_ok=True)
                    logger.info(f"Created directory: {target_dir}")
                except Exception as e:
                    logger.warning(f"Could not create directory {target_dir}: {e}")
        
        if args[0] == "--directory" and args[2] == "run":
            mcp_tool_file = os.path.join(args[1], args[3])
            if not os.path.exists(mcp_tool_file):
                raise FileNotFoundError(f"{mcp_tool_file} does not exist.")

    async def init(self) -> None:
        """Initialize the stdio connection to the MCP server process.

        Spawns an external process (such as a Node.js script) that acts as an MCP server,
        establishes stdio communication channels, creates a client session, and discovers
        available tools from the server.

        The method performs several validation steps:
        1. Resolves the command path (with special handling for 'npx')
        2. Validates that required files exist for directory-based commands
        3. Sets up environment variables
        4. Establishes stdio transport and session
        """
        command = (
            shutil.which("npx")
            if self.params["command"] == "npx"
            else self.params["command"]
        )
        if command is None:
            raise ValueError("The command must be a valid string and cannot be None.")

        args = self.params["args"]
        await self._ensure_directories_exist(args)
        if args[0] == "--directory" and args[2] == "run":
            mcp_tool_file = os.path.join(args[1], args[3])
            if not os.path.exists(mcp_tool_file):
                raise FileNotFoundError(f"{mcp_tool_file} does not exist.")
        server_params = StdioServerParameters(
            command=command,
            args=args,
            env={**os.environ, **self.params["env"]}
            if self.params.get("env")
            else {**os.environ},
        )
        try:
            stdio_transport = await self._exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            read, write = stdio_transport
            self._session = await self._exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await self._session.initialize()
            await self.list_tools()
        except Exception as e:
            logger.error(f"Error initializing server {self.name}: {e}")
            await self.cleanup()
            raise Exception(f"Server {self.name} error")

