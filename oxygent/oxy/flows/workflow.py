"""Workflow module for custom workflow execution.

This module provides the Workflow class, which enables execution of custom workflow
functions within the OxyGent flow system. It serves as a bridge between the flow
framework and user-defined workflow logic.
"""

from typing import Callable, Optional

from pydantic import Field

from ...schemas import OxyRequest, OxyResponse, OxyState
from ..base_flow import BaseFlow


class Workflow(BaseFlow):
    """Flow that executes custom workflow functions.

    Attributes:
        func_execute (Optional[Callable]): The custom workflow function to execute.
            This function should accept an OxyRequest and return an OxyResponse.
    """

    func_workflow: Optional[Callable] = Field(None, exclude=True, description="")

    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        return OxyResponse(
            state=OxyState.COMPLETED, output=await self.func_workflow(oxy_request)
        )
