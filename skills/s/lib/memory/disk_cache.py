"""
L2 Disk Cache Layer - SQLite Persistent Storage

Persistent disk cache with automatic cleanup of expired entries.
Default TTL: 72 hours.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


class DiskCacheLayer:
    """
    L2 disk cache with SQLite backend.

    Characteristics:
    - Persistent storage
    - Automatic TTL cleanup (72h default)
    - Thread-safe
    - JSON serialization for complex types
    """

    def __init__(self, cache_dir: Path | None = None, ttl_hours: int = 72):
        """
        Initialize the disk cache layer.

        Args:
            cache_dir: Directory for cache storage (default: ~/.cache/brainstorm)
            ttl_hours: Time-to-live in hours (default: 72)

        """
        if cache_dir is None:
            cache_dir = Path.home() / ".cache" / "brainstorm"

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = self.cache_dir / "brainstorm_cache.db"
        self.ttl_seconds = ttl_hours * 3600

        # Thread lock for database operations
        self._lock = threading.Lock()

        # Initialize database
        self._init_db()

        # Cleanup expired entries on init
        self._cleanup_expired()

    def _init_db(self) -> None:
        """Initialize the SQLite database schema."""
        with sqlite3.connect(str(self.db_path)) as conn:
            # Enable WAL mode for better Windows concurrency
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')

            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    access_count INTEGER DEFAULT 1
                )
            """)

            # Create index for faster cleanup queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires_at
                ON cache_entries(expires_at)
            """)

            conn.commit()

    def get(self, key: str) -> Any | None:
        """
        Retrieve a value from disk cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired

        """
        with self._lock:
            try:
                with sqlite3.connect(str(self.db_path)) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT value, expires_at
                        FROM cache_entries
                        WHERE key = ?
                    """, (key,))

                    row = cursor.fetchone()

                    if row is None:
                        return None

                    value_json, expires_at = row

                    # Check if expired
                    if time.time() > expires_at:
                        # Delete expired entry
                        cursor.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                        conn.commit()
                        return None

                    # Update access count
                    cursor.execute("""
                        UPDATE cache_entries
                        SET access_count = access_count + 1
                        WHERE key = ?
                    """, (key,))
                    conn.commit()

                    # Deserialize value
                    return json.loads(value_json)

            except (sqlite3.Error, json.JSONDecodeError):
                return None

    def set(self, key: str, value: Any, ttl_hours: int | None = None) -> bool:
        """
        Store a value in disk cache.

        Args:
            key: Cache key
            value: Value to store (must be JSON-serializable)
            ttl_hours: Custom TTL in hours (overrides default)

        Returns:
            True if successful, False otherwise

        """
        with self._lock:
            try:
                # Serialize value
                value_json = json.dumps(value)

                # Calculate expiration
                ttl = ttl_hours * 3600 if ttl_hours else self.ttl_seconds
                expires_at = time.time() + ttl

                with sqlite3.connect(str(self.db_path)) as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO cache_entries
                        (key, value, created_at, expires_at, access_count)
                        VALUES (?, ?, ?, ?, 0)
                    """, (key, value_json, time.time(), expires_at))
                    conn.commit()

                return True

            except (sqlite3.Error, json.JSONDecodeError, TypeError):
                return False

    def delete(self, key: str) -> bool:
        """
        Delete a value from disk cache.

        Args:
            key: Cache key

        Returns:
            True if key was found and deleted, False otherwise

        """
        with self._lock:
            try:
                with sqlite3.connect(str(self.db_path)) as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                    conn.commit()
                    return cursor.rowcount > 0

            except sqlite3.Error:
                return False

    def clear(self) -> bool:
        """
        Clear all entries from disk cache.

        Returns:
            True if successful, False otherwise

        """
        with self._lock:
            try:
                with sqlite3.connect(str(self.db_path)) as conn:
                    conn.execute("DELETE FROM cache_entries")
                    conn.commit()
                    return True

            except sqlite3.Error:
                return False

    def _cleanup_expired(self) -> int:
        """
        Remove expired entries from cache.

        Returns:
            Number of entries removed

        """
        with self._lock:
            try:
                with sqlite3.connect(str(self.db_path)) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        DELETE FROM cache_entries
                        WHERE expires_at < ?
                    """, (time.time(),))
                    conn.commit()
                    return cursor.rowcount

            except sqlite3.Error:
                return 0

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats

        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()

                # Total entries
                cursor.execute("SELECT COUNT(*) FROM cache_entries")
                total_entries = cursor.fetchone()[0]

                # Expired entries
                cursor.execute("SELECT COUNT(*) FROM cache_entries WHERE expires_at < ?", (time.time(),))
                expired_entries = cursor.fetchone()[0]

                # Total access count
                cursor.execute("SELECT SUM(access_count) FROM cache_entries")
                total_access = cursor.fetchone()[0] or 0

                # Database size
                db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

                return {
                    "total_entries": total_entries,
                    "active_entries": total_entries - expired_entries,
                    "expired_entries": expired_entries,
                    "total_access": total_access,
                    "db_size_bytes": db_size,
                    "db_size_mb": db_size / (1024 * 1024),
                    "ttl_hours": self.ttl_seconds / 3600,
                    "db_path": str(self.db_path),
                }

        except sqlite3.Error:
            return {
                "error": "Failed to retrieve stats",
            }

    def vacuum(self) -> bool:
        """
        Vacuum the database to reclaim space.

        Returns:
            True if successful, False otherwise

        """
        with self._lock:
            try:
                with sqlite3.connect(str(self.db_path)) as conn:
                    conn.execute("VACUUM")
                    conn.commit()
                    return True

            except sqlite3.Error:
                return False

    def get_all_keys(self) -> list[str]:
        """
        Get all non-expired cache keys.

        Returns:
            List of all keys in the cache

        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT key FROM cache_entries
                    WHERE expires_at > ?
                """, (time.time(),))
                return [row[0] for row in cursor.fetchall()]

        except sqlite3.Error:
            return []

    def close(self) -> None:
        """
        Close the disk cache layer.

        Runs a WAL checkpoint to ensure -wal and -shm files are cleaned up.
        Critical for Windows file locking.
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.isolation_level = None  # Autocommit mode
            conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            conn.execute('PRAGMA optimize')
            conn.close()
        except sqlite3.Error:
            pass  # Database may not exist yet

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        # Force garbage collection to ensure connections are closed
        import gc
        gc.collect()
        # Delay to allow Windows to release file locks
        import time
        time.sleep(0.05)
        return False
