"""local_redis.py Local Key-value Implementation Module.

This file implements a local file system-based simulation of Key-value database,
providing Redis-like functionality for development and testing environments without
requiring an actual Elasticsearch server.
"""

import json
import time
from collections import deque
from typing import Dict, Union


class LocalRedis:
    """Local in-memory implementation of Redis-like key-value store.

    This class provides a lightweight, in-memory simulation of Redis functionality
    using Python's built-in data structures. It's designed for development, testing,
    and environments where a full Redis server is not available or needed.

    Features:
    - In-memory key-value storage using deques for list operations
    - Automatic expiration handling with TTL support
    - List operations with configurable size limits
    - Value type validation and conversion
    """

    def __init__(self):
        self.data: Dict[str, deque] = {}
        self.expiry: Dict[str, float] = {}
        self.default_expire_time = 86400  # Default TTL: 1 day
        self.default_list_max_size = 10

    async def lpush(
        self,
        key: str,
        *values: Union[bytes, int, str, float, dict],
        ex: int = None,
        max_size: int = None,
        max_length: int = 81920,
    ) -> int:
        """Push one or more values to the left (head) of a list.

        This method adds elements to the beginning of a list, creating the list
        if it doesn't exist. It includes automatic size limiting, value type
        conversion, and expiration management.

        Args:
            key: The list key to push values to
            *values: One or more values to push (single or multiple types)
            ex: Expiration time in seconds (default: 1 day)
            max_size: Maximum number of elements in the list (default: uses default_list_max_size)
            max_length: Maximum length for string/bytes values (default: 81920)

        Returns:
            int: The length of the list after the push operation

        Raises:
            ValueError: If an unsupported value type is provided

        NOTE:
            Values are processed and potentially truncated based on type:
            - str/bytes: Truncated to max_length
            - int/float: Added as-is
            - dict: Converted to JSON string and truncated
        """
        if ex is None:
            ex = self.default_expire_time
        if max_size is None:
            max_size = self.default_list_max_size

        if key not in self.data:
            self.data[key] = deque(
                maxlen=max_size
            )  # Create new deque if key dosen't exist

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

        # Add values to the laft (head) of the deque
        self.data[key].extendleft(
            reversed(new_values)
        )  # Use reserved to ensure proper order
        self.expiry[key] = time.time() + ex
        return len(self.data[key])

    async def rpop(self, key: str) -> Union[str, bytes, int, float, None]:
        """Remove and return the last (rightmost, tail) element from a list.

        This method implements the Redis RPOP command, removing elements from
        the tail of the list. It includes automatic expiration checking.

        Args:
            key: The list key to pop from

        Returns:
            The removed element, or None if the list is empty or doesn't exist

        Note:
            This method automatically checks and handles key expiration before
            attempting the pop operation.
        """
        self._check_expiry(key)
        if key in self.data and self.data[key]:
            return self.data[key].pop()
        return None

    def _check_expiry(self, key: str):
        """Check if a key has expired and remove it if necessary.

        Args:
            key: The key to check for expiration
        """
        if key in self.expiry and time.time() > self.expiry[key]:
            del self.data[key]
            del self.expiry[key]

    async def close(
        self,
    ):  # This method is async to maintain compatibility with the Redis interface
        pass
