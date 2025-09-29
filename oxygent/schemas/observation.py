import logging
from typing import List

from pydantic import BaseModel, Field

from ..utils.common_utils import to_json
from .oxy import OxyOutput, OxyResponse

logger = logging.getLogger(__name__)


class ExecResult(BaseModel):
    executor: str
    oxy_response: OxyResponse


class Observation(BaseModel):
    """Observation for multimodal."""

    exec_results: List[ExecResult] = Field(default_factory=list)

    def add_exec_result(self, exec_result: ExecResult) -> None:
        """Add a exec result to exec_results."""
        self.exec_results.append(exec_result)

    def to_str(self):
        outs = []
        for exec_result in self.exec_results:
            prefix = f"Tool [{exec_result.executor}] execution result: "
            if isinstance(exec_result.oxy_response.output, OxyOutput):
                outs.append(prefix + to_json(exec_result.oxy_response.output.result))
            else:
                outs.append(prefix + to_json(exec_result.oxy_response.output))
        return "\n\n".join(outs)
