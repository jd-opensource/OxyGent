"""SkillTool: Tool for LLM-driven skill invocation.

Allows the LLM to invoke skills by name through the standard tool-calling
mechanism. Looks up the skill in the registry, loads its content with
$ARGUMENTS substitution, and returns it wrapped in <skill-instructions> tags.

Integrates with SkillRegistry hooks for pre/post invocation auditing.
"""

import difflib
import logging

from pydantic import Field, PrivateAttr

from ...schemas import OxyRequest, OxyResponse, OxyState
from ...schemas.skill import escape_xml_attr
from ...skills.skill_registry import SkillHookEvent, SkillRegistry
from ..base_tool import BaseTool

logger = logging.getLogger(__name__)


class SkillTool(BaseTool):
    """Tool that enables LLM to invoke skills from the registry.

    The LLM calls this tool with a skill name and optional arguments.
    The tool loads the skill's SKILL.md content, performs $ARGUMENTS
    substitution, and returns it wrapped in <skill-instructions> tags.

    Skills with disable_model_invocation=True are auto-injected into
    the prompt by the SkillAgent and should not be called via this tool.
    """

    name: str = Field(default="skill", description="Tool name")
    desc: str = Field(
        default="Invoke a skill by name to load its instructions and resources.",
        description="Tool description",
    )
    category: str = Field(default="tool", description="Category")

    input_schema: dict = Field(
        default_factory=lambda: {
            "properties": {
                "skill": {
                    "type": "string",
                    "description": "The skill name to invoke",
                },
                "args": {
                    "type": "string",
                    "description": "Optional arguments for the skill (replaces $ARGUMENTS in skill content)",
                },
                "file": {
                    "type": "string",
                    "description": "Load a companion resource file from the skill's directory instead of the main skill content. Use the filename shown in available_resources.",
                },
            },
            "required": ["skill"],
        },
        description="Input schema",
    )

    _registry: SkillRegistry = PrivateAttr(default=None)

    def __init__(self, registry: SkillRegistry, **kwargs):
        super().__init__(**kwargs)
        self._registry = registry

    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        """Execute the skill invocation.

        1. Look up skill in registry
        2. If `file` param given, return companion resource content
        3. Otherwise: validate, fire hooks, load SKILL.md content, append resource list
        """
        arguments = oxy_request.arguments
        skill_name = arguments.get("skill", "")
        args = arguments.get("args", "")
        file_name = arguments.get("file", "")

        if not skill_name:
            return OxyResponse(
                state=OxyState.FAILED,
                output="Missing required parameter: skill",
            )

        # Look up skill
        metadata = self._registry.get(skill_name)
        if metadata is None:
            all_names = [s.name for s in self._registry.list_all()]
            suggestions = difflib.get_close_matches(skill_name, all_names, n=3, cutoff=0.4)
            msg = f"Skill '{skill_name}' not found."
            if suggestions:
                msg += f" Did you mean: {', '.join(suggestions)}?"
            else:
                msg += f" Available skills: {', '.join(all_names)}"
            return OxyResponse(
                state=OxyState.FAILED,
                output=msg,
            )

        # --- Branch: load companion resource file ---
        if file_name:
            content = metadata.load_resource(file_name)
            if content is None:
                available = metadata.resource_names
                msg = f"Resource '{file_name}' not found in skill '{skill_name}'."
                if available:
                    msg += f" Available resources: {', '.join(available)}"
                else:
                    msg += " This skill has no companion resource files."
                return OxyResponse(state=OxyState.FAILED, output=msg)
            formatted = (
                f'<skill-resource name="{escape_xml_attr(metadata.name)}" '
                f'file="{escape_xml_attr(file_name)}">\n'
                f"{content}\n"
                f"</skill-resource>"
            )
            return OxyResponse(state=OxyState.COMPLETED, output=formatted)

        # --- Branch: load main skill content ---

        # Fire pre_invoke hooks
        pre_event = SkillHookEvent(
            hook_type="pre_invoke",
            skill_name=skill_name,
            args=args,
            source="tool",
            metadata=metadata,
        )
        block_msg = await self._registry.fire_hook_async(pre_event)
        if block_msg:
            return OxyResponse(
                state=OxyState.FAILED,
                output=f"Skill invocation blocked: {block_msg}",
            )

        # Load content with $ARGUMENTS substitution
        try:
            content = metadata.load_content(arguments=args)
        except Exception as e:
            logger.error(f"Failed to load skill content for '{skill_name}': {e}")
            return OxyResponse(
                state=OxyState.FAILED,
                output=f"Failed to load skill '{skill_name}': {e}",
            )

        # Build formatted output with <skill-instructions> tags
        args_attr = f' args="{escape_xml_attr(args)}"' if args else ""
        formatted = (
            f'<skill-instructions name="{escape_xml_attr(metadata.name)}"{args_attr}>\n'
            f"{content}\n"
            f"</skill-instructions>"
        )

        # Append available resources hint if any exist
        resources = metadata.resource_names
        if resources:
            res_list = ", ".join(resources)
            formatted += (
                f"\n\nThis skill has companion resource files: [{res_list}]. "
                f"To load one, call: skill(skill=\"{skill_name}\", file=\"<filename>\")"
            )

        # Fire post_invoke hooks
        post_event = SkillHookEvent(
            hook_type="post_invoke",
            skill_name=skill_name,
            args=args,
            source="tool",
            metadata=metadata,
            result=formatted,
        )
        await self._registry.fire_hook_async(post_event)

        return OxyResponse(
            state=OxyState.COMPLETED,
            output=formatted,
        )
