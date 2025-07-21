"""HTTP tool module for making HTTP requests.

This module provides the HttpTool class, which enables making HTTP requests to external
APIs and services. It supports configurable methods, headers, and parameters with proper
timeout handling.
"""

import httpx
from pydantic import Field

from ...schemas import OxyRequest, OxyResponse, OxyState
from ..base_tool import BaseTool


class HttpTool(BaseTool):
    """Tool for making HTTP requests to external APIs and services.

    Attributes:
        method (str): HTTP method to use. Defaults to "GET".
        url (str): Target URL for the HTTP request.
        headers (dict): HTTP headers to include in the request.
        default_params (dict): Default parameters that will be merged with
            request arguments.
    """

    method: str = Field("GET", description="HTTP method to use")
    url: str = Field("", description="Target URL for the HTTP request")
    headers: dict = Field(default_factory=dict, description="HTTP headers to include")
    default_params: dict = Field(
        default_factory=dict, description="Default request parameters"
    )

    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        """Execute the HTTP request."""
        # Merge default parameters with request arguments
        params = self.default_params.copy()
        params.update(oxy_request.arguments)

        # Make HTTP request with timeout handling
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            http_response = await client.get(
                self.url, params=params, headers=self.headers
            )
            return OxyResponse(state=OxyState.COMPLETED, output=http_response.text)
