"""Skill metadata module for lightweight skill indexing.

This module provides SkillTrigger and SkillMetadata classes for skill discovery,
LLM-based semantic matching, and on-demand content loading with $ARGUMENTS support.
"""

import logging
from html import escape as html_escape
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, PrivateAttr

logger = logging.getLogger(__name__)


class SkillTrigger(BaseModel):
    """Trigger conditions for automatic skill invocation.

    Supports both plain string and structured dict formats:
        - "user asks about weather"  →  when=["user asks about weather"]
        - {when: [...], not_when: [...]}
        - {when: "single string", not-when: "single string"}
    """

    when: List[str] = Field(default_factory=list)
    not_when: List[str] = Field(default_factory=list)

    def to_prompt_block(self) -> str:
        """Format trigger conditions as prompt text (no indentation)."""
        lines = []
        if self.when:
            lines.append(f"TRIGGER when: {', '.join(self.when)}")
        if self.not_when:
            lines.append(f"DO NOT TRIGGER when: {', '.join(self.not_when)}")
        return "\n".join(lines)

    @classmethod
    def from_value(cls, value) -> Optional["SkillTrigger"]:
        """Create SkillTrigger from string, dict, or None.

        Args:
            value: Plain string, dict with when/not_when, or None.

        Returns:
            SkillTrigger instance or None.
        """
        if value is None:
            return None
        if isinstance(value, str):
            return cls(when=[value])
        if isinstance(value, dict):
            when = value.get("when", [])
            # Accept not_when / not-when / unless as aliases
            not_when = value.get("not_when", value.get("not-when", value.get("unless", [])))
            # Normalize single string to list
            if isinstance(when, str):
                when = [when]
            if isinstance(not_when, str):
                not_when = [not_when]
            return cls(when=when, not_when=not_when)
        return None


class SkillMetadata(BaseModel):
    """Lightweight skill metadata for indexing and on-demand loading.

    Loaded at startup, injected into the agent's system prompt for LLM awareness.
    Full skill content is loaded on-demand via load_content() with caching.
    """

    name: str = Field(..., description="Unique skill identifier")
    description: str = Field(..., description="Short description for LLM semantic matching")
    skill_path: Path = Field(..., description="Path to SKILL.md file")
    trigger: Optional[SkillTrigger] = Field(None, description="Trigger conditions")
    namespace: Optional[str] = Field(None, description="Optional namespace prefix")
    version: Optional[str] = Field(None, description="Optional semantic version")
    author: Optional[str] = Field(None, description="Optional author information")

    disable_model_invocation: bool = Field(
        False,
        description="If true, skill content is auto-injected into context "
        "without requiring the model to call the skill tool",
    )
    source_name: Optional[str] = Field(
        None,
        description="Name of the source that registered this skill",
    )
    required_tools: List[str] = Field(
        default_factory=list,
        description="Tools that this skill depends on (auto-injected into agent's tool list)",
    )
    argument_hint: Optional[str] = Field(
        None,
        description="Hint describing the expected argument format for $ARGUMENTS placeholder",
    )

    # Internal cache fields (not serialized, per-instance via PrivateAttr)
    _content_cache: Optional[str] = PrivateAttr(default=None)
    _mtime: Optional[float] = PrivateAttr(default=None)
    _has_arguments_template: Optional[bool] = PrivateAttr(default=None)
    _resources_cache: Optional[Dict[str, str]] = PrivateAttr(default=None)

    @property
    def base_name(self) -> str:
        """Return name without namespace prefix. 'dongx:weather' → 'weather'."""
        if ":" in self.name:
            return self.name.split(":", 1)[1]
        return self.name

    @property
    def full_name(self) -> str:
        """Return namespace-qualified name. Auto-prepends namespace if not present."""
        if self.namespace and ":" not in self.name:
            return f"{self.namespace}:{self.name}"
        return self.name

    @property
    def has_arguments_template(self) -> bool:
        """Whether the raw SKILL.md body contains $ARGUMENTS placeholder."""
        if self._has_arguments_template is None:
            self._ensure_cache()
        return self._has_arguments_template

    def _ensure_cache(self) -> None:
        """Load and cache the skill body from disk. Re-loads when file mtime changes."""
        try:
            current_mtime = self.skill_path.stat().st_mtime
        except OSError:
            current_mtime = None

        if self._content_cache is not None and current_mtime == self._mtime:
            return

        raw = self.skill_path.read_text(encoding="utf-8")
        lines = raw.splitlines(True)

        if not lines or lines[0].strip() != "---":
            body = "".join(lines)
        else:
            end_line = None
            for i, line in enumerate(lines[1:], 1):
                if line.strip() == "---":
                    end_line = i
                    break
            if end_line is not None:
                body = "".join(lines[end_line + 1:])
            else:
                body = "".join(lines)

        self._content_cache = body.strip()
        self._mtime = current_mtime
        self._has_arguments_template = "$ARGUMENTS" in self._content_cache

    def load_content(self, arguments: str = "") -> str:
        """Load the markdown body from SKILL.md, stripping frontmatter.

        Re-reads the file when mtime changes (hot-reload support).
        Replaces $ARGUMENTS with the provided arguments string.

        Args:
            arguments: Optional string to substitute for $ARGUMENTS in the body.

        Returns:
            The markdown body content with $ARGUMENTS replaced.
        """
        self._ensure_cache()
        content = self._content_cache

        if arguments:
            content = content.replace("$ARGUMENTS", arguments)

        return content

    @property
    def resource_names(self) -> List[str]:
        """Return sorted list of companion resource filenames (*.md except SKILL.md)."""
        self._ensure_resources()
        return sorted(self._resources_cache.keys())

    def load_resource(self, name: str) -> Optional[str]:
        """Load a companion resource file by name.

        Args:
            name: Filename (e.g. 'security_checklist.md').

        Returns:
            File content string, or None if not found.
        """
        self._ensure_resources()
        return self._resources_cache.get(name)

    def _ensure_resources(self) -> None:
        """Scan skill directory for companion .md files and cache their content."""
        if self._resources_cache is not None:
            return

        self._resources_cache = {}
        skill_dir = self.skill_path.parent
        for md_file in skill_dir.glob("*.md"):
            if md_file.name == "SKILL.md":
                continue
            try:
                self._resources_cache[md_file.name] = md_file.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning(f"[SkillMetadata] Failed to cache resource '{md_file.name}': {e}")

    def to_prompt_entry(self) -> str:
        """Format for system prompt injection with trigger conditions."""
        entry = f"- **{self.name}**: {self.description}"
        if self.argument_hint:
            entry += f" (args: `{self.argument_hint}`)"
        if self.trigger:
            trigger_block = self.trigger.to_prompt_block()
            if trigger_block:
                indented = "\n".join(f"  {line}" for line in trigger_block.splitlines())
                entry += "\n" + indented
        return entry

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        result = {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "namespace": self.namespace,
            "disable_model_invocation": self.disable_model_invocation,
            "required_tools": self.required_tools,
            "argument_hint": self.argument_hint,
        }
        if self.trigger:
            result["trigger"] = self.trigger.model_dump()
        return result

    @classmethod
    def from_frontmatter(cls, frontmatter: dict, skill_path: Path) -> "SkillMetadata":
        """Create SkillMetadata from PyYAML-parsed frontmatter dict.

        Supports nested trigger structures, hyphenated and underscored field names.
        Validates skill name format for user-invocable skills.
        """
        if "name" not in frontmatter:
            raise ValueError("Skill frontmatter missing required field: name")
        if "description" not in frontmatter:
            raise ValueError("Skill frontmatter missing required field: description")

        # Parse trigger (supports string, dict, or None)
        trigger = SkillTrigger.from_value(frontmatter.get("trigger"))

        # Handle hyphenated and underscored field names
        disable_model_invocation = frontmatter.get("disable-model-invocation")
        if disable_model_invocation is None:
            disable_model_invocation = frontmatter.get("disable_model_invocation", False)

        # Parse required_tools (supports hyphenated key)
        required_tools = frontmatter.get("required-tools")
        if required_tools is None:
            required_tools = frontmatter.get("required_tools", [])
        if isinstance(required_tools, str):
            required_tools = [required_tools]

        # Parse argument_hint (supports hyphenated key)
        argument_hint = frontmatter.get("argument-hint", frontmatter.get("argument_hint"))

        return cls(
            name=frontmatter["name"],
            description=frontmatter["description"],
            skill_path=skill_path,
            trigger=trigger,
            namespace=frontmatter.get("namespace"),
            version=frontmatter.get("version"),
            author=frontmatter.get("author"),
            disable_model_invocation=bool(disable_model_invocation),
            required_tools=required_tools if isinstance(required_tools, list) else [],
            argument_hint=str(argument_hint) if argument_hint is not None else None,
        )

    def __repr__(self) -> str:
        version_str = f" v{self.version}" if self.version else ""
        return f"SkillMetadata(name='{self.name}'{version_str})"


def escape_xml_attr(value: str) -> str:
    """Escape a string for safe use in XML attribute values."""
    return html_escape(value, quote=True)
