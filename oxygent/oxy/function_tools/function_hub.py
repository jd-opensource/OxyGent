"""Function hub module for dynamic function registration and management.

This module provides the FunctionHub class, which serves as a central registry for
Python functions that can be dynamically converted into tools within the OxyGent system.
It supports both synchronous and asynchronous functions with automatic conversion.
"""

import asyncio
import functools

from pydantic import Field

from ..base_tool import BaseTool
from .function_tool import FunctionTool


class FunctionHub(BaseTool):
    """Central hub for registering and managing Python functions as tools.

    This class provides a decorator-based interface for converting regular
    Python functions into executable tools within the OxyGent system.

    Attributes:
        func_dict (dict): Dictionary mapping function names to their descriptions
            and execution functions. Format: {name: (description, async_func)}
    """

    func_dict: dict = Field(
        default_factory=dict, description="Registry of functions and their metadata"
    )

    async def init(self):
        """Initialize the hub by creating FunctionTool instances for all registered
        functions.

        This method converts all functions in func_dict into individual FunctionTool
        instances and registers them with the MAS (Multi-Agent System).
        """
        await super().init()
        params = self.model_dump(exclude={"func_dict", "name", "desc"})

        # Create FunctionTool instances for each registered function
        for tool_name, (tool_desc, tool_func) in self.func_dict.items():
            function_tool = FunctionTool(
                name=tool_name, desc=tool_desc, func_process=tool_func, **params
            )
            function_tool.set_mas(self.mas)
            self.mas.add_oxy(function_tool)

    def tool(self, description):
        """Decorator for registering functions as tools.

        This decorator automatically converts both synchronous and asynchronous
        functions into async functions and registers them in the function hub.
        Synchronous functions are wrapped to run asynchronously.

        Args:
            description (str): Human-readable description of the tool's functionality.

        Returns:
            Callable: Decorator function that registers and returns the async version
                of the decorated function.
        """

        def decorator(func):
            # Check if function is already asynchronous
            if asyncio.iscoroutinefunction(func):
                async_func = func
            else:
                # Wrap synchronous function to make it asynchronous
                @functools.wraps(func)
                async def async_func(*args, **kwargs):
                    # TODO: Use thread pool for blocking synchronous operations
                    return func(*args, **kwargs)

            # Register function in the hub's dictionary
            self.func_dict[func.__name__] = (description, async_func)
            return async_func  # Return the async version

        return decorator
