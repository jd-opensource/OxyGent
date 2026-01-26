"""OxyGent Preset Skills.

This package contains built-in skills for the OxyGent framework.
These skills are automatically discovered and available to all agents.

Note: Preset skills should align with the runtime's actual tool/agent
capabilities. See `oxygent/preset_skills/README.md` for the current list.
"""

from pathlib import Path

__all__ = ["PRESET_SKILLS_DIR"]

PRESET_SKILLS_DIR = Path(__file__).parent
