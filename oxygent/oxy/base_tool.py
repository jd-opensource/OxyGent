"""Base tool module for OxyGent framework.

This module provides the BaseTool class, which serves as the abstract base class for all
tools in the OxyGent system. Tools are specialized Oxy instances that typically require
permissions and have shorter timeout periods.
"""

from pydantic import Field

from ..schemas import OxyRequest, OxyResponse
from .base_oxy import Oxy


class BaseTool(Oxy):
    """Abstract base class for all tools in the OxyGent system.

    Attributes:
        is_permission_required (bool): Whether permission is required to execute
            this tool. Defaults to True for security.
        category (str): Tool category identifier. Always "tool".
        timeout (float): Execution timeout in seconds. Defaults to 60 seconds.
    """

    is_permission_required: bool = Field(
        True, description="Whether permission is required for execution"
    )
    category: str = Field("tool", description="Tool category identifier")
    timeout: float = Field(60, description="Timeout in seconds.")

    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        raise NotImplementedError("This method is not yet implemented")
