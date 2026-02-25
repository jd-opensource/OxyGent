"""Skill tool module for skill invocation.

This module provides the SkillTool class, which is the tool that agents use
to invoke skills. When invoked, it loads the full skill content and injects
it into the agent's context along with environment modifications.
"""

import logging
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Tuple

from pydantic import Field

from ...schemas import OxyRequest, OxyResponse, OxyState
from ..base_tool import BaseTool

logger = logging.getLogger(__name__)


class SkillTool(BaseTool):
    """The Skill tool that agents use to invoke skills.

    When invoked, this tool:
    1. Loads the full skill content from the registry (on-demand)
    2. Injects the skill instructions into the conversation context
    3. Returns environment modifications for the agent to apply
    4. Returns control to the agent with enriched context

    The tool itself does NOT execute the skill's task. Instead, it loads
    the skill and modifies the agent's context, allowing the agent to
    continue execution with the skill's guidance.

    Attributes:
        name: Tool name, always "Skill".
        desc: Tool description.
        skill_registry: Reference to the skill registry for loading skills.
        is_permission_required: Skills don't require permission (default False).
    """

    name: str = Field("Skill", description="Tool name")
    desc: str = Field(
        "Invoke a skill to get specialized instructions and capabilities",
        description="Tool description",
    )
    is_permission_required: bool = Field(
        False,
        description="Skills don't require explicit permission",
    )
    skill_registry: Any = Field(
        None,
        description="Reference to the skill registry",
        exclude=True,
    )

    # Cache scoped registries by normalized directory tuple.
    _scoped_registry_cache: ClassVar[Dict[Tuple[str, ...], Any]] = {}

    input_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "The name of the skill to invoke",
            },
            "arguments": {
                "type": "string",
                "description": "Optional argument string passed to the skill (used for $ARGUMENTS substitution)",
            },
            "invocation_source": {
                "type": "string",
                "description": "Invocation source: user | selector | model",
            },
            "skill_dirs": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional absolute skill directories for scoped resolution",
            },
        },
        "required": ["name"],
    }

    def __init__(self, **kwargs):
        """Initialize the Skill tool."""
        super().__init__(**kwargs)
        self._set_desc_for_llm()

    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        """Execute skill invocation.

        This method loads the skill content and returns it for context injection.
        It does NOT directly execute the skill's task.

        Args:
            oxy_request: The request containing the skill name in arguments.

        Returns:
            OxyResponse with:
                - state: COMPLETED if skill found, FAILED otherwise
                - output: Context injection string with skill instructions
                - extra: Environment modifications and skill metadata
        """
        skill_name = oxy_request.arguments.get("name")
        skill_args = oxy_request.arguments.get("arguments")
        invocation_source = oxy_request.arguments.get("invocation_source", "model")
        scoped_skill_dirs = oxy_request.arguments.get("skill_dirs")
        if not isinstance(invocation_source, str) or not invocation_source.strip():
            invocation_source = "model"
        invocation_source = invocation_source.strip()

        if not isinstance(skill_args, str):
            skill_args = "" if skill_args is None else str(skill_args)

        if not skill_name:
            return OxyResponse(
                state=OxyState.FAILED,
                output='Skill name is required. Usage: Skill(name="skill-name")',
            )

        # Get skill registry from request's mas if not set
        registry = self.skill_registry
        if scoped_skill_dirs is not None:
            try:
                registry = self._get_scoped_registry(scoped_skill_dirs)
            except Exception as e:
                return OxyResponse(state=OxyState.FAILED, output=str(e))
        elif not registry:
            registry = getattr(oxy_request.mas, "skill_registry", None)

        if not registry:
            return OxyResponse(
                state=OxyState.FAILED,
                output="Skill registry not initialized. Cannot invoke skills.",
            )

        # Check if skill exists
        if not registry.has_skill(skill_name):
            available = ", ".join(registry.metadata_index.keys())
            return OxyResponse(
                state=OxyState.FAILED,
                output=f"Skill '{skill_name}' not found. Available skills: {available}",
            )

        # Load full skill content (on-demand)
        skill_content = registry.load_full_content(skill_name)
        if not skill_content:
            return OxyResponse(
                state=OxyState.FAILED,
                output=f"Failed to load content for skill '{skill_name}'",
            )

        # Enforce invocation policy
        if invocation_source == "model":
            return OxyResponse(
                state=OxyState.SKIPPED,
                output=(
                    "Skill tool invocation from the model is not supported in this runtime. "
                    "Use selector-based activation or manual /skill-name invocation."
                ),
            )
        if invocation_source == "selector" and getattr(
            skill_content, "disable_model_invocation", False
        ):
            return OxyResponse(
                state=OxyState.SKIPPED,
                output=(
                    f"Skill '{skill_name}' has disable-model-invocation=true; selector activation blocked."
                ),
            )
        if (
            invocation_source == "user"
            and getattr(skill_content, "user_invocable", True) is False
        ):
            return OxyResponse(
                state=OxyState.SKIPPED,
                output=(
                    f"Skill '{skill_name}' is not user-invocable (user-invocable=false)."
                ),
            )

        # Build context injection
        context_injection = skill_content.to_context_injection()
        if skill_args.strip():
            if "$ARGUMENTS" in context_injection:
                context_injection = context_injection.replace("$ARGUMENTS", skill_args)
            else:
                context_injection = context_injection + "\n\nARGUMENTS: " + skill_args

        # Build execution environment modifications
        env_mods = skill_content.get_environment_modifications()

        # Log skill activation
        logger.info(
            f"Skill activated: {skill_name}",
            extra={
                "trace_id": oxy_request.current_trace_id,
                "node_id": oxy_request.node_id,
            },
        )

        return OxyResponse(
            state=OxyState.COMPLETED,
            output=context_injection,
            extra={
                "skill_name": skill_name,
                "invocation_source": invocation_source,
                "environment_modifications": env_mods,
                "context_type": "skill_injection",
                "skill_version": skill_content.version,
                "skill_author": skill_content.author,
            },
        )

    def set_registry(self, registry):
        """Set the skill registry reference.

        This is typically called during MAS initialization.

        Args:
            registry: The skill registry instance.
        """
        self.skill_registry = registry

    @classmethod
    def _normalize_skill_dirs(cls, skill_dirs: Any) -> List[str]:
        if not isinstance(skill_dirs, list):
            raise ValueError("skill_dirs must be a list of absolute directory paths")
        if not skill_dirs:
            raise ValueError("skill_dirs must not be empty")

        normalized: list[str] = []
        for raw in skill_dirs:
            if not isinstance(raw, str) or not raw.strip():
                raise ValueError("skill_dirs contains an empty path")
            p = Path(raw.strip())
            if not p.is_absolute():
                raise ValueError(f"skill_dirs path must be absolute: {raw}")
            if not p.exists():
                raise ValueError(f"skill_dirs path does not exist: {raw}")
            if not p.is_dir():
                raise ValueError(f"skill_dirs path is not a directory: {raw}")
            resolved = str(p.resolve())
            if resolved not in normalized:
                normalized.append(resolved)

        if not normalized:
            raise ValueError("skill_dirs must not be empty")
        return normalized

    @classmethod
    def _get_scoped_registry(cls, skill_dirs: Any):
        normalized = cls._normalize_skill_dirs(skill_dirs)
        key = tuple(normalized)
        if key in cls._scoped_registry_cache:
            return cls._scoped_registry_cache[key]

        from .skill_registry import SkillRegistry

        registry = SkillRegistry(skill_dirs=list(key), auto_discover=True)
        cls._scoped_registry_cache[key] = registry
        return registry

    def _set_desc_for_llm(self):
        """Generate LLM-friendly description."""
        self.desc_for_llm = f"""
 Tool: {self.name}
 Description: {self.desc}
 Arguments:
 - name: string, The name of the skill to invoke (required)
 - arguments: string, Optional argument string passed to the skill
 - invocation_source: string, Invocation source (user|selector|model)
 - skill_dirs: string[], Optional absolute directories for scoped skill resolution
 """
