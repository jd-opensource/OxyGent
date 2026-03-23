"""Skill registry for centralized skill discovery and management.

Provides SkillRegistry for scanning directories, parsing SKILL.md frontmatter
with PyYAML, and maintaining a priority-indexed registry of available skills.
Uses asyncio.to_thread to avoid blocking the event loop during file I/O.

Features:
    - Priority-based conflict resolution across multiple sources
    - O(1) base_name lookup via secondary index
    - Namespace auto-derivation from source name
    - Content validation during discovery
    - Hot-reload with file mtime tracking
    - Remote skill source fetching via URL
    - Skill hook/audit callback system
"""

import asyncio
import atexit
import inspect
import logging
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import yaml

from ..schemas.skill import SkillMetadata

logger = logging.getLogger(__name__)

# Subdirectories to skip during skill discovery
_SKIP_SUBDIRS = {"scripts", "references", "assets"}

# Track temp directories created for remote sources (for cleanup on exit)
_TEMP_DIRS: List[Path] = []


def _cleanup_temp_dirs():
    """Clean up all temporary directories created for remote skill sources."""
    for temp_dir in _TEMP_DIRS:
        try:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
                logger.debug(f"[SkillRegistry] Cleaned up temp dir: {temp_dir}")
        except Exception as e:
            logger.warning(f"[SkillRegistry] Failed to clean up {temp_dir}: {e}")


atexit.register(_cleanup_temp_dirs)

# Callback type for skill invocation hooks (sync or async)
SkillHookCallback = Callable[["SkillHookEvent"], Optional[str]]


@dataclass
class SkillHookEvent:
    """Event payload passed to skill hooks.

    Attributes:
        hook_type: "pre_invoke" or "post_invoke".
        skill_name: Name of the skill being invoked.
        args: Arguments passed to the skill.
        source: "tool" (LLM called SkillTool), "slash" (user slash command), or "auto" (auto-inject).
        metadata: The SkillMetadata object.
        result: For post_invoke hooks, the skill output content. None for pre_invoke.
    """

    hook_type: str
    skill_name: str
    args: str = ""
    source: str = ""
    metadata: Optional[SkillMetadata] = None
    result: Optional[str] = None


@dataclass
class SkillSource:
    """Represents a source location for skill discovery.

    Attributes:
        name: Source identifier (e.g., "project", "custom").
        paths: List of directories to scan for skills.
        priority: Higher values take precedence when skills overlap.
        namespace: Optional namespace to auto-assign to discovered skills.
    """

    name: str
    paths: List[Path] = field(default_factory=list)
    priority: int = 0
    namespace: Optional[str] = None


class SkillRegistry:
    """Centralized registry for skill discovery and lookup.

    Scans configured sources for SKILL.md files, parses their frontmatter
    using PyYAML, and maintains a name-indexed registry with priority-based
    conflict resolution.

    Features:
        - O(1) lookup by name and base_name via dual index
        - Namespace auto-derivation from source
        - Content validation during discovery
        - Hot-reload via refresh()
        - Skill invocation hooks (pre/post)
    """

    def __init__(self):
        self._sources: List[SkillSource] = []
        self._skills: Dict[str, SkillMetadata] = {}
        self._base_name_index: Dict[str, SkillMetadata] = {}
        self._hooks: List[SkillHookCallback] = []

    def add_source(self, source: SkillSource) -> None:
        """Register a skill source for discovery."""
        self._sources.append(source)

    def add_hook(self, callback: SkillHookCallback) -> None:
        """Register a skill invocation hook.

        Hooks are called in registration order. Pre-invoke hooks can return
        a string to block invocation (the string is returned as error message).
        Post-invoke hooks return values are ignored.
        """
        self._hooks.append(callback)

    def fire_hook(self, event: SkillHookEvent) -> Optional[str]:
        """Fire all registered hooks synchronously.

        For pre_invoke: returns the first non-None result (blocks invocation).
        For post_invoke: always returns None (fire-and-forget).

        Note: Use fire_hook_async() if any hook is a coroutine function.
        """
        for hook in self._hooks:
            try:
                if inspect.iscoroutinefunction(hook):
                    logger.warning(
                        f"[SkillRegistry] Async hook {hook} called from sync fire_hook, skipping. "
                        f"Use fire_hook_async() instead."
                    )
                    continue
                result = hook(event)
                if event.hook_type == "pre_invoke" and result is not None:
                    return result
            except Exception as e:
                logger.warning(f"[SkillRegistry] Hook raised exception: {e}")
        return None

    async def fire_hook_async(self, event: SkillHookEvent) -> Optional[str]:
        """Fire all registered hooks, supporting both sync and async callbacks.

        For pre_invoke: returns the first non-None result (blocks invocation).
        For post_invoke: always returns None (fire-and-forget).
        """
        for hook in self._hooks:
            try:
                if inspect.iscoroutinefunction(hook):
                    result = await hook(event)
                else:
                    result = hook(event)
                if event.hook_type == "pre_invoke" and result is not None:
                    return result
            except Exception as e:
                logger.warning(f"[SkillRegistry] Hook raised exception: {e}")
        return None

    async def discover(self) -> int:
        """Scan all sources and load skill metadata (non-blocking).

        Runs file I/O in a thread pool to avoid blocking the event loop.

        Returns:
            Number of unique skills discovered.
        """
        return await asyncio.to_thread(self._discover_sync)

    async def refresh(self) -> int:
        """Re-scan all sources, picking up new/changed/deleted skills.

        Clears existing registry and re-discovers. Skill content caches
        are automatically refreshed via mtime tracking in SkillMetadata.

        Returns:
            Number of unique skills after refresh.
        """
        return await asyncio.to_thread(self._refresh_sync)

    def _refresh_sync(self) -> int:
        """Synchronous refresh implementation."""
        self._skills.clear()
        self._base_name_index.clear()
        return self._discover_sync()

    def _discover_sync(self) -> int:
        """Synchronous discovery implementation.

        Sources are scanned in priority order (lowest first, so higher
        priority sources overwrite lower ones).
        """
        sorted_sources = sorted(self._sources, key=lambda s: s.priority)

        for source in sorted_sources:
            for scan_path in source.paths:
                scan_path = Path(scan_path).expanduser()
                if not scan_path.is_absolute():
                    scan_path = Path.cwd() / scan_path

                if not scan_path.exists():
                    logger.warning(f"[SkillRegistry] Source path does not exist: {scan_path}")
                    continue

                # Check if this is a direct skill folder
                if (scan_path / "SKILL.md").exists():
                    self._process_skill_file(scan_path / "SKILL.md", source)
                else:
                    # Recursive scan
                    for skill_file in scan_path.rglob("SKILL.md"):
                        try:
                            rel_parts = skill_file.relative_to(scan_path).parts
                            if any(p in _SKIP_SUBDIRS for p in rel_parts[:-1]):
                                continue
                        except ValueError:
                            pass
                        self._process_skill_file(skill_file, source)

        logger.info(f"[SkillRegistry] Discovery complete: {len(self._skills)} skills found")
        return len(self._skills)

    def _process_skill_file(self, skill_file: Path, source: SkillSource) -> None:
        """Parse and register a single SKILL.md file."""
        metadata = self._parse_skill_file(skill_file)
        if metadata is None:
            return

        metadata.source_name = source.name

        # Auto-derive namespace from source if not set in frontmatter
        if metadata.namespace is None and source.namespace:
            metadata.namespace = source.namespace

        # Validate content body is not empty
        try:
            body = metadata.load_content()
            if not body.strip():
                logger.warning(
                    f"[SkillRegistry] Skill '{metadata.name}' has empty body in {skill_file}. "
                    f"Skill will be registered but may not provide useful instructions."
                )
        except Exception as e:
            logger.warning(
                f"[SkillRegistry] Failed to validate content for skill '{metadata.name}': {e}"
            )

        if metadata.name in self._skills:
            existing = self._skills[metadata.name]
            logger.warning(
                f"[SkillRegistry] Skill '{metadata.name}' from source '{source.name}' "
                f"overrides existing from source '{existing.source_name}'"
            )

        self._skills[metadata.name] = metadata

        # Maintain base_name index for O(1) lookup
        bname = metadata.base_name
        if bname != metadata.name:
            if bname in self._base_name_index and self._base_name_index[bname].name != metadata.name:
                logger.debug(
                    f"[SkillRegistry] base_name '{bname}' collision: "
                    f"'{metadata.name}' overrides '{self._base_name_index[bname].name}'"
                )
            self._base_name_index[bname] = metadata

        logger.debug(f"[SkillRegistry] Loaded skill '{metadata.name}' from {skill_file}")

    def get(self, name: str) -> Optional[SkillMetadata]:
        """Look up a skill by name.

        Resolution order:
            1. Exact match on full name (O(1))
            2. Fallback match on base_name via index (O(1))
        """
        if name in self._skills:
            return self._skills[name]

        if name in self._base_name_index:
            return self._base_name_index[name]

        return None

    def list_all(self) -> List[SkillMetadata]:
        """Return all registered skills, sorted by name."""
        return sorted(self._skills.values(), key=lambda s: s.name)

    def list_invocable(self) -> List[SkillMetadata]:
        """Return skills the model can invoke via the skill tool.

        Excludes skills with disable_model_invocation=True (those are auto-injected).
        """
        return sorted(
            [s for s in self._skills.values() if not s.disable_model_invocation],
            key=lambda s: s.name,
        )

    def list_user_invocable(self) -> List[SkillMetadata]:
        """Return skills invocable via user slash commands."""
        return sorted(
            [s for s in self._skills.values() if s.user_invocable],
            key=lambda s: s.name,
        )

    def list_auto_inject(self) -> List[SkillMetadata]:
        """Return skills that should be auto-injected into context.

        These are skills with disable_model_invocation=True — their content
        is injected directly without requiring the model to call the skill tool.
        """
        return sorted(
            [s for s in self._skills.values() if s.disable_model_invocation],
            key=lambda s: s.name,
        )

    def get_required_tools(self) -> List[str]:
        """Collect all required_tools from all registered skills (deduplicated)."""
        tools = set()
        for skill in self._skills.values():
            tools.update(skill.required_tools)
        return sorted(tools)

    def get_skill_references(self, skill_name: str) -> List[str]:
        """Get skills that reference the given skill in their content.

        Used for skill chaining — checks if any skill body mentions another
        skill by name (e.g., "invoke the weather skill first").
        """
        refs = []
        target = self.get(skill_name)
        if target is None:
            return refs

        for skill in self._skills.values():
            if skill.name == target.name:
                continue
            try:
                body = skill.load_content()
                if target.name in body or target.base_name in body:
                    refs.append(skill.name)
            except Exception:
                pass
        return refs

    @staticmethod
    def _parse_skill_file(path: Path) -> Optional[SkillMetadata]:
        """Parse a single SKILL.md file using PyYAML.

        Uses line-by-line frontmatter extraction to avoid matching
        '---' horizontal rules in the body.
        """
        try:
            lines = path.read_text(encoding="utf-8").splitlines(True)

            if not lines or lines[0].strip() != "---":
                logger.warning(f"SKILL.md missing frontmatter: {path}")
                return None

            # Find closing --- line by line
            end_line = None
            for i, line in enumerate(lines[1:], 1):
                if line.strip() == "---":
                    end_line = i
                    break

            if end_line is None:
                logger.warning(f"Invalid SKILL.md frontmatter format: {path}")
                return None

            frontmatter_text = "".join(lines[1:end_line]).strip()
            if not frontmatter_text:
                logger.warning(f"Empty frontmatter in: {path}")
                return None

            frontmatter = yaml.safe_load(frontmatter_text)
            if not isinstance(frontmatter, dict):
                logger.warning(f"Invalid frontmatter structure in: {path}")
                return None

            return SkillMetadata.from_frontmatter(frontmatter, path)

        except Exception as e:
            logger.warning(f"Failed to load skill metadata from {path}: {e}")
            return None

    @staticmethod
    def make_project_source(root: Path) -> SkillSource:
        """Create a project-level skill source (.oxygent/skills/, priority=100)."""
        return SkillSource(
            name="project",
            paths=[root / ".oxygent" / "skills"],
            priority=100,
        )

    @staticmethod
    def make_path_source(
        paths: List[str],
        name: str = "custom",
        priority: int = 80,
        namespace: Optional[str] = None,
    ) -> SkillSource:
        """Create a skill source from explicit paths.

        If namespace is not provided and name is not "custom", the source
        name is used as the default namespace for discovered skills.
        """
        auto_ns = namespace if namespace is not None else (name if name != "custom" else None)
        return SkillSource(
            name=name,
            paths=[Path(p) for p in paths],
            priority=priority,
            namespace=auto_ns,
        )

    @staticmethod
    def make_remote_source(
        url: str,
        name: str = "remote",
        priority: int = 60,
        namespace: Optional[str] = None,
        cache_dir: Optional[Path] = None,
    ) -> SkillSource:
        """Create a remote skill source by fetching a zip archive from URL.

        Downloads the archive to a local cache directory and returns a
        SkillSource pointing to the extracted path. The archive should
        contain SKILL.md files in subdirectories.

        Args:
            url: URL to a .zip archive containing skill directories.
            name: Source identifier.
            priority: Priority for conflict resolution.
            namespace: Optional namespace for discovered skills.
            cache_dir: Where to extract. Defaults to a temp directory.

        Returns:
            SkillSource pointing to the extracted directory.
        """
        if cache_dir is None:
            cache_dir = Path(tempfile.mkdtemp(prefix="oxygent_skills_"))
            _TEMP_DIRS.append(cache_dir)  # Register for cleanup on exit

        extract_path = cache_dir / name
        extract_path.mkdir(parents=True, exist_ok=True)

        try:
            import urllib.request
            zip_path = cache_dir / f"{name}.zip"
            urllib.request.urlretrieve(url, str(zip_path))

            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(str(extract_path))

            zip_path.unlink()
            logger.info(f"[SkillRegistry] Remote source '{name}' fetched from {url}")
        except Exception as e:
            logger.error(f"[SkillRegistry] Failed to fetch remote source '{name}' from {url}: {e}")
            return SkillSource(name=name, paths=[], priority=priority, namespace=namespace)

        auto_ns = namespace if namespace is not None else name
        return SkillSource(
            name=name,
            paths=[extract_path],
            priority=priority,
            namespace=auto_ns,
        )
