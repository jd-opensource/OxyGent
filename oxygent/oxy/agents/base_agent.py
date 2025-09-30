"""Base agent module for OxyGent framework.

This module provides the BaseAgent class, which serves as the foundation for all agent
implementations in the OxyGent system. It handles trace management, data persistence,
and common agent lifecycle operations.
"""

import logging
from typing import Any

from pydantic import Field

from ...config import Config
from ...schemas import OxyRequest, OxyResponse
from ...utils.common_utils import generate_uuid, get_format_time, to_json
from ..base_flow import BaseFlow

logger = logging.getLogger(__name__)


class BaseAgent(BaseFlow):
    """Base class for all agents in the OxyGent system.

    This class extends the Oxy base class and provides common functionality for
    agent implementations including permission management, trace handling, and
    data persistence operations.

    Attributes:
        category (str): The category of this tool/agent. Defaults to "agent".
        input_schema (dict[str, Any]): Input schema configuration for the agent.
    """

    category: str = Field("agent", description="tool type")

    input_schema: dict[str, Any] = Field(
        default_factory=Config.get_agent_input_schema,
        description="input parameters schema",
    )

    async def _pre_process(self, oxy_request: OxyRequest) -> OxyRequest:
        """Pre-process the request before handling.

        This method handles trace management and root trace ID setup for user requests.
        It retrieves historical trace information from Elasticsearch and prepares the
        trace hierarchy for the current request.
        """
        oxy_request = await super()._pre_process(oxy_request)

        # TODO: Move this code to user class for better organization
        if oxy_request.caller_category == "user":
            # Retrieve historical trace_id list for the request
            if oxy_request.from_trace_id:
                # Query Elasticsearch for the parent trace information
                es_response = await self.mas.es_client.search(
                    Config.get_app_name() + "_trace",
                    {"query": {"term": {"_id": oxy_request.from_trace_id}}},
                )

                # Extract root trace IDs from the parent trace if available
                if (
                    es_response
                    and es_response["hits"]["hits"]
                    and es_response["hits"]["hits"][0]["_source"]["root_trace_ids"]
                ):
                    oxy_request.root_trace_ids = es_response["hits"]["hits"][0][
                        "_source"
                    ]["root_trace_ids"]
                else:
                    oxy_request.root_trace_ids = []

                # Add the current from_trace_id to the root trace IDs
                oxy_request.root_trace_ids.append(oxy_request.from_trace_id)

        return oxy_request

    async def _pre_save_data(self, oxy_request: OxyRequest):
        """Save preliminary trace data before processing the request.

        This method persists initial trace information to Elasticsearch for
        user requests, creating a record of the request before it's processed.

        Args:
            oxy_request (OxyRequest): The request object containing trace data
                to be saved.
        """
        await super()._pre_save_data(oxy_request)

        if oxy_request.caller_category == "user":
            if self.mas and self.mas.es_client:
                # save shared_data
                shared_data_schema = Config.get_es_schema_shared_data().get(
                    "properties", {}
                )
                if shared_data_schema:
                    to_save_shared_data = {
                        k: v
                        for k, v in oxy_request.shared_data.items()
                        if k in shared_data_schema
                    }
                else:
                    to_save_shared_data = to_json(oxy_request.shared_data)
                # save group_data
                group_data_schema = Config.get_es_schema_group_data().get(
                    "properties", {}
                )
                if group_data_schema:
                    to_save_group_data = {
                        k: v
                        for k, v in oxy_request.group_data.items()
                        if k in group_data_schema
                    }
                else:
                    to_save_group_data = to_json(oxy_request.group_data)
                # Store the current conversation trace record
                await self.mas.es_client.index(
                    Config.get_app_name() + "_trace",
                    doc_id=oxy_request.current_trace_id,
                    body={
                        "request_id": oxy_request.request_id,
                        "trace_id": oxy_request.current_trace_id,
                        "shared_data": to_save_shared_data,
                        "group_id": oxy_request.group_id,
                        "group_data": to_save_group_data,
                        "from_trace_id": oxy_request.from_trace_id,
                        "root_trace_ids": oxy_request.root_trace_ids,
                        "input": to_json(oxy_request.arguments),
                        "callee": oxy_request.callee,
                        "output": "",  # Output will be filled in post_save_data
                        "create_time": get_format_time(),
                    },
                )
            else:
                logger.warning(f"Save {oxy_request.callee} pre trace data error")

    async def _post_save_data(self, oxy_response: OxyResponse):
        """Save complete trace and history data after processing the request.

        This method updates the trace record with the response output and
        optionally saves conversation history for user requests.

        Args:
            oxy_response (OxyResponse): The response object containing the
                processed result and associated request data.
        """
        await super()._post_save_data(oxy_response)
        oxy_request = oxy_response.oxy_request

        if oxy_request.caller_category == "user":
            # Update trace record with the response output
            if self.mas and self.mas.es_client:
                # save shared_data
                shared_data_schema = Config.get_es_schema_shared_data().get(
                    "properties", {}
                )
                if shared_data_schema:
                    to_save_shared_data = {
                        k: v
                        for k, v in oxy_request.shared_data.items()
                        if k in shared_data_schema
                    }
                else:
                    to_save_shared_data = to_json(oxy_request.shared_data)
                # save group_data
                group_data_schema = Config.get_es_schema_group_data().get(
                    "properties", {}
                )
                if group_data_schema:
                    to_save_group_data = {
                        k: v
                        for k, v in oxy_request.group_data.items()
                        if k in group_data_schema
                    }
                else:
                    to_save_group_data = to_json(oxy_request.group_data)
                await self.mas.es_client.index(
                    Config.get_app_name() + "_trace",
                    doc_id=oxy_request.current_trace_id,
                    body={
                        "request_id": oxy_request.request_id,
                        "trace_id": oxy_request.current_trace_id,
                        "shared_data": to_save_shared_data,
                        "group_id": oxy_request.group_id,
                        "group_data": to_save_group_data,
                        "from_trace_id": oxy_request.from_trace_id,
                        "root_trace_ids": oxy_request.root_trace_ids,
                        "input": to_json(oxy_request.arguments),
                        "callee": oxy_request.callee,
                        "output": to_json(oxy_response.output),
                        "create_time": get_format_time(),
                    },
                )
            else:
                logger.warning(f"Save {oxy_request.callee} post trace data error")

        # Save conversation history if requested
        if oxy_request.is_save_history:
            if self.mas and self.mas.es_client:
                # Prepare history data with query-answer pair
                history = {
                    "query": oxy_request.get_query(),
                    "answer": oxy_response.output,
                }
                history.update(oxy_response.extra)

                # Store the conversation history record
                history_id = generate_uuid()
                await self.mas.es_client.index(
                    Config.get_app_name() + "_history",
                    doc_id=history_id,
                    body={
                        "history_id": history_id,
                        "session_name": oxy_request.session_name,
                        "trace_id": oxy_request.current_trace_id,
                        "memory": to_json(history),
                        "create_time": get_format_time(),
                    },
                )
            else:
                logger.warning(f"Save {oxy_request.callee} history data error")
