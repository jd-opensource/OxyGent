"""Base flow module for OxyGent framework.

This module provides the BaseFlow class, which serves as the abstract base class for all
flows in the OxyGent system. Flows are specialized Oxy instances that orchestrate
complex workflows and coordinate multiple agents or tools.
"""

from pydantic import Field

from ..schemas import OxyRequest, OxyResponse
from .base_oxy import Oxy


class BaseFlow(Oxy):
    """Abstract base class for all flows in the OxyGent system.

    Attributes:
        category (str): Flow category identifier. Always "flow".
    """

    is_permission_required: bool = Field(
        True, description="Whether this flow requires permission."
    )
    category: str = Field("agent", description="")

    is_master: bool = Field(
        False, description="Whether this flow is a 'MASTER' (central controller)."
    )

    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        raise NotImplementedError("This method is not yet implemented")
