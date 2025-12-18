"""local_redis.py Local Key-value Implementation Module.

This file implements a local file system-based simulation of Key-value database,
providing Redis-like functionality for development and testing environments without
requiring an actual Elasticsearch server.
"""

import asyncio
import json
import time
from collections import deque
from typing import Dict, Optional, Union, List, Tuple
import bisect

from ...config import Config


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
    - Sorted set (zset) operations with score-based ordering
    """

    def __init__(self, *, yield_on_ops: bool = True):
        self.data: Dict[str, deque] = {}
        self.zsets: Dict[str, Tuple[List[float], List[str]]] = {}  # (scores, members)
        self.expiry: Dict[str, float] = {}
        self.default_expire_time = Config.get_redis_expire_time()
        self.default_list_max_size = Config.get_redis_max_size()
        self.default_list_max_length = Config.get_redis_max_length() * 1024
        # When True, each mutating/read pop yields the event loop once for fairness.
        self._yield_on_ops = yield_on_ops

    async def lpush(
        self,
        key: str,
        *values: Union[bytes, int, str, float, dict],
        ex: Optional[int] = None,
        max_size: Optional[int] = None,
        max_length: Optional[int] = None,
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
            max_length: Maximum length for string/bytes values (default: 20MB)

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
        if max_length is None:
            max_length = self.default_list_max_length

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

        if self._yield_on_ops:
            await asyncio.sleep(0)

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
            item = self.data[key].pop()

            # Yield after a successful pop so producers/other tasks get a turn too
            if self._yield_on_ops:
                await asyncio.sleep(0)

            return item

        # Optional tiny yield even on empty pops helps polling loops be nicer
        if self._yield_on_ops:
            await asyncio.sleep(0)
        return None

    def _check_expiry(self, key: str):
        """Check if a key has expired and remove it if necessary.

        Args:
            key: The key to check for expiration
        """
        if key in self.expiry and time.time() > self.expiry[key]:
            if key in self.data:
                del self.data[key]
            if key in self.zsets:
                del self.zsets[key]
            del self.expiry[key]

    async def zadd(self, key: str, mapping: Dict[str, float], ex: Optional[int] = None) -> int:
        """Add one or more members to a sorted set, or update their score if they already exist.

        Args:
            key: The sorted set key
            mapping: Dictionary of member-score pairs
            ex: Expiration time in seconds (default: 1 day)

        Returns:
            int: Number of new members added (excluding updated scores)
        """
        if ex is None:
            ex = self.default_expire_time

        if key not in self.zsets:
            self.zsets[key] = ([], [])
            self.expiry[key] = time.time() + ex

        scores, members = self.zsets[key]
        added = 0

        for member, score in mapping.items():
            # Check if member exists
            if member in members:
                idx = members.index(member)
                # Always update: remove old position and re-insert at new position
                del scores[idx]
                del members[idx]
                insert_pos = bisect.bisect_left(scores, score)
                scores.insert(insert_pos, score)
                members.insert(insert_pos, member)
            else:
                # Add new member
                insert_pos = bisect.bisect_left(scores, score)
                scores.insert(insert_pos, score)
                members.insert(insert_pos, member)
                added += 1

        self.expiry[key] = time.time() + ex

        if self._yield_on_ops:
            await asyncio.sleep(0)
        return added

    async def zrange(
        self,
        key: str,
        start: int,
        stop: int,
        withscores: bool = False
    ) -> Union[List[str], List[Tuple[str, float]]]:
        """Return a range of members in a sorted set, by index.

        Args:
            key: The sorted set key
            start: Starting index (0-based)
            stop: Ending index (inclusive, -1 for last)
            withscores: Whether to return scores with members

        Returns:
            List of members or list of (member, score) tuples
        """
        self._check_expiry(key)
        if key not in self.zsets:
            return []

        scores, members = self.zsets[key]
        # Handle negative indices
        if stop < 0:
            stop = len(members) + stop
        if start < 0:
            start = len(members) + start

        result = members[start:stop+1]
        if withscores:
            result_scores = scores[start:stop+1]
            return list(zip(result, result_scores))
        return result

    async def zrem(self, key: str, *members: str) -> int:
        """Remove one or more members from a sorted set.

        Args:
            key: The sorted set key
            *members: Members to remove

        Returns:
            int: Number of members removed
        """
        self._check_expiry(key)
        if key not in self.zsets:
            return 0

        scores, members_list = self.zsets[key]
        removed = 0

        for member in members:
            if member in members_list:
                idx = members_list.index(member)
                del scores[idx]
                del members_list[idx]
                removed += 1

        if not members_list:  # If set is empty, remove it
            del self.zsets[key]
            del self.expiry[key]

        if self._yield_on_ops:
            await asyncio.sleep(0)
        return removed

    async def zincrby(self, key: str, increment: float, member: str, ex: Optional[int] = None) -> float:
        """Increment the score of a member in a sorted set.

        Args:
            key: The sorted set key
            increment: The amount to increment the score by
            member: The member to increment
            ex: Expiration time in seconds (default: 1 day)

        Returns:
            float: The new score of the member
        """
        if ex is None:
            ex = self.default_expire_time

        self._check_expiry(key)

        # Initialize the sorted set if it doesn't exist
        if key not in self.zsets:
            self.zsets[key] = ([], [])
            self.expiry[key] = time.time() + ex
        else:
            # Update expiry even if key exists
            self.expiry[key] = time.time() + ex

        scores, members_list = self.zsets[key]

        # Check if member exists
        if member in members_list:
            idx = members_list.index(member)
            old_score = scores[idx]
            new_score = old_score + increment
            
            # Always remove and re-insert to maintain sorted order
            del scores[idx]
            del members_list[idx]
            insert_pos = bisect.bisect_left(scores, new_score)
            scores.insert(insert_pos, new_score)
            members_list.insert(insert_pos, member)
        else:
            # Member doesn't exist, add it with the increment as score
            new_score = increment
            insert_pos = bisect.bisect_left(scores, new_score)
            scores.insert(insert_pos, new_score)
            members_list.insert(insert_pos, member)

        if self._yield_on_ops:
            await asyncio.sleep(0)

        return new_score

    async def close(self):
        # This method is async to maintain compatibility with the Redis interface
        # Async for interface compatibility
        if self._yield_on_ops:
            await asyncio.sleep(0)
