"""
L3 CKS Integration Layer - Persistent Semantic Search

Integration with the Constitutional Knowledge System (CKS) for
persistent storage and semantic search capabilities.

This layer provides graceful degradation if CKS is unavailable.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class CKSLayer:
    """
    L3 CKS integration layer.

    Characteristics:
    - Persistent long-term storage
    - Semantic search capabilities
    - Vector-based similarity matching
    - Graceful degradation if unavailable
    """

    def __init__(self, fallback_to_disk: bool = True):
        """
        Initialize the CKS integration layer.

        Args:
            fallback_to_disk: If True, falls back to disk cache when CKS unavailable

        """
        self.fallback_to_disk = fallback_to_disk
        self._cks_available = False
        self._cks_client = None
        self._disk_fallback = None

        # Try to import and initialize CKS
        self._init_cks()

    def _init_cks(self) -> None:
        """
        Initialize CKS client.

        Attempts to import and configure the CKS integration.
        Sets _cks_available flag based on success.
        """
        try:
            from src.zen.memory_system import MemorySystem

            # Initialize CKS client
            self._cks_client = MemorySystem()
            self._cks_available = True

            logger.info("CKS integration initialized successfully")

        except ImportError as e:
            logger.warning(f"CKS not available: {e}")
            self._cks_available = False

        except Exception as e:
            logger.error(f"Failed to initialize CKS: {e}")
            self._cks_available = False

    def is_available(self) -> bool:
        """
        Check if CKS integration is available.

        Returns:
            True if CKS is available and functional

        """
        return self._cks_available and self._cks_client is not None

    async def store(self, key: str, value: Any, metadata: dict | None = None) -> bool:
        """
        Store a value in CKS.

        Args:
            key: Storage key
            value: Value to store
            metadata: Optional metadata dict

        Returns:
            True if successful, False otherwise

        """
        if not self.is_available():
            if self.fallback_to_disk and self._disk_fallback:
                logger.debug(f"CKS unavailable, using disk fallback for key: {key}")
                return await self._disk_fallback.set(key, value)
            return False

        try:
            # Prepare storage data
            storage_data = {
                "key": key,
                "value": value,
                "metadata": metadata or {},
            }

            # Store in CKS memory system
            # Note: This is a stub implementation
            # Actual CKS integration depends on the MemorySystem interface
            await self._cks_client.store(
                content=storage_data,
                metadata={"source": "brainstorm", "key": key}
            )

            return True

        except Exception as e:
            logger.error(f"Failed to store in CKS: {e}")
            return False

    async def retrieve(self, key: str) -> Any | None:
        """
        Retrieve a value from csf.cks.

        Args:
            key: Storage key

        Returns:
            Cached value or None if not found

        """
        if not self.is_available():
            if self.fallback_to_disk and self._disk_fallback:
                logger.debug(f"CKS unavailable, using disk fallback for key: {key}")
                return await self._disk_fallback.get(key)
            return None

        try:
            # Query CKS for the key
            # Note: This is a stub implementation
            results = await self._cks_client.search(
                query=key,
                filters={"source": "brainstorm", "key": key},
                limit=1
            )

            if results and len(results) > 0:
                return results[0].get("value")

            return None

        except Exception as e:
            logger.error(f"Failed to retrieve from CKS: {e}")
            return None

    async def find_similar(
        self,
        query: str,
        top_k: int = 5,
        filters: dict | None = None
    ) -> list[Any]:
        """
        Find similar entries using semantic search.

        Args:
            query: Search query
            top_k: Number of results to return
            filters: Optional metadata filters

        Returns:
            List of similar entries

        """
        if not self.is_available():
            logger.debug("CKS unavailable, semantic search not available")
            return []

        try:
            # Prepare default filters
            search_filters = filters or {}
            search_filters.setdefault("source", "brainstorm")

            # Perform semantic search in CKS
            results = await self._cks_client.search(
                query=query,
                filters=search_filters,
                limit=top_k
            )

            # Extract values from results
            return [result.get("value") for result in results if result.get("value")]

        except Exception as e:
            logger.error(f"Failed to perform semantic search in CKS: {e}")
            return []

    async def delete(self, key: str) -> bool:
        """
        Delete a value from csf.cks.

        Args:
            key: Storage key

        Returns:
            True if successful, False otherwise

        """
        if not self.is_available():
            if self.fallback_to_disk and self._disk_fallback:
                return await self._disk_fallback.delete(key)
            return False

        try:
            # Delete from CKS
            # Note: This is a stub implementation
            await self._cks_client.delete(
                filters={"source": "brainstorm", "key": key}
            )

            return True

        except Exception as e:
            logger.error(f"Failed to delete from CKS: {e}")
            return False

    async def clear(self) -> bool:
        """
        Clear all brainstorm entries from csf.cks.

        Returns:
            True if successful, False otherwise

        """
        if not self.is_available():
            if self.fallback_to_disk and self._disk_fallback:
                return await self._disk_fallback.clear()
            return False

        try:
            # Delete all brainstorm entries
            await self._cks_client.delete(filters={"source": "brainstorm"})
            return True

        except Exception as e:
            logger.error(f"Failed to clear CKS entries: {e}")
            return False

    def get_stats(self) -> dict:
        """
        Get CKS layer statistics.

        Returns:
            Dictionary with layer stats

        """
        return {
            "available": self.is_available(),
            "fallback_enabled": self.fallback_to_disk,
            "client_initialized": self._cks_client is not None,
        }

    async def store_pattern(
        self,
        pattern_name: str,
        pattern_data: dict,
        tags: list[str] | None = None
    ) -> bool:
        """
        Store a brainstorm pattern in CKS.

        Args:
            pattern_name: Name of the pattern
            pattern_data: Pattern data dictionary
            tags: Optional list of tags for categorization

        Returns:
            True if successful, False otherwise

        """
        metadata = {
            "type": "pattern",
            "name": pattern_name,
            "tags": tags or [],
        }

        return await self.store(
            key=f"pattern:{pattern_name}",
            value=pattern_data,
            metadata=metadata
        )

    async def find_patterns(
        self,
        query: str,
        tags: list[str] | None = None,
        top_k: int = 5
    ) -> list[dict]:
        """
        Find patterns matching query and/or tags.

        Args:
            query: Search query
            tags: Filter by tags
            top_k: Number of results

        Returns:
            List of matching pattern data

        """
        filters = {"type": "pattern"}

        if tags:
            filters["tags"] = tags

        results = await self.find_similar(query, top_k=top_k, filters=filters)
        return results
