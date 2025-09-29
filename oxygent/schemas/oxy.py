"""oxy.py.

NOTE: The variables difined in this file have meanings as:
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
import traceback
from enum import Enum, auto
from functools import partial
from typing import Any, List, Optional, Union

from pydantic import BaseModel, Field

from ..config import Config
from ..utils.common_utils import generate_uuid, is_image

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
    from_trace_id: Optional[str] = Field("", description="")
    current_trace_id: Optional[str] = Field(
        default_factory=generate_uuid, description=""
    )
    reference_trace_id: Optional[str] = Field("", description="")
    restart_node_id: Optional[str] = Field("", description="")
    restart_node_output: Optional[str] = Field("", description="")
    restart_node_order: Optional[str] = Field("", description="")
    is_load_data_for_restart: bool = Field(
        True, description="wehether to load data from database"
    )
    input_md5: Optional[str] = Field("", description="")
    root_trace_ids: list = Field(default_factory=list, description="")
    mas: Optional[Any] = Field(None, description="", repr=False)

    caller: Optional[str] = Field("user", description="")
    callee: Optional[str] = Field("", description="")
    call_stack: List[str] = Field(default_factory=lambda: ["user"], description="")
    node_id_stack: List[str] = Field(default_factory=lambda: [""], description="")
    father_node_id: Optional[str] = Field("", description="")
    pre_node_ids: Optional[Union[List[str], str]] = Field(
        default_factory=list, description=""
    )
    latest_node_ids: Optional[Union[List[str], str]] = Field(
        default_factory=list, description=""
    )
    caller_category: Optional[str] = Field("user", description="")
    callee_category: Optional[str] = Field("", description="")

    node_id: Optional[str] = Field("", description="")

    is_save_history: bool = Field(True, description="whether history is saved")
    is_async_storage: bool = Field(True, description="whether async storage is used")

    parallel_id: Optional[str] = Field("", description="")
    parallel_dict: Optional[dict] = Field(default_factory=dict, description="")

    arguments: dict = Field(
        default_factory=dict, description="public data in the scope of a oxy node"
    )
    shared_data: dict = Field(
        default_factory=dict, description="public data in the scope of a single request"
    )
    group_data: dict = Field(
        default_factory=dict, description="public data in the scope of a session group"
    )

    @property
    def session_name(self) -> str:  # We use a easy method to create session name
        return self.caller + "__" + self.callee

    def set_mas(self, mas):
        self.mas = mas

    def get_oxy(self, oxy_name):
        return self.mas.oxy_name_to_oxy[oxy_name]

    def has_oxy(self, oxy_name):
        return oxy_name in self.mas.oxy_name_to_oxy

    def __deepcopy__(self, memo):
        # Dump all the fields into a dict
        fields = self.model_dump()

        # Quote messanger
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

        # 直接赋值共享引用
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
            not in caller_oxy.permitted_tool_name_list
            + caller_oxy.extra_permitted_tool_name_list
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

    async def start(self) -> "OxyResponse":
        return await self.get_oxy(self.callee).execute(self)

    async def send_message(self, message):
        if self.mas and message:
            redis_key = (
                f"{self.mas.message_prefix}:{self.mas.name}:{self.current_trace_id}"
            )
            await self.mas.send_message(message, redis_key)

    def set_query(self, query, master_level=False):
        if master_level:
            self.shared_data["query"] = query
        else:
            self.arguments["query"] = query

    def get_query(self, master_level=False):
        md_attachments = []
        for i, attachment in enumerate(self.arguments.get("attachments", [])):
            if attachment.startswith("../static/"):
                attachment = f"{Config.get_cache_save_dir()}/uploads{attachment[9:]}"
            is_image_flag = "!" if is_image(attachment) else ""
            md_attachments.append(f"{is_image_flag}[file {i + 1}]({attachment})")
        attachments_str = "\n".join(md_attachments)
        if attachments_str:
            attachments_str += " "

        if master_level:
            return attachments_str + self.shared_data.get("query", "")
        else:
            return attachments_str + self.arguments.get("query", "")

    def has_short_memory(self, master_level=False):
        var_short_memory = "master_short_memory" if master_level else "short_memory"
        return var_short_memory in self.arguments

    def set_short_memory(self, short_memory, master_level=False):
        var_short_memory = "master_short_memory" if master_level else "short_memory"
        self.arguments[var_short_memory] = short_memory

    def get_short_memory(self, master_level=False):
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
        return key in self.arguments

    def get_arguments(self, key=None):
        if key is None:
            return self.arguments
        return self.arguments.get(key)

    def set_arguments(self, key, value):
        self.arguments[key] = value

    def has_shared_data(self, key):
        return key in self.shared_data

    def get_shared_data(self, key=None):
        if key is None:
            return self.shared_data
        return self.shared_data.get(key)

    def set_shared_data(self, key, value):
        self.shared_data[key] = value

    def has_group_data(self, key):
        return key in self.group_data

    def get_group_data(self, key=None):
        if key is None:
            return self.group_data
        return self.group_data.get(key)

    def set_group_data(self, key, value):
        self.group_data[key] = value

    def has_global_data(self, key):
        return key in self.mas.global_data

    def get_global_data(self, key=None):
        if key is None:
            return self.mas.global_data
        return self.mas.global_data.get(key)

    def set_global_data(self, key, value):
        self.mas.global_data[key] = value

    async def break_task(self):
        await self.send_message({"event": "close", "data": "done"})
        self.mas.active_tasks[self.current_trace_id].cancel()


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
    extra: dict = Field(default_factory=dict)
    oxy_request: Optional[OxyRequest] = Field(None)


class OxyOutput(BaseModel):
    result: Any
    attachments: list = Field(default_factory=list)
