"""HTTP-based LLM implementation for remote language model APIs.

This module provides the HttpLLM class, which implements the BaseLLM interface for
communicating with remote language model APIs over HTTP. It supports various LLM
providers that follow OpenAI-compatible API standards.
"""

import json
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

        # Construct payload for the API request
        if is_gemini:
            raw_msgs = await self._get_messages(oxy_request)
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
            llm_config = {
                k: v
                for k, v in Config.get_llm_config().items()
                if k
                not in {
                    "cls",
                    "base_url",
                    "api_key",
                    "name",
                    "model_name",
                }
            }
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

        if payload.get("stream", False) and (use_openai or not is_gemini):
            result_parts: list[str] = []
            async with httpx.AsyncClient(timeout=None) as client:
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
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            logger.error(
                                e,
                                extra={
                                    "trace_id": oxy_request.current_trace_id,
                                    "node_id": oxy_request.node_id,
                                },
                            )
                        if use_openai:
                            delta = chunk["choices"][0]["delta"].get(
                                "content", ""
                            ) or chunk["choices"][0]["delta"].get(
                                "reasoning_content", ""
                            )
                        else:
                            delta = chunk.get("message", {}).get(
                                "content", ""
                            ) or chunk.get("message", {}).get("reasoning_content", "")
                        if delta:
                            result_parts.append(delta)
                            await oxy_request.send_message(
                                {"type": "stream", "content": {"delta": delta}}
                            )
            result = "".join(result_parts)
            return OxyResponse(state=OxyState.COMPLETED, output=result)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
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
            elif use_openai:
                response_message = data["choices"][0]["message"]
                result = response_message.get("content") or response_message.get(
                    "reasoning_content"
                )
            else:  # ollama
                result = data["message"]["content"]

            return OxyResponse(state=OxyState.COMPLETED, output=result)
