"""Skill content module for full skill data.

This module provides the SkillContent class, which contains the full content
of a skill including instructions, environment modifications, and associated
resources. This is loaded on-demand when a skill is invoked.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SkillContent(BaseModel):
    """Full skill content, loaded on-demand when skill is invoked.

    This class contains all the information needed to activate a skill,
    including the detailed instructions, execution environment modifications,
    and any associated resource files.

    Attributes:
        name: Unique skill identifier.
        description: Short description for LLM semantic matching.
        version: Optional semantic version string.
        author: Optional author information.
        instructions: Full markdown instructions from SKILL.md body.
        allowed_tools: Tools available when skill is active.
        model: Preferred LLM model for this skill.
        timeout: Timeout override for skill execution.
        resources: Loaded resource files mapping filename to content.
        skill_path: Path to the SKILL.md file.
    """

    name: str = Field(..., description="Unique skill identifier")
    description: str = Field(
        ...,
        description="Short description for LLM semantic matching",
    )
    version: Optional[str] = Field(
        None,
        description="Optional semantic version",
    )
    author: Optional[str] = Field(
        None,
        description="Optional author information",
    )
    instructions: str = Field(
        ...,
        description="Full markdown instructions from SKILL.md body",
    )
    allowed_tools: List[str] = Field(
        default_factory=list,
        description="Tools available when skill is active",
    )
    model: Optional[str] = Field(
        None,
        description="Preferred LLM model for this skill",
    )
    timeout: Optional[float] = Field(
        None,
        description="Timeout override for skill execution in seconds",
    )
    resources: Dict[str, str] = Field(
        default_factory=dict,
        description="Loaded resource files: filename -> content",
    )
    skill_path: Optional[Path] = Field(
        None,
        description="Path to the SKILL.md file",
    )

    disable_model_invocation: bool = Field(
        False,
        description="If true, this skill must not be auto-invoked by the system/model",
    )
    user_invocable: bool = Field(
        True,
        description="If false, this skill must not be manually invoked by /skill-name",
    )
    argument_hint: Optional[str] = Field(
        None,
        description="Optional hint for user-provided arguments",
    )

    def to_context_injection(self) -> str:
        """Format for conversation context injection.

        Creates a formatted string that can be injected into the agent's
        conversation context when the skill is activated. This includes
        the skill activation marker, instructions, and any resources.

        Returns:
            A formatted string ready for context injection.
        """
        lines = [
            f"[SKILL ACTIVATED: {self.name}]",
            "",
            self.instructions,
        ]

        # Add resources if any
        if self.resources:
            lines.append("")
            lines.append("## Skill Resources")
            lines.append("")
            for name, content in self.resources.items():
                lines.append(f"### {name}")
                lines.append("")
                lines.append(content)
                lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization.

        Returns:
            A dictionary representation of the skill content.
        """
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "instructions": self.instructions,
            "allowed_tools": self.allowed_tools,
            "model": self.model,
            "timeout": self.timeout,
            "resources": list(self.resources.keys()),
            "disable_model_invocation": self.disable_model_invocation,
            "user_invocable": self.user_invocable,
            "argument_hint": self.argument_hint,
        }

    def get_environment_modifications(self) -> dict:
        """Get execution environment modifications.

        Returns a dictionary of modifications that should be applied to
        the agent's execution environment when this skill is active.

        Returns:
            A dictionary with keys like 'allowed_tools', 'model', 'timeout'.
        """
        mods = {}

        if self.allowed_tools:
            mods["allowed_tools"] = self.allowed_tools

        if self.model:
            mods["model"] = self.model

        if self.timeout:
            mods["timeout"] = self.timeout

        return mods

    @classmethod
    def from_frontmatter_and_body(
        cls,
        frontmatter: dict,
        body: str,
        skill_path: Path,
        loaded_resources: Optional[Dict[str, str]] = None,
    ) -> "SkillContent":
        """Create SkillContent from parsed frontmatter and body.

        Args:
            frontmatter: Parsed YAML frontmatter from SKILL.md.
            body: The markdown body content from SKILL.md.
            skill_path: Path to the SKILL.md file.
            loaded_resources: Optional dict of loaded resource files.

        Returns:
            A SkillContent instance.

        Raises:
            ValueError: If required fields (name, description) are missing.
        """
        if "name" not in frontmatter:
            raise ValueError("Skill frontmatter missing required field: name")
        if "description" not in frontmatter:
            raise ValueError("Skill frontmatter missing required field: description")

        disable_model_invocation = frontmatter.get("disable-model-invocation")
        if disable_model_invocation is None:
            disable_model_invocation = frontmatter.get(
                "disable_model_invocation", False
            )

        user_invocable = frontmatter.get("user-invocable")
        if user_invocable is None:
            user_invocable = frontmatter.get("user_invocable", True)

        argument_hint = frontmatter.get("argument-hint")
        if argument_hint is None:
            argument_hint = frontmatter.get("argument_hint")

        # Handle both 'allowed-tools' and 'allowed_tools' naming conventions
        allowed_tools_raw = frontmatter.get("allowed-tools")
        if allowed_tools_raw is None:
            allowed_tools_raw = frontmatter.get("allowed_tools", [])

        if isinstance(allowed_tools_raw, str):
            allowed_tools = [allowed_tools_raw]
        elif isinstance(allowed_tools_raw, list):
            allowed_tools = [t for t in allowed_tools_raw if isinstance(t, str)]
            if len(allowed_tools) != len(allowed_tools_raw):
                logger.warning(
                    "Invalid allowed-tools entries in %s; non-string values dropped",
                    skill_path,
                )
        else:
            if allowed_tools_raw:
                logger.warning(
                    "Invalid allowed-tools type in %s; expected list or string",
                    skill_path,
                )
            allowed_tools = []

        return cls(
            name=frontmatter["name"],
            description=frontmatter["description"],
            version=frontmatter.get("version"),
            author=frontmatter.get("author"),
            instructions=body,
            allowed_tools=allowed_tools,
            model=frontmatter.get("model"),
            timeout=frontmatter.get("timeout"),
            resources=loaded_resources or {},
            skill_path=skill_path,
            disable_model_invocation=bool(disable_model_invocation),
            user_invocable=bool(user_invocable),
            argument_hint=argument_hint if isinstance(argument_hint, str) else None,
        )

    def __repr__(self) -> str:
        """String representation for debugging."""
        version_str = f" v{self.version}" if self.version else ""
        return f"SkillContent(name='{self.name}'{version_str})"
