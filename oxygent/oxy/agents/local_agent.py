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
from ...schemas import Memory, Message, OxyRequest, OxyResponse, OxyState
from ..bank_tools.bank_client import BankClient
from ..bank_tools.bank_tool import BankTool
from ..base_tool import BaseTool
from ..function_tools.function_hub import FunctionHub
from ..function_tools.function_tool import FunctionTool
from ..mcp_tools.mcp_tool import MCPTool
from ..mcp_tools.stdio_mcp_client import BaseMCPClient
from .base_agent import BaseAgent
from ...live_prompt.manager import get_dynamic_prompt

from ..skills.skill_selector import select_skill

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

    # Skills (selector-based activation)
    enable_skills: bool = Field(
        True,
        description="Whether to enable skill selector + activation for this agent",
    )
    skill_selector_min_confidence: float = Field(
        0.6,
        description="Minimum confidence required to auto-activate a skill",
    )
    skill_selector_max_candidates: int = Field(
        30,
        description="Max skill candidates included in selector prompt",
    )

    _active_skill_shared_key: str = "_active_skill"
    _skip_skill_selector_shared_key: str = "_skip_skill_selector"

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
            logger.debug(
                f"Agent '{self.name}' has live prompt disabled, skipping reload"
            )
            return False

        try:
            fallback = self.prompt if self.prompt else ""
            new_prompt = await get_dynamic_prompt(self.prompt_key, fallback)

            if new_prompt != self._resolved_prompt:
                self._resolved_prompt = new_prompt
                logger.info(
                    f"Agent '{self.name}' prompt hot-reloaded via key '{self.prompt_key}': {len(self._resolved_prompt)} chars"
                )
                return True
            else:
                logger.debug(f"Agent '{self.name}' prompt unchanged")
                return True
        except Exception as e:
            logger.error(
                f"Failed to reload prompt for agent '{self.name}' with key '{self.prompt_key}': {e}"
            )
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
                self._resolved_prompt = await get_dynamic_prompt(
                    self.prompt_key, fallback
                )
                logger.debug(
                    f"Agent '{self.name}' resolved prompt via key '{self.prompt_key}': {len(self._resolved_prompt)} chars"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to resolve dynamic prompt for agent '{self.name}' with key '{self.prompt_key}': {e}"
                )
                self._resolved_prompt = self.prompt if self.prompt else ""
        else:
            # Live prompt disabled, use static prompt from code
            self._resolved_prompt = self.prompt if self.prompt else ""
            logger.debug(
                f"Agent '{self.name}' using static prompt from code (live prompt disabled)"
            )

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
        prompt_to_use = (
            self._resolved_prompt if self._resolved_prompt else (self.prompt or "")
        )
        rendered = pattern.sub(replacer, prompt_to_use.strip())

        # If the prompt template does not include ${additional_prompt}, still append it.
        additional = arguments.get("additional_prompt")
        if (
            "${additional_prompt}" not in prompt_to_use
            and isinstance(additional, str)
            and additional.strip()
        ):
            rendered = f"{rendered}\n\n{additional.strip()}"

        return rendered

    def _parse_manual_skill_invocation(
        self, query: str, registry
    ) -> tuple[str, str] | None:
        if not isinstance(query, str):
            return None
        q = query.strip()
        if not q.startswith("/"):
            return None
        # Only support the "first token is /skill-name" style.
        first, *rest = q.split(maxsplit=1)
        skill_name = first[1:].strip()
        if not skill_name:
            return None
        if not registry or not registry.has_skill(skill_name):
            return None
        metadata = registry.get_skill(skill_name)
        if metadata is not None and getattr(metadata, "user_invocable", True) is False:
            return None
        args = rest[0] if rest else ""
        return (skill_name, args)

    def _is_skill_catalog_query(self, query: str) -> bool:
        if not isinstance(query, str):
            return False
        q = query.strip().lower()
        if not q:
            return False

        # English patterns
        if re.search(r"\bwhat\b.*\bskills?\b", q):
            return True
        if re.search(r"\bskills?\b.*\b(do|can)\b.*\bhave\b", q):
            return True
        if re.search(r"\blist\b.*\bskills?\b", q):
            return True
        if re.search(r"\bavailable\b.*\bskills?\b", q):
            return True

        # Chinese patterns
        if "你有什么技能" in q or "有哪些技能" in q or "技能列表" in q:
            return True
        if q.startswith("技能") and ("有哪些" in q or "有什么" in q):
            return True

        return False

    def _append_additional_prompt(self, oxy_request: OxyRequest, text: str) -> None:
        if not isinstance(text, str) or not text.strip():
            return
        base = oxy_request.arguments.get("additional_prompt", "")
        if not isinstance(base, str):
            base = str(base)
        oxy_request.arguments["additional_prompt"] = (base + "\n\n" + text).strip()

    def _maybe_inject_skill_catalog(self, oxy_request: OxyRequest) -> None:
        if not self.enable_skills or not self.mas:
            return
        registry = getattr(self.mas, "skill_registry", None)
        if not registry:
            return
        raw_query = oxy_request.arguments.get("query", "")
        if not self._is_skill_catalog_query(str(raw_query)):
            return

        help_text = registry.generate_user_help_section()
        if not help_text:
            return

        # For "what skills do you have" queries, avoid selector call and
        # provide the skill list as context for the agent to answer.
        oxy_request.set_shared_data(self._skip_skill_selector_shared_key, True)
        self._append_additional_prompt(
            oxy_request,
            (
                "The user is asking what skills are available. "
                "Answer by listing the skills below and how to invoke them.\n\n"
                + help_text
            ),
        )

    async def _maybe_activate_skill(self, oxy_request: OxyRequest) -> None:
        if not self.enable_skills:
            return
        if not self.mas:
            return
        registry = getattr(self.mas, "skill_registry", None)
        if not registry:
            return

        if oxy_request.get_shared_data(self._skip_skill_selector_shared_key):
            return

        # Prevent repeated activation in nested calls.
        if oxy_request.get_shared_data(self._active_skill_shared_key):
            return

        raw_query = oxy_request.arguments.get("query", "")

        selected_skill: str | None = None
        skill_args: str = ""
        invocation_source: str = "selector"
        selector_reason: str = ""
        selector_confidence: float = 0.0

        manual = self._parse_manual_skill_invocation(raw_query, registry)
        if manual:
            selected_skill, skill_args = manual
            invocation_source = "user"
            selector_reason = "manual"
            selector_confidence = 1.0
            # Remove the /skill-name prefix from the user query passed to the agent.
            remaining = (skill_args or "").strip()
            oxy_request.arguments["query"] = remaining or f"Use skill {selected_skill}."
        else:
            # Exclude disable-model-invocation skills from selector.
            skills = []
            for m in registry.list_skills():
                if getattr(m, "disable_model_invocation", False):
                    continue
                skills.append(m)

            selection = await select_skill(
                oxy_request=oxy_request,
                llm_model=self.llm_model,
                skills=skills,
                query=str(raw_query),
                max_candidates=self.skill_selector_max_candidates,
                min_confidence=self.skill_selector_min_confidence,
            )
            selected_skill = selection.selected_skill
            selector_reason = selection.reason
            selector_confidence = selection.confidence

        if not selected_skill:
            return

        # Activate via SkillTool (loads full SKILL.md content).
        oxy_response = await oxy_request.call(
            callee="Skill",
            arguments={
                "name": selected_skill,
                "arguments": skill_args,
                "invocation_source": invocation_source,
            },
            is_send_message=False,
            is_save_history=False,
        )

        if oxy_response.state is not OxyState.COMPLETED:
            logger.info(
                "Skill activation failed: %s",
                selected_skill,
                extra={
                    "trace_id": oxy_request.current_trace_id,
                    "node_id": oxy_request.node_id,
                },
            )
            return

        injection = str(oxy_response.output or "").strip()
        env_mods = (oxy_response.extra or {}).get("environment_modifications", {})
        if injection:
            base_additional = oxy_request.arguments.get("additional_prompt", "")
            if not isinstance(base_additional, str):
                base_additional = str(base_additional)
            oxy_request.arguments["additional_prompt"] = (
                base_additional + "\n\n" + injection
            ).strip()

        # Apply model override (request-scoped) via llm_params.
        if isinstance(env_mods, dict) and env_mods.get("model"):
            llm_params = oxy_request.arguments.get("llm_params")
            if not isinstance(llm_params, dict):
                llm_params = {}
            llm_params["model"] = env_mods["model"]
            oxy_request.arguments["llm_params"] = llm_params

        oxy_request.set_shared_data(
            self._active_skill_shared_key,
            {
                "name": selected_skill,
                "invocation_source": invocation_source,
                "selector_reason": selector_reason,
                "selector_confidence": selector_confidence,
                "env_mods": env_mods,
                "skill_version": (oxy_response.extra or {}).get("skill_version"),
                "skill_author": (oxy_response.extra or {}).get("skill_author"),
            },
        )

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

        # Ensure additional_prompt exists for prompt rendering.
        oxy_request.arguments["additional_prompt"] = self.additional_prompt

        # If the user asks what skills are available, inject the metadata list.
        # This also skips selector execution for this request.
        self._maybe_inject_skill_catalog(oxy_request)

        # Skill selector / activation happens before tool retrieval, so allowed-tools
        # constraints can affect subsequent tool calls.
        await self._maybe_activate_skill(oxy_request)
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
        oxy_request.arguments[self.tools_placeholder] = "\n\n".join(llm_tool_desc_list)

        return oxy_request

    async def _after_execute(self, oxy_response: OxyResponse) -> OxyResponse:
        oxy_response = await super()._after_execute(oxy_response)
        oxy_request = oxy_response.oxy_request
        if not oxy_request:
            return oxy_response
        active = oxy_request.get_shared_data(self._active_skill_shared_key)
        if isinstance(active, dict) and active.get("name"):
            oxy_response.extra = oxy_response.extra or {}
            oxy_response.extra.update(
                {
                    "skill_name": active.get("name"),
                    "skill_invocation_source": active.get("invocation_source"),
                    "skill_selector_reason": active.get("selector_reason"),
                    "skill_selector_confidence": active.get("selector_confidence"),
                    "skill_environment_modifications": active.get("env_mods"),
                    "skill_version": active.get("skill_version"),
                    "skill_author": active.get("skill_author"),
                }
            )
        return oxy_response

    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        raise NotImplementedError("This method is not yet implemented")
