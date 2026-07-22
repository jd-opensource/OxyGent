"""Python code execution tools for OxyGent agents."""

import logging
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from typing import Optional

from oxygent.oxy import FunctionHub

logger = logging.getLogger(__name__)
python_tools = FunctionHub(name="python_tools")


@python_tools.tool(description="Runs Python code in the current environment.")
def run_python_code(
    code: str,
    variable_to_return: Optional[str] = None,
    safe_globals: Optional[dict] = None,
    safe_locals: Optional[dict] = None,
) -> str:
    try:
        logger.debug(f"Running code:\n\n{code}\n\n")
        if safe_globals is None:
            safe_globals = globals()
        if safe_locals is None:
            safe_locals = {}

        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exec(code, safe_globals, safe_locals)

        result_parts = []
        stdout_output = stdout.getvalue().rstrip()
        stderr_output = stderr.getvalue().rstrip()
        if stdout_output:
            result_parts.append(stdout_output)
        if stderr_output:
            result_parts.append(f"[stderr] {stderr_output}")

        if variable_to_return:
            variable_value = safe_locals.get(variable_to_return)
            if variable_value is None:
                result_parts.append(f"Variable {variable_to_return} not found")
                return "\n".join(result_parts)
            logger.debug(f"Variable {variable_to_return} value: {variable_value}")
            result_parts.append(str(variable_value))

        return "\n".join(result_parts) or "successfully run python code"
    except Exception as e:
        logger.error(
            f"Error in run_python_code (variable_to_return={variable_to_return!r}): {e}",
            exc_info=True,
        )
        return f"Error running python code: {e}"
