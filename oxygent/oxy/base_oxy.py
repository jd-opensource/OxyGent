"""Base OxyGent framework module for agent and tool abstraction.

This module provides the core Oxy class, which serves as the abstract base class for all
agents and tools in the OxyGent system. It defines the execution lifecycle, message
handling, logging, and data persistence patterns.
"""

import asyncio
import inspect
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

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


def _serialize_data_for_es(
    data: dict[str, Any], schema_getter: Callable[[], dict[str, Any]]
) -> Any:
    """Serialize shared_data or group_data for ES storage.

    If a schema is configured (via *schema_getter*), only the keys present in
    the schema are kept; otherwise the whole dict is serialised to JSON.
    """
    schema = schema_getter().get("properties", {})
    if schema:
        return {k: v for k, v in data.items() if k in schema}
    return to_json(data)


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

    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)

    return async_wrapper


async def default_async_identity(x: Any) -> Any:
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
    alias: Optional[str] = Field(
        None,
        description="Human-friendly display name shown in the web UI; falls back to name.",
    )
    desc: str = Field("", description="Description of the agent's functionality.")
    category: str = Field("tool", description="Category classification")
    class_name: Optional[str] = Field(None, description="Class name")

    input_schema: dict[str, Any] = Field(
        default_factory=dict, description="Input schema definition"
    )
    system_args: list[str] = Field(
        default_factory=list,
        description="System-level arguments extracted from input_schema",
    )
    desc_for_llm: str = Field("", description="Description shown to LLM")

    is_entrance: bool = Field(False, description="Whether this is a MAS entry point")

    is_permission_required: bool = Field(False, description="Whether needs permission")
    is_save_data: bool = Field(True, description="Whether to save data")
    permitted_tool_name_list: list[str] = Field(
        default_factory=list, description="List of tools this entity can call"
    )
    permitted_oxy: list[str] = Field(
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
    semaphore: int = Field(
        default_factory=Config.get_oxy_semaphore, description="Concurrency limit"
    )
    timeout: float = Field(
        default_factory=Config.get_oxy_timeout, description="Timeout in seconds."
    )
    retries: int = Field(
        default_factory=Config.get_oxy_retries,
        description="Number of retry attempts on failure",
    )
    delay: float = Field(
        default_factory=Config.get_oxy_delay,
        description="Delay in seconds between retries",
    )

    preceding_oxy: Optional[list[str]] = Field(
        default_factory=list,
        description="A list of oxy names that must be called before the current oxy.",
    )
    preceding_placeholder: str = Field(
        "preceding_text",
        description="Key name in arguments for injecting preceding Oxy outputs",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(self.semaphore)
        self._ensure_async_functions()
        self._set_desc_for_llm()
        self.permitted_oxy.extend(self.preceding_oxy)

    _async_func_fields = [
        "func_process_input",
        "func_process_output",
        "func_format_input",
        "func_format_output",
        "func_execute",
        "func_interceptor",
        "func_map_memory_order",
        "func_mock_process",
        "func_parse_llm_response",
        "func_parse_planner_response",
        "func_parse_replanner_response",
        "func_process",
        "func_reflexion",
        "func_retrieve_knowledge",
        "func_workflow",
    ]

    def _ensure_async_functions(self) -> None:
        """Ensure all function fields are async. Convert sync functions to async if needed."""
        for field_name in self._async_func_fields:
            func = getattr(self, field_name, None)
            if func is not None and callable(func):
                object.__setattr__(self, field_name, ensure_async(func))

    def model_post_init(self, __context: Any) -> None:
        """Auto-populate class_name from the actual class if not explicitly set."""
        if self.class_name is None:
            object.__setattr__(self, "class_name", self.__class__.__name__)

    def set_mas(self, mas: Any) -> None:
        """Bind this Oxy instance to a MAS runtime container."""
        self.mas = mas

    def add_permitted_tool(self, tool_name: str) -> None:
        """Add a tool to the permitted tools list."""
        if tool_name in self.permitted_tool_name_list:
            logger.warning(f"Tool {tool_name} already exists.")
        else:
            self.permitted_tool_name_list.append(tool_name)

    def add_permitted_tools(self, tool_names: list[str]) -> None:
        """Add multiple tools to the permitted tools list."""
        for tool_name in tool_names:
            self.add_permitted_tool(tool_name)

    def _set_desc_for_llm(self) -> None:
        """Generate LLM-friendly description from input schema."""
        args_desc = []
        if "properties" in self.input_schema:
            for param_name, param_info in self.input_schema["properties"].items():
                # Skip system parameters that shouldn't be shown to LLM
                param_desc = param_info.get("description", "No description")
                if param_desc.startswith("SystemArg."):
                    self.system_args.append(param_info["description"][10:])
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

    async def init(self) -> None:
        """Perform async initialization. Rebuilds the LLM-facing description."""
        self._set_desc_for_llm()

    async def cleanup(self) -> None:
        """Release resources acquired during init().

        Subclasses that allocate external resources (connections, thread pools,
        child processes, etc.) should override this method.  The default
        implementation is a no-op.
        """

    async def _pre_process(self, oxy_request: OxyRequest) -> OxyRequest:
        """Pre-process the request before execution."""
        if not oxy_request.node_id:
            oxy_request.node_id = generate_uuid()
        oxy_request.callee = self.name
        oxy_request.callee_category = self.category
        oxy_request.call_stack.append(self.name)
        oxy_request.node_id_stack.append(oxy_request.node_id)
        # Handle input
        oxy_request = await self.func_process_input(oxy_request)
        return oxy_request

    async def _pre_log(self, oxy_request: OxyRequest) -> None:
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

    async def _request_interceptor(
        self, oxy_request: OxyRequest
    ) -> Optional[OxyResponse]:
        """Intercept the request for restart/replay scenarios.

        When a reference_trace_id and restart_node_id are present, queries ES
        for cached outputs from a prior trace. Returns an OxyResponse built
        from the cached data if found, allowing execution to be skipped.
        Returns None when no cache hit occurs, so normal execution continues.
        """
        if (
            oxy_request.reference_trace_id
            and oxy_request.restart_node_id
            and oxy_request.get_shared_data("_is_read_cache_for_restart", True)
            and self.mas
            and self.mas.es_client
            and self.category in ["llm", "tool"]
        ):
            es_response = await self.mas.es_client.search(
                Config.get_app_name() + "_node",
                {
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"trace_id": oxy_request.reference_trace_id}},
                                {"term": {"input_md5": oxy_request.input_md5}},
                            ]
                        }
                    },
                    "size": 1,
                },
            )
            logger.info(f"ES search returned {len(es_response['hits']['hits'])} hits")
            if es_response["hits"]["hits"]:
                current_node_order = es_response["hits"]["hits"][0]["_source"][
                    "update_time"
                ]
                if current_node_order < oxy_request.restart_node_order:
                    restart_node_output = es_response["hits"]["hits"][0]["_source"][
                        "output"
                    ]

                    copied_node_id = es_response["hits"]["hits"][0]["_source"][
                        "copied_node_id"
                    ]
                    oxy_request.copied_node_id = (
                        copied_node_id
                        if copied_node_id
                        else es_response["hits"]["hits"][0]["_source"]["node_id"]
                    )

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
                    await oxy_request.send_message({"type": "re_run", "content": {}})
                    oxy_request.set_shared_data("_is_read_cache_for_restart", False)
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
                    await oxy_request.send_message({"type": "re_run", "content": {}})
                    oxy_request.set_shared_data("_is_read_cache_for_restart", False)
            else:
                logger.warning(
                    f"{' === '.join(oxy_request.call_stack)}  : load null from ES.",
                    extra={
                        "trace_id": oxy_request.current_trace_id,
                        "node_id": oxy_request.node_id,
                    },
                )

    async def _pre_save_data(self, oxy_request: OxyRequest) -> None:
        """Persist the initial node record to ES before execution starts."""
        if not self.is_save_data:
            return
        if self.mas and self.mas.es_client:
            callee_name = oxy_request.callee
            callee_cat = oxy_request.callee_category
            # save shared_data
            to_save_shared_data = _serialize_data_for_es(
                oxy_request.shared_data, Config.get_es_schema_shared_data
            )
            await self.mas.es_client.upsert(
                Config.get_app_name() + "_node",
                doc_id=oxy_request.node_id,
                body={
                    "node_id": oxy_request.node_id,
                    "copied_node_id": oxy_request.copied_node_id,
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
                    "create_time": oxy_request.create_time,
                },
            )
        else:
            logger.warning(f"Node {oxy_request.callee} data unsaved.")

    async def _format_input(self, oxy_request: OxyRequest) -> OxyRequest:
        """Format input arguments for execution."""
        return await self.func_format_input(oxy_request)

    async def _pre_send_message(self, oxy_request: OxyRequest) -> None:
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
                        "copied_node_id": oxy_request.copied_node_id,
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
        """Run preceding Oxy instances and merge their outputs into the request."""
        if self.preceding_oxy:
            arguments = oxy_request.arguments.copy()
            tasks = [
                oxy_request.call(callee=oxy_name, arguments=arguments)
                for oxy_name in self.preceding_oxy
            ]
            oxy_responses = await asyncio.gather(*tasks)
            oxy_request.arguments[self.preceding_placeholder] = "\n".join(
                [oxy_response.output for oxy_response in oxy_responses]
            )
        return oxy_request

    @abstractmethod
    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        """Core execution logic. Subclasses must implement this method."""
        pass

    async def _handle_exception(self, e: Exception) -> None:
        """Hook for subclass-specific exception handling during retries."""
        pass

    async def _after_execute(self, oxy_response: OxyResponse) -> OxyResponse:
        """Post-execution hook for modifying the response before post-processing."""
        return oxy_response

    async def _post_process(self, oxy_response: OxyResponse) -> OxyResponse:
        """Apply the output processing function to the response."""
        return await self.func_process_output(oxy_response)

    async def _post_log(self, oxy_response: OxyResponse) -> None:
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

    async def _post_save_data(self, oxy_response: OxyResponse) -> None:
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
            to_save_shared_data = _serialize_data_for_es(
                oxy_request.shared_data, Config.get_es_schema_shared_data
            )
            await self.mas.es_client.upsert(
                Config.get_app_name() + "_node",
                doc_id=oxy_request.node_id,
                body={
                    "node_id": oxy_request.node_id,
                    "copied_node_id": oxy_request.copied_node_id,
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
                    "update_time": oxy_request.update_time,
                },
            )
        else:
            logger.warning(f"Node {oxy_request.callee} data unsaved.")

    async def _format_output(self, oxy_response: OxyResponse) -> OxyResponse:
        """Format the output for the caller and substitute friendly error text on failure."""
        oxy_response = await self.func_format_output(oxy_response)
        if oxy_response.state is OxyState.FAILED and self.friendly_error_text:
            oxy_response.output = self.friendly_error_text
        return oxy_response

    async def _post_send_message(self, oxy_response: OxyResponse) -> None:
        """Send observation and answer messages to frontend if enabled."""
        oxy_request = oxy_response.oxy_request

        # Send observation message to frontend
        if self.is_send_observation:
            await oxy_request.send_message(
                {
                    "type": "observation",
                    "content": {
                        "node_id": oxy_request.node_id,
                        "copied_node_id": oxy_request.copied_node_id,
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
        - Pre-processing, logging, and data saving
        - Input formatting and pre-send message handling
        - Request interception (restart/replay cache)
        - Before-execute hooks (preceding Oxy calls)
        - Core execution with retry logic
        - After-execute hooks
        - Post-processing, logging, and data saving
        - Output formatting and post-send message handling
        """
        async with self._semaphore:
            oxy_request = await self._pre_process(oxy_request)
            await self._pre_log(oxy_request)

            key_to_md5 = {}
            for k, v in oxy_request.arguments.items():
                if isinstance(v, set):
                    key_to_md5[k] = sorted(v, key=str)
                elif isinstance(v, (int, str, float, list, dict, tuple)):
                    key_to_md5[k] = v
            oxy_request.input_md5 = get_md5(
                json.dumps(key_to_md5, sort_keys=True, ensure_ascii=False, default=str)
            )
            result = await self._request_interceptor(oxy_request)
            if isinstance(result, OxyResponse):
                await self._pre_send_message(oxy_request)
                # Persist the replayed node under the new trace_id so restart
                # chains (T1 -> T2 -> T3) keep a complete node tree.
                if self.mas and self.mas.es_client:
                    oxy_request.create_time = get_format_time()
                    await self._pre_save_data(oxy_request)

                    await self._post_log(result)
                    oxy_request.update_time = get_format_time()
                    await self._post_save_data(result)
                await self._post_send_message(result)
                return result

            event = asyncio.Event()
            if self.mas:
                oxy_request.create_time = get_format_time()

                pre_save_data_task = asyncio.create_task(
                    self._pre_save_data(oxy_request)
                )

                pre_save_data_task.add_done_callback(lambda _: event.set())
                self.mas.add_background_task(
                    oxy_request.current_trace_id, pre_save_data_task
                )
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

                    if oxy_request.is_async_storage:
                        post_save_data_task = asyncio.create_task(
                            self._post_save_data(oxy_response)
                        )
                        self.mas.add_background_task(
                            oxy_request.current_trace_id,
                            post_save_data_task,
                        )
                    else:
                        await self._post_save_data(oxy_response)

                    raise
                except Exception as e:
                    # Handle exceptions and retry logic
                    await self._handle_exception(e)
                    attempt += 1
                    logger.warning(
                        f"Error executing oxy {self.name}: {e}. Attempt {attempt} of {self.retries}.",
                        exc_info=True,
                        extra={
                            "trace_id": oxy_request.current_trace_id,
                            "node_id": oxy_request.node_id,
                        },
                    )
                    if attempt < self.retries:
                        await asyncio.sleep(self.delay)
                    else:
                        logger.error(
                            "Max retries reached. Failed.",
                            exc_info=True,
                            extra={
                                "trace_id": oxy_request.current_trace_id,
                                "node_id": oxy_request.node_id,
                            },
                        )
                        oxy_response = OxyResponse(
                            state=OxyState.FAILED,
                            output=f"Error executing oxy {self.name}: {e}",
                        )

            oxy_response.oxy_request = oxy_request
            oxy_response = await self._after_execute(oxy_response)
            oxy_response = await self._post_process(oxy_response)
            await self._post_log(oxy_response)

            if self.mas:
                oxy_request.update_time = get_format_time()

                async def _post_save_data_task(oxy_response: OxyResponse) -> None:
                    await event.wait()
                    await self._post_save_data(oxy_response)

                if oxy_request.is_async_storage:
                    post_save_data_task = asyncio.create_task(
                        _post_save_data_task(oxy_response)
                    )
                    self.mas.add_background_task(
                        oxy_request.current_trace_id,
                        post_save_data_task,
                    )
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
