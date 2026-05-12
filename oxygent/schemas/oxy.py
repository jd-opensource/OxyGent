"""oxy.py.

NOTE: The variables defined in this file have meanings as:
    - mas: the runtime container that knows every agent/tool(oxy) and routes messages among them
    - oxy: autonomous object, the agent/tool that can be called by other agents/tools
    - session: persistent channel between caller and callee
    - trace: conversation thread (a session can branch into different traces)
    - caller: parent node
    - callee: the node being entered during a nested call
"""

import asyncio
import copy
import logging
import os
import time
import traceback
from enum import Enum, auto
from functools import partial
from typing import Any, List, Optional, Union

from pydantic import BaseModel, Field

from ..config import Config
from ..utils.common_utils import generate_uuid, is_image
from .message import SSEMessage

logger = logging.getLogger(__name__)


class OxyState(Enum):  # The status of the node (oxy)
    CREATED = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    PAUSED = auto()
    SKIPPED = auto()
    CANCELED = auto()


class OxyRequest(BaseModel):
    """Envelope for a single MAS task invocation.

    Attributes
    ----------
    from_trace_id : str | None
        The parent conversation node's trace id.
    current_trace_id : str
        Unique id for *this* node; forms a conversation DAG.
    root_trace_ids : list[str]
        All roots composing the current session tree.
    caller / callee : str
        Names of the oxy initiating the call and the oxy being called.
    arguments : dict
        Call-specific parameters (user input, tool args, etc.).
    shared_data : dict
        Scratch space shared with descendants in the same trace.
    """

    # Static
    request_id: str = Field(
        default_factory=partial(generate_uuid, length=22),
        description="Client-side id for tracing & resuming requests.",
    )
    group_id: str = Field(
        default_factory=generate_uuid,
        description="Static group identifier for trace trees.",
    )
    from_trace_id: Optional[str] = Field(
        "", description="Parent trace ID this conversation branched from"
    )
    current_trace_id: Optional[str] = Field(
        default_factory=generate_uuid,
        description="Unique identifier for this conversation node",
    )
    reference_trace_id: Optional[str] = Field(
        "", description="Trace ID of a prior execution used for restart/replay"
    )
    restart_node_id: Optional[str] = Field(
        "", description="Node ID to restart execution from"
    )
    restart_node_output: Optional[str] = Field(
        "", description="User-overridden output for the restart node"
    )
    restart_node_order: Optional[str] = Field(
        "", description="Timestamp ordering of the restart node"
    )
    input_md5: Optional[str] = Field(
        "", description="MD5 hash of the input for cache matching"
    )
    root_trace_ids: list = Field(
        default_factory=list,
        description="All root trace IDs composing the current session tree",
    )
    mas: Optional[Any] = Field(
        None, description="Reference to the bound MAS runtime container", repr=False
    )

    caller: Optional[str] = Field(
        "user", description="Name of the Oxy initiating this call"
    )
    callee: Optional[str] = Field("", description="Name of the Oxy being called")
    call_stack: List[str] = Field(
        default_factory=lambda: ["user"],
        description="Ordered list of caller names forming the invocation chain",
    )
    node_id_stack: List[str] = Field(
        default_factory=lambda: [""],
        description="Ordered list of node IDs paralleling the call stack",
    )
    father_node_id: Optional[str] = Field(
        "", description="Node ID of the direct parent in the call tree"
    )
    pre_node_ids: Optional[Union[List[str], str]] = Field(
        default_factory=list,
        description="Node IDs that must complete before this node executes",
    )
    latest_node_ids: Optional[Union[List[str], str]] = Field(
        default_factory=list,
        description="Most recently completed node IDs in the current branch",
    )
    caller_category: Optional[str] = Field(
        "user", description="Category of the caller (e.g. user, agent, tool)"
    )
    callee_category: Optional[str] = Field(
        "", description="Category of the callee (e.g. agent, tool, llm)"
    )

    node_id: Optional[str] = Field(
        "", description="Unique identifier for this execution node"
    )
    copied_node_id: Optional[str] = Field(
        "", description="Original node ID when this node is replayed from a prior trace"
    )

    is_save_history: bool = Field(
        True, description="Whether conversation history is persisted to ES"
    )
    is_send_message: bool = Field(
        True, description="Whether messages are sent to the frontend"
    )
    is_async_storage: bool = Field(
        True, description="Whether data storage runs asynchronously in background tasks"
    )

    parallel_id: Optional[str] = Field(
        "", description="Identifier grouping nodes in the same parallel execution batch"
    )
    parallel_dict: Optional[dict] = Field(
        default_factory=dict,
        description="Mapping of parallel execution metadata for batch coordination",
    )

    arguments: dict = Field(
        default_factory=dict,
        description="Call-specific parameters (user input, tool args, etc.)",
    )
    shared_data: dict = Field(
        default_factory=dict,
        description="Public data shared across the entire trace tree",
    )
    group_data: dict = Field(
        default_factory=dict,
        description="Data shared across all traces in the same session group",
    )

    create_time: Optional[str] = Field(
        None, description="Timestamp when this node was created"
    )
    update_time: Optional[str] = Field(
        None, description="Timestamp when this node was last updated"
    )

    @property
    def session_name(self) -> str:  # We use a easy method to create session name
        return self.caller + "__" + self.callee

    def set_mas(self, mas):
        """Bind a MAS instance to this request."""
        self.mas = mas

    def get_oxy(self, oxy_name):
        """Retrieve a registered Oxy instance by name from the bound MAS."""
        return self.mas.oxy_name_to_oxy[oxy_name]

    def has_oxy(self, oxy_name):
        """Check whether a named Oxy instance is registered in the bound MAS."""
        return oxy_name in self.mas.oxy_name_to_oxy

    def __deepcopy__(self, memo):
        """Deep copy the request while sharing mutable cross-trace references."""
        # Dump all the fields into a dict
        fields = self.model_dump()

        # Exclude messenger fields during deep copy
        temp_data = {
            "mas": None,
            "shared_data": dict(),
            "group_data": dict(),
            "parallel_id": "",
            "latest_node_ids": [],
        }
        for k, v in temp_data.items():
            fields[k] = v
        for k in fields:
            if k not in temp_data:
                fields[k] = copy.deepcopy(fields[k], memo)

        # create new instance
        new_instance = self.__class__(**fields)

        # Assign shared references directly (no deep copy)
        new_instance.mas = self.mas
        new_instance.shared_data = self.shared_data
        new_instance.group_data = self.group_data

        return new_instance

    def clone_with(self, **kwargs) -> "OxyRequest":
        """Return a deep copy with selected fields overridden.

        This method is *side effect free*: the original request is untouched.

        Examples
        --------
        >>> new_req = req.clone_with(
        ...     callee="search_tool",
        ...     arguments={"query": "python asyncio"}
        ... )
        """
        new_instance = copy.deepcopy(self)
        # Update defined attributes
        for key, value in kwargs.items():
            if hasattr(new_instance, key):
                setattr(new_instance, key, value)
            else:
                raise AttributeError(
                    f"{self.__class__.__name__} has no attribute '{key}'"
                )
        return new_instance

    async def retry_execute(self, oxy, oxy_request=None) -> "OxyResponse":
        """Execute an oxy with automatic retries.

        Retries
        -------
        Controlled by `oxy.retries` and `oxy.delay`.

        Returns:
            OxyResponse: Completed or FAILED after exhausting retries.
        """
        if oxy_request is None:
            oxy_request = self
        attempt = 0
        while attempt < oxy.retries:
            try:
                return await oxy.execute(oxy_request)
            except Exception as e:
                attempt += 1
                logger.warning(
                    f"Error executing oxy: {e}. Attempt {attempt} of {oxy.retries}.",
                    extra={
                        "trace_id": oxy_request.current_trace_id,
                        "node_id": oxy_request.node_id,
                    },
                )
                if attempt < oxy.retries:
                    await asyncio.sleep(oxy.delay)
                else:
                    error_msg = traceback.format_exc()
                    logger.warning(
                        f"Max retries reached. Failing. {error_msg}",
                        extra={
                            "trace_id": oxy_request.current_trace_id,
                            "node_id": oxy_request.node_id,
                        },
                    )
                    return OxyResponse(
                        state=OxyState.FAILED,
                        output=f"Error executing tool {oxy.name}: {str(e)}",
                    )

    async def call(self, **kwargs) -> "OxyResponse":
        """Invoke another oxy or tool.

        Args:
            Any fields to override in a cloned request
            (e.g., `callee="search_tool", arguments={"query": "hello"}`).

        Returns:
            OxyResponse: The result object (COMPLETED, FAILED, SKIPPED, etc.).

        NOTE:
        * Performs permission checks and dangerous-tool confirmation.
        * Wraps the target oxy in a timeout guard.
        * Converts special tools (e.g., retrieve_tools) into the expected downstream format.
        """
        oxy_request = self.clone_with(**kwargs)

        oxy_request.node_id = generate_uuid()
        if not oxy_request.parallel_id:
            oxy_request.parallel_id = generate_uuid()

        if oxy_request.parallel_id in self.parallel_dict:
            self.parallel_dict[oxy_request.parallel_id]["parallel_node_ids"].append(
                oxy_request.node_id
            )
        else:
            self.parallel_dict[oxy_request.parallel_id] = {
                "pre_node_ids": self.latest_node_ids,
                "parallel_node_ids": [oxy_request.node_id],
            }

        if "pre_node_ids" not in kwargs:
            oxy_request.pre_node_ids = self.parallel_dict[oxy_request.parallel_id][
                "pre_node_ids"
            ]

        self.latest_node_ids = self.parallel_dict[oxy_request.parallel_id][
            "parallel_node_ids"
        ]
        oxy_request.father_node_id = self.node_id
        oxy_request.caller = self.callee
        oxy_request.caller_category = self.callee_category

        oxy_name = oxy_request.callee
        # Check if the oxy exists
        if not self.has_oxy(oxy_name):
            logger.error(
                f"oxy {oxy_name} not exists",
                extra={
                    "trace_id": oxy_request.current_trace_id,
                    "node_id": oxy_request.node_id,
                },
            )
            return OxyResponse(
                state=OxyState.FAILED, output=f"Tool {oxy_name} not exists"
            )

        caller_oxy = self.get_oxy(oxy_request.caller)
        oxy = self.get_oxy(oxy_name)
        # Ensure permission for calling
        if (
            oxy_request.caller_category != "user"
            and oxy.is_permission_required
            and oxy_name
            not in caller_oxy.permitted_tool_name_list + caller_oxy.permitted_oxy
        ):
            error_msg = (
                f"No permission for oxy: {oxy_name}, caller: {oxy_request.caller}"
            )
            logger.error(
                error_msg,
                extra={
                    "trace_id": oxy_request.current_trace_id,
                    "node_id": oxy_request.node_id,
                },
            )
            return OxyResponse(
                state=OxyState.SKIPPED, output=f"No permission for tool: {oxy_name}"
            )
        # Process special parameters for tools
        if oxy_name == "retrieve_tools":
            oxy_request.arguments["app_name"] = Config.get_app_name()
            oxy_request.arguments["agent_name"] = caller_oxy.name
            oxy_request.arguments["top_k"] = caller_oxy.top_k_tools
            oxy_request.arguments["vearch_client"] = self.mas.vearch_client
        system_arg_dict = {
            "agent_pin": oxy_request.caller,
            "user_pin": oxy_request.get_group_data("user_pin", ""),
        }
        for system_arg in oxy.system_args:
            if system_arg in oxy_request.arguments:
                continue
            oxy_request.arguments[system_arg] = system_arg_dict[system_arg]
        # Execute the oxy
        try:
            oxy_response = await asyncio.wait_for(
                oxy.execute(oxy_request), timeout=oxy.timeout
            )
            # Process special parameters in response
            if oxy_name == "retrieve_tools":
                llm_tool_desc_list = [
                    self.get_oxy(tool_name).desc_for_llm
                    for tool_name in oxy_response.output
                ]
                oxy_response.output = "\n\n".join(llm_tool_desc_list)
            return oxy_response
        except asyncio.TimeoutError:
            logger.warning(
                f"Task {caller_oxy.name} -> {oxy.name} was timeouted",
                extra={
                    "trace_id": oxy_request.current_trace_id,
                    "node_id": oxy_request.node_id,
                },
            )
            return OxyResponse(
                state=OxyState.FAILED, output=f"Executing tool {oxy.name} timed out"
            )
        except asyncio.CancelledError:
            logger.error(
                f"Task {caller_oxy.name} -> {oxy.name} was cancelled",
                extra={
                    "trace_id": oxy_request.current_trace_id,
                    "node_id": oxy_request.node_id,
                },
            )
            raise
        except Exception as e:
            error_msg = traceback.format_exc()
            logger.error(
                f"Error executing oxy {oxy.name}: {error_msg}",
                extra={
                    "trace_id": oxy_request.current_trace_id,
                    "node_id": oxy_request.node_id,
                },
            )
            return OxyResponse(
                state=OxyState.FAILED,
                output=f"Error executing tool {oxy.name}: {str(e)}",
            )
        # return await self.retry_execute(oxy, oxy_request)

    async def call_async(self, **kwargs):
        """Call a callee asynchronously in a background task."""
        task = asyncio.create_task(self.call(**kwargs))
        self.mas.background_tasks.add(task)

    async def start(self) -> "OxyResponse":
        """Start a streaming call to the callee."""
        return await self.get_oxy(self.callee).execute(self)

    async def send_message(self, message=None, event=None, id=None, retry=None):
        """Send a message to the frontend via the bound MAS."""
        if self.mas and self.is_send_message:
            # Record first response time on user-facing messages
            # Exclude: tool_call (preparing to execute), observation (internal execution result)
            # Include: answer, stream, stream_end (messages sent to user)
            if message is not None and isinstance(message, dict):
                msg_type = message.get("type", "")
                if msg_type not in ["tool_call", "observation"]:
                    metrics = self.shared_data.get("_metrics", {})
                    if "first_response_time_ms" not in metrics:
                        query_start_time = metrics.get("_query_start_time")
                        if query_start_time:
                            first_response_ms = (time.time() - query_start_time) * 1000
                            metrics["first_response_time_ms"] = first_response_ms
                            logger.info(
                                f"First response time: {first_response_ms:.2f}ms, message_type: {msg_type}",
                                extra={
                                    "trace_id": self.current_trace_id,
                                    "node_id": self.node_id,
                                },
                            )

            dict_message = {"id": id, "event": event, "data": message, "retry": retry}
            dict_message_processed = self.mas.func_process_message(dict_message, self)
            dict_message_filtered = {
                k: v for k, v in dict_message_processed.items() if v is not None
            }
            sse_message = SSEMessage(**dict_message_filtered)
            redis_key = (
                f"{self.mas.message_prefix}:{self.mas.name}:{self.current_trace_id}"
            )
            await self.mas.send_message(sse_message, redis_key, group_id=self.group_id)

    def set_query(self, query, master_level=False):
        """Set the query text in the arguments."""
        if master_level:
            self.shared_data["query"] = query
        else:
            self.arguments["query"] = query

    def get_query(self, master_level=False):
        """Get the query text from the arguments."""
        md_attachments = []
        for i, attachment in enumerate(self.arguments.get("attachments", [])):
            if attachment.startswith("../static/"):
                relative_path = attachment[9:].lstrip('/')
                attachment = f"{Config.get_cache_save_dir()}/uploads/{relative_path}"
            is_image_flag = "!" if is_image(attachment) else ""
            attachment_base_name = os.path.basename(attachment)
            # Generate a clearer format to help LLM correctly understand the path
            md_attachments.append(
                f"{is_image_flag}File: {attachment_base_name}, Path: {attachment}"
            )
        attachments_str = "\n".join(md_attachments)
        if attachments_str:
            attachments_str += "\n\n"

        if master_level:
            return attachments_str + self.shared_data.get("query", "")
        else:
            return attachments_str + self.arguments.get("query", "")

    def has_short_memory(self, master_level=False):
        """Check whether short-term memory exists in arguments."""
        var_short_memory = "master_short_memory" if master_level else "short_memory"
        return var_short_memory in self.arguments

    def set_short_memory(self, short_memory, master_level=False):
        """Set short-term memory in arguments."""
        var_short_memory = "master_short_memory" if master_level else "short_memory"
        self.arguments[var_short_memory] = short_memory

    def get_short_memory(self, master_level=False):
        """Get short-term memory from arguments."""
        var_short_memory = "master_short_memory" if master_level else "short_memory"
        return self.arguments.get(var_short_memory, [])

    def get_request_id(self) -> str:
        """Return the current request_id."""
        return self.request_id

    def set_request_id(self, request_id: str):
        """Manually override the request_id (rarely needed)."""
        self.request_id = request_id

    def get_group_id(self) -> str:
        """Return the group_id associated with this request."""
        return self.group_id

    def set_group_id(self, request_id: str):
        """Manually override the group_id."""
        self.group_id = request_id

    def has_arguments(self, key):
        """Check whether arguments exist."""
        return key in self.arguments

    def get_arguments(self, key=None, default=None):
        """Get a specific argument by key."""
        if key is None:
            return self.arguments
        return self.arguments.get(key, default)

    def set_arguments(self, key, value):
        """Set a specific argument by key."""
        self.arguments[key] = value

    def has_shared_data(self, key):
        """Check whether a key exists in shared_data."""
        return key in self.shared_data

    def get_shared_data(self, key=None, default=None):
        """Get a value from shared_data."""
        if key is None:
            return self.shared_data
        return self.shared_data.get(key, default)

    def set_shared_data(self, key, value):
        """Set a value in shared_data."""
        self.shared_data[key] = value

    def has_group_data(self, key):
        """Check whether a key exists in group_data."""
        return key in self.group_data

    def get_group_data(self, key=None, default=None):
        """Get a value from group_data."""
        if key is None:
            return self.group_data
        return self.group_data.get(key, default)

    def set_group_data(self, key, value):
        """Set a value in group_data."""
        self.group_data[key] = value

    def has_global_data(self, key):
        """Check whether a key exists in global_data."""
        return key in self.mas.global_data

    def get_global_data(self, key=None, default=None):
        """Get a value from global_data."""
        if key is None:
            return self.mas.global_data
        return self.mas.global_data.get(key, default)

    def set_global_data(self, key, value):
        """Set a value in global_data."""
        self.mas.global_data[key] = value

    async def break_task(self):
        """Signal task cancellation for the current trace."""
        await self.send_message(message="done", event="close")
        self.mas.active_tasks[self.current_trace_id].cancel()

    async def get_feedback_stream(self, channel_id=None):
        """Get the feedback stream channel for interactive responses."""
        if channel_id is None:
            channel_id = self.current_trace_id
        if channel_id not in self.mas.feedback_dict:
            self.mas.feedback_dict[channel_id] = asyncio.Queue()
            # Store all channel_ids used by the current trace_id
            if self.current_trace_id not in self.mas.channel_id_dict:
                self.mas.channel_id_dict[self.current_trace_id] = []
            self.mas.channel_id_dict[self.current_trace_id].append(channel_id)
        queue = self.mas.feedback_dict[channel_id]
        while True:
            data = await queue.get()
            if not data:
                queue.task_done()
                break
            yield data
            queue.task_done()


class OxyResponse(BaseModel):
    """Result of an oxy execution.

    Attributes
    ----------
    state : OxyState
        Final state of the task.
    output : Any
        User-visible payload or error message.
    extra : dict
        Optional metadata (tokens used, latency, etc.).
    oxy_request : OxyRequest | None
        Echo of the originating request (useful for logging).
    """

    state: OxyState
    output: Any
    extra: dict = Field(
        default_factory=dict,
        description="Optional metadata (token usage, latency, etc.)",
    )
    oxy_request: Optional[OxyRequest] = Field(
        None, description="Echo of the originating request for traceability"
    )


class OxyOutput(BaseModel):
    """Container for the final output of an Oxy execution chain."""

    result: Any
    attachments: list = Field(
        default_factory=list,
        description="Supplementary files or data attached to the output",
    )
