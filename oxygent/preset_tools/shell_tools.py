import logging
import subprocess
from typing import List, Optional

from oxygent.oxy import FunctionHub
from pydantic import Field

logger = logging.getLogger(__name__)
shell_tools = FunctionHub(name="shell_tools")


@shell_tools.tool(
    description="Run a shell command and return the output or error."
)
def run_shell_command(
    args: List[str] = Field(description="command arguments"),
    tail: int = 10,
    base_dir: Optional[str] = None
) -> str:
    """Runs a shell command and returns the output or error."""

    try:
        logger.info(f"Running shell command: {args}")
        result = subprocess.run(
            args,
            capture_output=True,
            encoding="utf8",
            shell=True,
            text=True,
            cwd=base_dir
        )
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        return "\n".join(result.stdout.split("\n")[-tail:])
    except Exception as e:
        logger.warning(f"Failed to run shell command: {e}")
        return f"Error: {e}"
