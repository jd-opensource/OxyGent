"""HTTP-based LLM implementation for remote language model APIs.

This module provides the HttpLLM class, which implements the BaseLLM interface for
communicating with remote language model APIs over HTTP. It supports various LLM
providers that follow OpenAI-compatible API standards.
"""

import json
import logging

import httpx

from ...schemas import OxyRequest, OxyResponse, OxyState
from .remote_llm import RemoteLLM
from pydantic import Field
from typing import Callable

logger = logging.getLogger(__name__)


class HttpLLM(RemoteLLM):
    """HTTP-based Large Language Model implementation.

    This class provides a concrete implementation of RemoteLLM for communicating
    with remote LLM APIs over HTTP. It handles API authentication, request
    formatting, and response parsing for OpenAI-compatible APIs.
    """
    llm_request_modifier: Callable = Field(
        lambda url, headers, payload: (url, headers, payload), exclude=True, description="Modifier function to modify request params before sending."
    )
    
    def _before_request_hook(self, url: str, headers: dict, payload: dict) -> tuple[str, dict, dict]:
        """Hook function to modify request URL, headers, and payload before sending.
        
        This method can be overridden by subclasses or set dynamically to modify
        the request parameters before sending to the LLM API.
        
        Args:
            url: The request URL
            headers: The request headers
            payload: The request payload
        
        Returns:
            Tuple of (modified_url, modified_headers, modified_payload)
        """
        url, headers, payload = self.llm_request_modifier(url, headers, payload)
        return url, headers, payload

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

        url = self.base_url.rstrip("/")
        is_gemini = "generativelanguage.googleapis.com" in url
        use_openai = (self.api_key is not None) and (not is_gemini)
        if is_gemini:
            if not url.endswith(":generateContent"):
                url = f"{url}/models/{self.model_name}:generateContent"
        elif use_openai:
            if not url.endswith("/chat/completions"):
                url = f"{url}/chat/completions"
        else:
            if not url.endswith("/api/chat"):  # only support ollama
                url = f"{url}/api/chat"

        headers = {"Content-Type": "application/json"}
        if is_gemini:
            headers["X-goog-api-key"] = self.api_key
        elif use_openai:
            headers["Authorization"] = f"Bearer {self.api_key}"

        headers.update(self.headers(oxy_request))

        if is_gemini:
            raw_msgs = await self._get_messages(oxy_request)
            messages = raw_msgs
            contents = [
                {
                    "role": ("user" if m["role"] == "user" else "model"),
                    "parts": [{"text": m["content"]}],
                }
                for m in raw_msgs
                if m.get("content")
            ]
            payload: dict = {"contents": contents}
            payload.update(self.llm_params)
            for k, v in oxy_request.arguments.items():
                if k != "messages":
                    payload[k] = v
        else:
            messages = await self._get_messages(oxy_request)
            payload = {
                "messages": messages,
                "model": self.model_name,
                "stream": True,
                "stream_options": {"include_usage": True},
            }
            self._build_payload(oxy_request, payload)

        if payload.get("stream", False) and (use_openai or not is_gemini):
            result_parts: list[str] = []
            usage_data = None
            async with httpx.AsyncClient(timeout=None) as client:
                # Apply before request hook
                url, headers, payload = self._before_request_hook(url, headers, payload)
                
                async with client.stream(
                    "POST", url, headers=headers, json=payload
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        if line.startswith("data:"):
                            line = line[5:].strip()
                        if line.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError as e:
                            logger.warning(
                                f"Failed to decode streaming chunk as JSON from {url}: {e} | line: {line[:200]}",
                                extra={
                                    "trace_id": oxy_request.current_trace_id,
                                    "node_id": oxy_request.node_id,
                                },
                                exc_info=True,
                            )
                            continue
                        except Exception as e:
                            logger.error(
                                f"Unexpected error parsing streaming chunk from {url}: {e} | line: {line[:200]}",
                                extra={
                                    "trace_id": oxy_request.current_trace_id,
                                    "node_id": oxy_request.node_id,
                                },
                                exc_info=True,
                            )
                            continue
                        # Extract usage from final chunk
                        if chunk.get("usage"):
                            usage_data = chunk["usage"]
                        if use_openai:
                            if chunk.get("choices"):
                                delta = chunk["choices"][0]["delta"].get(
                                    "content", ""
                                ) or chunk["choices"][0]["delta"].get(
                                    "reasoning_content", ""
                                )
                            else:
                                delta = ""
                        else:
                            delta = chunk.get("message", {}).get(
                                "content", ""
                            ) or chunk.get("message", {}).get("reasoning_content", "")
                        if delta:
                            result_parts.append(delta)
                            await oxy_request.send_message(
                                {
                                    "type": "stream",
                                    "content": {
                                        "delta": delta,
                                        "agent": oxy_request.caller,
                                        "node_id": oxy_request.node_id,
                                    },
                                }
                            )
                await oxy_request.send_message(
                    {
                        "type": "stream_end",
                        "content": {
                            "delta": "",
                            "agent": oxy_request.caller,
                            "node_id": oxy_request.node_id,
                        },
                    }
                )
            result = "".join(result_parts)
            token_usage = self._build_token_usage(usage_data, messages, result)
            return OxyResponse(
                state=OxyState.COMPLETED,
                output=result,
                extra={"usage": token_usage},
            )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Apply before request hook
            url, headers, payload = self._before_request_hook(url, headers, payload)
            
            http_response = await client.post(url, headers=headers, json=payload)
            http_response.raise_for_status()
            data = http_response.json()
            if "error" in data:
                error_message = data["error"].get("message", "Unknown error")
                raise ValueError(f"LLM API error: {error_message}")
            if is_gemini:
                result = (
                    data["candidates"][0]["content"]["parts"][0].get("text", "")
                    if data.get("candidates")
                    else ""
                )
                usage_data = data.get("usageMetadata")
            elif use_openai:
                response_message = data["choices"][0]["message"]
                result = response_message.get("content") or response_message.get(
                    "reasoning_content"
                )
                usage_data = data.get("usage")
            else:  # ollama
                result = data["message"]["content"]
                usage_data = data.get("usage")

            token_usage = self._build_token_usage(usage_data, messages, result)
            return OxyResponse(
                state=OxyState.COMPLETED,
                output=result,
                extra={"usage": token_usage},
            )
