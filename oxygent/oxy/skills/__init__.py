"""OxyGent Skills System.

This module provides the skills system for OxyGent. Skills are Markdown-based
instructions that extend agent capabilities through prompt injection, distinct
from code-based tools.

The skills system follows the Claude Agent SDK pattern with progressive disclosure:
- Metadata (name + description) is loaded at startup for fast initialization
- Full content is loaded on-demand when a skill is invoked
- Skills modify the agent's context and execution environment dynamically
"""

from .skill_content import SkillContent
from .skill_metadata import SkillMetadata
from .skill_registry import SkillRegistry
from .skill_tool import SkillTool

__all__ = [
    "SkillMetadata",
    "SkillContent",
    "SkillRegistry",
    "SkillTool",
]
