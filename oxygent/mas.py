"""mas.py OxyGent MAS (Multi-Agent System) Module.

NOTE: This module contains the following parts:
    - launcher
    - register
    - agent organization
    - resource management
    The core variables are:
    - name: Identifier for the MAS instance
    - oxy_name_to_oxy: Dictionary mapping Oxy names to Oxy instances (register table)
    - oxy_space: List of Oxy instances (registered Oxy)
    - master_agent_name: Name of the master agent (instance of BaseAgent)
    - active_tasks: Dictionary to manage active tasks, for SSE and other async operations
    - es_client / redis_client / vearch_client: Database clients for Elasticsearch, Redis, and Vearch
    - agent_organization: Dictionary representing the organization structure of agents
    - lock: Boolean to control task execution flow
"""
# from __future__ import annotations

import asyncio
import datetime
import json
import os
import traceback
from collections import OrderedDict
from typing import Callable, Optional

import msgpack
import shortuuid
from elasticsearch import AsyncElasticsearch
from pydantic import BaseModel, ConfigDict, Field

from .config import Config
from .databases.db_es import JesEs, LocalEs
from .databases.db_redis import JimdbApRedis, LocalRedis
from .databases.db_vector import VearchDB
from .db_factory import DBFactory
from .log_setup import setup_logging
from .oxy import Oxy
from .oxy.agents.base_agent import BaseAgent
from .oxy.agents.remote_agent import RemoteAgent
from .oxy.base_flow import BaseFlow
from .oxy.base_tool import BaseTool
from .oxy.llms.base_llm import BaseLLM
from .oxy.mcp_tools.base_mcp_client import BaseMCPClient
from .routes import router
from .schemas import OxyRequest, OxyResponse, WebResponse
from .utils.common_utils import (
    _compose_query_parts,
    msgpack_preprocess,
    print_tree,
    to_json,
)

logger = None


class MAS(BaseModel):
    """The main class for the OxyGent Multi-Agent System (MAS)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = Field("", description="Identifier for the mas.")

    default_oxy_space: list = Field(default_factory=list, description="")

    oxy_space: list = Field(default_factory=list, description="")

    oxy_name_to_oxy: dict[str, Oxy] = Field(default_factory=dict, description="")

    master_agent_name: str = Field("")

    first_query: str = Field("")

    welcome_message: str = Field(default_factory=Config.get_agent_welcome_message)

    agent_organization: dict = Field(default_factory=list)

    vearch_client: Optional[VearchDB] = Field(None)
    es_client: Optional[AsyncElasticsearch] = Field(None)
    redis_client: Optional[JimdbApRedis] = Field(None)

    lock: bool = Field(False)
    active_tasks: dict = Field(default_factory=dict)
    background_tasks: set = Field(default_factory=set)
    event_dict: dict = Field(default_factory=dict)

    message_prefix: str = Field("oxygent")

    global_data: dict = Field(
        default_factory=dict, description="public data in the scope of application"
    )

    func_filter: Optional[Callable] = Field(
        lambda x: x, exclude=True, description="filter function"
    )

    def __init__(self, **kwargs):
        """Construct a new :class:`MAS`.

        Args:
            name: Optional explicit instance name.  If *None*, the value from
                :class:`~config.Config` is used.
            oxy_space: Initial list of *Oxy* objects (agents, tools, LLMs…)
                to be registered and initialised.
            default_oxy_space: Built-in core components that are always
                present; mainly used by internal helpers and tests.
        """
        super().__init__(**kwargs)
        global logger
        logger = setup_logging()
        if self.name:
            Config.set_app_name(self.name)
        else:
            self.name = Config.get_app_name()

    async def __aenter__(self):
        await self.init()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await asyncio.gather(*self.background_tasks)
        logger.info("=" * 64)
        logger.info("🪂 OxyGent MAS Application Exit")
        logger.info("=" * 64)
        await self.es_client.close()
        await self.redis_client.close()
        await self.cleanup_servers()

    @classmethod
    async def create(cls, **kwargs):
        self = cls(**kwargs)
        await self.init()
        return self

    def show_banner(self):
        from .banner import oxygent_slant as banner_str

        print(banner_str[1:-1])

    def show_mas_info(self):
        import platform
        from datetime import datetime

        # logger.info(f"MAS app name: {Config.get_app_name()}")
        # logger.info(f"MAS app env: {Config._env}")
        logger.info("=" * 64)
        logger.info("🚀 OxyGent MAS Application Startup Information")
        logger.info("=" * 64)
        logger.info(f"App Name     : {Config.get_app_name()}")
        logger.info(f"Version      : {Config.get_app_version()}")
        logger.info(f"Environment  : {Config._env}")
        logger.info(f"Port         : {Config.get_server_port()}")
        logger.info(f"Python Ver   : {platform.python_version()}")
        # logger.info(f"Config Path  : {Config.get_config_path()}")
        logger.info(f"Cache Dir    : {Config.get_cache_save_dir()}")
        logger.info(f"Start Time   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 64)

    def add_oxy(self, oxy: Oxy):
        """Register a single Oxy object.

        Args:
            oxy: The component instance to add.

        Raises:
            ValueError: If another component with the same ``oxy.name``
                already exists in the registry.
        """
        # print(self.oxy_name_to_oxy)
        # import pdb
        # pdb.set_trace()
        if oxy.name in self.oxy_name_to_oxy:
            raise Exception(f"oxy [{oxy.name}] already exists.")
        self.oxy_name_to_oxy[oxy.name] = oxy

    def add_oxy_list(self, oxy_list: list[Oxy]):
        """Register a list of Oxy objects.

        Args:
            oxy_list: List of Oxy instances to register.
        """
        for oxy in oxy_list:
            self.add_oxy(oxy)

    async def init(self):
        """Initialize the MAS. This coroutine performs all necessary setup steps to
        prepare the MAS for operation.

        It includes:
        - Printing the startup banner and environment information
        - Register all the oxy instances in the oxy_space and inject them into the MAS
        - Initializing the database connections (Elasticsearch, Redis)
        - Setting up the agent organization structure
        - Initialize the vector search if configured
        """
        self.show_banner()
        self.show_mas_info()
        # Register default oxy_space
        self.add_oxy_list(self.oxy_space)
        if Config.get_vearch_config():
            from .core_tools.retrieve_tools import fh as retrieve_fh

            self.add_oxy(retrieve_fh)
        # Initialize datebase asynchronously
        await self.init_db()
        # Initialize all oxy instances
        await self.init_all_oxy()
        # Initialize the master agent name
        self.init_master_agent_name()
        # Initialize the Redis client
        if Config.get_vearch_config():
            await self.create_vearch_table()
        # Build the agent organization structure
        self.init_agent_organization()
        self.show_org()

    async def cleanup_servers(self) -> None:
        """Gracefully shut down remote servers/clients.

        The method concurrently calls ``cleanup()`` on every
        :class:`BaseMCPClient` that has been registered.  It is automatically
        invoked by :func:`__aexit__`.
        """
        cleanup_tasks = []
        for oxy in self.oxy_name_to_oxy.values():
            if not isinstance(oxy, BaseMCPClient):
                continue
            cleanup_tasks.append(asyncio.create_task(oxy.cleanup()))

        if cleanup_tasks:
            try:
                await asyncio.gather(*cleanup_tasks, return_exceptions=False)
            except Exception as e:
                logger.warning(f"Warning during final cleanup: {e}")

    async def init_db(self):
        """Es --- (table_name: key)

        {app_name}_trace: trace_id: record trace of each call {app_name}_node: node_id:
        record log of each node {app_name}_history: sub_session_id: record history of
        read and write operations

        sub_session_id = trace_id_{caller}_{callee}
        """

        # es
        db_factory = DBFactory()
        if Config.get_es_config():
            jes_config = Config.get_es_config()
            hosts = jes_config["hosts"]
            user = jes_config["user"]
            password = jes_config["password"]
            self.es_client = db_factory.get_instance(JesEs, hosts, user, password)
        else:
            self.es_client = db_factory.get_instance(LocalEs)
        # trace table
        await self.es_client.create_index(
            Config.get_app_name() + "_trace",
            {
                "mappings": {
                    "properties": {
                        "request_id": {"type": "keyword"},
                        "group_id": {"type": "keyword"},
                        "group_data": Config.get_es_schema_group_data(),
                        "trace_id": {"type": "keyword"},
                        "shared_data": Config.get_es_schema_shared_data(),
                        "from_trace_id": {"type": "keyword"},
                        "root_trace_ids": {"type": "keyword"},
                        "input": {"type": "text"},
                        "callee": {"type": "keyword"},
                        "output": {"type": "text"},
                        "create_time": {
                            "format": "yyyy-MM-dd HH:mm:ss.SSSSSSSSS",
                            "type": "date",
                        },
                    }
                }
            },
        )
        # message table
        if Config.get_message_is_stored():
            await self.es_client.create_index(
                Config.get_app_name() + "_message",
                {
                    "mappings": {
                        "properties": {
                            "trace_id": {"type": "keyword"},
                            "message": {"type": "text"},
                            "message_type": {"type": "keyword"},
                            "create_time": {
                                "format": "yyyy-MM-dd HH:mm:ss.SSSSSSSSS",
                                "type": "date",
                            },
                        }
                    }
                },
            )
        # node table
        await self.es_client.create_index(
            Config.get_app_name() + "_node",
            {
                "mappings": {
                    "properties": {
                        "node_id": {"type": "keyword"},
                        "node_type": {"type": "keyword"},
                        "group_id": {"type": "keyword"},
                        "trace_id": {"type": "keyword"},
                        "caller": {"type": "keyword"},
                        "callee": {"type": "keyword"},
                        "parallel_id": {"type": "keyword"},
                        "father_node_id": {"type": "keyword"},
                        "input": {"type": "text"},
                        "input_md5": {"type": "keyword"},
                        "output": {"type": "text"},
                        "state": {"type": "keyword"},
                        "extra": {"type": "text"},
                        "call_stack": {"type": "text"},
                        "node_id_stack": {"type": "text"},
                        "pre_node_ids": {"type": "text"},
                        "shared_data": Config.get_es_schema_shared_data(),
                        "create_time": {
                            "format": "yyyy-MM-dd HH:mm:ss.SSSSSSSSS",
                            "type": "date",
                        },
                        "update_time": {
                            "format": "yyyy-MM-dd HH:mm:ss.SSSSSSSSS",
                            "type": "date",
                        },
                    }
                }
            },
        )
        # history table
        await self.es_client.create_index(
            Config.get_app_name() + "_history",
            {
                "mappings": {
                    "properties": {
                        "sub_session_id": {"type": "keyword"},
                        "session_name": {"type": "keyword"},
                        "trace_id": {"type": "keyword"},
                        "memory": {"type": "text"},
                        "create_time": {
                            "format": "yyyy-MM-dd HH:mm:ss.SSSSSSSSS",
                            "type": "date",
                        },
                    }
                }
            },
        )

        # init redis client
        redis_config = Config.get_redis_config()
        if redis_config:
            host = redis_config["host"]
            port = redis_config["port"]
            password = redis_config["password"]
            db = redis_config.get("db", 0)
            self.redis_client = JimdbApRedis(
                host=host, port=port, password=password, db=db
            )
        else:
            self.redis_client = LocalRedis()

    async def batch_init_oxy(self, *class_type):
        """Batch initialize oxy objects of specified types asynchronously.

        Args:
            class_types: List of class types to initialize (e.g., BaseLLM, BaseTool, BaseAgent).

        NOTE:
            Fetch all oxy objects of the specified class types,
        """
        tasks = []
        for oxy_name in list(self.oxy_name_to_oxy.keys()):
            oxy = self.oxy_name_to_oxy[oxy_name]
            if not isinstance(oxy, class_type):
                continue
            oxy.set_mas(self)
            task = oxy.init()
            if Config.get_tool_is_concurrent_init():
                tasks.append(task)
            else:
                await task
        if tasks:
            await asyncio.gather(*tasks)

    async def init_all_oxy(self):
        """Initializing all tools and agents assign values of agent.tools to each
        agent."""
        await self.batch_init_oxy(BaseLLM, BaseTool)
        await self.batch_init_oxy(BaseFlow, BaseAgent)

    def init_master_agent_name(self):
        """Initialize the master agent name.

        This method iterates through all registered Oxy objects and checks if they are
        master agents. If a master agent is found, its name is set as the master agent
        name.
        """
        for oxy_name, oxy in self.oxy_name_to_oxy.items():
            if not self.is_agent(oxy_name):
                continue
            # Set the first agent as the master agent if not already set
            if not self.master_agent_name:
                self.master_agent_name = oxy_name
            if oxy.is_master:
                self.master_agent_name = oxy_name
                break

    # ------------------------------------------------------------------
    # Organisation helpers
    # ------------------------------------------------------------------
    def is_agent(self, oxy_name):
        """Show if the oxy_name is an agent."""
        if not oxy_name:
            return False
        # return self.oxy_name_to_oxy[oxy_name].category == 'agent'
        return isinstance(self.oxy_name_to_oxy[oxy_name], (BaseFlow, BaseAgent))

    def init_agent_organization(self):
        """Append callable tools to the agent organization structure."""

        def add_tools(agent_organization: list, agent_names: list, path: list = []):
            for agent_name in agent_names:
                agent = self.oxy_name_to_oxy[agent_name]
                temp_path = path.copy()
                temp_path.append(agent_name)
                agent_organization.append(
                    {
                        "name": agent_name,
                        "type": agent.category,
                    }
                )
                if not self.is_agent(agent_name):
                    continue

                if isinstance(agent, RemoteAgent):
                    agent_organization[-1]["children"] = agent.get_org()
                else:
                    agent_organization[-1]["children"] = []

                tool_name_list = []
                for tool_name in agent.permitted_tool_name_list:
                    # if not agent.is_sourcing_tools and tool_name == 'retrieve_tools':
                    #     continue
                    tool_name_list.append(tool_name)

                add_tools(agent_organization[-1]["children"], tool_name_list, temp_path)

        agent_organization = []
        if self.master_agent_name:
            add_tools(agent_organization, [self.master_agent_name])
        else:
            # If no master agent is found, create an empty organization structure
            agent_organization.append(dict())

        self.agent_organization = agent_organization[0]

    """
    Display the organization structure of the MAS.
    Prints the agent organization in a tree format in the logs.
    """

    def show_org(self):
        logger.info("🌐 OxyGent MAS Organization Structure Overview")
        logger.info("=" * 64)
        print_tree(self.agent_organization, logger=logger)
        logger.info("=" * 64)

    # ------------------------------------------------------------------
    # Optional Vearch integration
    # ------------------------------------------------------------------

    async def create_vearch_table(self):
        """Link to the vearch database and create tables for tools."""
        tool_list = []
        for tool_name, tool in self.oxy_name_to_oxy.items():
            if not self.is_agent(tool_name):
                continue
            for permitted_tool_name in tool.permitted_tool_name_list:
                tool_desc = self.oxy_name_to_oxy[permitted_tool_name].desc_for_llm
                if permitted_tool_name in ["retrieve_tools"]:
                    continue
                if tool.is_retain_subagent_in_toolset and self.is_agent(
                    permitted_tool_name
                ):
                    continue
                tool_list.append((self.name, tool_name, permitted_tool_name, tool_desc))
        if tool_list:
            # vearch
            self.vearch_client = VearchDB(Config.get_vearch_config())
            await self.vearch_client.create_vearch_table_by_tool_list(tool_list)

    # ------------------------------------------------------------------
    # Misc. public helpers
    # ------------------------------------------------------------------

    async def wait_next(self):
        """Block execution until :attr:`lock` becomes ``False``.

        This coroutine is particularly useful in *step‑debug* or *demo* modes where a
        human operator wants to inspect the current MAS state before allowing it to
        continue.
        """
        self.lock = True
        while True:
            if self.lock:
                await asyncio.sleep(0.1)
            else:
                return

    def set_oxy_attr(self, oxy_name, attr_key, attr_value):
        """Dynamically mutate a component attribute at runtime.

        Args:
            oxy_name: Registered name of the component.
            attr_key: Attribute to change.
            attr_value: New value to assign.

        Returns:
            bool: ``True`` if the mutation succeeded, else ``False``.
        """
        if oxy_name not in self.oxy_name_to_oxy:
            return False
        oxy = self.oxy_name_to_oxy[oxy_name]
        if not hasattr(oxy, attr_key):
            return False
        try:
            setattr(oxy, attr_key, attr_value)
            logger.info(
                f"Attribute [{attr_key}] for oxy [{oxy_name}] has been modified to [{attr_value}]"
            )
            return True
        except Exception as e:
            logger.error(
                f"Failed to set attribute [{attr_key}] for oxy [{oxy_name}]: {e}"
            )
            return False

    async def call(self, callee, arguments, **kwargs):
        """Invoke an *Oxy* component directly and return its output.

        Args:
            callee (str): Name of the target component (must exist in the
                internal registry).
            arguments (dict): Payload that will populate
                :attr:`~schemas.OxyRequest.arguments`.
            **kwargs: Additional :class:`~schemas.OxyRequest` fields such as
                *caller*, *from_trace_id*, or *shared_data*.

        Returns:
            Any: The ``output`` field of the resulting
            :class:`~schemas.OxyResponse`.

        Raises:
            KeyError: If *callee* is not registered.
        """
        oxy_request = OxyRequest(callee=callee, arguments=arguments, **kwargs)
        oxy_request.mas = self

        oxy = self.oxy_name_to_oxy[oxy_request.callee]
        oxy_response = await oxy.execute(oxy_request)
        return oxy_response.output

    async def send_message(self, message, redis_key):
        """Push *message* onto a capped Redis list.

        The data is MsgPack‑encoded before being stored.  At most **10** items
        are kept to bound memory usage for long‑running SSE connections.

        Args:
            message: Any serialisable Python object.
            redis_key: Target Redis key (usually ``mas_msg:{app}:{trace_id}``).
        """
        if Config.get_message_is_show_in_terminal():
            logger.info(message)
        bytes_msg = msgpack.packb(msgpack_preprocess(message))
        if Config.get_message_is_stored():
            parts = redis_key.split(":")
            current_trace_id = parts[-1] if len(parts) >= 3 else ""

            message_doc = {
                "trace_id": current_trace_id,
                "message": to_json(message),  # Convert message to JSON string
                "message_type": message.get("type", "")
                if isinstance(message, dict)
                else "",
                "create_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            }

            # Insert into Elasticsearch
            await self.es_client.index(
                index=Config.get_app_name() + "_message", body=message_doc
            )
        await self.redis_client.lpush(redis_key, bytes_msg)

    async def chat_with_agent(
        self,
        payload: dict = None,
        send_msg_key: str = "",
    ) -> OxyResponse:
        """Top‑level helper that forwards a *chat query* into the MAS.

        The method converts *payload* into an :class:`~schemas.OxyRequest`,
        ensures reasonable defaults (e.g. *callee* = master agent), and then
        awaits the resulting :class:`~schemas.OxyResponse`.

        If *send_msg_key* is supplied, partial outputs are written to the
        corresponding Redis list so that a connected SSE client can stream
        them to the browser.

        Args:
            payload: Mapping that **must** contain the key ``query``.
            send_msg_key: Optional Redis key for SSE streaming.

        Returns:
            OxyResponse: Fully populated response object.
        """
        try:
            # distinct attachments
            if "attachments" in payload and payload["attachments"]:
                atts, remotes = [], []
                for att in payload["attachments"]:
                    is_remote = att.startswith(("http://", "https://"))
                    full_path = (
                        att
                        if is_remote
                        else os.path.join(Config.get_cache_save_dir(), "uploads", att)
                    )
                    atts.append(full_path)
                    if is_remote:
                        remotes.append(full_path)
                payload["attachments"] = atts
                if remotes:
                    urls = payload.get("web_file_url_list", [])
                    payload["web_file_url_list"] = list(dict.fromkeys(urls + remotes))

                payload["query"] = _compose_query_parts(payload.get("query", ""), atts)

            if "shared_data" not in payload:
                payload["shared_data"] = dict()
            payload["shared_data"]["query"] = payload["query"]

            group_data = payload.get("group_data", {})

            # payload = payload or {}
            # payload.set default("shared_data",{})["query"] = payload.get("query","")

            if "restart_node_id" in payload and payload.get("restart_node_id"):
                es_response = await self.es_client.search(
                    Config.get_app_name() + "_node",
                    {
                        "query": {"term": {"node_id": payload["restart_node_id"]}},
                        "size": 1,
                    },
                )

                if es_response["hits"]["hits"]:
                    restart_node_data = es_response["hits"]["hits"][0]["_source"]

                    if payload.get("reference_trace_id"):
                        if (
                            restart_node_data["trace_id"]
                            == payload["reference_trace_id"]
                        ):
                            payload["restart_node_order"] = restart_node_data[
                                "update_time"
                            ]
                            logger.info(
                                f"Found restart node {payload['restart_node_id']} with matching trace_id"
                            )
                        else:
                            logger.warning(
                                f"Node {payload['restart_node_id']} found but trace_id mismatch: "
                                f"expected {payload['reference_trace_id']}, got {restart_node_data['trace_id']}"
                            )
                    else:
                        payload["restart_node_order"] = restart_node_data["update_time"]
                        payload["reference_trace_id"] = restart_node_data[
                            "trace_id"
                        ]  # 自动设置
                        logger.info(
                            f"Found restart node {payload['restart_node_id']}, auto-set trace_id to {restart_node_data['trace_id']}"
                        )
                else:
                    logger.warning(
                        f"Restart node {payload['restart_node_id']} not found in ES"
                    )

            oxy_request = OxyRequest(mas=self)
            oxy_request.group_data = group_data
            if "current_trace_id" in payload and payload["current_trace_id"]:
                oxy_request.current_trace_id = payload["current_trace_id"]
            # Set group_id: inherit if from_trace_id is provided, else new
            if "from_trace_id" in payload and payload["from_trace_id"]:
                es_response_group_id = await self.es_client.search(
                    Config.get_app_name() + "_trace",
                    {
                        "query": {"term": {"_id": payload["from_trace_id"]}},
                        "size": 1,
                    },
                )

                hits = es_response_group_id.get("hits", {}).get("hits", [])
                if hits:
                    oxy_request.group_id = hits[0]["_source"].get("group_id", "")
                    raw_group_data = hits[0]["_source"].get("group_data", {})
                    if isinstance(raw_group_data, str):
                        try:
                            history_group_data = json.loads(raw_group_data)
                        except json.JSONDecodeError:
                            logger.warning(
                                "Failed to parse group_data from string, using empty dict"
                            )
                            history_group_data = {}
                    else:
                        history_group_data = (
                            raw_group_data if isinstance(raw_group_data, dict) else {}
                        )

                    merged_group_data = history_group_data.copy()
                    merged_group_data.update(oxy_request.group_data)
                    oxy_request.group_data = merged_group_data
                    logger.debug(
                        f"继承历史会话 group_id: {oxy_request.group_id}, "
                        f"历史 group_data: {history_group_data if history_group_data else '空'}, "
                        f"当前 group_data: {oxy_request.group_data if oxy_request.group_data else '空'}, "
                        f"合并后 group_data: {merged_group_data}",
                        extra={"trace_id": oxy_request.current_trace_id},
                    )
                else:
                    logger.warning(
                        f"未找到 from_trace_id: {payload['from_trace_id']} 对应的记录，无法继承历史 group_data",
                        extra={"trace_id": oxy_request.current_trace_id},
                    )

            oxy_request_fields = oxy_request.model_fields
            for k, v in payload.items():
                if k in oxy_request_fields:
                    setattr(oxy_request, k, v)
                else:
                    oxy_request.arguments[k] = v

            if not oxy_request.callee:
                oxy_request.callee = self.master_agent_name

            oxy_response = await oxy_request.start()

            if send_msg_key:
                await self.send_message(
                    {"event": "close", "data": "done"}, send_msg_key
                )
            return oxy_response
        except Exception:
            logger.error(traceback.format_exc())
            raise

    # ------------------------------------------------------------------
    # Interactive CLI helper
    # ------------------------------------------------------------------

    async def start_cli_mode(self, first_query=None):
        """MAS communicates with the environment, launching REPL."""
        from_trace_id = ""
        if first_query:
            print("You: ", first_query)
            payload = {"query": first_query, "from_trace_id": from_trace_id}
            oxy_response = await self.chat_with_agent(payload=payload)
            from_trace_id = oxy_response.oxy_request.current_trace_id
            print("LLM: ", oxy_response.output)
        while True:
            query = input("Enter your query: ").strip()
            if query in ["exit", "quite", "bye"]:
                break
            if query in ["reset", "clear"]:
                from_trace_id = ""
                logger.info("System: The session has been reset.")
                continue
            payload = {"query": query, "from_trace_id": from_trace_id}
            oxy_response = await self.chat_with_agent(payload=payload)
            from_trace_id = oxy_response.oxy_request.current_trace_id
            print("LLM: ", oxy_response.output)

    # ------------------------------------------------------------------
    # FastAPI + SSE web service (unedited original docstring preserved)
    # ------------------------------------------------------------------

    async def event_stream(self, redis_key, current_trace_id, task):
        try:
            task.add_done_callback(
                lambda future: self.active_tasks.pop(current_trace_id, None)
            )
            self.active_tasks[current_trace_id] = task
            while True:
                bytes_msg = await self.redis_client.rpop(redis_key)
                if bytes_msg is None:
                    await asyncio.sleep(0.1)
                    continue
                message = msgpack.unpackb(bytes_msg)
                if message:
                    if isinstance(message, dict):
                        if "event" in message:
                            yield message
                            logger.info(
                                "SSE connection terminated.",
                                extra={"trace_id": current_trace_id},
                            )
                            break
                        # Convert before sending message: Use msg.content.arguments.query
                        if message.get("type", "") == "tool_call" and isinstance(
                            message.get("content", {})
                            .get("arguments", {})
                            .get("query", ""),
                            list,
                        ):
                            for msg in message["content"]["arguments"]["query"]:
                                if msg.get("type") == "text":
                                    message["content"]["arguments"]["query"] = msg.get(
                                        "text", ""
                                    )
                                    break
                        if message.get("type", "") == "observation":
                            message["content"]["output"] = to_json(
                                message["content"]["output"]
                            )
                    # Send message
                    yield {"data": to_json(message)}
        except asyncio.CancelledError:
            logger.info(
                "SSE connection terminated.",
                extra={"trace_id": current_trace_id},
            )
            self.active_tasks[current_trace_id].cancel()
            raise

    async def start_web_service(
        self, first_query=None, welcome_message=None, host=None, port=None
    ):
        """Start the FastAPI + SSE service (see original inline documentation)."""

        if not self.master_agent_name:
            logger.warning("No agent was registered.")

        self.first_query = first_query  # First query would be displayed in the frontend
        if welcome_message:
            self.welcome_message = welcome_message
        if host is None:
            host = Config.get_server_host()
        if port is None:
            port = Config.get_server_port()

        # Start the FastAPI web service simultaneously with the MAS
        import importlib.resources

        import uvicorn
        from fastapi import FastAPI, Request
        from fastapi.staticfiles import StaticFiles
        from sse_starlette.sse import EventSourceResponse

        app = FastAPI()

        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Or assign specific frontend origins
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        web_src = "web"
        with importlib.resources.as_file(
            importlib.resources.files("oxygent") / web_src
        ) as web_path:
            app.mount("/web", StaticFiles(directory=str(web_path)), name="web")
        app.include_router(router)
        """
        For all of the nodes we fill the following information:
        - path: The path from the root node (master agent) to the currrent node.
        - id_dict: A dictionary mapping agent names to their unique IDs.
        However the path would not be sent here.
        """

        @app.get("/get_organization")
        def get_organization():
            def add_path(node, current_path=None):
                if current_path is None:
                    current_path = []
                # Build the current node's path
                path = current_path + [node.get("name", "")]
                # Build a new node with the path by shallow copying
                new_node = dict(node)  # or copy.copy(node)
                new_node["path"] = path
                # Dispose the children recursively
                if "children" in node and isinstance(node["children"], list):
                    new_node["children"] = [
                        add_path(child, path) for child in node["children"]
                    ]
                return new_node

            def get_agent_to_id(org):
                result = []

                def traverse(node):
                    if isinstance(node, dict):
                        if node.get("type") in ["flow", "agent"]:
                            result.append(node.get("name", ""))
                        # Dispose the children recursively
                        children = node.get("children", [])
                        if isinstance(children, list):
                            for child in children:
                                traverse(child)

                traverse(org)
                # Remove duplicates while preserving order
                unique_names = list(OrderedDict.fromkeys(result))
                return {name: idx for idx, name in enumerate(unique_names)}

            return WebResponse(
                data={
                    "id_dict": get_agent_to_id(self.agent_organization),
                    "organization": add_path(self.agent_organization),
                }
            ).to_dict()

        """
        When teh frontend is loaded, it will send the first query to user.
        """

        @app.get("/get_first_query")
        def get_first_query():
            return WebResponse(
                data={"first_query": self.first_query if self.first_query else ""}
            ).to_dict()

        @app.get("/get_welcome_message")
        def get_welcome_message():
            return WebResponse(
                data={
                    "welcome_message": self.welcome_message
                    if self.welcome_message
                    else ""
                }
            ).to_dict()

        async def request_to_payload(request: Request):
            if request.method == "GET":
                params = dict(request.query_params)
                payload = dict()
                if "payload" in params:
                    try:
                        payload = json.loads(params["payload"])
                    except Exception as e:
                        return WebResponse(
                            code=400, message=f"can not convert data into JSON: {e}"
                        ).to_dict()
            elif request.method == "POST":
                payload = await request.json()

            payload = self.func_filter(payload)

            if "query" not in payload:
                payload["query"] = ""

            if "attachments" in payload:
                attachments_with_path = []
                remote_urls = []

                for attachment in payload["attachments"]:
                    is_remote = attachment.startswith(("http://", "https://"))
                    file_path = (
                        attachment
                        if is_remote
                        else os.path.join(
                            Config.get_cache_save_dir(), "uploads", attachment
                        )
                    )
                    attachments_with_path.append(file_path)
                    if is_remote:
                        remote_urls.append(file_path)

                # distinct attachments
                payload["attachments"] = attachments_with_path
                if remote_urls:
                    existing_urls = payload.get("web_file_url_list", [])
                    payload["web_file_url_list"] = list(
                        dict.fromkeys(existing_urls + remote_urls)
                    )

                # a2a style query
                payload["query"] = _compose_query_parts(
                    payload.get("query", ""), attachments_with_path
                )

            if "current_trace_id" not in payload:
                payload["current_trace_id"] = shortuuid.ShortUUID().random(length=16)

            # fetch headers
            if "shared_data" not in payload:
                payload["shared_data"] = dict()
            payload["shared_data"]["_headers"] = dict(request.headers)

            return payload

        @app.api_route("/chat", methods=["GET", "POST"])
        async def chat(request: Request):
            payload = await request_to_payload(request)
            oxy_response = await self.chat_with_agent(payload=payload)
            return oxy_response.output

        @app.api_route("/sse/chat", methods=["GET", "POST"])
        async def sse_chat(request: Request):
            payload = await request_to_payload(request)
            current_trace_id = payload["current_trace_id"]

            logger.info(
                "SSE connection established.",
                extra={"trace_id": current_trace_id},
            )
            redis_key = f"{self.message_prefix}:{self.name}:{current_trace_id}"
            task = asyncio.create_task(
                self.chat_with_agent(payload=payload, send_msg_key=redis_key)
            )

            return EventSourceResponse(
                self.event_stream(redis_key, current_trace_id, task)
            )

        async def run_uvicorn():
            """Run the Uvicorn server with the FastAPI app."""
            logger.info("🔗 OxyGent MAS FastAPI Service Initialization")
            logger.info("=" * 64)
            config = uvicorn.Config(
                app,
                host=host,
                port=port,
                log_level=Config.get_server_log_level().lower(),
                log_config=None,
            )
            server = uvicorn.Server(config)

            await server.serve()

        web_task = asyncio.create_task(run_uvicorn())

        # Automatically open the web page after a short delay
        if Config.get_server_auto_open_webpage():
            import webbrowser

            await asyncio.sleep(1)
            web_url = f"http://{host}:{port}/web/index.html"
            webbrowser.open(web_url)
            logger.info(
                f"The web page {web_url} has been opened.", extra={"color": "yellow"}
            )
        await asyncio.gather(web_task)

    # ------------------------------------------------------------------
    # Batch helper
    # ------------------------------------------------------------------

    async def start_batch_processing(self, querys, return_trace_id=False):
        """Execute a batch of queries concurrently.

        Args:
            querys: Iterable of natural-language prompts.
            return_trace_id: If ``True`` the trace ID is returned together
                with each answer - handy for offline audits.

        Returns:
            list: Answers (or dicts with *output* + *trace_id*).
        """
        import time

        cost_times = []

        async def handle_query(query):
            start_time = time.time()
            from_trace_id = ""
            payload = {
                "query": query,
                "from_trace_id": from_trace_id,
                "extra_arg": "value",
            }
            oxy_response = await self.chat_with_agent(payload=payload)
            from_trace_id = oxy_response.oxy_request.current_trace_id
            end_time = time.time()
            cost_times.append(end_time - start_time)
            if return_trace_id:
                return {
                    "output": oxy_response.output,
                    "trace_id": oxy_response.oxy_request.current_trace_id,
                }
            else:
                return oxy_response.output

        tasks = [asyncio.create_task(handle_query(query)) for query in querys]
        results = await asyncio.gather(*tasks)
        logger.info("done.")
        return results
