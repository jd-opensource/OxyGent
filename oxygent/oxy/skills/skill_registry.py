"""Skill registry module for skill discovery and on-demand loading.

This module provides the SkillRegistry class, which manages skill discovery,
metadata indexing, and on-demand loading following the progressive disclosure
pattern.

The registry implements two-phase loading:
1. Startup: Load metadata only (name + description) for fast initialization
2. Runtime: Load full content when skill is invoked
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from .skill_content import SkillContent
from .skill_metadata import SkillMetadata

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Manages skill discovery, metadata indexing, and on-demand loading.

    The registry implements progressive disclosure for efficient resource usage:
    - At startup, only skill metadata (name + description) is loaded
    - Full skill content is loaded on-demand when a skill is invoked
    - Loaded content is cached for subsequent invocations

    Attributes:
        skill_dirs: Directories to search for skill definitions.
        metadata_index: Lightweight index of all discovered skills.
        _content_cache: Cache for loaded full skill content.
    """

    # Discovery precedence: later entries override earlier ones on name collision.
    DEFAULT_SKILL_DIRS = [
        "oxygent/preset_skills/",  # Built-in preset skills (lowest priority)
        "~/.oxygent/skills/",  # User-level OxyGent skills
        ".oxygent/skills/",  # Project-local OxyGent skills
        "~/.claude/skills/",  # User-level Claude skills
        ".claude/skills/",  # Project-local Claude skills (highest priority)
    ]

    # Directories inside a skill that must not be treated as separate skills.
    _NON_SKILL_SUBDIRS = {"scripts", "references", "assets"}

    def __init__(
        self,
        skill_dirs: Optional[List[str]] = None,
        auto_discover: bool = True,
    ):
        """Initialize the skill registry.

        Args:
            skill_dirs: List of directories to search for skills. Defaults
                to [.oxygent/skills/, ~/.oxygent/skills/].
            auto_discover: If True, automatically discover skills on init.
        """
        self.skill_dirs = skill_dirs or self.DEFAULT_SKILL_DIRS

        # Metadata index (lightweight, always in memory)
        self.metadata_index: Dict[str, SkillMetadata] = {}

        # Content cache (loaded on-demand)
        self._content_cache: Dict[str, SkillContent] = {}

        if auto_discover:
            self.discover_all()

    def discover_all(self) -> List[str]:
        """Discover all skills and load metadata ONLY.

        This method scans all configured skill directories and loads only
        the metadata (name + description) from each SKILL.md file.
        The full content is NOT loaded to minimize startup time and memory.

        Returns:
            A list of discovered skill names.
        """
        discovered = []

        for skill_dir in self.skill_dirs:
            path = Path(skill_dir).expanduser()
            if not path.exists():
                logger.debug(f"Skill directory does not exist: {skill_dir}")
                continue

            if not path.is_dir():
                logger.warning(f"Skill path is not a directory: {skill_dir}")
                continue

            for skill_file in path.rglob("SKILL.md"):
                # Support the standard "skill folder" layout where a skill may contain
                # scripts/references/assets. Those subdirectories may themselves contain
                # a file named SKILL.md (e.g., in templates), which must not be discovered
                # as an independent skill.
                try:
                    rel_parts = skill_file.relative_to(path).parts
                except Exception:
                    rel_parts = skill_file.parts

                # rel_parts like: (<skill-name>, 'SKILL.md') or
                # (<group>, <skill-name>, 'SKILL.md') or
                # (<skill-name>, 'assets', ..., 'SKILL.md')
                if any(p in self._NON_SKILL_SUBDIRS for p in rel_parts[1:-1]):
                    continue

                metadata = self._load_metadata_only(skill_file)
                if metadata:
                    # Check for duplicate skill names
                    if metadata.name in self.metadata_index:
                        existing_path = self.metadata_index[metadata.name].skill_path
                        logger.warning(
                            "Duplicate skill name '%s'. Using %s, overriding %s",
                            metadata.name,
                            skill_file,
                            existing_path,
                        )
                    self.metadata_index[metadata.name] = metadata
                    discovered.append(metadata.name)
                    logger.debug(f"Discovered skill: {metadata.name} at {skill_file}")

        logger.info(f"Discovered {len(discovered)} skills")
        return discovered

    def _load_metadata_only(self, skill_path: Path) -> Optional[SkillMetadata]:
        """Load ONLY the frontmatter metadata from a SKILL.md file.

        Parses only the YAML frontmatter to extract name and description.
        Does not read the full markdown body to minimize I/O and memory.

        Args:
            skill_path: Path to the SKILL.md file.

        Returns:
            SkillMetadata if parsing succeeded, None otherwise.
        """
        try:
            with skill_path.open(encoding="utf-8") as handle:
                first_line = handle.readline()
                if not first_line or first_line.strip() != "---":
                    logger.warning(f"SKILL.md missing frontmatter: {skill_path}")
                    return None

                frontmatter_lines = []
                for line in handle:
                    if line.strip() == "---":
                        break
                    frontmatter_lines.append(line)
                else:
                    logger.warning(f"Invalid SKILL.md frontmatter format: {skill_path}")
                    return None

            try:
                frontmatter = yaml.safe_load("".join(frontmatter_lines))
            except yaml.YAMLError as e:
                logger.warning(f"Failed to parse YAML frontmatter: {skill_path}: {e}")
                return None

            if not frontmatter:
                logger.warning(f"Empty frontmatter in: {skill_path}")
                return None

            return SkillMetadata.from_frontmatter(frontmatter, skill_path)

        except Exception as e:
            logger.warning(f"Failed to load skill metadata from {skill_path}: {e}")
            return None

    def load_full_content(self, skill_name: str) -> Optional[SkillContent]:
        """Load full skill content on-demand.

        This method loads the complete skill content including instructions,
        environment modifications, and associated resources. The result is
        cached for subsequent invocations.

        Args:
            skill_name: The name of the skill to load.

        Returns:
            SkillContent if found, None otherwise.
        """
        # Check cache first
        if skill_name in self._content_cache:
            logger.debug(f"Using cached content for skill: {skill_name}")
            return self._content_cache[skill_name]

        # Get metadata
        metadata = self.metadata_index.get(skill_name)
        if not metadata:
            logger.warning(f"Skill not found in registry: {skill_name}")
            return None

        # Load full content
        try:
            skill_content = self._load_content_from_file(metadata.skill_path)
            if skill_content:
                # Cache for future use
                self._content_cache[skill_name] = skill_content
                logger.debug(f"Loaded full content for skill: {skill_name}")
            return skill_content

        except Exception as e:
            logger.error(f"Error loading skill content for {skill_name}: {e}")
            return None

    def _load_content_from_file(self, skill_path: Path) -> Optional[SkillContent]:
        """Load full skill content from a SKILL.md file.

        Parses the complete SKILL.md file including frontmatter and body,
        and loads any associated resource files.

        Args:
            skill_path: Path to the SKILL.md file.

        Returns:
            SkillContent if parsing succeeded, None otherwise.
        """
        try:
            content = skill_path.read_text(encoding="utf-8")

            # Parse frontmatter and body
            if not content.startswith("---"):
                return None

            parts = content.split("---", 2)
            if len(parts) < 3:
                return None

            frontmatter = yaml.safe_load(parts[1])
            body = parts[2].strip()

            if not frontmatter:
                return None

            # Load resources if specified
            resources = {}
            resource_paths = frontmatter.get("resources", [])
            if isinstance(resource_paths, str):
                resource_paths = [resource_paths]
            elif not isinstance(resource_paths, list):
                if resource_paths:
                    logger.warning(
                        "Invalid resources in %s; expected list or string",
                        skill_path,
                    )
                resource_paths = []

            if resource_paths:
                skill_dir = skill_path.parent
                skill_dir_resolved = skill_dir.resolve()
                for resource_path in resource_paths:
                    if not isinstance(resource_path, str):
                        logger.warning(
                            "Invalid resource path in %s; expected string",
                            skill_path,
                        )
                        continue
                    resource_rel = Path(resource_path)
                    if resource_rel.is_absolute():
                        logger.warning(
                            "Resource path must be relative to skill dir: %s",
                            resource_path,
                        )
                        continue
                    resource_file = (skill_dir / resource_rel).resolve()
                    try:
                        resource_file.relative_to(skill_dir_resolved)
                    except ValueError:
                        logger.warning(
                            "Resource path escapes skill dir: %s",
                            resource_path,
                        )
                        continue
                    if resource_file.exists():
                        # Support directory resources (e.g. "references/") by
                        # recursively loading text files under the directory.
                        if resource_file.is_dir():
                            loaded = self._load_resource_directory(
                                base_dir=skill_dir,
                                target_dir=resource_file,
                                max_files=50,
                                max_bytes=200_000,
                            )
                            resources.update(loaded)
                            continue

                        try:
                            resources[resource_path] = resource_file.read_text(
                                encoding="utf-8"
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to load resource {resource_file}: {e}"
                            )
                    else:
                        logger.warning(f"Resource file not found: {resource_file}")

            return SkillContent.from_frontmatter_and_body(
                frontmatter, body, skill_path, resources
            )

        except Exception as e:
            logger.error(f"Error loading skill content from {skill_path}: {e}")
            return None

    def _load_resource_directory(
        self,
        base_dir: Path,
        target_dir: Path,
        max_files: int,
        max_bytes: int,
    ) -> Dict[str, str]:
        """Recursively load text resources under a directory.

        Returned keys are POSIX-style relative paths from base_dir.
        """
        loaded: Dict[str, str] = {}
        total_bytes = 0
        file_count = 0

        # Prefer stable ordering for deterministic prompts.
        for p in sorted(target_dir.rglob("*")):
            if file_count >= max_files:
                break
            if not p.is_file():
                continue

            # Skip common binary extensions by default.
            if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip"}:
                continue

            try:
                rel = p.resolve().relative_to(base_dir.resolve())
            except Exception:
                continue

            key = rel.as_posix()
            try:
                text = p.read_text(encoding="utf-8")
            except Exception:
                continue

            total_bytes += len(text.encode("utf-8", errors="ignore"))
            if total_bytes > max_bytes:
                break

            loaded[key] = text
            file_count += 1

        return loaded

    def generate_system_prompt_section(self) -> str:
        """Generate the skill catalog section for the agent's system prompt.

        Creates a formatted markdown section listing all available skills
        with their descriptions. This is injected into the agent's system
        prompt to enable LLM-based skill selection.

        Returns:
            A formatted markdown string, or empty string if no skills.
        """
        if not self.metadata_index:
            return ""

        lines = [
            "## Available Skills",
            "",
            "Skills are loaded with progressive disclosure:",
            "- Metadata (name + description) is always available",
            "- Full SKILL.md content is loaded only when a skill is activated",
            "",
            "Do NOT invoke the Skill tool unless the user explicitly requests it.",
            "(This system uses a selector-based activator.)",
            "",
        ]

        for metadata in self.metadata_index.values():
            if getattr(metadata, "disable_model_invocation", False):
                continue
            lines.append(metadata.to_prompt_entry())

        return "\n".join(lines)

    def generate_user_help_section(self) -> str:
        """Generate a user-facing skill list.

        This is intended for answering questions like "what skills do you have?"
        without loading full SKILL.md content.
        """
        if not self.metadata_index:
            return ""

        lines: list[str] = [
            "Available skills (metadata only):",
            "",
        ]

        for metadata in sorted(self.metadata_index.values(), key=lambda m: m.name):
            flags: list[str] = []
            if getattr(metadata, "disable_model_invocation", False):
                flags.append("manual-only")
            if getattr(metadata, "user_invocable", True) is False:
                flags.append("not-user-invocable")
            suffix = f" ({', '.join(flags)})" if flags else ""
            lines.append(f"- {metadata.name}: {metadata.description}{suffix}")

            arg_hint = getattr(metadata, "argument_hint", None)
            if isinstance(arg_hint, str) and arg_hint.strip():
                lines.append(f"  args: {arg_hint.strip()}")

        lines.extend(
            [
                "",
                "Invoke a skill with: /<skill-name> [arguments]",
            ]
        )
        return "\n".join(lines)

    def list_skills(self) -> List[SkillMetadata]:
        """Return all registered skill metadata.

        Returns:
            A list of SkillMetadata for all discovered skills.
        """
        return list(self.metadata_index.values())

    def get_skill(self, skill_name: str) -> Optional[SkillMetadata]:
        """Get metadata for a specific skill.

        Args:
            skill_name: The name of the skill.

        Returns:
            SkillMetadata if found, None otherwise.
        """
        return self.metadata_index.get(skill_name)

    def has_skill(self, skill_name: str) -> bool:
        """Check if a skill is registered.

        Args:
            skill_name: The name of the skill.

        Returns:
            True if the skill exists in the registry.
        """
        return skill_name in self.metadata_index

    def clear_cache(self):
        """Clear the content cache.

        This forces subsequent invocations to reload content from disk.
        Useful for development when skill files may change.
        """
        self._content_cache.clear()
        logger.debug("Skill content cache cleared")

    def reload(self) -> List[str]:
        """Reload all skills from disk.

        Clears the cache and re-discovers all skills.

        Returns:
            A list of discovered skill names.
        """
        self.clear_cache()
        self.metadata_index.clear()
        return self.discover_all()

    def __len__(self) -> int:
        """Return the number of registered skills."""
        return len(self.metadata_index)

    def __contains__(self, skill_name: str) -> bool:
        """Check if a skill is registered."""
        return skill_name in self.metadata_index

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"SkillRegistry(skills={len(self.metadata_index)})"

    def iter_skills(self):
        """Iterate over all skill metadata."""
        return iter(self.metadata_index.values())
