import logging
from typing import Optional

from oxygent.oxy import FunctionHub

logger = logging.getLogger(__name__)
python_tools = FunctionHub(name="python_tools")


@python_tools.tool(
    description="Runs Python code in the current environment."
)
def run_python_code(
    code: str,
    variable_to_return: Optional[str] = None,
    safe_globals: Optional[dict] = None,
    safe_locals: Optional[dict] = None
) -> str:
    try:
        logger.debug(f"Running code:\n\n{code}\n\n")
        if not safe_globals:
            safe_globals = globals()
        if not safe_locals:
            safe_locals = locals()

        exec(code, safe_globals, safe_locals)

        if variable_to_return:
            variable_value = safe_locals.get(variable_to_return)
            if variable_value is None:
                return f"Variable {variable_to_return} not found"
            logger.debug(
                f"Variable {variable_to_return} value: {variable_value}")
            return str(variable_value)
        else:
            return "successfully run python code"
    except Exception as e:
        logger.error(f"Error running python code: {e}")
        return f"Error running python code: {e}"
