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
import logging

from pydantic import Field

from ..base_tool import BaseTool
from .function_tool import FunctionTool

logger = logging.getLogger(__name__)


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
        """Clean up resources, including the thread pool.
        
        This method ensures proper shutdown of the thread pool to prevent
        resource leaks and dangling threads. It waits for all pending tasks
        to complete before shutting down.
        
        The cleanup process is idempotent - multiple calls are safe.
        """
        if self._thread_pool:
            try:
                logger.info(f"FunctionHub {self.name}: Starting thread pool cleanup...")
                # Wait for all pending tasks to complete
                self._thread_pool.shutdown(wait=True)
                logger.info(f"FunctionHub {self.name}: Thread pool shutdown completed")
            except Exception as e:
                logger.error(f"FunctionHub {self.name}: Error during thread pool cleanup: {e}")
                # Even if shutdown fails, ensure _thread_pool is set to None
                # to prevent further usage and potential memory leaks
            finally:
                self._thread_pool = None
    
    def is_thread_pool_active(self):
        """Check if the thread pool is currently active.
        
        Returns:
            bool: True if thread pool is initialized and active, False otherwise.
        """
        return self._thread_pool is not None
    
    def get_thread_pool_info(self):
        """Get information about the current thread pool.
        
        Returns:
            dict: Thread pool information including worker count and status,
                  or None if pool is not initialized.
        """
        if self._thread_pool is None:
            return None
        
        try:
            # ThreadPoolExecutor doesn't expose internal state directly,
            # but we can check if it's shut down
            return {
                "initialized": True,
                "workers": getattr(self._thread_pool, '_max_workers', 'unknown'),
                "shutdown": getattr(self._thread_pool, '_shutdown', False)
            }
        except Exception:
            return {"initialized": True, "status": "active"}
    
    async def __aenter__(self):
        """Async context manager entry point.
        
        Returns:
            FunctionHub: Self for use in async with statement
        """
        await self.init()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit point.
        
        Ensures cleanup is performed even if exceptions occur during usage.
        
        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred
        """
        await self.cleanup()
