import logging
from typing import List

from pydantic import BaseModel, Field

from ..utils.common_utils import process_attachments, to_json
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
                outs.append(prefix + exec_result.oxy_response.output.result)
            else:
                outs.append(prefix + exec_result.oxy_response.output)
        return "\n\n".join(outs)

    def to_content(self, is_multimodal_supported):
        query_attachments = []
        outs = []
        for exec_result in self.exec_results:
            prefix = f"Tool [{exec_result.executor}] execution result: "
            if isinstance(exec_result.oxy_response.output, OxyOutput):
                query_attachments.extend(
                    process_attachments(exec_result.oxy_response.output.attachments)
                )
                outs.append(prefix + to_json(exec_result.oxy_response.output.result))
            else:
                outs.append(prefix + to_json(exec_result.oxy_response.output))
        if is_multimodal_supported and query_attachments:
            return query_attachments + [
                {"type": "text", "text": "\n\n".join(outs)},
            ]
        else:
            return "\n\n".join(outs)
