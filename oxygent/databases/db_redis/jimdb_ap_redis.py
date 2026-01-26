"""jimdb_ap_redis.py JimDB Redis Implementation Module.

This file implements a Redis client specifically designed for JimDB (JD's internal
database), providing robust connection handling, automatic retries, and enhanced list
operations with size limits and expiration management.
"""

import asyncio
import json
import logging
import traceback
from functools import wraps
from typing import Union

from aioredis import Redis
from aioredis.exceptions import ConnectionError, TimeoutError

from ...config import Config

logger = logging.getLogger(__name__)


def retry_decorator(func):
    """Decorator that provides automatic retry logic for Redis operations.

    This decorator handles connection errors by automatically reconnecting
    and retrying the operation once. Other exceptions are logged and return None.

    Args:
        func: The Redis operation function to wrap

    Returns:
        Callable: Wrapped function with retry capability
    """

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        try:
            return await func(self, *args, **kwargs)
        except (ConnectionError, ConnectionResetError, TimeoutError) as e:
            logger.error(f"Reconnect for Connection Error in {func.__name__}: {str(e)}")
            # Close current connection and retry
            await self.close()
            self.redis_pool = self._get_redis_connection()
            return await func(self, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            return None

    return wrapper


class JimdbApRedis:
    """JimDB Redis client implementation with enhanced features.

    This class provides a Redis client specifically tailored for JimDB usage, including
    automatic connection management, retry logic, and enhanced list operations with
    built-in size limits and expiration handling.
    """

    def __init__(self, host, port, password, db=0):
        """Initialize the JimDB Redis client.

        Args:
            host: Redis server hostname or IP address
            port: Redis server port number
            password: Authentication password for Redis server
        """
        self.host = host
        self.port = port
        self.password = password
        self.db = db
        self.redis_pool = None
        self.default_expire_time = Config.get_redis_expire_time()
        self.default_list_max_size = Config.get_redis_max_size()
        self.default_list_max_length = Config.get_redis_max_length() * 1024

        # Initialize Redis connection pool
        try:
            self.redis_pool = self._get_redis_connection()
        except Exception as e:
            logger.error(f"Error while creating Redis pool: {str(e)}")
            logger.error(traceback.format_exc())

    def _get_redis_connection(self):
        """Create and configure a Redis connection pool.

        Returns:
            Redis: Redis connection pool configured for JimDB usage
        """
        return Redis.from_url(
            f"redis://{self.host}:{self.port}/{self.db}",
            password=self.password,
            max_connections=5,
            # decode_responses=True,  # Automatic decoding (disabled)
            health_check_interval=30,
        )

    async def close(self):
        """Close the Redis connection pool and clean up resources.

        This method properly closes all connections and disconnects the pool to prevent
        resource leaks.
        """
        if self.redis_pool is not None:
            await self.redis_pool.close()
            await self.redis_pool.connection_pool.disconnect()

    @retry_decorator
    async def set(self, key, value, ex=86400):  # Key-value expiration time is 1 day
        """Set a key-value pair with expiration time.

        NOTE: all of the following functions would call self.execute_command() to execute the command,
        thus you shall check this function to get the details of the return value

        Args:
            key: The key to set
            value: The value to store
            ex: Expiration time in seconds (default: 86400 = 24 hours)

        Returns:
            Optional[bool]: The response of the set operation
        """
        return await self.redis_pool.set(key, value, ex=ex)

    @retry_decorator
    async def get(self, key):
        """Get the value associated with a key.

        Args:
            key: The key to retrieve

        Returns:
            Optional[bytes]: The response of the get operation
        """
        return await self.redis_pool.get(key)

    @retry_decorator
    async def exists(self, key):
        """Check if a key exists in the database.

        Args:
            key: The key to check

        Returns:
            Optional[int]: The response of the exists operation
        """
        return await self.redis_pool.exists(key)

    @retry_decorator
    async def mset(self, items, ex=None):
        """
        Multiple set: Set multiple key-value pairs in a single operation.

        Args:
            items: Dictionary containing key-value pairs to set
            ex: Optional expiration time in seconds for all keys

        Returns:
            Optional[bool]: The response of the multiple-set operation
        """
        return await self.redis_pool.mset(items, ex=ex)

    @retry_decorator
    async def mget(self, keys):
        """
        Multiple get: Get multiple values for the given keys in a single operation.

        Args:
            keys: List of keys to retrieve

        Returns:
            Optional[List[Optional[bytes]]]: The response of the multiple-get operation
        """
        return await self.redis_pool.mget(keys)

    @retry_decorator
    async def delete(self, key: str):
        """Delete a key from the database.

        Args:
            key: The key to delete

        Returns:
            Optional[int]: The response of the delete operation
        """
        return await self.redis_pool.delete(key)

    @retry_decorator
    async def expire(self, key: str, ex: int):
        """Set an expiration time for a key.

        Args:
            key: The key to set expiration for
            ex: Expiration time in seconds

        Returns:
            Optional[bool]: The response of the expire operation
        """
        if ex is not None:
            return await self.redis_pool.expire(key, ex)
        return True

    # @retry_decorator
    async def lpush(
        self,
        key: str,
        *values: Union[bytes, int, str, float],
        ex: int = None,
        max_size: int = None,
        max_length: int = None,
    ):
        """Push values to the left (head) of a list with size and length limits.

        This enhanced lpush operation includes automatic list trimming to maintain
        size limits, value length truncation, and expiration setting. It uses
        Redis pipeline for atomic operations.

        Args:
            key: The list key
            *values: Values to push (supports str, bytes, int, float, dict)
            ex: Expiration time in seconds (default: 1 day)
            max_size: Maximum number of elements to keep in list (default: 10)
            max_length: Maximum length for string values (default: 20MB)

        Returns:
            int: The length of the list after the push operation

        Raises:
            ValueError: If an unsupported value type is provided
        """
        # Apply defaults if not specified
        if ex is None:
            ex = self.default_expire_time
        if max_size is None:
            max_size = self.default_list_max_size
        if max_length is None:
            max_length = self.default_list_max_length
        # Default value lehgth: 3
        # Process and validate input values
        new_values = []
        for value in values:
            if isinstance(value, (str, bytes)):
                new_values.append(value[:max_length])
            elif isinstance(value, (int, float)):
                new_values.append(value)
            elif isinstance(value, dict):
                new_values.append(json.dumps(value, ensure_ascii=False)[:max_length])
            else:
                raise ValueError(f"Unsupported value type: {type(value)}")

        async with self.redis_pool.pipeline(transaction=False) as pipe:
            # Batch commands: use pipeline for operations
            pipe.lpush(key, *new_values)
            pipe.ltrim(key, 0, max_size - 1)
            pipe.expire(key, ex)

            results = await pipe.execute()
            return results[0]

    async def rpop(self, key: str):  # Waiting for 1 sec for default
        """Remove and return the last element of a list.

        Args:
            key: The list key

        Returns:
            Optional[bytes]: The response of the rpop operation
        """
        return await self.redis_pool.rpop(key)

    # @retry_decorator
    async def brpop(self, key: str, timeout=1):  # Waiting for 1 sec for default
        """Blocking pop operation that removes and returns the last element of a list.

        NOTE: Since JimDB doesn't support brpop, this implementation simulates
        blocking behavior using rpop with sleep fallback.

        Args:
            key: The list key to pop from
            timeout: Maximum time to wait in seconds (default: 1)

        Returns:
            Optional[bytes]: The response of the simulated brpop operation
        """
        # Simulating brpop
        value = await self.redis_pool.rpop(key)
        if value is not None:
            return value
        else:  # Simulating blocking by sleeping and trying again
            await asyncio.sleep(timeout)
            return await self.redis_pool.rpop(key)

    @retry_decorator
    async def lrange(self, key: str, start: int = 0, end: int = -1):
        """Get a range of elements from a list.

        NOTE: Elements added later appear at the beginning of the list
        when retrieved (LIFO behavior due to lpush).

        Args:
            key: The list key
            start: Start index (default: 0)
            end: End index, -1 means last element (default: -1)

        Returns:
            Optional[List[bytes]]: List of elements in the specified range,
                                 empty list if key doesn't exist, None if error occurred
        """
        return await self.redis_pool.lrange(key, start, end)

    @retry_decorator
    async def lrem(self, key: str, count: int, value: str):
        """Remove elements from a list by value.

        Args:
            key: The list key
            count: Number of elements to remove (direction depends on sign)
            value: The value to remove

        Returns:
            Optional[int]: Number of elements removed, None if error occurred
        """
        return await self.redis_pool.lrem(key, count, value)

    @retry_decorator
    async def lindex(self, key: str, index: int):
        """Get an element from a list by its index.

        Args:
            key: The list key
            index: The index of the element to retrieve

        Returns:
            Optional[bytes]: The response of the lindex operation
        """
        return await self.redis_pool.lindex(key, index)

    @retry_decorator
    async def llen(self, key: str):
        """Get the length of a list.

        Args:
            key: The list key

        Returns:
            Optional[int]: The response of the llen operation
        """
        return await self.redis_pool.llen(key)

    @retry_decorator
    async def ltrim(self, key: str, start: int, end: int):
        """Get the length of a list.

        Args:
            key: The list key

        Returns:
            Optional[bool]: The response of the ltrim operation
        """
        return await self.redis_pool.ltrim(key, start, end)
