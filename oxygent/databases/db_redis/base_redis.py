"""base_redis.py Base Key-value Database Class Module.

This file defines the abstract base class for Key-value database services, inheriting
from BaseDB and providing the interface contract for Redis operations.
"""

import logging
from abc import ABC, abstractmethod

from oxygent.databases.base_db import BaseDB

logger = logging.getLogger(__name__)


class BaseRedis(BaseDB, ABC):
    """Abstract base class for Key-value database services.

    This class inherits from BaseDB to get retry functionality and error handling,
    while defining the essential interface that all Redis implementations
    must provide. All methods are abstract and must be implemented by subclasses.

    Supports common Redis operations including:
    - Basic key-value operations (get, set, delete)
    - Batch operations (mget, mset)
    - List operations (lpush, brpop, lrange, ltrim)
    - Key management (exists, expire)
    """

    @abstractmethod
    async def set(self, key: str, value: str, ex: int = None):
        """Set a key-value pair with optional expiration time.

        Args:
            key: The key to set
            value: The value to store
            ex: Optional expiration time in seconds

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        pass

    @abstractmethod
    async def get(self, key: str):
        """Get the value associated with a key.

        Args:
            key: The key to retrieve

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        pass

    @abstractmethod
    async def exists(self, key: str):
        """Check if a key exists in the database.

        Args:
            key: The key to check

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        pass

    @abstractmethod
    async def mset(self, items: dict, ex: int = None):
        """Set multiple key-value pairs in a single operation.

        Args:
            items: Dictionary containing key-value pairs to set
            ex: Optional expiration time in seconds for all keys

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        pass

    @abstractmethod
    async def mget(self, keys: list):
        """Get multiple values for the given keys in a single operation.

        Args:
            keys: List of keys to retrieve

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        pass

    @abstractmethod
    async def close(self):
        """Close the Redis client connection and clean up resources.

        This method should be called when the Redis client is no longer needed
        to properly release connections and resources.

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        pass

    @abstractmethod
    async def delete(self, key: str):
        """Delete a key from the database.

        Args:
            key: The key to delete

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        pass

    @abstractmethod
    async def lpush(self, key: str, *values: list):
        """Push one or more values to the left (head) of a list.

        Args:
            key: The list key
            *values: One or more values to push to the list

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        pass

    @abstractmethod
    async def brpop(self, key: str, timeout: int = 1):
        """Blocking pop operation that removes and returns the last element of a list.

        This is a blocking operation that waits for an element to be available
        or until the timeout is reached.

        Args:
            key: The list key to pop from
            timeout: Maximum time to wait in seconds (default: 1)

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        pass

    @abstractmethod
    async def lrange(self, key: str, start: int = 0, end: int = -1):
        """Get a range of elements from a list.

        Args:
            key: The list key
            start: Start index (default: 0)
            end: End index, -1 means last element (default: -1)

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        pass

    @abstractmethod
    async def expire(self, key: str, ex: int):
        """Set an expiration time for a key.

        Args:
            key: The key to set expiration for
            ex: Expiration time in seconds

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        pass

    @abstractmethod
    async def llen(self, key: str):
        """Get the length of a list.

        Args:
            key: The list key

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        pass

    @abstractmethod
    async def ltrim(self, key: str, start: int, end: int):
        """Trim a list to keep only elements within the specified range.

        Args:
            key: The list key
            start: Start index to keep
            end: End index to keep


        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        pass
