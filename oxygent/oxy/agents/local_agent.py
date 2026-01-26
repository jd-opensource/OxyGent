"""Local agent module for OxyGent framework.

This module provides the LocalAgent class, which serves as the base class for agents
that execute locally with access to tools, sub-agents, and memory management
capabilities. It handles tool retrieval, conversation history, and instruction building
for LLM interactions.
"""

import copy
import json
import logging
import re
from typing import Optional

from pydantic import Field

from ...config import Config
from ...schemas import Memory, Message, OxyRequest, OxyResponse
from ..bank_tools.bank_client import BankClient
from ..bank_tools.bank_tool import BankTool
from ..base_tool import BaseTool
from ..function_tools.function_hub import FunctionHub
from ..function_tools.function_tool import FunctionTool
from ..mcp_tools.mcp_tool import MCPTool
from ..mcp_tools.stdio_mcp_client import BaseMCPClient
from .base_agent import BaseAgent
from ...live_prompt.manager import get_dynamic_prompt

logger = logging.getLogger(__name__)


class LocalAgent(BaseAgent):
    """Local agent with tool management and memory capabilities.

    This agent extends BaseAgent to provide local execution capabilities with:
    - Dynamic tool discovery and retrieval
    - Sub-agent delegation and hierarchical support
    - Conversation memory management
    - LLM model integration with prompt templating
    - Team-based parallel execution support

    Attributes:
        llm_model (str): The language model to use for this agent.
        prompt (str): System prompt template for agent behavior.
        sub_agents (list): Names of delegatable sub-agents.
        tools (list): Available tools for this agent.
        except_tools (list): Tools explicitly forbidden for this agent.
        is_sourcing_tools (bool): Whether to use dynamic tool retrieval.
        top_k_tools (int): Maximum number of tools to retrieve.
        short_memory_size (int): Number of conversation turns to retain.
        team_size (int): Number of parallel instances for team execution.
        is_retain_master_short_memory (bool): Whether to retain user history.
        is_multimodal_supported (bool): Whether to support multimodal input.
        team_size (int): Number of parallel instances for m execution.
    """

    llm_model: str = Field(
        default_factory=Config.get_agent_llm_model,
        description="suggesting integration with a specific LLM service.",
    )
    prompt: Optional[str] = Field(
        default_factory=Config.get_agent_prompt,
        description="Defaults to 'SYSTEM_PROMPT', the prompt to initialize the agent's behavior.",
    )
    prompt_key: Optional[str] = Field(
        default=None,
        description="Key for live prompt lookup. Defaults to '{agent_name}_prompt' if not specified. Used for dynamic prompt hot-reloading.",
    )
    use_live_prompt: bool = Field(
        default=True,
        description="Whether to use live prompt system. If False, only uses the static 'prompt' parameter from code.",
    )
    additional_prompt: Optional[str] = Field(
        default="", description="The prompt add by user, addit to the origin prompt."
    )
    _resolved_prompt: Optional[str] = None
    tools_placeholder: str = Field("tools_description")
    sub_agents: Optional[list] = Field(
        default_factory=list,
        description="Names of other agents this agent can delegate to (hierarchy support).",
    )
    tools: Optional[list] = Field(
        default_factory=list, description="Tools available to this agent."
    )
    except_tools: Optional[list] = Field(
        default_factory=list, description="Tools explicitly forbidden to this agent."
    )

    banks: Optional[list] = Field(
        default_factory=list, description="Banks available to this agent."
    )

    is_sourcing_tools: bool = Field(
        False,
        description="When enabled, agent actively retrieves tools instead of direct tool recall",
    )
    is_retain_subagent_in_toolset: bool = Field(
        False,
        description="Whether sub-agents remain in the toolset (equivalent to guaranteed recall when enabled)",
    )
    top_k_tools: int = Field(10, description="Number of tools to retrieve")
    is_retrieve_even_if_tools_scarce: bool = Field(
        True,
        description="When enabled, still perform retrieval even if agent has fewer than k tools (may return 0 tools)",
    )

    short_memory_size: int = Field(
        default_factory=Config.get_agent_short_memory_size,
        description="Number of short-term memory entries to retain",
    )
    intent_understanding_agent: Optional[str] = Field(
        None,
        description="Intent understanding agent (used for query rewriting to retrieve tools)",
    )
    is_retain_master_short_memory: bool = Field(
        False, description="Whether to retrieve user history"
    )
    is_attachment_processing_enabled: bool = Field(
        True, description="Whether to inject attachments into `query`."
    )

    is_multimodal_supported: bool = Field(
        False, description="Whether support for multimodal input"
    )

    team_size: int = Field(1, description="Number of instances for team execution")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if not self.llm_model:
            raise Exception(f"agent {self.name} not set llm_model")

    def _init_available_tool_name_list(self):
        """Initialize the list of tools(sub-agents, MCP tools, function tools and
        function hubs) available to this agent.

        Raises:
            Exception: If a referenced agent or tool doesn't exist.
        """
        for sub_agent in set(self.sub_agents):
            if sub_agent not in self.mas.oxy_name_to_oxy:
                raise Exception(f"Agent [{sub_agent}] not exists.")
            self.add_permitted_tool(sub_agent)
        for oxy_name in set(self.tools):
            if oxy_name in self.except_tools:
                continue
            if oxy_name not in self.mas.oxy_name_to_oxy:
                raise Exception(f"Tool [{oxy_name}] not exists.")
            oxy = self.mas.oxy_name_to_oxy[oxy_name]
            if not isinstance(oxy, BaseTool):
                raise Exception(f"[{oxy_name}] is not a tool.")
            # mcp tool
            if isinstance(oxy, (MCPTool, FunctionTool)):
                self.add_permitted_tool(oxy_name)
            elif isinstance(oxy, BaseMCPClient):
                for tool_name in oxy.included_tool_name_list:
                    if tool_name in self.except_tools:
                        continue
                    self.add_permitted_tool(tool_name)
            elif isinstance(oxy, FunctionHub):
                for tool_name in oxy.func_dict.keys():
                    if tool_name in self.except_tools:
                        continue
                    self.add_permitted_tool(tool_name)
            else:
                logger.warning(f"Unknown tool type: {type(oxy)}")
        for oxy_name in set(self.banks):
            if oxy_name not in self.mas.oxy_name_to_oxy:
                raise Exception(f"bank [{oxy_name}] not exists.")
            oxy = self.mas.oxy_name_to_oxy[oxy_name]
            if isinstance(oxy, BankTool):
                self.add_permitted_tool(oxy_name)
            elif isinstance(oxy, BankClient):
                for tool_name in oxy.included_bank_name_list:
                    self.add_permitted_tool(tool_name)
            else:
                logger.warning(f"Unknown bank type: {type(oxy)}")

    def __deepcopy__(self, memo):
        # Extract all fields from the current instance
        fields = self.model_dump()

        # Keep MAS reference shared (not deep copied) to maintain system connectivity
        fields["mas"] = self.mas

        # Deep copy all other fields to ensure complete isolation
        for k in fields:
            if k not in ["mas"]:
                fields[k] = copy.deepcopy(fields[k], memo)
        return self.__class__(**fields)

    async def reload_prompt(self) -> bool:
        """Reload prompt from live prompt system (hot reload support).
        
        This method re-fetches the prompt from storage, enabling hot updates
        without restarting the agent. Useful when prompts are modified in the
        management platform.
        
        Returns:
            bool: True if prompt was successfully reloaded, False otherwise.
        """
        # Check if live prompt is enabled
        if not self.use_live_prompt:
            logger.debug(f"Agent '{self.name}' has live prompt disabled, skipping reload")
            return False
            
        try:
            fallback = self.prompt if self.prompt else ""
            new_prompt = await get_dynamic_prompt(self.prompt_key, fallback)
            
            if new_prompt != self._resolved_prompt:
                self._resolved_prompt = new_prompt
                logger.info(f"Agent '{self.name}' prompt hot-reloaded via key '{self.prompt_key}': {len(self._resolved_prompt)} chars")
                return True
            else:
                logger.debug(f"Agent '{self.name}' prompt unchanged")
                return True
        except Exception as e:
            logger.error(f"Failed to reload prompt for agent '{self.name}' with key '{self.prompt_key}': {e}")
            return False

    async def init(self):
        """Initialize the agent and set up team-based execution if configured.

        This method performs agent initialization including tool setup and creates
        parallel agent instances for team-based execution when team_size > 1.
        """
        # Resolve dynamic prompt if live prompt is enabled
        if self.use_live_prompt:
            # Set default prompt_key if not specified
            if self.prompt_key is None:
                # Default: use agent name + "_prompt" as the key
                self.prompt_key = f"{self.name}_prompt"
            
            # Resolve the prompt from live prompt system
            try:
                fallback = self.prompt if self.prompt else ""
                self._resolved_prompt = await get_dynamic_prompt(self.prompt_key, fallback)
                logger.debug(f"Agent '{self.name}' resolved prompt via key '{self.prompt_key}': {len(self._resolved_prompt)} chars")
            except Exception as e:
                logger.warning(f"Failed to resolve dynamic prompt for agent '{self.name}' with key '{self.prompt_key}': {e}")
                self._resolved_prompt = self.prompt if self.prompt else ""
        else:
            # Live prompt disabled, use static prompt from code
            self._resolved_prompt = self.prompt if self.prompt else ""
            logger.debug(f"Agent '{self.name}' using static prompt from code (live prompt disabled)")
        
        self.is_multimodal_supported = self.mas.oxy_name_to_oxy[
            self.llm_model
        ].is_multimodal_supported
        if self.is_multimodal_supported:
            self.input_schema["properties"]["query"]["description"] = (
                "The image path and the query to ask about the images, for example: ![image1.png](./static/image1.png) ![image2.png](./static/image2.png) What are image1.png and image2.png, respectively?"
            )

        await super().init()
        if self.intent_understanding_agent:
            self.sub_agents.append(self.intent_understanding_agent)
        self._init_available_tool_name_list()
        if self.llm_model not in self.mas.oxy_name_to_oxy:
            raise Exception(f"LLM model [{self.llm_model}] not exists.")

        if self.team_size > 1:
            team_names = []
            for i in range(self.team_size):
                new_instance = copy.deepcopy(self)
                new_instance.name = f"{self.name}_{i + 1}"
                new_instance.is_master = False
                new_instance.func_process_input = self.func_process_input
                new_instance.func_process_output = self.func_process_output
                new_instance.func_format_input = self.func_format_input
                new_instance.func_format_output = self.func_format_output
                team_names.append(new_instance.name)
                self.mas.oxy_name_to_oxy[new_instance.name] = new_instance
            from .parallel_agent import ParallelAgent

            parallel_agent = ParallelAgent(
                name=self.name,
                desc=self.desc,
                permitted_tool_name_list=team_names,
                llm_model=self.llm_model,
                is_master=self.is_master,
            )
            parallel_agent.set_mas(self.mas)
            self.mas.oxy_name_to_oxy[self.name] = parallel_agent

    async def _get_history(
        self, oxy_request: OxyRequest, is_get_user_master_session=False
    ) -> Memory:
        """Retrieve conversation history from Elasticsearch.

        Args:
            oxy_request (OxyRequest): The current request containing trace info.
            is_get_user_master_session (bool): Whether to get master session history.

        Returns:
            Memory: A Memory object containing the conversation history as
                alternating user and assistant messages.
        """
        short_memory = Memory()
        if oxy_request.from_trace_id:
            if is_get_user_master_session:
                session_name = "__".join(oxy_request.call_stack[:2])
            else:
                session_name = oxy_request.session_name
            es_response = await self.mas.es_client.search(
                Config.get_app_name() + "_history",
                {
                    "query": {
                        "bool": {
                            "must": [
                                {
                                    "terms": {
                                        "trace_id": oxy_request.root_trace_ids
                                        + [oxy_request.current_trace_id]
                                    }
                                },
                                {"term": {"session_name": session_name}},
                            ]
                        }
                    },
                    "size": self.short_memory_size,
                    "sort": [{"create_time": {"order": "desc"}}],
                },
            )
            historys = es_response["hits"]["hits"][::-1]
            for history in historys:
                memory = json.loads(history["_source"]["memory"])
                short_memory.add_message(Message.user_message(memory["query"]))
                short_memory.add_message(Message.assistant_message(memory["answer"]))
        return short_memory

    async def _get_llm_tool_desc_list(self, oxy_request: OxyRequest, query: str) -> str:
        """Get tool descriptions for LLM context based on configuration and query.

        This method handles different tool retrieval strategies:
        - Direct tool listing when vector search is disabled
        - Dynamic tool retrieval based on query similarity
        - Sub-agent retention in toolset
        - Tool scarcity handling

        Args:
            oxy_request (OxyRequest): The current request object.
            query (str): The user query for tool retrieval.

        Returns:
            str: Concatenated tool descriptions for LLM context.
        """
        # Build tool description list for LLM instruction
        self.permitted_tool_name_list.sort()
        # Create instruction
        llm_tool_desc_list = []
        if not Config.get_vearch_config():
            # TODO: Modify tool description list - not all permitted tools are callable
            # (e.g., Reflexion Agent is a special case)
            for tool_name in self.permitted_tool_name_list:
                tool_desc = oxy_request.get_oxy(tool_name).desc_for_llm
                llm_tool_desc_list.append(tool_desc)
            return llm_tool_desc_list

        # Add sub-agents if they should be retained in toolset
        if self.is_retain_subagent_in_toolset:
            for tool_name in self.permitted_tool_name_list:
                tool_desc = oxy_request.get_oxy(tool_name).desc_for_llm
                if self.mas.is_agent(tool_name):
                    llm_tool_desc_list.append(tool_desc)

        if self.is_sourcing_tools:
            # Enable autonomous tool retrieval
            # TODO: Start with initial tools, then retrieve based on query
            tool_desc = oxy_request.get_oxy("retrieve_tools").desc_for_llm
            llm_tool_desc_list.append(tool_desc)
        else:
            # Calculate current agent's tool count, excluding sub-agents if configured
            tool_number = len(self.permitted_tool_name_list)
            if self.is_retain_subagent_in_toolset:
                # TODO: Consider tool description ordering (sub-agents first, then tools)
                pure_tool_desc_list = []
                for tool_name in self.permitted_tool_name_list:
                    tool_desc = oxy_request.get_oxy(tool_name).desc_for_llm
                    if self.mas.is_agent(tool_name):
                        continue
                    pure_tool_desc_list.append(tool_desc)
                tool_number = len(pure_tool_desc_list)

            # Handle tool retrieval based on availability
            if (
                self.is_retrieve_even_if_tools_scarce
                and self.top_k_tools >= tool_number
            ):
                # When tool count is low, provide all tools without retrieval
                for tool_name in self.permitted_tool_name_list:
                    tool_desc = oxy_request.get_oxy(tool_name).desc_for_llm
                    if tool_name in ["retrieve_tools"]:
                        continue
                    if self.is_retain_subagent_in_toolset and self.mas.is_agent(
                        tool_name
                    ):
                        continue
                    llm_tool_desc_list.append(tool_desc)
            else:
                # Retrieve tools based on current query relevance
                oxy_response = await oxy_request.call(
                    callee="retrieve_tools", arguments={"query": query}
                )
                if oxy_response.output:
                    # Append multiple tools connected with \n\n
                    llm_tool_desc_list.append(oxy_response.output)
        return llm_tool_desc_list

    def _build_instruction(self, arguments) -> str:
        """Build instruction prompt by substituting template variables.

        Args:
            arguments: Dictionary containing variable values for substitution.

        Returns:
            str: The formatted instruction string with variables substituted.
        """
        pattern = re.compile(r"\$\{(\w+)\}")

        def replacer(match):
            key = match.group(1)
            return str(arguments.get(key, match.group(0)))

        # Use resolved prompt (with live prompt support) instead of static prompt
        prompt_to_use = self._resolved_prompt if self._resolved_prompt else (self.prompt or "")
        return pattern.sub(replacer, prompt_to_use.strip())

    async def _pre_process(self, oxy_request: OxyRequest) -> OxyRequest:
        """Pre-process request to load conversation history if needed.

        Args:
            oxy_request (OxyRequest): The request to process.

        Returns:
            OxyRequest: The request with short_memory populated.
        """
        oxy_request = await super()._pre_process(oxy_request)
        if not oxy_request.has_short_memory():
            short_memory = await self._get_history(oxy_request)
            oxy_request.arguments["short_memory"] = short_memory.to_dict_list()

        if self.is_retain_master_short_memory:
            short_memory = await self._get_history(
                oxy_request, is_get_user_master_session=True
            )
            oxy_request.arguments["master_short_memory"] = short_memory.to_dict_list()

        return oxy_request

    async def _before_execute(self, oxy_request: OxyRequest) -> OxyRequest:
        """Prepare tools description for LLM execution.

        This method optionally uses intent understanding for query rewriting
        and retrieves relevant tool descriptions for the LLM context.

        Args:
            oxy_request (OxyRequest): The request to prepare.

        Returns:
            OxyRequest: The request with tools_description added to arguments.
        """
        oxy_request = await super()._before_execute(oxy_request)
        # get multimodal input
        if self.intent_understanding_agent:
            oxy_response = await oxy_request.call(
                callee=self.intent_understanding_agent,
                arguments={
                    "query": oxy_request.get_query(),
                    "short_memory": oxy_request.get_short_memory(),
                },
            )
            llm_tool_desc_list = await self._get_llm_tool_desc_list(
                oxy_request, oxy_response.output
            )
        else:
            llm_tool_desc_list = await self._get_llm_tool_desc_list(
                oxy_request, oxy_request.get_query()
            )
        oxy_request.arguments["additional_prompt"] = self.additional_prompt
        oxy_request.arguments[self.tools_placeholder] = "\n\n".join(llm_tool_desc_list)

        return oxy_request

    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        raise NotImplementedError("This method is not yet implemented")
