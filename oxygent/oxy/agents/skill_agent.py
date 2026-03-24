"""SkillAgent: Skill-aware agent with SkillTool integration.

Features:
    - SkillTool for LLM-driven invocation via tool-calling
    - Auto-injection for disable_model_invocation skills
    - Dynamic skill_section prompt construction
    - Skill dependency (required_tools) auto-injection
    - Pre/post invocation hooks via SkillRegistry
    - Context eviction: model can drop tools/skills mid-task to save tokens

Usage:
    >>> oxy_space = [
    ...     oxy.SkillAgent(
    ...         name="agent",
    ...         skills=[".oxygent/skills"],
    ...     ),
    ... ]
"""

from __future__ import annotations

import json
import logging
import re
from typing import List, Optional

from pydantic import Field, PrivateAttr

from ...prompts import SYSTEM_PROMPT_SKILLS
from ...schemas import LLMResponse, LLMState, OxyRequest
from ...skills.skill_registry import SkillRegistry
from ...utils.common_utils import extract_json_blocks
from ..skill_tools.context_eviction_tool import (
    ContextEvictionTool,
    get_evicted_skills,
    get_evicted_tools,
)
from ..skill_tools.skill_tool import SkillTool
from .react_agent import ReActAgent

logger = logging.getLogger(__name__)

# Pre-compiled regex for stripping <think> blocks
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


class SkillAgent(ReActAgent):
    """Skill-aware agent with SkillTool support.

    Extends ReActAgent to provide:
        - Automatic skill discovery from custom paths
        - SkillTool registration for LLM-driven skill invocation
        - Auto-injection of disable_model_invocation skills into context
        - Dynamic prompt construction (skill_section is empty when no skills)
        - Auto-injection of required_tools from skills into agent's tool list
        - Pre/post invocation hooks
    """

    SKILL_TOOL_NAME: str = "skill"
    EVICTION_TOOL_NAME: str = "drop_context"

    skills: Optional[List[str]] = Field(
        default=None,
        description="List of skill directory paths to load skills from.",
    )
    enable_project_skills: bool = Field(
        default=False,
        description="Auto-scan .oxygent/skills/ relative to CWD for project-level skills.",
    )
    enable_context_eviction: bool = Field(
        default=True,
        description=(
            "Register the drop_context tool so the LLM can evict tools/skills "
            "from context to save tokens mid-task."
        ),
    )

    prompt: Optional[str] = Field(
        default=SYSTEM_PROMPT_SKILLS,
        description="System prompt template with skill support.",
    )

    _skill_registry: SkillRegistry = PrivateAttr(default_factory=SkillRegistry)
    _auto_inject_section: str = PrivateAttr(default="")
    _cached_skill_section: str = PrivateAttr(default="")

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

    async def refresh_skills(self) -> int:
        """Hot-reload skills from all registered sources.

        Re-scans all source paths, rebuilds the registry and prompt cache.
        Safe to call at runtime in cloud deployments without restarting.

        Returns:
            Number of skills discovered after refresh.
        """
        count = await self._skill_registry.refresh()
        # Rebuild auto-inject and skill section after refresh
        auto_inject = self._skill_registry.list_auto_inject()
        if auto_inject:
            content_blocks = []
            for skill in auto_inject:
                try:
                    content = skill.load_content()
                except Exception as e:
                    logger.warning(
                        f"[SkillAgent] Failed to load auto-inject content for '{skill.name}': {e}"
                    )
                    content = skill.description
                trigger_hint = ""
                if skill.trigger:
                    trigger_block = skill.trigger.to_prompt_block()
                    if trigger_block:
                        trigger_hint = "\n" + "\n".join(
                            f"  {line}" for line in trigger_block.splitlines()
                        ) + "\n"
                content_blocks.append(
                    f"### {skill.name}\n"
                    f"{trigger_hint}"
                    f"{content}"
                )
            self._auto_inject_section = (
                "## Always-Active Skills\n\n"
                "The following skills are always active. Their full instructions are "
                "embedded below — apply them automatically whenever their trigger "
                "conditions match.\n\n"
                + "\n\n---\n\n".join(content_blocks)
            )
        else:
            self._auto_inject_section = ""
        self._cached_skill_section = self._build_skill_section()
        logger.info(
            f"[SkillAgent] Hot-reload complete: {count} skills, "
            f"skill_section rebuilt"
        )
        return count

    async def init(self) -> None:
        """Initialize with skill discovery and SkillTool registration.

        1. Create and populate SkillRegistry
        2. Create and register SkillTool in MAS
        3. Auto-inject required_tools from skills into agent's tool list
        4. Pre-build auto-inject skill section
        5. Add skill tool to agent's tool list
        6. Call parent init
        """
        logger.info(
            f"[SkillAgent] Initializing agent '{self.name}' "
            f"with {len(self.skills) if self.skills else 0} skill path(s)"
        )

        # Phase 1: Set up registry sources
        self._skill_registry = SkillRegistry()

        if self.skills:
            self._skill_registry.add_source(
                SkillRegistry.make_path_source(self.skills)
            )

        if self.enable_project_skills:
            project_skills_path = ".oxygent/skills"
            self._skill_registry.add_source(
                SkillRegistry.make_path_source(
                    [project_skills_path],
                    name="project",
                    priority=50,
                )
            )

        # Phase 2: Discover skills (runs in thread pool)
        await self._skill_registry.discover()

        # Phase 3: Register SkillTool
        if self.SKILL_TOOL_NAME in self.mas.oxy_name_to_oxy:
            logger.warning(
                f"[SkillAgent] Tool '{self.SKILL_TOOL_NAME}' already registered in MAS. "
                f"Agent '{self.name}' will overwrite it."
            )

        skill_tool = SkillTool(registry=self._skill_registry, name=self.SKILL_TOOL_NAME)
        skill_tool.set_mas(self.mas)
        self.mas.oxy_name_to_oxy[self.SKILL_TOOL_NAME] = skill_tool

        # Phase 3b: Register ContextEvictionTool (optional)
        if self.enable_context_eviction:
            eviction_tool = ContextEvictionTool(name=self.EVICTION_TOOL_NAME)
            eviction_tool.set_mas(self.mas)
            self.mas.oxy_name_to_oxy[self.EVICTION_TOOL_NAME] = eviction_tool

        # Phase 4: Auto-inject required_tools from skills into agent's tool list
        required_tools = self._skill_registry.get_required_tools()
        for tool_name in required_tools:
            if tool_name not in self.tools and tool_name != self.SKILL_TOOL_NAME:
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

        # Phase 5: Pre-build auto-inject full content section
        auto_inject = self._skill_registry.list_auto_inject()
        if auto_inject:
            content_blocks = []
            for skill in auto_inject:
                try:
                    content = skill.load_content()
                except Exception as e:
                    logger.warning(
                        f"[SkillAgent] Failed to load auto-inject content for '{skill.name}': {e}"
                    )
                    content = skill.description
                trigger_hint = ""
                if skill.trigger:
                    trigger_block = skill.trigger.to_prompt_block()
                    if trigger_block:
                        trigger_hint = "\n" + "\n".join(
                            f"  {line}" for line in trigger_block.splitlines()
                        ) + "\n"
                content_blocks.append(
                    f"### {skill.name}\n"
                    f"{trigger_hint}"
                    f"{content}"
                )

            self._auto_inject_section = (
                "## Always-Active Skills\n\n"
                "The following skills are always active. Their full instructions are "
                "embedded below — apply them automatically whenever their trigger "
                "conditions match.\n\n"
                + "\n\n---\n\n".join(content_blocks)
            )

        # Phase 6: Add skill tool (and optional eviction tool) to this agent's tools
        if self.SKILL_TOOL_NAME not in self.tools:
            self.tools.append(self.SKILL_TOOL_NAME)
        if self.enable_context_eviction and self.EVICTION_TOOL_NAME not in self.tools:
            self.tools.append(self.EVICTION_TOOL_NAME)

        # Phase 7: Call parent init
        await super().init()

        # Phase 8: Pre-build skill section (immutable after init)
        self._cached_skill_section = self._build_skill_section()

        logger.info(
            f"[SkillAgent] Agent '{self.name}' initialized: "
            f"{self.skills_count} skills discovered"
        )

    async def _before_execute(self, oxy_request: OxyRequest) -> OxyRequest:
        """Inject pre-built skill_section into prompt arguments."""
        oxy_request = await super()._before_execute(oxy_request)
        oxy_request.set_arguments("skill_section", self._cached_skill_section)
        return oxy_request

    def _build_instruction_for_round(self, oxy_request: OxyRequest) -> str:
        """Override: apply context eviction filtering each round."""
        return self._build_instruction_with_eviction(oxy_request.arguments, oxy_request)

    def _build_instruction_with_eviction(
        self, arguments: dict, oxy_request: OxyRequest
    ) -> str:
        """Build instruction prompt, filtering out evicted tools and skills.

        Called every ReAct round so evictions take effect immediately.
        """
        evicted_tools = get_evicted_tools(oxy_request)
        evicted_skills = get_evicted_skills(oxy_request)

        if not evicted_tools and not evicted_skills:
            return self._build_instruction(arguments)

        # Rebuild skill_section without evicted skills
        if evicted_skills:
            skill_section = self._build_skill_section(evicted_skills=evicted_skills)
            patched_args = dict(arguments)
            patched_args["skill_section"] = skill_section
        else:
            patched_args = arguments

        instruction = self._build_instruction(patched_args)

        # Strip tool descriptions for evicted tools (post-substitution filter)
        if evicted_tools:
            lines = instruction.splitlines()
            filtered_lines = []
            skip_until_blank = False
            for line in lines:
                if skip_until_blank:
                    # Skip tool block lines until we hit an empty line / next tool
                    if line.strip() == "" or (
                        line.startswith("- **") and line.strip().endswith("**")
                    ):
                        skip_until_blank = False
                    else:
                        continue
                # Check if this line starts a tool description for an evicted tool
                if any(
                    line.strip().startswith(f"- **{t}") for t in evicted_tools
                ):
                    skip_until_blank = True
                    continue
                filtered_lines.append(line)
            instruction = "\n".join(filtered_lines)

        return instruction

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
            response = _THINK_RE.sub("", response).strip()

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

    def _build_skill_section(self, evicted_skills: Optional[set] = None) -> str:
        """Build the complete dynamic skill section for prompt injection.

        Args:
            evicted_skills: Optional set of skill names to exclude (for context eviction).

        Returns empty string when no skills exist (no orphaned headers).
        Includes: invocable skills and auto-injected content.
        """
        parts = []
        evicted = evicted_skills or set()

        # 1. Model-invocable skills (called via skill tool)
        invocable = [
            s for s in self._skill_registry.list_invocable()
            if s.name not in evicted
        ]
        if invocable:
            entries = [s.to_prompt_entry() for s in invocable]
            parts.append(
                f"## Skills\n\n"
                f"The `{self.SKILL_TOOL_NAME}` tool loads specialized instructions "
                f"for specific tasks. When a skill's trigger conditions match the "
                f"current task, you MUST invoke the `{self.SKILL_TOOL_NAME}` tool "
                f"BEFORE generating any other response.\n\n"
                f"To invoke a skill:\n"
                f"```json\n"
                f'{{\n'
                f'    "think": "reasoning about why this skill matches",\n'
                f'    "tool_name": "{self.SKILL_TOOL_NAME}",\n'
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

        # 2. Auto-injected skills (pre-built in init, no eviction needed — always-active)
        if self._auto_inject_section:
            parts.append(self._auto_inject_section)

        return "\n\n".join(parts)
