"""ReadFileTool: lets the LLM read files on demand.

Enables the Claude Code pattern where SKILL.md content references companion
files (e.g. "see ./FORMS.md") and the LLM reads them using this tool.

Usage by LLM:
    ```json
    {
        "tool_name": "read_file",
        "arguments": {
            "file_path": "/path/to/FORMS.md"
        }
    }
    ```
"""

import logging
import os
from typing import List

from pydantic import Field, PrivateAttr

from ...schemas import OxyRequest, OxyResponse, OxyState
from ..base_tool import BaseTool

logger = logging.getLogger(__name__)

# Default max lines to return when no limit is specified
_DEFAULT_LIMIT = 2000


class ReadFileTool(BaseTool):
    """Tool that lets the LLM read file contents on demand.

    Supports reading entire files or specific line ranges via offset/limit.
    Returns content with line numbers for easy reference.
    """

    _skill_context_dirs: List[str] = PrivateAttr(default_factory=list)

    name: str = Field(default="read_file")
    description: str = Field(
        default=(
            "Read the contents of a file. Returns file content with line numbers. "
            "Use offset and limit to read specific sections of large files."
        )
    )
    input_schema: dict = Field(
        default={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to read. Supports ~ expansion.",
                },
                "offset": {
                    "type": "integer",
                    "description": "Starting line number (1-indexed). Defaults to 1.",
                    "default": 1,
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of lines to read. Defaults to 2000.",
                    "default": _DEFAULT_LIMIT,
                },
            },
            "required": ["file_path"],
        }
    )

    def set_skill_context_dir(self, dir_path: str) -> None:
        """Add a skill context directory for relative path resolution.

        Supports parallel skill invocations: each skill appends its dir
        so that subsequent read_file calls can resolve against any of them.
        Deduplicates to avoid redundant lookups.
        """
        if dir_path not in self._skill_context_dirs:
            self._skill_context_dirs.append(dir_path)

    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        arguments = oxy_request.arguments
        file_path = arguments.get("file_path", "")
        offset = arguments.get("offset", 1)
        limit = arguments.get("limit", _DEFAULT_LIMIT)

        if not file_path:
            return OxyResponse(
                state=OxyState.FAILED,
                output="Missing required argument: file_path",
            )

        file_path = os.path.expanduser(file_path)

        # Fallback: resolve relative paths against skill context directories
        if (
            not os.path.isabs(file_path)
            and not os.path.exists(file_path)
            and self._skill_context_dirs
        ):
            for ctx_dir in self._skill_context_dirs:
                resolved = os.path.normpath(os.path.join(ctx_dir, file_path))
                if os.path.exists(resolved):
                    file_path = resolved
                    break

        if not os.path.exists(file_path):
            return OxyResponse(
                state=OxyState.FAILED,
                output=f"File not found: {file_path}",
            )

        if not os.path.isfile(file_path):
            return OxyResponse(
                state=OxyState.FAILED,
                output=f"Not a file: {file_path}",
            )

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            return OxyResponse(
                state=OxyState.FAILED,
                output=f"Cannot read file (not UTF-8 text): {file_path}",
            )
        except Exception as e:
            logger.error(f"[ReadFileTool] Error reading {file_path}: {e}")
            return OxyResponse(
                state=OxyState.FAILED,
                output=f"Error reading file: {e}",
            )

        total_lines = len(lines)

        # Clamp offset
        if offset < 1:
            offset = 1
        if offset > total_lines:
            return OxyResponse(
                state=OxyState.COMPLETED,
                output=f"File has {total_lines} lines, offset {offset} is beyond end of file.",
            )

        # Clamp limit
        if limit < 1:
            limit = _DEFAULT_LIMIT

        start_idx = offset - 1
        end_idx = min(start_idx + limit, total_lines)

        content = "".join(
            f"{i + 1}\t{lines[i]}" for i in range(start_idx, end_idx)
        )

        truncated = ""
        if end_idx < total_lines:
            truncated = f"\n... ({total_lines - end_idx} more lines)"

        return OxyResponse(
            state=OxyState.COMPLETED,
            output=f"{file_path} ({total_lines} lines)\n{content}{truncated}",
        )
