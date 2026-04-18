"""
Log rotation utility for API response logs (P0-4).

Implements automatic log rotation based on file size to prevent
unbounded growth of API response logs.

Usage:
    from lib.utils.log_rotation import ensure_log_rotation, rotate_large_logs

    # Rotate logs if they exceed threshold
    rotate_large_logs()

    # Get current log file path with date-based rotation
    log_path = get_rotated_log_path()
"""

from __future__ import annotations

import gzip
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Configuration
_MAX_LOG_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
_MAX_LOG_FILES = 5  # Keep at most 5 rotated logs
_LOG_DIR = Path(__file__).parent.parent.parent / ".claude"
_BASE_LOG_NAME = "api_responses_log.jsonl"


def get_log_path() -> Path:
    """Get the current log file path."""
    log_path = _LOG_DIR / _BASE_LOG_NAME
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    return log_path


def get_log_size(log_path: Path | None = None) -> int:
    """Get the current log file size in bytes.

    Args:
        log_path: Path to log file, or None to use default

    Returns:
        File size in bytes, or 0 if file doesn't exist
    """
    if log_path is None:
        log_path = get_log_path()

    if log_path.exists():
        return log_path.stat().st_size
    return 0


def rotate_log_file(log_path: Path | None = None) -> Path | None:
    """Rotate the log file if it exceeds the size threshold.

    Args:
        log_path: Path to log file, or None to use default

    Returns:
        Path to the rotated (compressed) file, or None if no rotation occurred
    """
    if log_path is None:
        log_path = get_log_path()

    # Check if rotation is needed
    if not log_path.exists():
        return None

    file_size = log_path.stat().st_size
    if file_size < _MAX_LOG_SIZE_BYTES:
        return None

    # Create timestamp for rotation
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    rotated_name = f"{log_path.stem}.{timestamp}.jsonl"
    rotated_path = _LOG_DIR / rotated_name

    # Move current log to rotated name
    shutil.move(str(log_path), str(rotated_path))

    # Create compressed version
    compressed_path = rotated_path.with_suffix(".jsonl.gz")
    with open(rotated_path, "rb") as f_in:
        with gzip.open(compressed_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

    # Remove uncompressed rotated file
    rotated_path.unlink()

    # Clean up old log files
    _cleanup_old_logs()

    return compressed_path


def _cleanup_old_logs() -> None:
    """Remove old rotated log files, keeping only the most recent ones."""
    log_files = sorted(
        _LOG_DIR.glob("api_responses_log.*.jsonl.gz"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    # Keep only the most recent files
    for old_log in log_files[_MAX_LOG_FILES:]:
        old_log.unlink()


def append_log_entry(entry: dict[str, Any], log_path: Path | None = None) -> None:
    """Append a log entry to the log file with automatic rotation.

    Args:
        entry: Dictionary entry to log (will be JSON serialized)
        log_path: Path to log file, or None to use default
    """
    if log_path is None:
        log_path = get_log_path()

    # Check if rotation is needed before appending
    if log_path.exists() and log_path.stat().st_size >= _MAX_LOG_SIZE_BYTES:
        rotate_log_file(log_path)

    # Append the entry
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_recent_log_entries(
    limit: int = 100, log_path: Path | None = None
) -> list[dict[str, Any]]:
    """Get the most recent log entries.

    Args:
        limit: Maximum number of entries to return
        log_path: Path to log file, or None to use default

    Returns:
        List of log entry dictionaries
    """
    if log_path is None:
        log_path = get_log_path()

    if not log_path.exists():
        return []

    entries = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            if len(entries) >= limit:
                break

    # Return in reverse order (most recent first)
    return list(reversed(entries))


def rotate_large_logs() -> dict[str, Any]:
    """Rotate all large log files in the log directory.

    Returns:
        Dictionary with rotation results
    """
    results = {
        "rotated_files": [],
        "space_freed_bytes": 0,
        "errors": [],
    }

    if not _LOG_DIR.exists():
        return results

    for log_file in _LOG_DIR.glob("*.jsonl"):
        if log_file.stat().st_size >= _MAX_LOG_SIZE_BYTES:
            try:
                compressed = rotate_log_file(log_file)
                if compressed:
                    results["rotated_files"].append(str(compressed))
                    # Estimate space freed (compressed is typically ~10% of original)
                    results["space_freed_bytes"] += int(
                        log_file.stat().st_size * 0.9
                    )
            except Exception as e:
                results["errors"].append(f"{log_file}: {e}")

    return results


def ensure_log_rotation() -> None:
    """Ensure log rotation is configured and running.

    This function checks for large logs and rotates them if needed.
    Call this periodically (e.g., on skill startup).
    """
    results = rotate_large_logs()

    if results["rotated_files"]:
        import sys

        print(
            f"[LOG ROTATION] Rotated {len(results['rotated_files'])} log files, "
            f"freed ~{results['space_freed_bytes'] / 1024 / 1024:.1f} MB",
            file=sys.stderr,
            flush=True,
        )

    if results["errors"]:
        import sys

        for error in results["errors"]:
            print(f"[LOG ROTATION ERROR] {error}", file=sys.stderr, flush=True)


__all__ = [
    "get_log_path",
    "get_log_size",
    "rotate_log_file",
    "append_log_entry",
    "get_recent_log_entries",
    "rotate_large_logs",
    "ensure_log_rotation",
]
