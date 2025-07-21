"""Function tool module for wrapping Python functions as executable tools.

This module provides the FunctionTool class, which wraps Python functions to make them
executable within the OxyGent system. It automatically extracts input schemas from
function signatures and handles execution with proper error handling.
"""

from inspect import Parameter, signature
from typing import Callable, Optional

import logging
from pydantic import Field
from pydantic.fields import FieldInfo

from ...schemas import OxyRequest, OxyResponse, OxyState
from ..base_tool import BaseTool


logger = logging.getLogger(__name__)


class FunctionTool(BaseTool):
    """Tool that wraps Python functions for execution within the OxyGent system.

    This class provides a bridge between regular Python functions and the
    OxyGent tool system.

    Attributes:
        is_permission_required (bool): Whether permission is required for execution.
            Defaults to True for security.
        func_execute (Optional[Callable]): The Python function to execute.
            Should be an async function or will be wrapped as async.
    """

    is_permission_required: bool = Field(True, description="")
    func_process: Optional[Callable] = Field(None, exclude=True, description="")
    needs_oxy_request: bool = Field(
        False, description="Whether this tool needs oxy_request parameter"
    )

    def __init__(self, **kwargs):
        """Initialize the function tool and extract input schema from function
        signature."""
        super().__init__(**kwargs)
        self.input_schema = self._extract_input_schema(self.func_process)
        self._set_desc_for_llm()

    def _extract_input_schema(self, func):
        """Extract input schema from function signature.

        Args:
            func (Callable): The function to analyze.

        Returns:
            dict: Input schema with 'properties' and 'required' fields describing
                the function's parameters.
        """
        sig = signature(func)
        schema = {"properties": {}, "required": []}
        needs_oxy_request = False

        for name, param in sig.parameters.items():
            param_type = param.annotation
            if param_type != Parameter.empty:
                type_name = getattr(param_type, "__name__", str(param_type))
                if type_name == "OxyRequest" or (
                    hasattr(param_type, "__name__")
                    and param_type.__name__ == "OxyRequest"
                ):
                    needs_oxy_request = True
                    continue
            # Get the type of parameter
            param_type = param.annotation
            # Handle the case where the type is not specified
            if param_type is Parameter.empty:
                type_name = None
            else:
                type_name = getattr(param_type, "__name__", str(param_type))
            if isinstance(param.default, FieldInfo):
                # Handle Pydantic Field annotations
                desc = param.default.description or ""
                schema["properties"][name] = {"description": desc, "type": type_name}
                if param.default.is_required():
                    schema["required"].append(name)
            elif param.default is Parameter.empty:
                schema["properties"][name] = {"description": "", "type": type_name}
                schema["required"].append(name)

        self.needs_oxy_request = needs_oxy_request

        return schema

    async def _execute(self, oxy_request: OxyRequest) -> OxyResponse:
        """Execute the wrapped function with provided arguments."""
        try:
            func_kwargs = {}

            sig = signature(self.func_process)

            for param_name, param in sig.parameters.items():
                if param.annotation != Parameter.empty:
                    param_type = param.annotation
                    type_name = getattr(param_type, "__name__", str(param_type))

                    if type_name == "OxyRequest" or (
                        hasattr(param_type, "__name__")
                        and param_type.__name__ == "OxyRequest"
                    ):
                        func_kwargs[param_name] = oxy_request
                    elif param_name in oxy_request.arguments:
                        func_kwargs[param_name] = oxy_request.arguments[param_name]
                elif param_name in oxy_request.arguments:
                    func_kwargs[param_name] = oxy_request.arguments[param_name]

            result = await self.func_process(**func_kwargs)
            return OxyResponse(state=OxyState.COMPLETED, output=result)
        except Exception as e:
            import traceback

            error_msg = traceback.format_exc()
            logger.error(f"Error in function tool {self.name}: {error_msg}")
            return OxyResponse(state=OxyState.FAILED, output=str(e))
