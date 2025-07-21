"""Parallel flow module for concurrent execution workflows.

This module provides the ParallelFlow class, which orchestrates concurrent execution of
multiple tools or agents and aggregates their results into a unified response.
"""

import asyncio

from ...schemas import OxyRequest, OxyResponse, OxyState
from ..base_flow import BaseFlow


class ParallelFlow(BaseFlow):
    """Flow that executes multiple tools or agents concurrently."""

    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        """Execute the request concurrently across all permitted tools.

        Distributes the same request to all tools in the permitted_tool_name_list
        simultaneously and aggregates their outputs into a unified response.
        """
        # Execute the same request concurrently across all permitted tools
        oxy_responses = await asyncio.gather(
            *[
                oxy_request.call(
                    callee=permitted_tool_name, arguments=oxy_request.arguments
                )
                for permitted_tool_name in self.permitted_tool_name_list
            ]
        )

        # Aggregate all outputs into a single response
        oxy_response = OxyResponse(
            state=OxyState.COMPLETED,
            output="The following are the results from multiple executions:"
            + "\n".join([res.output for res in oxy_responses]),
        )
        return oxy_response
