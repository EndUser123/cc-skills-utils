"""
L1 Session Layer - In-Memory Cache

Fast, temporary storage with LRU eviction.
Evicts oldest entries when cache exceeds 1000 items.
"""
from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any


class SessionLayer:
    """
    L1 in-memory cache with LRU eviction.

    Characteristics:
    - Fastest access (memory-resident)
    - Limited capacity (1000 items)
    - LRU eviction policy
    - Non-persistent
    """

    def __init__(self, max_size: int = 1000):
        """
        Initialize the session layer.

        Args:
            max_size: Maximum number of items before eviction (default: 1000)

        """
        self.max_size = max_size
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        """
        Retrieve a value from the session cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found

        """
        if key in self._cache:
            # Move to end (most recently used)
            value, timestamp = self._cache.pop(key)
            self._cache[key] = (value, timestamp)
            self._hits += 1
            return value

        self._misses += 1
        return None

    def set(self, key: str, value: Any) -> None:
        """
        Store a value in the session cache.

        Args:
            key: Cache key
            value: Value to store

        """
        # Remove if exists (will be re-added at end)
        if key in self._cache:
            self._cache.pop(key)

        # Evict oldest if at capacity
        if len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)

        # Add to cache
        self._cache[key] = (value, time.time())

    def delete(self, key: str) -> bool:
        """
        Delete a value from the session cache.

        Args:
            key: Cache key

        Returns:
            True if key was found and deleted, False otherwise

        """
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all entries from the session cache."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats (size, hits, misses, hit_rate)

        """
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "utilization": len(self._cache) / self.max_size,
        }

    def get_all_keys(self) -> list[str]:
        """
        Get all cache keys.

        Returns:
            List of all keys in the cache

        """
        return list(self._cache.keys())

    def get_size(self) -> int:
        """
        Get current cache size.

        Returns:
            Number of items in cache

        """
        return len(self._cache)
