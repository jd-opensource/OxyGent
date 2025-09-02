"""llm.py LLM status module.

The module difines the status and the output of the LLM.
"""

from enum import Enum
from typing import Union

from pydantic import BaseModel, Field


class LLMState(Enum):
    TOOL_CALL = "tool_call"
    ANSWER = "answer"
    ERROR_PARSE = "error_parse"
    ERROR_CALL = "error_call"


class LLMResponse(BaseModel):
    state: LLMState
    output: Union[str, dict, list]
    ori_response: str = Field(default="")
