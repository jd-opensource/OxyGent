"""Function hub module for dynamic function registration and management.

This module provides the FunctionHub class, which serves as a central registry for
Python functions that can be dynamically converted into tools within the OxyGent system.
It supports both synchronous and asynchronous functions with automatic conversion.
"""

import asyncio
import functools
import concurrent.futures
import os
import threading

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

    def __init__(self, **data):
        """Initialize the FunctionHub with thread pool support."""
        super().__init__(**data)
        self._thread_pool = None  # Private attribute for thread pool
        self._thread_pool_lock = threading.Lock()  # Lock for thread pool initialization

    @property
    def thread_pool(self):
        """Lazy initialization of thread pool with thread safety."""
        if self._thread_pool is None:
            with self._thread_pool_lock:
                if self._thread_pool is None:  # Double-checked locking pattern
                    cpu_count = os.cpu_count() or 1
                    max_workers = min(max(cpu_count * 3, 4), 32)
                    self._thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        return self._thread_pool

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
                # Wrap synchronous function to make it asynchronous using thread pool
                @functools.wraps(func)
                async def async_func(*args, **kwargs):
                    # Use thread pool for blocking synchronous operations
                    loop = asyncio.get_event_loop()
                    if kwargs:
                        # 如果有kwargs，使用functools.partial包装函数
                        partial_func = functools.partial(func, **kwargs)
                        return await loop.run_in_executor(
                            self.thread_pool,
                            partial_func,
                            *args
                        )
                    else:
                        # 如果没有kwargs，直接调用
                        return await loop.run_in_executor(
                            self.thread_pool,
                            func,
                            *args
                        )

            # Register function in the hub's dictionary
            self.func_dict[func.__name__] = (description, async_func)
            return async_func  # Return the async version

        return decorator

    async def cleanup(self):
        """Clean up resources, including the thread pool."""
        if self._thread_pool:
            self._thread_pool.shutdown(wait=True)
            self._thread_pool = None
