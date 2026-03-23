"""SkillAgent: Skill-aware agent with SkillTool integration and slash command support.

Aligns with Claude Code's skill architecture:
    - SkillTool for LLM-driven invocation via tool-calling
    - Slash commands (/skill_name args) with $ARGUMENTS substitution
    - Auto-injection for disable_model_invocation skills
    - Dynamic skill_section prompt construction
    - Progressive slash command matching for multi-token names
    - Content caching with mtime-based hot-reload
    - Skill dependency (required_tools) auto-injection
    - Pre/post invocation hooks via SkillRegistry

Usage:
    >>> oxy_space = [
    ...     oxy.SkillAgent(
    ...         name="agent",
    ...         skills=[".oxygent/skills"],
    ...         enable_project_skills=True,
    ...     ),
    ... ]
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

from pydantic import Field, PrivateAttr

from ...prompts import SYSTEM_PROMPT_SKILLS
from ...schemas import LLMResponse, LLMState, OxyRequest, OxyResponse
from ...schemas.skill import escape_xml_attr
from ...skills.skill_registry import SkillHookEvent, SkillRegistry
from ...utils.common_utils import extract_json_blocks
from ..skill_tools.skill_tool import SkillTool
from .react_agent import ReActAgent

logger = logging.getLogger(__name__)


class SkillAgent(ReActAgent):
    """Skill-aware agent with SkillTool and slash command support.

    Extends ReActAgent to provide:
        - Automatic skill discovery from project and custom paths
        - SkillTool registration for LLM-driven skill invocation
        - Auto-injection of disable_model_invocation skills into context
        - Slash command interception with $ARGUMENTS substitution
        - Dynamic prompt construction (skill_section is empty when no skills)
        - Content caching with mtime-based hot-reload
        - Auto-injection of required_tools from skills into agent's tool list
        - Pre/post invocation hooks
    """

    skills: Optional[List[str]] = Field(
        default=None,
        description="List of skill directory paths to load skills from.",
    )

    enable_project_skills: bool = Field(
        default=True,
        description="Whether to scan .oxygent/skills/ in the current working directory.",
    )

    skill_tool_name: str = Field(
        default="skill",
        description="Name for the registered SkillTool in MAS.",
    )

    prompt: Optional[str] = Field(
        default=SYSTEM_PROMPT_SKILLS,
        description="System prompt template with skill support.",
    )

    _skill_registry: SkillRegistry = PrivateAttr(default_factory=SkillRegistry)
    _auto_inject_cache: dict = PrivateAttr(default_factory=dict)

    @property
    def skills_count(self) -> int:
        """Number of discovered skills."""
        return len(self._skill_registry.list_all())

    @property
    def skill_names(self) -> List[str]:
        """Names of all discovered skills."""
        return [s.name for s in self._skill_registry.list_all()]

    @property
    def skill_registry(self) -> SkillRegistry:
        """Access to the skill registry (for hook registration etc.)."""
        return self._skill_registry

    def __deepcopy__(self, memo):
        """Preserve _skill_registry across deep copies (team_size > 1 safety)."""
        new_instance = self.model_copy(deep=True)
        object.__setattr__(new_instance, '_skill_registry', self._skill_registry)
        object.__setattr__(new_instance, '_auto_inject_cache', self._auto_inject_cache)
        return new_instance

    async def init(self) -> None:
        """Initialize with skill discovery and SkillTool registration.

        1. Create and populate SkillRegistry
        2. Create and register SkillTool in MAS (with conflict detection)
        3. Auto-inject required_tools from skills into agent's tool list
        4. Pre-cache auto-inject skill content
        5. Add skill tool to agent's tool list
        6. Call parent init
        """
        logger.info(
            f"[SkillAgent] Initializing agent '{self.name}' "
            f"with {len(self.skills) if self.skills else 0} custom skill path(s)"
        )

        # Phase 1: Set up registry sources
        self._skill_registry = SkillRegistry()

        if self.enable_project_skills:
            self._skill_registry.add_source(
                SkillRegistry.make_project_source(Path.cwd())
            )

        if self.skills:
            self._skill_registry.add_source(
                SkillRegistry.make_path_source(self.skills)
            )

        # Phase 2: Discover skills (runs in thread pool)
        await self._skill_registry.discover()

        # Phase 3: Register SkillTool (with conflict detection)
        if self.skill_tool_name in self.mas.oxy_name_to_oxy:
            logger.warning(
                f"[SkillAgent] Tool '{self.skill_tool_name}' already registered in MAS. "
                f"Agent '{self.name}' will overwrite it. Use a unique skill_tool_name "
                f"to avoid conflicts when running multiple SkillAgents."
            )

        skill_tool = SkillTool(
            registry=self._skill_registry,
            name=self.skill_tool_name,
        )
        skill_tool.set_mas(self.mas)
        self.mas.oxy_name_to_oxy[self.skill_tool_name] = skill_tool

        # Phase 4: Auto-inject required_tools from skills into agent's tool list
        required_tools = self._skill_registry.get_required_tools()
        for tool_name in required_tools:
            if tool_name not in self.tools and tool_name != self.skill_tool_name:
                if tool_name in self.mas.oxy_name_to_oxy:
                    self.tools.append(tool_name)
                    logger.info(
                        f"[SkillAgent] Auto-injected required tool '{tool_name}' "
                        f"from skill dependencies"
                    )
                else:
                    logger.warning(
                        f"[SkillAgent] Skill requires tool '{tool_name}' "
                        f"but it is not registered in MAS"
                    )

        # Phase 5: Pre-cache auto-inject skill content (avoid sync I/O in _before_execute)
        self._pre_cache_auto_inject()

        # Phase 6: Add skill tool to this agent's tools
        if self.skill_tool_name not in self.tools:
            self.tools.append(self.skill_tool_name)

        # Phase 7: Call parent init
        await super().init()

        logger.info(
            f"[SkillAgent] Agent '{self.name}' initialized: "
            f"{self.skills_count} skills discovered, "
            f"SkillTool '{self.skill_tool_name}' registered"
        )

    def _pre_cache_auto_inject(self) -> None:
        """Pre-cache auto-inject skill content to avoid sync I/O in event loop."""
        self._auto_inject_cache = {}
        for skill in self._skill_registry.list_auto_inject():
            try:
                content = skill.load_content()
                self._auto_inject_cache[skill.name] = content
            except Exception as e:
                logger.warning(f"Failed to pre-cache auto-inject skill '{skill.name}': {e}")

    async def _before_execute(self, oxy_request: OxyRequest) -> OxyRequest:
        """Inject dynamic skill_section into prompt arguments."""
        oxy_request = await super()._before_execute(oxy_request)
        oxy_request.set_arguments("skill_section", self._build_skill_section())
        return oxy_request

    def _parse_llm_response(
        self, ori_response: str, oxy_request: OxyRequest = None
    ) -> LLMResponse:
        """Parse LLM response with multi-tool batch call support.

        Overrides ReActAgent._parse_llm_response to support JSON arrays
        for parallel tool invocation. When multiple valid tool calls are
        detected, returns output as a list so ReActAgent._execute() uses
        its asyncio.gather branch.
        """
        try:
            response = ori_response
            # Remove <think>...</think> blocks outside of code fences
            response = re.sub(
                r"<think>.*?</think>", "", response, flags=re.DOTALL
            ).strip()

            results = extract_json_blocks(response)

            # Validate every item has "tool_name"
            valid = [r for r in results if isinstance(r, dict) and "tool_name" in r]
            if not valid:
                raise ValueError("No valid tool_name found in parsed JSON")

            if len(valid) == 1:
                return LLMResponse(
                    state=LLMState.TOOL_CALL,
                    output=valid[0],
                    ori_response=ori_response,
                )
            else:
                return LLMResponse(
                    state=LLMState.TOOL_CALL,
                    output=valid,
                    ori_response=ori_response,
                )

        except (json.JSONDecodeError, ValueError):
            # Delegate to parent for ANSWER / ERROR_PARSE handling
            return super()._parse_llm_response(ori_response, oxy_request)

    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        """Execute with slash command interception.

        If the query starts with / and matches a user-invocable skill,
        expands the skill content inline (with $ARGUMENTS substitution)
        before entering the ReAct loop.
        """
        query = oxy_request.get_query().strip()

        # Check for slash command
        slash_result = self._detect_slash_command(query)
        if slash_result is not None:
            skill_name, args = slash_result
            metadata = self._skill_registry.get(skill_name)

            if metadata and not metadata.user_invocable:
                # Skill exists but not user-invocable → give feedback
                oxy_request.set_query(
                    f"The skill '{skill_name}' exists but is not available as a "
                    f"slash command. Please invoke it through other means."
                )
                logger.info(
                    f"[SkillAgent] Slash command /{skill_name} blocked: "
                    f"user_invocable=False"
                )
            elif metadata:
                # Fire pre_invoke hook for slash commands
                pre_event = SkillHookEvent(
                    hook_type="pre_invoke",
                    skill_name=skill_name,
                    args=args,
                    source="slash",
                    metadata=metadata,
                )
                block_msg = await self._skill_registry.fire_hook_async(pre_event)
                if block_msg:
                    oxy_request.set_query(
                        f"Skill invocation blocked: {block_msg}"
                    )
                    logger.info(
                        f"[SkillAgent] Slash command /{skill_name} blocked by hook: {block_msg}"
                    )
                else:
                    # Valid slash command → expand
                    self._expand_slash_command(oxy_request, metadata, args)

                    # Fire post_invoke hook
                    post_event = SkillHookEvent(
                        hook_type="post_invoke",
                        skill_name=skill_name,
                        args=args,
                        source="slash",
                        metadata=metadata,
                        result=oxy_request.get_query(),
                    )
                    await self._skill_registry.fire_hook_async(post_event)
            # If metadata is None, _detect_slash_command already filtered it

        return await super()._execute(oxy_request)

    def _detect_slash_command(self, query: str) -> Optional[Tuple[str, str]]:
        """Detect if query is a slash command for a registered skill.

        Uses progressive matching to support multi-token skill names:
            /weather Beijing → ("weather", "Beijing")
            /dongx:d2c-s some args → ("dongx:d2c-s", "some args")
            /My Skill args → ("My Skill", "args") if registered
            /path/to/file → None (no matching skill)

        Tries longest match first, falls back to shorter prefixes.
        """
        if not query.startswith("/"):
            return None

        rest = query[1:]

        # Exclude obvious file paths and URLs (e.g., /usr/bin/python, /home/user)
        if rest.startswith("/") or rest.startswith("~"):
            return None

        tokens = rest.split()
        if not tokens:
            return None

        # Try progressively shorter prefixes (longest match wins)
        for i in range(len(tokens), 0, -1):
            candidate = " ".join(tokens[:i])
            metadata = self._skill_registry.get(candidate)
            if metadata is not None:
                args = " ".join(tokens[i:])
                return (candidate, args)

        return None

    def _expand_slash_command(
        self,
        oxy_request: OxyRequest,
        metadata,
        args: str,
    ) -> None:
        """Expand a slash command by loading skill content with $ARGUMENTS.

        Content is wrapped in <skill-instructions> tags and replaces the query.
        $ARGUMENTS in the skill body is replaced with the user's args.
        Uses cached has_arguments_template to avoid double file read.
        """
        try:
            content = metadata.load_content(arguments=args)
        except Exception as e:
            logger.error(f"Failed to load skill '{metadata.name}' for slash command: {e}")
            oxy_request.set_query(
                f"Error loading skill '{metadata.name}': {e}. "
                f"Please try again or use a different approach."
            )
            return

        args_attr = f' args="{escape_xml_attr(args)}"' if args else ""
        new_query = (
            f'<skill-instructions name="{escape_xml_attr(metadata.name)}"{args_attr}>\n'
            f"{content}\n"
            f"</skill-instructions>"
        )

        # Append args as context only if $ARGUMENTS was NOT in the original template
        # Uses cached property — no extra file read
        if args and not metadata.has_arguments_template:
            new_query += f"\n\n{args}"

        oxy_request.set_query(new_query)
        logger.info(
            f"[SkillAgent] Expanded slash command /{metadata.name} "
            f"(args={args!r}) for agent '{self.name}'"
        )

    def _build_skill_section(self) -> str:
        """Build the complete dynamic skill section for prompt injection.

        Returns empty string when no skills exist (no orphaned headers).
        Includes: invocable skills, slash command list, auto-injected content.
        Auto-injected content uses pre-cached bodies (no sync I/O here).
        """
        parts = []

        # 1. Model-invocable skills (called via skill tool)
        invocable = self._skill_registry.list_invocable()
        if invocable:
            entries = [s.to_prompt_entry() for s in invocable]
            parts.append(
                f"## Skills\n\n"
                f"The `{self.skill_tool_name}` tool loads specialized instructions "
                f"for specific tasks. When a skill's trigger conditions match the "
                f"current task, you MUST invoke the `{self.skill_tool_name}` tool "
                f"BEFORE generating any other response.\n\n"
                f"To invoke a skill:\n"
                f"```json\n"
                f'{{\n'
                f'    "think": "reasoning about why this skill matches",\n'
                f'    "tool_name": "{self.skill_tool_name}",\n'
                f'    "arguments": {{\n'
                f'        "skill": "skill_name",\n'
                f'        "args": "optional arguments"\n'
                f'    }}\n'
                f'}}\n'
                f"```\n\n"
                f"The tool returns instructions wrapped in `<skill-instructions>` tags. "
                f"Follow these instructions as your primary directive.\n\n"
                f"When multiple skills' trigger conditions match the current task "
                f"and their calls are independent, you can invoke them all at once "
                f"using a JSON array of tool calls.\n\n"
                f"When multiple skills could match, choose the most specific one. "
                f"When a skill has `DO NOT TRIGGER` conditions that match the current "
                f"context, do NOT invoke that skill even if `TRIGGER` conditions "
                f"also match.\n\n"
                f"Available skills:\n" + "\n".join(entries)
            )

        # 2. User-invocable skills (slash commands)
        user_invocable = self._skill_registry.list_user_invocable()
        if user_invocable:
            slash_entries = []
            for s in user_invocable:
                hint = f" {s.argument_hint}" if s.argument_hint else ""
                slash_entries.append(f"- /{s.name}{hint}: {s.description}")
            parts.append(
                "## Slash Commands\n\n"
                "Users may invoke skills directly using slash commands. "
                "When you receive content wrapped in `<skill-instructions>` tags, "
                "treat it as primary instructions and follow them carefully. "
                "The `$ARGUMENTS` in skill content has been replaced with the "
                "user's input.\n\n"
                "User-invocable skills:\n" + "\n".join(slash_entries)
            )

        # 3. Auto-injected skills (disable_model_invocation=True)
        # Uses pre-cached content — no sync I/O in event loop
        auto_inject = self._skill_registry.list_auto_inject()
        if auto_inject:
            inject_parts = []
            for skill in auto_inject:
                # Try pre-cache first, fall back to load (with mtime-based cache in SkillMetadata)
                content = self._auto_inject_cache.get(skill.name)
                if content is None:
                    try:
                        content = skill.load_content()
                    except Exception as e:
                        logger.warning(f"Failed to auto-inject skill '{skill.name}': {e}")
                        continue
                inject_parts.append(
                    f'<skill-instructions name="{escape_xml_attr(skill.name)}">\n'
                    f"{content}\n"
                    f"</skill-instructions>"
                )
            if inject_parts:
                parts.append(
                    "## Pre-loaded Skills\n\n"
                    "The following skill instructions are pre-loaded and active. "
                    "Follow them as applicable to the current task.\n\n"
                    + "\n\n".join(inject_parts)
                )

        return "\n\n".join(parts)
