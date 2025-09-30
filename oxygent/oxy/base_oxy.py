"""Base OxyGent framework module for agent and tool abstraction.

This module provides the core Oxy class, which serves as the abstract base class for all
agents and tools in the OxyGent system. It defines the execution lifecycle, message
handling, logging, and data persistence patterns.
"""

import asyncio
import inspect
import json
import logging
import traceback
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

# from ..mas import MAS
from ..config import Config
from ..schemas import OxyRequest, OxyResponse, OxyState
from ..utils.common_utils import (
    filter_json_types,
    generate_uuid,
    get_format_time,
    get_md5,
    to_json,
)

logger = logging.getLogger(__name__)


def ensure_async(func: Callable) -> Callable:
    """
    Ensure a function is async. If it's sync, wrap it to make it async.

    Args:
        func: The function to ensure is async

    Returns:
        An async function
    """
    if func is None:
        return None

    if inspect.iscoroutinefunction(func):
        return func

    async def async_wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return async_wrapper


async def default_async_identity(x):
    """Default async identity function that returns input unchanged."""
    return x


class Oxy(BaseModel, ABC):
    """Abstract base class for all agents and tools in the OxyGent system.

    This class defines the core execution lifecycle, permission management,
    message handling, and data persistence patterns. It provides a unified
    interface for both local and remote execution with comprehensive logging
    and error handling capabilities.

    Attributes:
        name (str): Unique identifier for the agent/tool.
        desc (str): Human-readable description of functionality.
        category (str): Category classification (tool, agent, etc.).
        is_permission_required (bool): Whether permission is needed for execution.
        semaphore (int): Maximum number of concurrent executions.
        timeout (float): Execution timeout in seconds.
        retries (int): Number of retry attempts on failure.
    """

    name: str = Field(..., description="Identifier for the agent.")
    desc: str = Field("", description="Description of the agent's functionality.")
    category: str = Field("tool", description="Category classification")
    class_name: Optional[str] = Field(None, description="Class name")

    input_schema: dict[str, Any] = Field(
        default_factory=dict, description="Input schema definition"
    )
    desc_for_llm: str = Field("", description="Description shown to LLM")

    is_entrance: bool = Field(False, description="Whether this is a MAS entry point")

    is_entrance: bool = Field(False, description="Whether is the entrance of MAS")

    is_permission_required: bool = Field(False, description="Whether needs permission")
    is_save_data: bool = Field(True, description="Whether to save data")
    permitted_tool_name_list: list = Field(
        default_factory=list, description="List of tools this entity can call"
    )
    extra_permitted_tool_name_list: list = Field(
        default_factory=list, description="Additional tool permissions"
    )

    is_send_tool_call: bool = Field(
        default_factory=Config.get_message_is_send_tool_call,
        description="Whether to send tool_call messages",
    )
    is_send_observation: bool = Field(
        default_factory=Config.get_message_is_send_observation,
        description="Whether to send observation messages",
    )
    is_send_answer: bool = Field(
        default_factory=Config.get_message_is_send_answer,
        description="Whether to send answer messages",
    )

    is_detailed_tool_call: bool = Field(
        default_factory=Config.get_log_is_detailed_tool_call,
        description="Whether to show detailed tool_call logs",
    )
    is_detailed_observation: bool = Field(
        default_factory=Config.get_log_is_detailed_observation,
        description="Whether to show detailed observation logs",
    )

    func_process_input: Callable = Field(
        default_async_identity, exclude=True, description="Input processing function"
    )
    func_process_output: Callable = Field(
        default_async_identity, exclude=True, description="Output processing function"
    )

    func_format_input: Optional[Callable] = Field(
        default_async_identity,
        exclude=True,
        description="Input formatting function for callee",
    )
    func_format_output: Optional[Callable] = Field(
        default_async_identity,
        exclude=True,
        description="Output formatting function for caller",
    )
    func_execute: Optional[Callable] = Field(
        None, exclude=True, description="Execution function"
    )

    func_interceptor: Optional[Callable] = Field(
        None, exclude=True, description="Interceptor function"
    )

    mas: Optional[Any] = Field(None, exclude=True, description="MAS instance reference")

    friendly_error_text: Optional[str] = Field(
        None, description="User-friendly error message"
    )
    semaphore: int = Field(16, description="Concurrency limit")
    timeout: float = Field(3600, description="Timeout in seconds.")
    retries: int = Field(2)
    delay: float = Field(1.0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(self.semaphore)
        self._ensure_async_functions()
        self._set_desc_for_llm()

    def _ensure_async_functions(self):
        """Ensure all function fields are async. Convert sync functions to async if needed."""
        # List of function field names to check and convert
        func_fields = [
            "func_process_input",
            "func_process_output",
            "func_format_input",
            "func_format_output",
            "func_execute",
            "func_interceptor",
        ]

        for field_name in func_fields:
            func = getattr(self, field_name, None)
            if func is not None:
                async_func = ensure_async(func)
                object.__setattr__(self, field_name, async_func)

    def model_post_init(self, __context):
        if self.class_name is None:
            object.__setattr__(self, "class_name", self.__class__.__name__)

    def set_mas(self, mas):
        self.mas = mas

    def add_permitted_tool(self, tool_name: str):
        """Add a tool to the permitted tools list."""
        if tool_name in self.permitted_tool_name_list:
            logger.warning(f"Tool {tool_name} already exists.")
        else:
            self.permitted_tool_name_list.append(tool_name)

    def add_permitted_tools(self, tool_names: list):
        """Add multiple tools to the permitted tools list."""
        for tool_name in tool_names:
            self.add_permitted_tool(tool_name)

    def _set_desc_for_llm(self):
        """Generate LLM-friendly description from input schema."""
        args_desc = []
        if "properties" in self.input_schema:
            for param_name, param_info in self.input_schema["properties"].items():
                # Skip system parameters that shouldn't be shown to LLM
                if param_info.get("description", "No description") == "SystemArg":
                    continue
                param_type = param_info.get("type", "string")
                param_key = "properties" if param_type == "object" else "description"
                arg_desc = f"- {param_name}: {param_type}, {param_info.get(param_key, 'No description')}"
                if param_name in self.input_schema.get("required", []):
                    arg_desc += " (required)"
                args_desc.append(arg_desc)

        self.desc_for_llm = f"""
            Tool: {self.name}
            Description: {self.desc}
            Arguments:
            {chr(10).join(args_desc)}
            """

    async def init(self):
        self._set_desc_for_llm()

    async def _pre_process(self, oxy_request: OxyRequest) -> OxyRequest:
        """Pre-process the request before execution."""
        # Initialize the parameters
        if not oxy_request.node_id:
            oxy_request.node_id = generate_uuid()
        oxy_request.callee = self.name
        oxy_request.callee_category = self.category
        oxy_request.call_stack.append(self.name)
        oxy_request.node_id_stack.append(oxy_request.node_id)
        # Handle input
        oxy_request = await self.func_process_input(oxy_request)
        return oxy_request

    async def _pre_log(self, oxy_request: OxyRequest):
        """Log the tool call information."""
        query = (
            oxy_request.arguments.get("query", "...")
            if self.is_detailed_tool_call
            else "..."
        )
        logger.info(
            f"{' >>> '.join(oxy_request.call_stack)}  : {query}",
            extra={
                "trace_id": oxy_request.current_trace_id,
                "node_id": oxy_request.node_id,
                "color": Config.get_log_color_tool_call(),
            },
        )

    async def _request_interceptor(self, oxy_request: OxyRequest):
        if (
            oxy_request.reference_trace_id
            and oxy_request.is_load_data_for_restart
            and self.mas
            and self.mas.es_client
            and self.category in ["llm", "tool"]
        ):
            if oxy_request.restart_node_id:
                es_response = await self.mas.es_client.search(
                    Config.get_app_name() + "_node",
                    {
                        "query": {
                            "bool": {
                                "must": [
                                    {
                                        "term": {
                                            "trace_id": oxy_request.reference_trace_id
                                        }
                                    },
                                    {"term": {"input_md5": oxy_request.input_md5}},
                                ]
                            }
                        },
                        "size": 1,
                    },
                )
            logging.info(f"ES search returned {len(es_response['hits']['hits'])} hits")
            if es_response["hits"]["hits"]:
                current_node_order = es_response["hits"]["hits"][0]["_source"][
                    "update_time"
                ]
                if current_node_order < oxy_request.restart_node_order:
                    restart_node_output = es_response["hits"]["hits"][0]["_source"][
                        "output"
                    ]

                    logger.info(
                        f"{' <<< '.join(oxy_request.call_stack)}  Load from ES: {restart_node_output}",
                        extra={
                            "trace_id": oxy_request.current_trace_id,
                            "node_id": oxy_request.node_id,
                        },
                    )

                    oxy_response = OxyResponse(
                        state=OxyState(
                            es_response["hits"]["hits"][0]["_source"]["state"]
                        ),
                        output=restart_node_output,
                        extra=json.loads(
                            es_response["hits"]["hits"][0]["_source"]["extra"]
                        ),
                    )
                    oxy_response.oxy_request = oxy_request
                    return await self._format_output(oxy_response)
                elif (
                    oxy_request.restart_node_output
                    and current_node_order == oxy_request.restart_node_order
                ):
                    oxy_request.is_load_data_for_restart = False
                    restart_node_output = oxy_request.restart_node_output
                    logger.info(
                        f"{' <<< '.join(oxy_request.call_stack)}  Wrote by user: {restart_node_output}",
                        extra={
                            "trace_id": oxy_request.current_trace_id,
                            "node_id": oxy_request.node_id,
                        },
                    )

                    oxy_response = OxyResponse(
                        state=OxyState(
                            es_response["hits"]["hits"][0]["_source"]["state"]
                        ),
                        output=restart_node_output,
                        extra=json.loads(
                            es_response["hits"]["hits"][0]["_source"]["extra"]
                        ),
                    )
                    oxy_response.oxy_request = oxy_request
                    return await self._format_output(oxy_response)
                else:
                    oxy_request.is_load_data_for_restart = False
            else:
                logger.warning(
                    f"{' === '.join(oxy_request.call_stack)}  : load null from ES.",
                    extra={
                        "trace_id": oxy_request.current_trace_id,
                        "node_id": oxy_request.node_id,
                    },
                )

    async def _pre_save_data(self, oxy_request: OxyRequest):
        if not self.is_save_data:
            return
        if self.mas and self.mas.es_client:
            callee_name = oxy_request.callee
            callee_cat = oxy_request.callee_category
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
            await self.mas.es_client.index(
                Config.get_app_name() + "_node",
                doc_id=oxy_request.node_id,
                body={
                    "node_id": oxy_request.node_id,
                    "node_type": callee_cat,
                    "trace_id": oxy_request.current_trace_id,
                    "group_id": oxy_request.group_id,
                    "request_id": oxy_request.request_id,
                    "caller": oxy_request.caller,
                    "callee": callee_name,
                    "parallel_id": oxy_request.parallel_id,
                    "father_node_id": oxy_request.father_node_id,
                    "call_stack": oxy_request.call_stack,
                    "node_id_stack": oxy_request.node_id_stack,
                    "pre_node_ids": oxy_request.pre_node_ids,
                    "shared_data": to_save_shared_data,
                    "create_time": get_format_time(),
                },
            )
        else:
            logger.warning(f"Node {oxy_request.callee} data unsaved.")

    async def _format_input(self, oxy_request: OxyRequest) -> OxyRequest:
        """Format input arguments for execution."""
        return await self.func_format_input(oxy_request)

    async def _pre_send_message(self, oxy_request: OxyRequest):
        """Send tool call message to frontend if enabled."""
        # Send tool_call message to frontend
        if self.is_send_tool_call:
            if Config.get_message_is_send_full_arguments():
                arguments = filter_json_types(oxy_request.arguments)
            else:
                arguments = {
                    k: v for k, v in oxy_request.arguments.items() if k in ["query"]
                }
            await oxy_request.send_message(
                {
                    "type": "tool_call",
                    "content": {
                        "node_id": oxy_request.node_id,
                        "caller": oxy_request.caller,
                        "callee": oxy_request.callee,
                        "caller_category": oxy_request.caller_category,
                        "callee_category": oxy_request.callee_category,
                        "call_stack": oxy_request.call_stack,
                        "arguments": arguments,
                        "request_id": oxy_request.request_id,
                    },
                }
            )

    async def _before_execute(self, oxy_request: OxyRequest) -> OxyRequest:
        return oxy_request

    @abstractmethod
    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        pass

    async def _handle_exception(self, e):
        pass

    async def _after_execute(self, oxy_response: OxyResponse) -> OxyResponse:
        return oxy_response

    async def _post_process(self, oxy_response: OxyResponse) -> OxyResponse:
        return await self.func_process_output(oxy_response)

    async def _post_log(self, oxy_response: OxyResponse):
        """Log the execution result."""
        obs = oxy_response.output if self.is_detailed_observation else "..."
        oxy_request = oxy_response.oxy_request
        logger.info(
            f"{' <<< '.join(oxy_request.call_stack)}  : {obs}",
            extra={
                "trace_id": oxy_request.current_trace_id,
                "node_id": oxy_request.node_id,
                "color": Config.get_log_color_observation(),
            },
        )

    async def _post_save_data(self, oxy_response: OxyResponse):
        """Save execution data to Elasticsearch for logging and training."""
        if not self.is_save_data:
            return
        oxy_request = oxy_response.oxy_request
        oxy_input = {
            "class_attr": self.model_dump(
                exclude=set(Oxy.model_fields.keys()) - {"class_name"}
            ),
            "arguments": oxy_request.arguments,
        }
        callee_name = oxy_request.callee
        callee_cat = oxy_request.callee_category
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
            await self.mas.es_client.update(
                Config.get_app_name() + "_node",
                doc_id=oxy_request.node_id,
                body={
                    "node_id": oxy_request.node_id,
                    "node_type": callee_cat,
                    "trace_id": oxy_request.current_trace_id,
                    "group_id": oxy_request.group_id,
                    "request_id": oxy_request.request_id,
                    "caller": oxy_request.caller,
                    "callee": callee_name,
                    "shared_data": to_save_shared_data,
                    "input": to_json(oxy_input),
                    "input_md5": oxy_request.input_md5,
                    "output": to_json(oxy_response.output),
                    "state": oxy_response.state.value,
                    "extra": to_json(oxy_response.extra),
                    "update_time": get_format_time(),
                },
            )
        else:
            logger.warning(f"Node {oxy_request.callee} data unsaved.")

    async def _format_output(self, oxy_response: OxyResponse) -> OxyResponse:
        oxy_response = await self.func_format_output(oxy_response)
        if oxy_response.state is OxyState.FAILED and self.friendly_error_text:
            oxy_response.output = self.friendly_error_text
        return oxy_response

    async def _post_send_message(self, oxy_response: OxyResponse):
        """Send observation and answer messages to frontend if enabled."""
        oxy_request = oxy_response.oxy_request

        # Send observation message to frontend
        if self.is_send_observation:
            await oxy_request.send_message(
                {
                    "type": "observation",
                    "content": {
                        "node_id": oxy_request.node_id,
                        "caller": oxy_request.caller,
                        "callee": oxy_request.callee,
                        "caller_category": oxy_request.caller_category,
                        "callee_category": oxy_request.callee_category,
                        "call_stack": oxy_request.call_stack,
                        "output": oxy_response.output,
                        "current_trace_id": oxy_request.current_trace_id,
                        "request_id": oxy_request.request_id,
                    },
                }
            )

        # Send additional observation-answer message to frontend
        if self.is_send_answer and oxy_request.caller_category == "user":
            await oxy_request.send_message(
                {
                    "type": "answer",
                    "content": oxy_response.output,
                    "current_trace_id": oxy_request.current_trace_id,
                    "request_id": oxy_request.request_id,
                }
            )

    async def execute(self, oxy_request: OxyRequest) -> OxyResponse:
        """Execute the complete lifecycle of an Oxy operation.

        This method orchestrates the entire execution pipeline including:
        - Pre-processing
        - logging and data saving
        - Input formatting
        - Pre-send message handling

        - validation and permission checks

        - Before execution hooks
        - Execution with retry logic
        - After execution hooks


        - Post-processing
        - Logging and data saving
        - Output formatting
        - Post-send message handling
        """
        async with self._semaphore:
            # Pre-process
            oxy_request = await self._pre_process(oxy_request)
            await self._pre_log(oxy_request)

            key_to_md5 = {
                k: v
                for k, v in oxy_request.arguments.items()
                if isinstance(v, (int, str, float, list, dict, tuple, set))
            }
            oxy_request.input_md5 = get_md5(to_json(key_to_md5))
            result = await self._request_interceptor(oxy_request)
            if isinstance(result, OxyResponse):
                return result

            event = asyncio.Event()
            if self.mas:

                def pre_done_callback(task):
                    self.mas.background_tasks.discard(task)
                    event.set()

                pre_save_data_task = asyncio.create_task(
                    self._pre_save_data(oxy_request)
                )

                pre_save_data_task.add_done_callback(pre_done_callback)
                self.mas.background_tasks.add(pre_save_data_task)
            else:
                logger.warning(
                    "Temporary invocation without storing data.",
                    extra={
                        "trace_id": oxy_request.current_trace_id,
                        "node_id": oxy_request.node_id,
                    },
                )
            oxy_request = await self._format_input(oxy_request)
            await self._pre_send_message(oxy_request)

            oxy_request = await self._before_execute(oxy_request)

            # Execute the request with retry logic
            attempt = 0
            while attempt < self.retries:
                try:
                    if self.func_interceptor:
                        error_message = await self.func_interceptor(oxy_request)
                        if error_message:
                            oxy_response = OxyResponse(
                                state=OxyState.SKIPPED,
                                output=error_message,
                            )
                            break
                    if self.func_execute:
                        oxy_response = await self.func_execute(oxy_request)
                    else:
                        oxy_response = await self._execute(oxy_request)
                    break
                except asyncio.CancelledError:
                    # if the task is cancelled, log and return a canceled response
                    logger.error(
                        f"oxy {self.name} was cancelled---",
                        extra={
                            "trace_id": oxy_request.current_trace_id,
                            "node_id": oxy_request.node_id,
                        },
                    )
                    oxy_response = OxyResponse(
                        state=OxyState.CANCELED,
                        output=f"Tool {self.name} was cancelled",
                    )
                    oxy_response.oxy_request = oxy_request
                    asyncio.create_task(self._post_save_data(oxy_response))
                    raise
                except Exception as e:
                    # Handle exceptions and retry logic
                    await self._handle_exception(e)
                    attempt += 1
                    logger.warning(
                        f"Error executing oxy {self.name}: {str(e)}. Attempt {attempt} of {self.retries}.",
                        extra={
                            "trace_id": oxy_request.current_trace_id,
                            "node_id": oxy_request.node_id,
                        },
                    )
                    logger.error(
                        traceback.format_exc(),
                        extra={
                            "trace_id": oxy_request.current_trace_id,
                            "node_id": oxy_request.node_id,
                        },
                    )
                    if attempt < self.retries:
                        await asyncio.sleep(self.delay)
                    else:
                        error_msg = traceback.format_exc()
                        logger.error(
                            f"Max retries reached. Failed. {error_msg}",
                            extra={
                                "trace_id": oxy_request.current_trace_id,
                                "node_id": oxy_request.node_id,
                            },
                        )
                        oxy_response = OxyResponse(
                            state=OxyState.FAILED,
                            output=f"Error executing oxy {self.name}: {str(e)}",
                        )

            oxy_response.oxy_request = oxy_request
            oxy_response = await self._after_execute(oxy_response)

            # Post-process
            oxy_response = await self._post_process(oxy_response)
            await self._post_log(oxy_response)

            if self.mas:

                async def _post_save_data_task(oxy_response):
                    await event.wait()
                    await self._post_save_data(oxy_response)

                if oxy_request.is_async_storage:
                    post_save_data_task = asyncio.create_task(
                        _post_save_data_task(oxy_response)
                    )
                    post_save_data_task.add_done_callback(
                        self.mas.background_tasks.discard
                    )
                    self.mas.background_tasks.add(post_save_data_task)
                else:
                    await _post_save_data_task(oxy_response)
            else:
                logger.warning(
                    "Temporary invocation without storing data.",
                    extra={
                        "trace_id": oxy_request.current_trace_id,
                        "node_id": oxy_request.node_id,
                    },
                )

            oxy_response = await self._format_output(oxy_response)
            await self._post_send_message(oxy_response)

            return oxy_response
