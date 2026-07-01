"""OxyGent Multi-Agent System (MAS) runtime container.

Provides the MAS class — the top-level runtime that registers all Oxy instances
(agents, tools, LLMs), initializes database connections, builds the agent
organization tree, and offers multiple execution modes:

- ``start_web_service()`` — FastAPI + SSE server with built-in web UI
- ``start_cli_mode()`` — Interactive REPL for local testing
- ``start_batch_processing()`` — Concurrent batch execution
- ``chat_with_agent()`` — Programmatic entry point for single queries
"""

import asyncio
import copy
import json
import os
import time
from collections import OrderedDict
from typing import Any, AsyncIterator, Callable, Optional, Union

import msgpack
from elasticsearch import AsyncElasticsearch
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from .config import Config
from .databases.db_es import JesEs, LocalEs, MemoryEs
from .databases.db_redis import JimdbApRedis, LocalRedis
from .databases.db_vector import VearchDB
from .db_factory import DBFactory
from .log_setup import setup_logging
from .oxy import Oxy
from .oxy.agents.base_agent import BaseAgent
from .oxy.agents.remote_agent import RemoteAgent
from .oxy.base_flow import BaseFlow
from .oxy.base_oxy import ensure_async
from .oxy.base_tool import BaseTool
from .oxy.llms.base_llm import BaseLLM
from .routes import router
from .schemas import OxyRequest, OxyResponse, SSEMessage, WebResponse
from .utils.common_utils import (
    generate_uuid,
    get_format_time,
    get_timestamp,
    msgpack_preprocess,
    print_tree,
    to_json,
)

logger = None


class MAS(BaseModel):
    """Runtime container that manages all Oxy instances and routes messages.

    Registers agents, tools, and LLMs into a name-to-instance lookup table,
    initializes database connections (ES, Redis, Vearch), builds the agent
    organization tree, and provides multiple execution entry points (web,
    CLI, batch, programmatic).

    Attributes:
        name: Identifier for this MAS instance.
        oxy_name_to_oxy: Registry mapping Oxy names to their instances.
        master_agent_name: Name of the entry-point master agent.
        es_client: Elasticsearch client for persistence.
        redis_client: Redis client for SSE message queuing.
        vearch_client: Vector DB client for tool retrieval.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = Field("", description="Identifier for the mas.")

    default_oxy_space: list[Oxy] = Field(
        default_factory=list,
        description="Built-in core Oxy components always registered",
    )

    oxy_space: list[Oxy] = Field(
        default_factory=list,
        description="User-provided Oxy instances to register at startup",
    )

    oxy_name_to_oxy: dict[str, Oxy] = Field(
        default_factory=dict,
        description="Registry mapping Oxy names to their instances",
    )

    master_agent_name: str = Field(
        "", description="Name of the master agent serving as the entry point"
    )

    first_query: Union[str, list[str]] = Field(
        "", description="Initial query sent to the master agent on web UI load"
    )

    welcome_message: str = Field(
        default_factory=Config.get_agent_welcome_message,
        description="Welcome message displayed to users on session start",
    )

    agent_organization: dict[str, Any] = Field(
        default_factory=dict,
        description="Hierarchical tree of agents and their callable tools",
    )

    vearch_client: Optional[VearchDB] = Field(
        None, description="Vearch vector database client for tool retrieval"
    )
    es_client: Optional[AsyncElasticsearch] = Field(
        None, description="Elasticsearch client for trace/node persistence"
    )
    redis_client: Optional[JimdbApRedis] = Field(
        None, description="Redis client for SSE message queuing"
    )

    lock: bool = Field(False, description="Global lock flag to pause new requests")
    active_tasks: dict[str, asyncio.Task] = Field(
        default_factory=dict,
        description="Currently running task futures keyed by trace_id",
    )
    background_tasks: dict[str, set[asyncio.Task]] = Field(
        default_factory=dict,
        description="Background asyncio tasks keyed by trace_id",
    )
    event_dict: dict[str, asyncio.Event] = Field(
        default_factory=dict,
        description="Asyncio events for coordinating task completion",
    )

    message_prefix: str = Field(
        "oxygent", description="Prefix for Redis message queue keys"
    )

    global_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Application-scoped public data shared across all traces",
    )

    func_filter: Optional[Callable] = Field(
        lambda x: x,
        exclude=True,
        description="Request filter function applied before routing",
    )
    func_interceptor: Optional[Callable] = Field(
        lambda x: None,
        exclude=True,
        description="Request interceptor for validation or early exit",
    )

    func_process_message: Optional[Callable] = Field(
        lambda x, oxy_request: x,
        exclude=True,
        description="Hook to transform outgoing messages before sending",
    )

    routers: list[Any] = Field(
        default_factory=list,
        description="Additional FastAPI routers to mount on the web server",
    )
    middlewares: list[Any] = Field(
        default_factory=list,
        description="Additional ASGI middlewares for the web server",
    )
    mounts: list[dict[str, Any]] = Field(
        default_factory=list, description="Additional ASGI mounts for the web server"
    )

    stream_dict: dict[str, list[str]] = Field(
        default_factory=dict, description="SSE stream buffers keyed by trace_id"
    )
    feedback_dict: dict[str, asyncio.Queue] = Field(
        default_factory=dict,
        description="Feedback queues keyed by trace_id for interactive responses",
    )
    channel_id_dict: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Channel IDs used by each trace for message routing",
    )
    enable_a2a_server: bool = Field(
        False, description="Whether to auto-enable built-in A2A server adapter."
    )
    a2a_server_name: str = Field("a2a_server_agent")
    a2a_server_desc: str = Field("")
    a2a_target_agent_name: str = Field("")
    a2a_base_path: str = Field("/a2a")

    def __init__(self, **kwargs: Any) -> None:
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
        for field_name in ("func_filter", "func_interceptor", "func_process_message"):
            func = getattr(self, field_name, None)
            if func is not None:
                object.__setattr__(self, field_name, ensure_async(func))
        global logger
        logger = setup_logging()
        if self.name:
            Config.set_app_name(self.name)
        else:
            self.name = Config.get_app_name()

    async def __aenter__(self) -> "MAS":
        await self.init()

        # Register this MAS instance globally for API access
        try:
            from .routes import set_global_mas_instance

            set_global_mas_instance(self)
            logger.debug("Registered MAS instance globally for API access")
        except Exception as e:
            logger.warning(
                f"Failed to register MAS instance globally: {e}", exc_info=True
            )

        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        async def _safe(coro, label: str) -> None:
            try:
                await coro
                logger.info(f"✓ {label} shutdown completed.")
            except Exception as e:
                logger.warning(f"Error during shutdown ({label}): {e}", exc_info=True)

        logger.info("=" * 64)
        logger.info("🔒 OxyGent MAS Application Shutdown Initiated")
        logger.info("=" * 64)

        # 1. Wait for background tasks
        all_tasks = [t for tasks in self.background_tasks.values() for t in tasks]
        if all_tasks:
            await _safe(
                asyncio.gather(*all_tasks, return_exceptions=True),
                "background tasks",
            )

        # 2. Tear down resources — each step runs regardless of prior failures
        from .live_prompt import close_prompt_manager

        await _safe(close_prompt_manager(), "prompt manager")

        if self.es_client:
            await _safe(self.es_client.close(), "ES client")

        if self.redis_client:
            await _safe(self.redis_client.close(), "Redis client")

        await _safe(self.cleanup_all(), "oxy cleanup")

        logger.info("=" * 64)
        logger.info("🪂 OxyGent MAS Application Exit")
        logger.info("=" * 64)

    def add_background_task(self, trace_id: str, task: asyncio.Task) -> None:
        """Register a background task under the given trace_id."""
        self.background_tasks.setdefault(trace_id, set()).add(task)
        task.add_done_callback(lambda t: self._discard_background_task(trace_id, t))

    def _discard_background_task(self, trace_id: str, task: asyncio.Task) -> None:
        """Remove a finished task from its trace_id bucket."""
        bucket = self.background_tasks.get(trace_id)
        if bucket is not None:
            bucket.discard(task)
            if not bucket:
                del self.background_tasks[trace_id]

    async def await_background_tasks(self, trace_id: str) -> None:
        """Wait for all background tasks belonging to *trace_id* to finish."""
        tasks = self.background_tasks.get(trace_id)
        if tasks:
            await asyncio.gather(*tasks)

    @classmethod
    async def create(cls, **kwargs: Any) -> "MAS":
        self = cls(**kwargs)
        await self.init()
        return self

    def show_banner(self) -> None:
        """Print the OxyGent ASCII art banner."""
        from .banner import oxygent_slant as banner_str

        print(banner_str[1:-1])

    def show_mas_info(self) -> None:
        """Print basic MAS configuration info."""
        import platform
        from datetime import datetime

        logger.info("=" * 64)
        logger.info("🚀 OxyGent MAS Application Startup Information")
        logger.info("=" * 64)
        logger.info(f"App Name     : {Config.get_app_name()}")
        logger.info(f"Version      : {Config.get_app_version()}")
        logger.info(f"Environment  : {Config._env}")
        logger.info(f"Port         : {Config.get_server_port()}")
        logger.info(f"Python Ver   : {platform.python_version()}")
        logger.info(f"Cache Dir    : {Config.get_cache_save_dir()}")
        logger.info(f"Start Time   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 64)

    def add_oxy(self, oxy: Oxy) -> None:
        """Register a single Oxy object.

        Args:
            oxy: The component instance to add.

        Raises:
            ValueError: If another component with the same ``oxy.name``
                already exists in the registry.
        """
        if oxy.name in self.oxy_name_to_oxy:
            raise Exception(f"oxy [{oxy.name}] already exists.")
        self.oxy_name_to_oxy[oxy.name] = oxy

    def add_oxy_list(self, oxy_list: list[Oxy]) -> None:
        """Register a list of Oxy objects.

        Args:
            oxy_list: List of Oxy instances to register.
        """
        for oxy in oxy_list:
            self.add_oxy(oxy)

    async def init(self) -> None:
        """Initialize the MAS. This coroutine performs all necessary setup steps to
        prepare the MAS for operation.

        It includes:
        - Printing the startup banner and environment information
        - Register all the oxy instances in the oxy_space and inject them into the MAS
        - Initializing the database connections (Elasticsearch, Redis)
        - Setting up the agent organization structure
        - Initialize the vector search if configured
        - Setting up dynamic agents for live prompt management
        """
        self.show_banner()
        self.show_mas_info()
        # Register default oxy_space
        self.add_oxy_list(self.oxy_space)
        if Config.get_vearch_config():
            from .core_tools.retrieve_tools import fh as retrieve_fh

            self.add_oxy(retrieve_fh)
        # Initialize database asynchronously
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

        # Setup dynamic agents for live prompt management
        logger.info("📋 OxyGent MAS Management Initialization")
        logger.info("=" * 64)
        try:
            from .live_prompt import setup_dynamic_agents

            await setup_dynamic_agents(self)
            logger.debug("Dynamic agent management initialized")
        except Exception as e:
            logger.warning(f"Failed to setup dynamic agents: {e}", exc_info=True)
        logger.info("=" * 64)

    async def cleanup_all(self) -> None:
        """Gracefully release resources held by all registered Oxy components.

        Calls ``cleanup()`` on every registered :class:`Oxy` instance.
        Each cleanup is invoked individually so that a failure in one
        component does not prevent others from releasing their resources.
        """
        for oxy_name, oxy in self.oxy_name_to_oxy.items():
            try:
                await oxy.cleanup()
            except Exception as e:
                logger.warning(
                    f"Error during cleanup of oxy '{oxy_name}': {e}",
                    exc_info=True,
                )

    async def init_db(self) -> None:
        """Es --- (table_name: key)

        {app_name}_trace: trace_id: record trace of each call
        {app_name}_node: node_id: record log of each node
        {app_name}_history: history_id: record history of read and write operations
        """

        # Initialize Elasticsearch client
        db_factory = DBFactory()
        if Config.get_es_config():
            jes_config = Config.get_es_config()
            hosts = jes_config["hosts"]
            user = jes_config["user"]
            password = jes_config["password"]
            self.es_client = db_factory.get_instance(JesEs, hosts, user, password)
        elif Config.get_storage_es_engine() == "MemoryEs":
            self.es_client = MemoryEs()
        else:
            self.es_client = db_factory.get_instance(LocalEs)

        app = Config.get_app_name()
        settings = Config.get_es_settings_config()

        # Create core indices
        await self.es_client.create_index(
            app + "_trace",
            self._trace_index_schema(settings),
        )
        if Config.get_message_is_stored():
            await self.es_client.create_index(
                app + "_message",
                self._message_index_schema(settings),
            )
        await self.es_client.create_index(
            app + "_node",
            self._node_index_schema(settings),
        )
        await self.es_client.create_index(
            app + "_history",
            self._history_index_schema(settings),
        )
        await self.es_client.create_index(
            app + "_prompt",
            self._prompt_index_schema(settings),
        )
        await self.es_client.create_index(
            app + "_prompt_history",
            self._prompt_history_index_schema(settings),
        )
        await self.es_client.create_index(
            app + "_rating",
            self._rating_index_schema(settings),
        )
        await self.es_client.create_index(
            app + "_rating_stats",
            self._rating_stats_index_schema(settings),
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

    # ------------------------------------------------------------------
    # Index schema definitions
    # ------------------------------------------------------------------

    @staticmethod
    def _trace_index_schema(settings: dict) -> dict:
        return {
            "mappings": {
                "properties": {
                    "request_id": {"type": "keyword"},
                    "group_id": {"type": "keyword"},
                    "group_data": Config.get_es_schema_group_data(),
                    "trace_id": {"type": "keyword"},
                    "shared_data": Config.get_es_schema_shared_data(),
                    "original_payload": {"type": "text"},
                    "from_trace_id": {"type": "keyword"},
                    "root_trace_ids": {"type": "keyword"},
                    "input": {"type": "text"},
                    "callee": {"type": "keyword"},
                    "output": {"type": "text"},
                    "create_time": {
                        "format": "yyyy-MM-dd HH:mm:ss.SSSSSSSSS",
                        "type": "date",
                    },
                    "update_time": {
                        "format": "yyyy-MM-dd HH:mm:ss.SSSSSSSSS",
                        "type": "date",
                    },
                },
            },
            "settings": settings,
        }

    @staticmethod
    def _message_index_schema(settings: dict) -> dict:
        return {
            "mappings": {
                "properties": {
                    "message_id": {"type": "keyword"},
                    "group_id": {"type": "keyword"},
                    "trace_id": {"type": "keyword"},
                    "node_id": {"type": "keyword"},
                    "node_name": {"type": "keyword"},
                    "message": {"type": "text"},
                    "message_type": {"type": "keyword"},
                    "message_event": {"type": "keyword"},
                    "message_timestamp": {"type": "long"},
                    "create_time": {
                        "format": "yyyy-MM-dd HH:mm:ss.SSSSSSSSS",
                        "type": "date",
                    },
                },
            },
            "settings": settings,
        }

    @staticmethod
    def _node_index_schema(settings: dict) -> dict:
        return {
            "mappings": {
                "properties": {
                    "node_id": {"type": "keyword"},
                    "copied_node_id": {"type": "keyword"},
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
                },
            },
            "settings": settings,
        }

    @staticmethod
    def _history_index_schema(settings: dict) -> dict:
        return {
            "mappings": {
                "properties": {
                    "history_id": {"type": "keyword"},
                    "session_name": {"type": "keyword"},
                    "trace_id": {"type": "keyword"},
                    "memory": {"type": "text"},
                    "create_time": {
                        "format": "yyyy-MM-dd HH:mm:ss.SSSSSSSSS",
                        "type": "date",
                    },
                },
            },
            "settings": settings,
        }

    @staticmethod
    def _prompt_index_schema(settings: dict) -> dict:
        return {
            "mappings": {
                "properties": {
                    "prompt_key": {"type": "keyword"},
                    "prompt_content": {
                        "type": "text",
                        "analyzer": "standard",
                    },
                    "description": {"type": "text"},
                    "category": {"type": "keyword"},
                    "agent_type": {"type": "keyword"},
                    "version": {"type": "integer"},
                    "is_active": {"type": "boolean"},
                    "created_at": {"type": "date"},
                    "updated_at": {"type": "date"},
                    "created_by": {"type": "keyword"},
                    "tags": {"type": "keyword"},
                }
            },
            "settings": settings,
        }

    @staticmethod
    def _prompt_history_index_schema(settings: dict) -> dict:
        return {
            "mappings": {
                "properties": {
                    "prompt_key": {"type": "keyword"},
                    "prompt_content": {
                        "type": "text",
                        "analyzer": "standard",
                    },
                    "description": {"type": "text"},
                    "category": {"type": "keyword"},
                    "agent_type": {"type": "keyword"},
                    "version": {"type": "integer"},
                    "is_active": {"type": "boolean"},
                    "is_history": {"type": "boolean"},
                    "history_id": {"type": "keyword"},
                    "created_at": {"type": "date"},
                    "updated_at": {"type": "date"},
                    "archived_at": {"type": "date"},
                    "created_by": {"type": "keyword"},
                    "tags": {"type": "keyword"},
                }
            },
            "settings": settings,
        }

    @staticmethod
    def _rating_index_schema(settings: dict) -> dict:
        return {
            "mappings": {
                "properties": {
                    "rating_id": {"type": "keyword"},
                    "trace_id": {"type": "keyword"},
                    "rating_type": {"type": "keyword"},
                    "user_id": {"type": "keyword"},
                    "user_ip": {"type": "ip"},
                    "comment": {"type": "text"},
                    "erp": {"type": "keyword"},
                    "create_time": {"type": "keyword"},
                    "update_time": {"type": "keyword"},
                }
            },
            "settings": settings,
        }

    @staticmethod
    def _rating_stats_index_schema(settings: dict) -> dict:
        return {
            "mappings": {
                "properties": {
                    "trace_id": {"type": "keyword"},
                    "like_count": {"type": "integer"},
                    "dislike_count": {"type": "integer"},
                    "total_ratings": {"type": "integer"},
                    "satisfaction_rate": {"type": "float"},
                    "last_updated": {"type": "keyword"},
                }
            },
            "settings": settings,
        }

    async def batch_init_oxy(self, *class_type: type) -> None:
        """Batch initialize oxy objects of specified types asynchronously.

        Args:
            class_types: List of class types to initialize (e.g., BaseLLM, BaseTool, BaseAgent).

        NOTE:
            Initialize all oxy objects of the specified class types.
            If any init fails, already-initialized oxy objects of the same
            batch are cleaned up before the exception propagates.
        """
        targets = [
            (name, oxy)
            for name, oxy in self.oxy_name_to_oxy.items()
            if isinstance(oxy, class_type)
        ]
        for _name, oxy in targets:
            oxy.set_mas(self)

        initialized_names: list[str] = []
        if Config.get_tool_is_concurrent_init():
            results = await asyncio.gather(
                *(oxy.init() for _name, oxy in targets),
                return_exceptions=True,
            )
            first_error = None
            for (name, _oxy), result in zip(targets, results):
                if isinstance(result, Exception):
                    logger.error(
                        f"Failed to initialize oxy '{name}': {result}", exc_info=result
                    )
                    if first_error is None:
                        first_error = result
                else:
                    initialized_names.append(name)
            if first_error is not None:
                for name in initialized_names:
                    try:
                        await self.oxy_name_to_oxy[name].cleanup()
                    except Exception as ce:
                        logger.warning(
                            f"Error during rollback cleanup of oxy '{name}': {ce}",
                            exc_info=True,
                        )
                raise first_error
        else:
            try:
                for name, oxy in targets:
                    await oxy.init()
                    initialized_names.append(name)
            except Exception:
                for name in initialized_names:
                    try:
                        await self.oxy_name_to_oxy[name].cleanup()
                    except Exception as ce:
                        logger.warning(
                            f"Error during rollback cleanup of oxy '{name}': {ce}",
                            exc_info=True,
                        )
                raise

    async def init_all_oxy(self) -> None:
        """Initializing all tools and agents assign values of agent.tools to each
        agent."""
        await self.batch_init_oxy(BaseLLM, BaseTool)
        await self.batch_init_oxy(BaseFlow, BaseAgent)

    def init_master_agent_name(self) -> None:
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
    def is_agent(self, oxy_name: str) -> bool:
        """Check if the oxy_name is an agent."""
        if not oxy_name:
            return False
        return isinstance(self.oxy_name_to_oxy[oxy_name], (BaseFlow, BaseAgent))

    def init_agent_organization(self) -> None:
        """Build the agent organization tree structure, including tools."""

        def add_tools(agent_organization: list, agent_names: list, path: list = None):
            if path is None:
                path = []
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

                tool_name_list = list(
                    set(agent.permitted_tool_name_list + agent.permitted_oxy)
                )

                add_tools(agent_organization[-1]["children"], tool_name_list, temp_path)

        agent_organization = []
        if self.master_agent_name:
            add_tools(agent_organization, [self.master_agent_name])
        else:
            # If no master agent is found, create an empty organization structure
            agent_organization.append(dict())

        self.agent_organization = agent_organization[0]

    def show_org(self) -> None:
        """Display the agent organization tree."""
        logger.info("🌐 OxyGent MAS Organization Structure Overview")
        logger.info("=" * 64)
        print_tree(self.agent_organization, logger=logger)
        logger.info("=" * 64)

    # ------------------------------------------------------------------
    # Optional Vearch integration
    # ------------------------------------------------------------------

    async def create_vearch_table(self) -> None:
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

    async def wait_next(self) -> None:
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

    def set_oxy_attr(self, oxy_name: str, attr_key: str, attr_value: Any) -> bool:
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
                f"Failed to set attribute [{attr_key}] for oxy [{oxy_name}]: {e}",
                exc_info=True,
            )
            return False

    async def call(
        self, callee: str, arguments: dict[str, Any], **kwargs: Any
    ) -> OxyResponse:
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

    async def send_message(
        self, sse_message: SSEMessage, redis_key: str, group_id: str = ""
    ) -> None:
        """Push *message* onto a capped Redis list.

        The data is MsgPack‑encoded before being stored.  At most **10** items
        are kept to bound memory usage for long‑running SSE connections.

        Args:
            message: Any serialisable Python object.
            redis_key: Target Redis key (usually ``mas_msg:{app}:{trace_id}``).
        """
        message = sse_message.data
        if Config.get_message_is_show_in_terminal():
            logger.info(f"--- Send Message ---: {sse_message.to_sse()}")

        message_type = ""
        message_is_stored = Config.get_message_is_stored()
        message_is_send = True
        _is_stored, _is_send = "_is_stored", "_is_send"
        if isinstance(message, dict):
            message_type = message.get("type", "")
            if _is_stored in message:
                message_is_stored = message[_is_stored]
                del message[_is_stored]
            if _is_send in message:
                message_is_send = message[_is_send]
                del message[_is_send]
            sse_message.data = message

        if message_is_stored:
            parts = redis_key.split(":")
            current_trace_id = parts[-1] if len(parts) >= 3 else ""

            # Handle the case where message is a str
            node_id = ""
            node_name = ""
            message_timestamp = get_timestamp()
            if isinstance(message, dict):
                message_timestamp = message.get("timestamp", get_timestamp())
                if isinstance(message.get("content"), dict):
                    node_id = message.get("content", {}).get("node_id", "")
                    node_name = message.get("content", {}).get("agent", "")

            if message_type in ["stream", "stream_end"]:
                # Enqueue
                if message_type == "stream":
                    delta = message.get("content", {}).get("delta", "")
                    if node_id not in self.stream_dict:
                        self.stream_dict[node_id] = []
                    self.stream_dict[node_id].append(delta)
                if message_type == "stream_end" or (
                    self.stream_dict[node_id]
                    and len(self.stream_dict[node_id])
                    % Config.get_message_stream_batch_size()
                    == 0
                ):
                    message_id = generate_uuid()
                    merged_type = "merged_stream"
                    save_message_task = asyncio.create_task(
                        self.es_client.index(
                            Config.get_app_name() + "_message",
                            doc_id=message_id,
                            body={
                                "message_id": message_id,
                                "group_id": group_id,
                                "trace_id": current_trace_id,
                                "node_id": node_id,
                                "node_name": node_name,
                                "message": to_json(
                                    {
                                        "type": merged_type,
                                        "content": "".join(self.stream_dict[node_id]),
                                    }
                                ),
                                "message_type": merged_type,
                                "message_event": sse_message.event,
                                "message_timestamp": message_timestamp,
                                "create_time": get_format_time(),
                            },
                        )
                    )
                    self.add_background_task(current_trace_id, save_message_task)
                    self.stream_dict.pop(node_id, None)
            else:
                save_message_task = asyncio.create_task(
                    self.es_client.index(
                        Config.get_app_name() + "_message",
                        doc_id=sse_message.id,
                        body={
                            "message_id": sse_message.id,
                            "group_id": group_id,
                            "trace_id": current_trace_id,
                            "node_id": node_id,
                            "node_name": node_name,
                            "message": to_json(message),
                            "message_type": message_type,
                            "message_event": sse_message.event,
                            "message_timestamp": message_timestamp,
                            "create_time": get_format_time(),
                        },
                    )
                )
                self.add_background_task(current_trace_id, save_message_task)
        if message_is_send:
            bytes_msg = msgpack.packb(msgpack_preprocess(sse_message.to_sse()))
            await self.redis_client.lpush(redis_key, bytes_msg)

    def clear_queues(self, trace_id: str) -> None:
        """Clear all Redis message queues for active traces."""
        for channel_id in self.channel_id_dict.get(trace_id, []):
            if channel_id in self.feedback_dict:
                del self.feedback_dict[channel_id]

    @staticmethod
    def _parse_dict_field(
        raw_value: Any, field_name: str = "dict field"
    ) -> dict[str, Any]:
        """Parse a raw value from ES into a dict.

        Handles str (JSON), dict, or other types gracefully.
        """
        if isinstance(raw_value, str):
            try:
                return json.loads(raw_value)
            except json.JSONDecodeError:
                logger.warning(
                    f"Failed to parse {field_name} from string (raw value: {raw_value!r}), using empty dict",
                    exc_info=True,
                )
                return {}
        elif isinstance(raw_value, dict):
            return raw_value
        return {}

    async def chat_with_agent(
        self,
        payload: Optional[dict[str, Any]] = None,
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
            payload: Mapping that contains the key ``query`` (optional when
                ``restart_node_id`` is provided — the original query is
                auto‑retrieved from the database).
            send_msg_key: Optional Redis key for SSE streaming.

        Returns:
            OxyResponse: Fully populated response object.
        """
        oxy_request = None
        try:
            # --- Restart: restore original payload from trace ---
            if payload.get("restart_node_id"):
                # Only these fields matter from the restart caller:
                restart_node_id = payload["restart_node_id"]
                restart_node_output = payload.get("restart_node_output", "")
                caller_trace_id = payload.get("current_trace_id", "")
                caller_request_id = payload.get("request_id", "")

                # Step 1: look up the node → derive reference_trace_id & ordering
                node_resp = await self.es_client.search(
                    Config.get_app_name() + "_node",
                    {
                        "query": {"term": {"node_id": restart_node_id}},
                        "size": 1,
                    },
                )
                if not node_resp["hits"]["hits"]:
                    raise ValueError(f"Restart node {restart_node_id} not found in ES")

                node_source = node_resp["hits"]["hits"][0]["_source"]
                reference_trace_id = node_source["trace_id"]
                restart_node_order = node_source["update_time"]

                # Step 2: look up the trace → retrieve original_payload
                trace_resp = await self.es_client.search(
                    Config.get_app_name() + "_trace",
                    {
                        "query": {"term": {"_id": reference_trace_id}},
                        "size": 1,
                    },
                )
                trace_hits = trace_resp.get("hits", {}).get("hits", [])
                if not trace_hits:
                    raise ValueError(
                        f"Trace {reference_trace_id} not found when restoring payload for restart"
                    )

                trace_source = trace_hits[0]["_source"]
                stored_payload = self._parse_dict_field(
                    trace_source.get("original_payload", "{}"),
                    "original_payload",
                )
                stored_payload.pop("restart_node_output", None)
                stored_payload.pop("current_trace_id", None)
                stored_payload.pop("request_id", None)

                # Step 3: rebuild payload — original as base, restart fields on top
                payload.clear()
                if stored_payload:
                    payload.update(stored_payload)
                    logger.info(
                        f"Restored original payload from trace {reference_trace_id} for restart"
                    )
                else:
                    # Fallback for old traces that lack original_payload
                    logger.warning(
                        f"Trace {reference_trace_id} has no original_payload, "
                        "falling back to trace-level fields"
                    )

                # Remove per-execution fields so they are regenerated
                payload.pop("current_trace_id", None)
                payload.pop("request_id", None)

                # Apply restart-specific fields
                payload["restart_node_id"] = restart_node_id
                payload["reference_trace_id"] = reference_trace_id
                payload["restart_node_order"] = restart_node_order
                if restart_node_output:
                    payload["restart_node_output"] = restart_node_output
                if caller_trace_id:
                    payload["current_trace_id"] = caller_trace_id
                if caller_request_id:
                    payload["request_id"] = caller_request_id

            # --- Common initialisation (both normal and restart paths) ---
            if "shared_data" not in payload:
                payload["shared_data"] = dict()

            # Initialize metrics dict and record query start time
            metrics = payload["shared_data"].setdefault("_metrics", {})
            metrics["_query_start_time"] = time.time()

            if "query" not in payload:
                payload["query"] = ""
            payload["shared_data"]["query"] = payload["query"]

            # Capture the effective payload (after merge, before OxyRequest mutations)
            # so future restarts from this execution can recover it.
            original_payload = copy.deepcopy(payload)

            oxy_request = OxyRequest(mas=self)
            if not send_msg_key:
                oxy_request.is_send_message = False

            # Set all fields from payload first，contain current_trace_id and group_data
            oxy_request_fields = OxyRequest.model_fields
            for k, v in payload.items():
                if k in oxy_request_fields:
                    setattr(oxy_request, k, v)
                else:
                    oxy_request.arguments[k] = v

            # Serialize the effective payload for restart recovery.
            oxy_request.original_payload = to_json(original_payload)

            # Special handling: when from_trace_id exists, inherit and merge historical group_data from ES
            # Note: This logic runs after the loop above to ensure merged result is the final value
            if "from_trace_id" in payload and payload["from_trace_id"]:
                # Wait for previous trace's background tasks to finish before proceeding
                await self.await_background_tasks(payload["from_trace_id"])
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
                    history_group_data = self._parse_dict_field(
                        hits[0]["_source"].get("group_data", {}),
                        "group_data",
                    )

                    merged_group_data = history_group_data.copy()
                    merged_group_data.update(oxy_request.group_data)
                    oxy_request.group_data = merged_group_data
                    logger.debug(
                        f"Inherited historical session group_id: {oxy_request.group_id}, "
                        f"history group_data: {history_group_data}, "
                        f"current group_data: {oxy_request.group_data}, "
                        f"merged group_data: {oxy_request.group_data}",
                        extra={"trace_id": oxy_request.current_trace_id},
                    )
                else:
                    logger.warning(
                        f"Cannot find record for from_trace_id: {oxy_request.from_trace_id}, unable to inherit historical group_data",
                        extra={"trace_id": oxy_request.current_trace_id},
                    )

            if not oxy_request.callee:
                oxy_request.callee = self.master_agent_name

            oxy_response = await oxy_request.start()

            if send_msg_key:
                await self.send_message(
                    SSEMessage(event="close", data="done"),
                    send_msg_key,
                    group_id=oxy_request.group_id,
                )
            return oxy_response
        except Exception as e:
            callee = (
                oxy_request.callee if oxy_request else payload.get("callee", "unknown")
            )
            trace_id = (
                oxy_request.current_trace_id
                if oxy_request
                else payload.get("current_trace_id", "unknown")
            )
            query_preview = str(payload.get("query", ""))[:200] if payload else "N/A"
            logger.error(
                f"Error in chat_with_agent (callee={callee}, trace_id={trace_id}, query={query_preview!r}): {e}",
                exc_info=True,
            )
            raise
        finally:
            if oxy_request:
                self.clear_queues(oxy_request.current_trace_id)

    # ------------------------------------------------------------------
    # Interactive CLI helper
    # ------------------------------------------------------------------

    async def start_cli_mode(self, first_query: Optional[str] = None) -> None:
        """Start an interactive CLI REPL for chatting with agents."""
        from_trace_id = ""
        if first_query:
            print("You: ", first_query)
            payload = {"query": first_query, "from_trace_id": from_trace_id}
            oxy_response = await self.chat_with_agent(payload=payload)
            from_trace_id = oxy_response.oxy_request.current_trace_id
            print("LLM: ", oxy_response.output)
        while True:
            query = input("Enter your query: ").strip()
            if query in ["exit", "quit", "bye"]:
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

    async def _process_redis_messages(
        self, redis_key: str, current_trace_id: str
    ) -> AsyncIterator[dict[str, Any]]:
        """Consume messages from Redis and yield them as SSE events."""
        while True:
            bytes_msg = await self.redis_client.rpop(redis_key)
            if bytes_msg is None:
                await asyncio.sleep(0.1)
                continue
            sse_message_dict = msgpack.unpackb(bytes_msg)
            if sse_message_dict:
                if sse_message_dict.get("event", "message") == "close":
                    yield sse_message_dict
                    logger.info(
                        "SSE connection terminated.",
                        extra={"trace_id": current_trace_id},
                    )
                    break
                # Convert before sending message: Use msg.content.arguments.query

                message = sse_message_dict.get("data", {})
                if isinstance(message, dict):
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
                    sse_message_dict["data"] = message
                # Send message
                yield sse_message_dict

    async def event_stream(
        self, redis_key: str, current_trace_id: str, task: asyncio.Task
    ) -> AsyncIterator[dict[str, Any]]:
        """Generate an SSE event stream for the given trace."""
        try:
            task.add_done_callback(
                lambda future: self.active_tasks.pop(current_trace_id, None)
            )
            self.active_tasks[current_trace_id] = task
            async for message in self._process_redis_messages(
                redis_key, current_trace_id
            ):
                yield message
        except asyncio.CancelledError:
            logger.info(
                "SSE connection terminated.",
                extra={"trace_id": current_trace_id},
            )
            self.active_tasks[current_trace_id].cancel()
            raise

    async def yield_async_message(
        self, redis_key: str, current_trace_id: str
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield async messages for the given trace from the Redis queue."""
        try:
            async for message in self._process_redis_messages(
                redis_key, current_trace_id
            ):
                yield message
        except asyncio.CancelledError:
            logger.info(
                "SSE connection terminated.",
                extra={"trace_id": current_trace_id},
            )
            raise

    async def start_web_service(
        self,
        first_query: Optional[Union[str, list[str]]] = None,
        welcome_message: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        routers: Optional[list[APIRouter]] = None,
        middlewares: Optional[list[Any]] = None,
        mounts: Optional[list[dict[str, Any]]] = None,
        shared_data: Optional[dict[str, Any]] = None,
        group_data: Optional[dict[str, Any]] = None,
        enable_a2a_server: bool | None = None,
        a2a_target_agent_name: str | None = None,
        a2a_base_path: str | None = None,
    ) -> None:
        """Start the FastAPI + SSE service (see original inline documentation)."""
        self.routers.extend(routers or [])
        self.middlewares.extend(middlewares or [])
        self.mounts.extend(mounts or [])

        if enable_a2a_server is not None:
            self.enable_a2a_server = enable_a2a_server
        # Deprecated: target is resolved from MAS master_agent_name.
        # Keep parameter for backward compatibility.
        if a2a_base_path:
            self.a2a_base_path = a2a_base_path

        existing_prefixes = {getattr(r, "prefix", "") for r in self.routers}

        if self.enable_a2a_server and self.a2a_base_path not in existing_prefixes:
            from .oxy.agents import A2AServerGateway

            a2a_server_agent = A2AServerGateway(
                a2a_base_path=self.a2a_base_path,
            )
            a2a_server_agent.set_mas(self)
            try:
                a2a_router = a2a_server_agent.build_router()
            except Exception as e:
                logger.warning(f"Failed to build auto A2A router: {e}", exc_info=True)
                a2a_router = None
            prefix = getattr(a2a_router, "prefix", "")
            if a2a_router and prefix not in existing_prefixes:
                self.routers.append(a2a_router)
                existing_prefixes.add(prefix)

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
        from fastapi import APIRouter, FastAPI, Request
        from fastapi.routing import APIRoute
        from fastapi.staticfiles import StaticFiles
        from sse_starlette.sse import EventSourceResponse

        def get_banks_from_router(router: APIRouter) -> list[dict[str, Any]]:
            banks = []
            for route in router.routes:
                if isinstance(route, APIRoute) and "bank" in getattr(route, "tags", []):
                    description = route.description
                    input_schema = {"type": "object", "properties": {}, "required": []}
                    for param in (
                        route.dependant.query_params + route.dependant.body_params
                    ):
                        param_type = (
                            getattr(param, "type_", None) or param.field_info.annotation
                        )
                        # Type conversion (simple implementation)
                        if param_type is str:
                            t = "string"
                        elif param_type is int:
                            t = "integer"
                        elif param_type is float:
                            t = "number"
                        elif param_type is bool:
                            t = "boolean"
                        else:
                            t = "string"
                        input_schema["properties"][param.name] = {
                            "type": t,
                            "description": param.field_info.description or "",
                        }
                        if (
                            getattr(param, "required", None)
                            or param.field_info.is_required()
                        ):
                            input_schema["required"].append(param.name)
                    banks.append(
                        {
                            "name": route.endpoint.__name__,
                            "endpoint": route.path,
                            "methods": route.methods,
                            "description": description,
                            "inputSchema": input_schema,
                        }
                    )
            return banks

        app = FastAPI()

        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=Config.get_server_allow_origins(),  # Or assign specific frontend origins
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @app.middleware("http")
        async def no_cache_static(request: Request, call_next):
            response = await call_next(request)
            if request.url.path.startswith("/web/"):
                response.headers["Cache-Control"] = "no-cache"
            # Prevent uploaded files from being rendered as HTML by the browser
            if request.url.path.startswith("/static/"):
                response.headers["Content-Disposition"] = "attachment"
                response.headers["X-Content-Type-Options"] = "nosniff"
                response.headers["Content-Security-Policy"] = "default-src 'none'"
            return response

        for app_middleware in self.middlewares:
            app.add_middleware(app_middleware)

        banks = []
        app.include_router(router)
        for app_router in self.routers:
            app.include_router(app_router)
            if isinstance(app_router, BankRouter):
                app_router.set_mas(self)
                banks.extend(get_banks_from_router(app_router))

        if banks:

            @app.get("/list_banks")
            def list_banks():
                return banks

        web_src = "web"
        with importlib.resources.as_file(
            importlib.resources.files("oxygent") / web_src
        ) as web_path:
            app.mount("/web", StaticFiles(directory=str(web_path)), name="web")

        upload_dir = os.path.join(Config.get_cache_save_dir(), "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        app.mount("/static", StaticFiles(directory=upload_dir), name="static")
        for mount in self.mounts:
            app.mount(**mount)

        # For all of the nodes we fill the following information:
        # - path: The path from the root node (master agent) to the current node.
        # - id_dict: A dictionary mapping agent names to their unique IDs.
        # However the path would not be sent here.

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

        # When the frontend is loaded, it will send the first query to the user.

        @app.get("/get_first_query")
        def get_first_query():
            return WebResponse(
                data={
                    "first_query": self.first_query if self.first_query else "",
                    "shared_data": shared_data,
                    "group_data": group_data,
                }
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

        @app.get("/get_description")
        def get_description():
            return WebResponse(
                data={"description": self.oxy_name_to_oxy[self.master_agent_name].desc}
            ).to_dict()

        @app.get("/get_agents")
        def get_agents():
            """Get detailed agent information for frontend display."""
            agents = []

            def extract_agents(node):
                """Recursively extract agent information from organization tree."""
                if isinstance(node, dict):
                    if node.get("type") == "agent":
                        # Extract agent details
                        agent_info = {
                            "name": node.get("name", ""),
                            "desc": node.get("desc", ""),
                            "type": node.get("type", "agent"),
                            "path": node.get("path", []),
                        }
                        agents.append(agent_info)

                    # Process children
                    children = node.get("children", [])
                    if isinstance(children, list):
                        for child in children:
                            extract_agents(child)

            # Extract agents from organization structure
            if hasattr(self, "agent_organization") and self.agent_organization:
                extract_agents(self.agent_organization)

            return WebResponse(data={"agents": agents}).to_dict()

        async def request_to_payload(request: Request):
            """Convert raw HTTP request data into an OxyRequest."""
            if request.method == "GET":
                params = dict(request.query_params)
                payload = dict()
                if "payload" in params:
                    try:
                        payload = json.loads(params["payload"])
                    except Exception as e:
                        logger.warning(
                            f"Failed to parse GET payload parameter as JSON (raw value: {params.get('payload', '')!r}): {e}",
                            exc_info=True,
                        )
                        return WebResponse(
                            code=400, message=f"can not convert data into JSON: {e}"
                        ).to_dict()
            elif request.method == "POST":
                payload = await request.json()

            current_trace_id = payload.get("current_trace_id", generate_uuid())
            logger.info(
                f"Received payload: {json.dumps(payload, ensure_ascii=False)}",
                extra={"trace_id": current_trace_id},
            )
            payload = await self.func_filter(payload)

            if "query" not in payload:
                payload["query"] = ""

            if "current_trace_id" not in payload:
                payload["current_trace_id"] = current_trace_id

            # fetch headers
            if "shared_data" not in payload:
                payload["shared_data"] = dict()
            payload["shared_data"]["_headers"] = dict(request.headers)

            return payload

        @app.api_route("/chat", methods=["GET", "POST"])
        async def chat(request: Request):
            payload = await request_to_payload(request)
            # Apply request interceptor if configured
            intercepted_response = await self.func_interceptor(payload)
            if intercepted_response is not None:
                return intercepted_response
            oxy_response = await self.chat_with_agent(payload=payload)
            return {
                "answer": oxy_response.output,
                "current_trace_id": oxy_response.oxy_request.current_trace_id,
            }

        @app.api_route("/sse/chat", methods=["GET", "POST"])
        async def sse_chat(request: Request):
            payload = await request_to_payload(request)
            # Apply request interceptor if configured
            intercepted_response = await self.func_interceptor(payload)
            if intercepted_response is not None:
                return intercepted_response
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

        @app.api_route("/async/chat", methods=["GET", "POST"])
        async def async_chat(request: Request):
            payload = await request_to_payload(request)
            # Apply request interceptor if configured
            intercepted_response = await self.func_interceptor(payload)
            if intercepted_response is not None:
                return intercepted_response

            current_trace_id = payload["current_trace_id"]

            logger.info(
                "SSE connection established.",
                extra={"trace_id": current_trace_id},
            )
            redis_key = f"{self.message_prefix}:{self.name}:{current_trace_id}"
            task = asyncio.create_task(
                self.chat_with_agent(payload=payload, send_msg_key=redis_key)
            )
            task.add_done_callback(
                lambda future: self.active_tasks.pop(current_trace_id, None)
            )
            self.active_tasks[current_trace_id] = task
            return WebResponse().to_dict()

        @app.api_route("/async/trace", methods=["GET", "POST"])
        async def async_trace(request: Request):
            payload = await request_to_payload(request)
            # Apply request interceptor if configured
            intercepted_response = await self.func_interceptor(payload)
            if intercepted_response is not None:
                return intercepted_response
            trace_id = payload["trace_id"]
            timestamp = payload["timestamp"]

            logger.info(
                "SSE connection established.",
                extra={"trace_id": trace_id, "timestamp": timestamp},
            )
            redis_key = f"{self.message_prefix}:{self.name}:{trace_id}"
            return EventSourceResponse(self.yield_async_message(redis_key, trace_id))

        @app.api_route("/feedback", methods=["GET", "POST"])
        async def feedback(request: Request):
            payload = await request_to_payload(request)
            channel_id = payload.get("channel_id", "")
            if channel_id not in self.feedback_dict:
                return WebResponse(code=400, message="illegal channel_id").to_dict()
            queue = self.feedback_dict[channel_id]
            data = payload.get("data", None)
            await queue.put(data)
            return WebResponse().to_dict()

        async def log_and_open():
            await asyncio.sleep(0.1)
            url_prefix = os.getenv("OXYGENT_URL", f"http://{host}:{port}/")
            web_url = url_prefix + "web/index.html"
            logger.info(
                f"The web page URL is: {web_url}, click to open.",
                extra={"color": "yellow"},
            )

            # Automatically open the web page after a short delay
            if Config.get_server_auto_open_webpage():
                import webbrowser

                if webbrowser.open(web_url):
                    logger.info(
                        "The web page has been opened.", extra={"color": "yellow"}
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
                workers=Config.get_server_workers(),
            )
            server = uvicorn.Server(config)
            asyncio.create_task(log_and_open())
            await server.serve()

        web_task = asyncio.create_task(run_uvicorn())

        await asyncio.gather(web_task)

    # ------------------------------------------------------------------
    # Batch helper
    # ------------------------------------------------------------------

    async def start_batch_processing(
        self, querys: list[str], return_trace_id: bool = False
    ) -> list[Any]:
        """Execute a batch of queries concurrently.

        Args:
            querys: Iterable of natural-language prompts.
            return_trace_id: If ``True`` the trace ID is returned together
                with each answer - handy for offline audits.

        Returns:
            list: Answers (or dicts with *output* + *trace_id*).
        """
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


class BankRouter(APIRouter):
    """FastAPI router that exposes bank tools as HTTP endpoints."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(tags=["bank"], *args, **kwargs)

    def set_mas(self, mas: MAS) -> None:
        """Bind the MAS instance to this bank router."""
        self.mas = mas
