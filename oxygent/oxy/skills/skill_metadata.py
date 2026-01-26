"""Skill metadata module for lightweight skill indexing.

This module provides the SkillMetadata class, which represents the lightweight
metadata for a skill that is loaded at startup and used for skill discovery
and LLM-based semantic matching.
"""

import logging
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SkillMetadata(BaseModel):
    """Lightweight skill metadata for indexing.

    This class contains only the essential information about a skill that is
    needed for discovery and matching. It is loaded at startup and injected
    into the agent's system prompt to enable LLM-based skill selection.

    The full skill content is loaded on-demand when the skill is invoked.

    Attributes:
        name: Unique skill identifier used to invoke the skill.
        description: Short description for LLM semantic matching.
        skill_path: Path to the SKILL.md file for on-demand loading.
        version: Optional semantic version string.
        author: Optional author information.
    """

    name: str = Field(..., description="Unique skill identifier")
    description: str = Field(
        ...,
        description="Short description for LLM semantic matching",
    )
    skill_path: Path = Field(
        ...,
        description="Path to SKILL.md file for on-demand loading",
    )
    version: Optional[str] = Field(
        None,
        description="Optional semantic version",
    )
    author: Optional[str] = Field(
        None,
        description="Optional author information",
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

    def to_prompt_entry(self) -> str:
        """Format for system prompt injection.

        Returns a formatted string suitable for inclusion in the agent's
        system prompt, showing the skill name and description.

        Returns:
            A formatted markdown string with skill name and description.
        """
        return f"- **{self.name}**: {self.description}"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization.

        Returns:
            A dictionary representation of the metadata, excluding the
            skill_path which is not needed for serialization.
        """
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "disable_model_invocation": self.disable_model_invocation,
            "user_invocable": self.user_invocable,
            "argument_hint": self.argument_hint,
        }

    @classmethod
    def from_frontmatter(
        cls,
        frontmatter: dict,
        skill_path: Path,
    ) -> "SkillMetadata":
        """Create SkillMetadata from parsed frontmatter.

        Args:
            frontmatter: Parsed YAML frontmatter from SKILL.md.
            skill_path: Path to the SKILL.md file.

        Returns:
            A SkillMetadata instance.

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

        return cls(
            name=frontmatter["name"],
            description=frontmatter["description"],
            skill_path=skill_path,
            version=frontmatter.get("version"),
            author=frontmatter.get("author"),
            disable_model_invocation=bool(disable_model_invocation),
            user_invocable=bool(user_invocable),
            argument_hint=argument_hint if isinstance(argument_hint, str) else None,
        )

    def __repr__(self) -> str:
        """String representation for debugging."""
        version_str = f" v{self.version}" if self.version else ""
        return f"SkillMetadata(name='{self.name}'{version_str})"
