"""File operation tools for OxyGent agents."""

import os
import shutil
from typing import List, Optional

# import pandas as pd
from pydantic import Field

from oxygent.oxy import FunctionHub

file_tools = FunctionHub(name="file_tools")


allowed_dir = os.getcwd()


@file_tools.tool(
    description="Create a new file or completely overwrite an existing file with new content. Use with caution as it will overwrite existing files without warning. Handles text content with proper encoding. Only works within allowed directories."
)
def write_file(
    path: str = Field(description="Path to the file to write"),
    content: str = Field(description="Content to write to the file"),
) -> str:
    if not os.path.abspath(path).startswith(allowed_dir):
        raise ValueError("Path is outside of the current working directory")
    with open(path, "w", encoding="utf-8") as file:
        file.write(content)
    return "Successfully wrote to " + path


@file_tools.tool(
    description="Read the content of a file. Returns an error message if the file does not exist. For uploaded files, use the complete file path including directory structure."
)
def read_file(path: str = Field(description="Path to the file to read")) -> str:
    if not os.path.abspath(path).startswith(allowed_dir):
        raise ValueError("Path is outside of the current working directory")
    if not os.path.exists(path):
        return f"Error: The file at {path} does not exist."
    with open(path, "r", encoding="utf-8") as file:
        return file.read()


@file_tools.tool(
    description="Delete a file or directory. Returns a success message if the item is deleted, or an error if the item does not exist. For directories, this will delete all contents recursively."
)
def delete_file(
    path: str = Field(description="Path to the file or directory to delete"),
) -> str:
    if not os.path.abspath(path).startswith(allowed_dir):
        raise ValueError("Path is outside of the current working directory")
    if not os.path.exists(path):
        return f"Error: The file or directory at {path} does not exist."

    try:
        if os.path.isfile(path):
            os.remove(path)
            return f"Successfully deleted the file at {path}"
        elif os.path.isdir(path):
            shutil.rmtree(path)
            return f"Successfully deleted the directory at {path} and all its contents"
    except PermissionError:
        return f"Error: Permission denied when trying to delete {path}"
    except Exception as e:
        return f"Error: Failed to delete {path}. Reason: {str(e)}"


@file_tools.tool(
    description="View the content of a text file with optional line range support. "
    "Returns file content with line numbers. Useful for viewing specific sections of large files."
)
def view_text_file(
    file_path: str,
    ranges: Optional[List[int]] = None,
) -> str:
    """View the file content in the specified range with line numbers.

    If `ranges` is not provided, the entire file will be returned.

    Args:
        file_path: The target file path. Supports ~ expansion for home directory.
        ranges: The range of lines to be viewed (e.g. [1, 100] for lines 1 to 100),
                inclusive. If not provided, the entire file will be returned.
                To view the last 100 lines, use [-100, -1].

    Returns:
        The file content with line numbers, or an error message.
    """
    if not os.path.abspath(file_path).startswith(allowed_dir):
        raise ValueError("Path is outside of the current working directory")
    file_path = os.path.expanduser(file_path)

    if not os.path.exists(file_path):
        return f"Error: The file {file_path} does not exist."

    if not os.path.isfile(file_path):
        return f"Error: The path {file_path} is not a file."

    try:
        content = _read_file_with_range(file_path, ranges)
    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error: Failed to read file: {str(e)}"

    if ranges is None:
        return f"The content of {file_path}:\n```\n{content}\n```"
    else:
        return f"The content of {file_path} in lines {ranges[0]}-{ranges[1]}:\n```\n{content}\n```"


def _read_file_with_range(file_path: str, ranges: Optional[List[int]] = None) -> str:
    """Read file content with optional line range.

    Args:
        file_path: Path to the file.
        ranges: Optional list of [start, end] line numbers (1-indexed, inclusive).
                Negative indices count from the end (-1 is the last line).

    Returns:
        File content with line numbers.

    Raises:
        ValueError: If ranges are invalid.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    total_lines = len(lines)

    if ranges is None:
        # Return all lines with line numbers
        return "".join(f"{i + 1} | {line}" for i, line in enumerate(lines))

    if len(ranges) != 2:
        raise ValueError("ranges must be a list of two integers [start, end]")

    start, end = ranges

    # Handle negative indices
    if start < 0:
        start = total_lines + start + 1
    if end < 0:
        end = total_lines + end + 1

    # Validate range
    if start < 1:
        start = 1
    if end > total_lines:
        end = total_lines
    if start > end:
        raise ValueError(f"Invalid range: start ({start}) > end ({end})")

    # Convert to 0-indexed
    start_idx = start - 1
    end_idx = end

    # Return lines with line numbers
    return "".join(f"{i + 1} | {lines[i]}" for i in range(start_idx, end_idx))
