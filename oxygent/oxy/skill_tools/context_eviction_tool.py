"""ContextEvictionTool: lets the LLM drop tools or skills from the active context.

When a task is long-running and certain tools/skills are no longer needed, the LLM
can call this tool to shrink the context window it occupies, preventing overflow.

The eviction is *per-request* — it does not permanently remove anything from the
agent's configuration. On the next request the full context is rebuilt from scratch.

Usage by LLM:
    ```json
    {
        "tool_name": "drop_context",
        "arguments": {
            "tools": ["security-check", "performance-check"],
            "skills": ["code-review"]
        }
    }
    ```
"""

import logging
from typing import List, Optional

from pydantic import Field

from ...schemas import OxyRequest, OxyResponse, OxyState
from ..base_tool import BaseTool

logger = logging.getLogger(__name__)

# Key used in oxy_request.arguments to track per-request evictions
_EVICTED_TOOLS_KEY = "_evicted_tools"
_EVICTED_SKILLS_KEY = "_evicted_skills"


def get_evicted_tools(oxy_request: OxyRequest) -> set:
    """Return the set of tool names evicted for this request."""
    v = oxy_request.arguments.get(_EVICTED_TOOLS_KEY)
    return v if isinstance(v, set) else set()


def get_evicted_skills(oxy_request: OxyRequest) -> set:
    """Return the set of skill names evicted for this request."""
    v = oxy_request.arguments.get(_EVICTED_SKILLS_KEY)
    return v if isinstance(v, set) else set()


class ContextEvictionTool(BaseTool):
    """Tool that lets the LLM evict tools or skills from the current context.

    Calling this tool removes the specified tools/skills from the tool
    description list and skill section for the remainder of this request.
    This reduces token usage when certain tools are no longer needed.

    The eviction is scoped to the current request only.
    """

    name: str = Field(default="drop_context")
    description: str = Field(
        default=(
            "Remove tools or skills from the current context to reduce token usage. "
            "Use this when you are done with certain tools and they are no longer needed "
            "for the rest of this task. Eviction is scoped to the current request only."
        )
    )
    input_schema: dict = Field(
        default={
            "type": "object",
            "properties": {
                "tools": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tool names to remove from context",
                    "default": [],
                },
                "skills": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Skill names to remove from the skill section",
                    "default": [],
                },
                "reason": {
                    "type": "string",
                    "description": "Brief reason for eviction (for logging)",
                    "default": "",
                },
            },
        }
    )

    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        arguments = oxy_request.arguments
        tools_to_evict: List[str] = arguments.get("tools") or []
        skills_to_evict: List[str] = arguments.get("skills") or []
        reason: str = arguments.get("reason", "")

        if not tools_to_evict and not skills_to_evict:
            return OxyResponse(
                state=OxyState.COMPLETED,
                output="No tools or skills specified for eviction.",
            )

        # Accumulate evictions into the parent request's arguments
        # We store them as sets directly in oxy_request.arguments so
        # _get_llm_tool_desc_list and _build_skill_section can check them.
        parent_args = oxy_request.arguments

        evicted_tools: set = parent_args.get(_EVICTED_TOOLS_KEY) or set()
        evicted_skills: set = parent_args.get(_EVICTED_SKILLS_KEY) or set()

        evicted_tools.update(tools_to_evict)
        evicted_skills.update(skills_to_evict)

        parent_args[_EVICTED_TOOLS_KEY] = evicted_tools
        parent_args[_EVICTED_SKILLS_KEY] = evicted_skills

        parts = []
        if tools_to_evict:
            parts.append(f"tools [{', '.join(tools_to_evict)}]")
        if skills_to_evict:
            parts.append(f"skills [{', '.join(skills_to_evict)}]")

        msg = f"Evicted {' and '.join(parts)} from context."
        if reason:
            msg += f" Reason: {reason}"

        logger.info(
            f"[ContextEvictionTool] {msg}",
            extra={
                "trace_id": oxy_request.current_trace_id,
                "node_id": oxy_request.node_id,
            },
        )

        return OxyResponse(
            state=OxyState.COMPLETED,
            output=msg,
        )
