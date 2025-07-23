"""HTTP-based LLM implementation for remote language model APIs.

This module provides the HttpLLM class, which implements the BaseLLM interface for
communicating with remote language model APIs over HTTP. It supports various LLM
providers that follow OpenAI-compatible API standards.
"""

import logging

import httpx

from ...config import Config
from ...schemas import OxyRequest, OxyResponse, OxyState
from .remote_llm import RemoteLLM


logger = logging.getLogger(__name__)


class HttpLLM(RemoteLLM):
    """HTTP-based Large Language Model implementation.

    This class provides a concrete implementation of RemoteLLM for communicating
    with remote LLM APIs over HTTP. It handles API authentication, request
    formatting, and response parsing for OpenAI-compatible APIs.
    """ 

    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        """Execute an HTTP request to the remote LLM API.

        Sends a formatted request to the remote LLM API and processes the response.
        The method handles authentication, payload construction, and response parsing
        for OpenAI-compatible APIs.

        Args:
            oxy_request: The request object containing messages and parameters.

        Returns:
            OxyResponse: The response containing the LLM's output with COMPLETED state.
        """
        use_openai = self.api_key is not None
        url = self.base_url.rstrip("/")
        headers = {"Content-Type": "application/json"}
        if use_openai:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Construct payload for the API request
        llm_config = Config.get_llm_config()
        payload = {
            "messages": await self._get_messages(oxy_request),
            "model": self.model_name,
            "stream": False,
        }
        payload.update(llm_config)
        for k, v in self.llm_params.items():
            payload[k] = v
        for k, v in oxy_request.arguments.items():
            if k == "messages":
                continue
            payload[k] = v

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            http_response = await client.post(
                url, headers=headers, json=payload
            )
            http_response.raise_for_status()
            data = http_response.json()
            if "error" in data:
                error_message = data["error"].get("message", "Unknown error")
                raise ValueError(f"LLM API error: {error_message}")
            
            if use_openai:
                response_message = data["choices"][0]["message"]
                result = response_message.get("content") or response_message.get(
                    "reasoning_content"
                )
            else:  # ollama
                result = data["message"]["content"]
            

            return OxyResponse(state=OxyState.COMPLETED, output=result)
