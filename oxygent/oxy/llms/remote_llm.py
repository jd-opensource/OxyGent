from typing import Callable, Dict, Optional

from pydantic import Field, field_validator

from ...schemas import OxyRequest, OxyResponse
from .base_llm import BaseLLM


class RemoteLLM(BaseLLM):
    """Large Language Model implementation.

    This class provides a concrete implementation of BaseLLM for communicating
    with remote LLM APIs. It handles API authentication, request
    formatting, and response parsing for OpenAI-compatible APIs.

    Attributes:
        api_key: The API key for authentication with the LLM service.
        base_url: The base URL endpoint for the LLM API.
        model_name: The specific model name to use for requests.
    """

    api_key: Optional[str] = Field(default=None)
    base_url: Optional[str] = Field("")
    model_name: Optional[str] = Field("")
    headers: Dict[str, str] | Callable[[OxyRequest], Dict[str, str]] = Field(
        default=lambda oxy_request: {},
        exclude=True,
        description="Extra HTTP headers or a function that returns headers",
    )

    @field_validator("base_url", "model_name")
    @classmethod
    def not_empty(cls, value, info):
        key = info.field_name

        if value is None:
            raise ValueError(
                f"Environment variable '{key}' is not set and no default value provided. Please check your .env or system env."
            )

        if not isinstance(value, str):
            raise ValueError(
                f"Environment variable '{key}' type error: expected str, got {type(value).__name__}."
            )

        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string")

        return value

    @field_validator("headers")
    @classmethod
    def convert_dict_to_function(cls, v):
        """自动将dict转换为返回该dict的函数"""
        if isinstance(v, dict):
            # 将dict转换为返回该dict的函数
            def headers_func(request: OxyRequest) -> Dict[str, str]:
                return v

            return headers_func
        elif callable(v):
            # 如果已经是函数，直接返回
            return v
        else:
            raise ValueError("headers must be either a dict or a callable")

    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        raise NotImplementedError("This method is not yet implemented")
