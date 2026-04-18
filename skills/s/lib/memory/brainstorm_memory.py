"""
Unified Brainstorm Memory Interface

Three-layer memory system with automatic layer traversal:
- L1: Session cache (fast, temporary)
- L2: Disk cache (persistent, 72h TTL)
- L3: CKS integration (persistent, semantic search)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .cks_integration import CKSLayer
from .disk_cache import DiskCacheLayer
from .session import SessionLayer

logger = logging.getLogger(__name__)


class StorageLayer(Enum):
    """Memory storage layer enumeration."""

    L1_SESSION = 1
    L2_DISK = 2
    L3_CKS = 3


@dataclass
class BrainstormPattern:
    """
    Brainstorm pattern data structure.

    Attributes:
        name: Pattern name
        description: Pattern description
        category: Pattern category (e.g., 'design', 'refactoring')
        code_snippets: List of code examples
        tags: List of tags for search
        metadata: Additional metadata

    """

    name: str
    description: str
    category: str
    code_snippets: list[str]
    tags: list[str]
    metadata: dict

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "code_snippets": self.code_snippets,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> BrainstormPattern:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            description=data["description"],
            category=data["category"],
            code_snippets=data["code_snippets"],
            tags=data["tags"],
            metadata=data["metadata"],
        )


class BrainstormMemory:
    """
    Three-layer memory system for brainstorm module.

    Provides unified interface with automatic layer traversal.
    Implements write-through caching and hierarchical retrieval.
    """

    def __init__(
        self,
        session_size: int = 1000,
        disk_ttl_hours: int = 72,
        cache_dir: str | None = None,
        enable_cks: bool = True
    ):
        """
        Initialize the three-layer memory system.

        Args:
            session_size: Max items in L1 cache (default: 1000)
            disk_ttl_hours: TTL for L2 cache in hours (default: 72)
            cache_dir: Directory for L2 cache (default: ~/.cache/brainstorm)
            enable_cks: Enable L3 CKS integration (default: True)

        """
        self.l1 = SessionLayer(max_size=session_size)
        self.l2 = DiskCacheLayer(cache_dir=cache_dir, ttl_hours=disk_ttl_hours)
        self.l3 = CKSLayer(fallback_to_disk=True) if enable_cks else None

        logger.info("Brainstorm memory system initialized")

    async def store(
        self,
        key: str,
        value: Any,
        layer: int = 1,
        propagate: bool = True
    ) -> bool:
        """
        Store a value in the memory system.

        Args:
            key: Storage key
            value: Value to store
            layer: Target layer (1-3, default: 1)
            propagate: If True, propagates to higher layers (default: True)

        Returns:
            True if successful, False otherwise

        """
        success = False

        # Store in L1
        if layer <= 1:
            try:
                self.l1.set(key, value)
                success = True
            except Exception as e:
                logger.error(f"Failed to store in L1: {e}")

        # Store in L2 (if layer is 2 or lower, regardless of propagate)
        if layer <= 2:
            try:
                if not self.l2.set(key, value):
                    logger.warning(f"Failed to store in L2 for key: {key}")
            except Exception as e:
                logger.error(f"Failed to store in L2: {e}")

        # Store in L3
        if propagate and layer <= 3 and self.l3:
            try:
                await self.l3.store(key, value)
            except Exception as e:
                logger.error(f"Failed to store in L3: {e}")

        return success

    async def retrieve(self, key: str) -> Any | None:
        """
        Retrieve a value from the memory system.

        Checks L1 → L2 → L3 in order.
        Promotes found values to higher layers.

        Args:
            key: Storage key

        Returns:
            Cached value or None if not found

        """
        # Check L1
        value = self.l1.get(key)
        if value is not None:
            logger.debug(f"Cache hit in L1 for key: {key}")
            return value

        # Check L2
        value = self.l2.get(key)
        if value is not None:
            logger.debug(f"Cache hit in L2 for key: {key}")
            # Promote to L1
            self.l1.set(key, value)
            return value

        # Check L3
        if self.l3:
            try:
                value = await self.l3.retrieve(key)
                if value is not None:
                    logger.debug(f"Cache hit in L3 for key: {key}")
                    # Promote to L2 and L1
                    self.l2.set(key, value)
                    self.l1.set(key, value)
                    return value
            except Exception as e:
                logger.error(f"Failed to retrieve from L3: {e}")

        logger.debug(f"Cache miss for key: {key}")
        return None

    async def store_pattern(self, pattern: BrainstormPattern) -> bool:
        """
        Store a brainstorm pattern across all layers.

        Args:
            pattern: BrainstormPattern instance

        Returns:
            True if successful

        """
        key = f"pattern:{pattern.name}"

        # Store in L1 and L2
        pattern_dict = pattern.to_dict()
        await self.store(key, pattern_dict, layer=2, propagate=True)

        # Store in L3 with special handling
        if self.l3:
            try:
                await self.l3.store_pattern(
                    pattern_name=pattern.name,
                    pattern_data=pattern_dict,
                    tags=pattern.tags
                )
            except Exception as e:
                logger.error(f"Failed to store pattern in L3: {e}")

        return True

    async def find_similar(
        self,
        query: str,
        top_k: int = 5,
        filters: dict | None = None
    ) -> list[Any]:
        """
        Find similar entries using semantic search (L3 only).

        Args:
            query: Search query
            top_k: Number of results to return
            filters: Optional metadata filters

        Returns:
            List of similar entries

        """
        if not self.l3:
            logger.warning("Semantic search not available (L3 disabled)")
            return []

        try:
            results = await self.l3.find_similar(query, top_k=top_k, filters=filters)

            # Promote results to L1 and L2
            for result in results:
                if isinstance(result, dict) and "name" in result:
                    key = f"pattern:{result['name']}"
                    self.l1.set(key, result)
                    self.l2.set(key, result)

            return results

        except Exception as e:
            logger.error(f"Failed to perform semantic search: {e}")
            return []

    async def find_patterns(
        self,
        query: str,
        tags: list[str] | None = None,
        top_k: int = 5
    ) -> list[BrainstormPattern]:
        """
        Find patterns matching query and/or tags.

        Args:
            query: Search query
            tags: Filter by tags
            top_k: Number of results

        Returns:
            List of matching BrainstormPattern instances

        """
        if not self.l3:
            logger.warning("Pattern search not available (L3 disabled)")
            return []

        try:
            pattern_dicts = await self.l3.find_patterns(query, tags=tags, top_k=top_k)

            return [BrainstormPattern.from_dict(p) for p in pattern_dicts]

        except Exception as e:
            logger.error(f"Failed to find patterns: {e}")
            return []

    async def delete(self, key: str, layer: int = 3) -> bool:
        """
        Delete a value from the memory system.

        Args:
            key: Storage key
            layer: Delete from this layer and above (default: 3)

        Returns:
            True if successful

        """
        success = True

        # Delete from L1
        if layer >= 1:
            self.l1.delete(key)

        # Delete from L2
        if layer >= 2:
            if not self.l2.delete(key):
                success = False

        # Delete from L3
        if layer >= 3 and self.l3:
            try:
                if not await self.l3.delete(key):
                    success = False
            except Exception as e:
                logger.error(f"Failed to delete from L3: {e}")
                success = False

        return success

    async def clear(self, layer: int = 3) -> bool:
        """
        Clear all entries from the memory system.

        Args:
            layer: Clear this layer and above (default: 3)

        Returns:
            True if successful

        """
        success = True

        # Clear L1
        if layer >= 1:
            self.l1.clear()

        # Clear L2
        if layer >= 2:
            if not self.l2.clear():
                success = False

        # Clear L3
        if layer >= 3 and self.l3:
            try:
                if not await self.l3.clear():
                    success = False
            except Exception as e:
                logger.error(f"Failed to clear L3: {e}")
                success = False

        return success

    def get_stats(self) -> dict:
        """
        Get comprehensive statistics for all layers.

        Returns:
            Dictionary with stats from all layers

        """
        return {
            "l1_session": self.l1.get_stats(),
            "l2_disk": self.l2.get_stats(),
            "l3_cks": self.l3.get_stats() if self.l3 else {"available": False},
        }

    async def vacuum_l2(self) -> bool:
        """
        Vacuum L2 database to reclaim space.

        Returns:
            True if successful

        """
        return self.l2.vacuum()

    async def cleanup_expired_l2(self) -> int:
        """
        Cleanup expired entries from L2.

        Returns:
            Number of entries removed

        """
        return self.l2._cleanup_expired()

    def get_all_l1_keys(self) -> list[str]:
        """
        Get all keys in L1 cache.

        Returns:
            List of L1 keys

        """
        return self.l1.get_all_keys()

    def get_all_l2_keys(self) -> list[str]:
        """
        Get all non-expired keys in L2 cache.

        Returns:
            List of L2 keys

        """
        return self.l2.get_all_keys()

    def close(self) -> None:
        """Close the memory system and release resources."""
        self.l2.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        # Force garbage collection for Windows file locking
        import gc
        import time
        gc.collect()
        time.sleep(0.05)
        return False
