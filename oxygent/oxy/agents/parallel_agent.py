"""Parallel agent module for concurrent task execution.

This module provides the ParallelAgent class, which executes multiple tasks concurrently
across team members and aggregates their results into a unified response.
"""

import asyncio

from ...schemas import Memory, Message, OxyRequest, OxyResponse
from ...utils.common_utils import generate_uuid
from .local_agent import LocalAgent


class ParallelAgent(LocalAgent):
    """Agent that executes tasks in parallel across multiple team members.

    This agent distributes the same task to all available team members simultaneously
    and combines their responses.
    """

    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        """Execute the request in parallel across all team members.

        Args:
            oxy_request (OxyRequest): The request to execute across all team members.

        Returns:
            OxyResponse: Combined response with numbered results from all team members.
        """

        parallel_id = generate_uuid()
        oxy_responses = await asyncio.gather(
            *[
                oxy_request.call(
                    callee=permitted_tool_name,
                    arguments=oxy_request.arguments,
                    parallel_id=parallel_id,
                )
                for permitted_tool_name in self.permitted_tool_name_list
            ]
        )

        temp_memory = Memory()
        temp_memory.add_message(
            Message.system_message(
                f"""You are a helpful assistant, the user's question is:{oxy_request.get_query()}.
Please summarize the results of the parallel execution of the above tasks."""
            )
        )
        temp_memory.add_message(
            Message.user_message(
                "The parallel resulte are as following:\n"
                + "\n".join(
                    [
                        str(i + 1) + ". " + res.output
                        for i, res in enumerate(oxy_responses)
                    ]
                )
            )
        )
        # llm call
        return await oxy_request.call(
            callee=self.llm_model,
            arguments={
                "messages": temp_memory.to_dict_list(
                    short_memory_size=self.short_memory_size
                )
            },
        )
