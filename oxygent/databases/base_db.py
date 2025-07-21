"""base_db.py Base Database Class Module.

This file defines the base class for database services, providing common functionality
such as retry mechanisms and error handling for database operations.
"""

import asyncio
import functools


class BaseDB:
    """Base class for database services providing common retry and error handling
    functionality.

    This class automatically applies retry decorators to all public methods of its
    subclasses, ensuring robust database operations with configurable retry policies.
    """

    def try_decorator(max_retries=1, delay_between_retries=0.1):
        """Decorator factory that creates a retry mechanism for database operations.

        This decorator will automatically retry failed operations up to a specified number
        of times with configurable delays between attempts.

        Args:
            max_retries: Maximum number of retry attempts (default: 1)
            delay_between_retries: Delay in seconds between retry attempts (default: 0.1)

        Returns:
            Callable: A decorator function that can be applied to async methods
        """

        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                """Wrapper function that implements the retry logic.

                Args:
                    *args: Positional arguments passed to the original function
                    **kwargs: Keyword arguments passed to the original function

                Returns:
                    Callable: Result from the original function, or None if all retries failed
                """
                retries = 0
                while retries < max_retries:
                    try:
                        return await func(
                            *args, **kwargs
                        )  # Attempt to execute the original function
                    except Exception:
                        retries += 1
                        if retries < max_retries:
                            await asyncio.sleep(
                                delay_between_retries
                            )  # Retry until reached max retries
                return None

            return wrapper

        return decorator

    def __init_subclass__(cls, **kwargs):
        """Class method called when a class is subclassed from BaseDB.

        This method automatically applies the retry decorator to all public methods
        of the subclass, excluding magic methods (those starting with underscore).

        Args:
            **kwargs: Additional keyword arguments passed to the parent class
        """
        super().__init_subclass__(**kwargs)
        for (
            name,
            method,
        ) in cls.__dict__.items():  # Iterate over all attributes of the subclass
            # Apply decorator only to callable methods that are not magic methods
            if callable(method) and not name.startswith(
                "_"
            ):  # Applt the try_decorator with default parameters
                setattr(cls, name, cls.try_decorator()(method))
