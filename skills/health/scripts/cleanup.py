#!/usr/bin/env python3
"""Safe filesystem cleanup with approval.

Enhanced with content conflict detection to prevent data loss
when moving files between locations.

PRINCIPLE: Fix source code problems first, file moves last.
This tool identifies what code generates violations before
suggesting cleanup actions.

Usage:
    python cleanup.py [--max N] [--dry-run] [--yes]

Options:
    --max N       Limit to N violations (default: 50)
    --dry-run     Show violations without prompting for action
    --yes         Auto-approve all cleanup (use with caution)

"""

from __future__ import annotations

import argparse

# Multi-terminal safety imports (platform-specific)
try:
    import fcntl  # Unix file locking

    UNIX_LOCKING_AVAILABLE = True
except ImportError:
    # Windows doesn't have fcntl
    UNIX_LOCKING_AVAILABLE = False

# Multi-terminal safety imports
import json

try:
    import msvcrt  # Windows file locking

    WINDOWS_LOCKING_AVAILABLE = True
except ImportError:
    WINDOWS_LOCKING_AVAILABLE = False
import os
import re
import shutil
import subprocess
import sys
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

# Import type validator and location optimizer for whitelist bypass detection
# Path: cleanup.py ($CLAUDE_ROOT/skills\cleanup\scripts\cleanup.py) -> up 4 levels -> .claude/ -> hooks/__lib/
lib_path = Path(__file__).parent.parent.parent.parent / "hooks" / "__lib"
sys.path.insert(0, str(lib_path))
try:
    from location_optimizer import infer_optimal_location, trace_file_references
    from type_validator import check_file_type_violations, validate_config_whitelist_entries

    TYPE_VALIDATOR_AVAILABLE = True
    LOCATION_OPTIMIZER_AVAILABLE = True
except ImportError:
    TYPE_VALIDATOR_AVAILABLE = False
    LOCATION_OPTIMIZER_AVAILABLE = False


def is_interactive() -> bool:
    """Check if running in an interactive terminal.

    Returns:
        True if stdin is a TTY (interactive terminal)
    """
    return sys.stdin.isatty()


def safe_input(prompt: str, default: str = "skip") -> str:
    """Get user input with fallback for non-interactive environments.

    Args:
        prompt: Input prompt text
        default: Default value when not interactive

    Returns:
        User input or default value
    """
    if is_interactive():
        try:
            return input(prompt)
        except EOFError:
            # TTY exists but no input available (e.g., skill launcher, IDE)
            return default
    # Non-interactive: return default behavior
    return default


# Multi-terminal cleanup lock to prevent race conditions
# Lock file location: P:\\\\\\.claude/state/cleanup.lock
CLEANUP_LOCK_FILE = Path(__file__).parent.parent.parent.parent / "state" / "cleanup.lock"
CLEANUP_LOCK_TIMEOUT = 300  # 5 minutes in seconds


def _acquire_lock_windows(lock_file) -> bool:
    """Acquire exclusive lock on Windows using msvcrt.locking.

    Args:
        lock_file: Open file handle for the lock file

    Returns:
        True if lock acquired successfully
    """
    try:
        # Try to acquire exclusive lock (LK_LOCK)
        # LK_LOCK = 0, LK_NBLCK = 1 (non-blocking)
        # We use blocking mode with timeout handling in context manager
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        return True
    except OSError:
        return False


def _acquire_lock_unix(lock_file) -> bool:
    """Acquire exclusive lock on Unix using fcntl.flock.

    Args:
        lock_file: Open file handle for the lock file

    Returns:
        True if lock acquired successfully
    """
    try:
        # LOCK_EX = exclusive lock
        # Returns immediately (doesn't block)
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


@contextmanager
def acquire_cleanup_lock(timeout: int = CLEANUP_LOCK_TIMEOUT) -> Generator[bool, None, None]:
    """Context manager for acquiring multi-terminal cleanup lock.

    Prevents race conditions when multiple terminals run cleanup simultaneously.

    Args:
        timeout: Maximum seconds to wait for lock (default: 300)

    Yields:
        True if lock acquired, False if lock acquisition failed

    Usage:
        with acquire_cleanup_lock() as acquired:
            if acquired:
                # Perform cleanup
            else:
                # Handle lock failure
                pass
    """
    import time

    # Ensure state directory exists
    CLEANUP_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)

    lock_file = None
    acquired = False
    start_time = time.time()

    try:
        # Open lock file in read-write mode
        lock_file = open(CLEANUP_LOCK_FILE, "w")

        # Try to acquire lock with timeout
        while time.time() - start_time < timeout:
            if sys.platform == "win32" and WINDOWS_LOCKING_AVAILABLE:
                acquired = _acquire_lock_windows(lock_file)
            elif sys.platform != "win32" and UNIX_LOCKING_AVAILABLE:
                acquired = _acquire_lock_unix(lock_file)
            else:
                # No locking available on this platform, proceed without lock
                acquired = True
                break

            if acquired:
                break

            # Wait before retry (exponential backoff)
            elapsed = time.time() - start_time
            wait_time = min(0.5, 2 ** int(elapsed))  # Max 0.5s, exponential backoff
            time.sleep(wait_time)

        yield acquired

    finally:
        # Release lock
        if lock_file and acquired:
            try:
                if sys.platform == "win32" and WINDOWS_LOCKING_AVAILABLE:
                    # Release Windows lock
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                elif sys.platform != "win32" and UNIX_LOCKING_AVAILABLE:
                    # Release Unix lock
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass  # Lock already released or file closed
            finally:
                lock_file.close()


# =============================================================================
# SESSION STATE MANAGEMENT - Multi-terminal isolated, compact-event immune
# =============================================================================


def get_terminal_id() -> str:
    """Get or create a unique terminal identifier.

    Terminal ID is persisted to disk and reused across sessions.
    This enables multi-terminal isolation: each terminal has its own state file.

    Returns:
        String terminal identifier (UUID prefix)
    """
    terminal_id_file = STATE_DIR / "terminal_id"

    # Try to read existing terminal ID
    if terminal_id_file.exists():
        try:
            terminal_id = terminal_id_file.read_text().strip()
            if terminal_id:
                return terminal_id
        except Exception:
            pass

    # Generate new terminal ID
    terminal_id = str(uuid.uuid4())[:8]

    # Persist it
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        terminal_id_file.write_text(terminal_id)
    except Exception:
        pass

    return terminal_id


def get_session_state_path() -> Path:
    """Get the terminal-specific session state file path.

    Uses terminal-scoped state directory per state_paths.py pattern:
    .claude/state/terminals/{terminal_id}/cleanup_session.json
    """
    terminal_id = get_terminal_id()
    # Import here to avoid circular import at module level
    from state_paths import get_terminal_state_path
    return get_terminal_state_path(terminal_id, "cleanup_session.json")


def load_session_state() -> dict:
    """Load session state from terminal-specific disk file.

    This enables:
    - Multi-terminal isolation: each terminal sees only its own state
    - Compact-event immunity: state survives session compaction/restart
    - Stale-data immunity: fresh scan on each run overwrites cached data

    Returns:
        Session state dict with keys: approved_actions, skipped_items,
        current_index, scan_timestamp, violations_snapshot, terminal_id
    """
    state_file = get_session_state_path()

    if not state_file.exists():
        return _empty_session_state()

    try:
        with open(state_file) as f:
            state = json.load(f)

        required_fields = [
            "approved_actions",
            "skipped_items",
            "current_index",
            "scan_timestamp",
            "violations_snapshot",
        ]
        for field in required_fields:
            if field not in state:
                return _empty_session_state()

        return state

    except (json.JSONDecodeError, OSError):
        return _empty_session_state()


def _empty_session_state() -> dict:
    """Return empty session state structure."""
    return {
        "approved_actions": [],
        "skipped_items": [],
        "current_index": 0,
        "scan_timestamp": None,
        "violations_snapshot": [],
        "terminal_id": get_terminal_id(),
    }


def save_session_state(state: dict) -> None:
    """Persist session state to terminal-specific disk file.

    Called after each action to ensure compact-event immunity and
    multi-terminal isolation.

    Args:
        state: Session state dict to persist
    """
    state_file = get_session_state_path()
    state["last_saved"] = datetime.now().isoformat()

    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)
    except OSError:
        pass


def invalidate_session_state(reason: str) -> None:
    """Invalidate session state when scan data may be stale.

    Args:
        reason: Why session state was invalidated
    """
    state_file = get_session_state_path()
    if state_file.exists():
        try:
            stale_path = state_file.with_suffix(".stale")
            state_file.rename(stale_path)
        except OSError:
            try:
                state_file.unlink()
            except OSError:
                pass


def is_session_state_valid(state: dict, violations_count: int) -> bool:
    """Validate that session state is still usable.

    Session state becomes invalid when:
    - Violations count changed (new scan needed)
    - Scan is older than 1 hour (stale data)
    - Terminal ID mismatch (multi-terminal confusion)

    Args:
        state: Session state dict to validate
        violations_count: Current violations count from fresh scan

    Returns:
        True if session state is valid and can be resumed
    """
    if state.get("terminal_id") != get_terminal_id():
        return False

    if len(state.get("violations_snapshot", [])) != violations_count:
        return False

    if state.get("scan_timestamp"):
        try:
            scan_time = datetime.fromisoformat(state["scan_timestamp"])
            age_seconds = (datetime.now() - scan_time).total_seconds()
            if age_seconds > 3600:
                return False
        except (ValueError, TypeError):
            return False

    return True


# =============================================================================
# BUILD ARTIFACT PATTERNS
# =============================================================================


BUILD_ARTIFACT_PATTERNS = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    ".dist",
    "build",
    ".build",
    "*.pyc",
    "*.pyo",
    "*.egg-info",
    ".tox",
    ".venv",
    "venv",
    ".env",
    "node_modules",
    ".next",
    ".nuxt",
    "coverage",
    ".coverage",
    ".coverage*",
    "htmlcov",
}

# Large file threshold (100 MB default)
LARGE_FILE_THRESHOLD_MB = 100
LARGE_FILE_THRESHOLD_BYTES = LARGE_FILE_THRESHOLD_MB * 1024 * 1024

# Windows system folders that should never be flagged as violations
WINDOWS_SYSTEM_FOLDERS = {
    "$RECYCLE.BIN",
    "System Volume Information",
    "RECYCLER",
    "Config.Msi",
    "$WinREAgent",
}


def is_build_artifact(path_str: str) -> tuple[bool, str | None]:
    """Check if path matches a build artifact pattern.

    Args:
        path_str: Path string to check

    Returns:
        (is_artifact, pattern_matched) tuple
    """
    path = Path(path_str)

    # Check directory names and files
    for part in path.parts:
        if part in BUILD_ARTIFACT_PATTERNS:
            # Prefer wildcard pattern if available (e.g., .coverage* over .coverage)
            wildcard_pattern = f"{part}*"
            if wildcard_pattern in BUILD_ARTIFACT_PATTERNS:
                return True, wildcard_pattern
            return True, part

    # Check file extensions with wildcard patterns
    if path.is_file():
        for pattern in BUILD_ARTIFACT_PATTERNS:
            if pattern.startswith("*") and path.match(pattern):
                return True, pattern

    return False, None


def is_large_file(
    path_str: str, threshold_mb: int = LARGE_FILE_THRESHOLD_MB
) -> tuple[bool, int, str]:
    """Check if file exceeds size threshold.

    Args:
        path_str: Path string to check
        threshold_mb: Size threshold in MB (default: 100)

    Returns:
        (is_large, size_mb, size_str) tuple
    """
    path = Path(path_str)

    if not path.exists() or path.is_dir():
        return False, 0, ""

    try:
        size_bytes = path.stat().st_size
        size_mb = size_bytes / (1024 * 1024)

        # Format for display
        if size_mb >= 1:
            size_str = f"{size_mb:.1f} MB"
        else:
            size_kb = size_bytes / 1024
            size_str = f"{size_kb:.0f} KB"

        return size_mb >= threshold_mb, size_mb, size_str
    except Exception:
        # Conservative: treat size check failures as "large" to require confirmation
        # This prevents unexpected processing of potentially large files
        return True, 0, "size check failed (conservative: treating as large)"


def is_symlink_file(path_str: str) -> bool:
    """Check if path is a symlink.

    Args:
        path_str: Path string to check

    Returns:
        True if path is a symlink
    """
    try:
        return Path(path_str).is_symlink()
    except Exception:
        return False


# ============================================================================
# Operational vs Generated Data Classification
# ============================================================================

# Define state paths - try to import from state_paths.py, otherwise use fallback
try:
    from hooks.__lib import state_paths as _state_paths

    # Use imported paths
    STATE_DIR = _state_paths.STATE_DIR
    TERMINALS_DIR = _state_paths.TERMINALS_DIR
    SESSIONS_DIR = _state_paths.SESSIONS_DIR
    SHARED_DIR = _state_paths.SHARED_DIR
except ImportError:
    # Fallback hardcoded paths
    STATE_DIR = Path(os.environ.get("PROJECT_ROOT", ".")) / ".claude" / "state"
    TERMINALS_DIR = STATE_DIR / "terminals"
    SESSIONS_DIR = STATE_DIR / "sessions"
    SHARED_DIR = STATE_DIR / "shared"


# Operational data: source code, user-created content, persistent configuration
_OPERATIONAL_DIRECTORIES = {
    "hooks",  # Source code: runtime hooks
    "skills",  # Source code: agent skills
    "commands",  # Source code: slash command stubs
    "agents",  # Source code: subagent definitions
    "rules",  # Source code: modular rule files
}

# Operational files: user-created configuration and documentation
_OPERATIONAL_FILES = {
    "config.yaml",
    "CLAUDE.md",
    "README.md",
    "settings.json",
    "settings.local.json",
    "SKILL.md",
}

# Generated CACHE patterns: optional tool caches (safe to relocate/delete)
# These are tool-specific artifacts that don't affect Claude Code operation
_GENERATED_CACHE_PATTERNS = {
    ".ruff_cache",  # Ruff linter cache
    ".pytest_cache",  # Pytest cache
    ".mypy_cache",  # MyPy type checker cache
    "__pycache__",  # Python bytecode cache
    ".hypothesis",  # Hypothesis test cache
    ".coverage",  # Coverage.py artifacts
}

# Generated STATE patterns: REQUIRED for Claude Code operation
# These are runtime artifacts that Claude Code depends on - DO NOT move without updating config
_GENERATED_STATE_PATTERNS = {
    "events.db",  # Telemetry database (configured in config.yaml)
    "fallback_events",  # Fallback event storage (configured in config.yaml)
    "event_queue",  # Event queue directory (configured in config.yaml)
    "state",  # state/ directory itself (canonical location for Claude Code runtime data)
    "session_data",  # Session artifacts (may be required for session recovery)
    "session_history",  # Session history (may be required for context restoration)
    "terminals",  # Terminal-specific state (required for multi-terminal coordination)
}


def classify_item(path: Path) -> str:
    """Classify a file/directory with respect to Claude Code operation.

    Three-category classification:
    - operational: Source code, user-created content, persistent configuration
    - generated_state: Runtime artifacts REQUIRED for Claude Code operation
    - generated_cache: Optional tool caches (safe to relocate/delete)
    - unknown: Items that don't fit any category

    The key distinction: generated_state items are configured (e.g., in config.yaml)
    and moving them would break Claude Code. generated_cache items are tool
    artifacts that can be safely relocated or deleted.

    Args:
        path: Path to classify

    Returns:
        "operational" for source code and user content
        "generated_state" for required runtime artifacts (DO NOT MOVE)
        "generated_cache" for optional tool caches (safe to relocate)
        "unknown" for items that don't fit any category
    """
    if not isinstance(path, Path):
        path = Path(path)

    # Get the item name (last part of path)
    name = path.name

    # Check operational directories (source code)
    if name in _OPERATIONAL_DIRECTORIES:
        return "operational"

    # Check operational files (user-created content)
    if name in _OPERATIONAL_FILES:
        return "operational"

    # Check generated STATE patterns (required for Claude Code operation)
    # These are configured paths - moving them breaks the system
    if name in _GENERATED_STATE_PATTERNS:
        return "generated_state"

    # Check generated CACHE patterns (optional tool artifacts)
    # These are tool-specific caches that can be safely relocated
    if name in _GENERATED_CACHE_PATTERNS:
        return "generated_cache"

    # Check for test files (operational - tests are source code)
    if name.startswith("test_") or name.endswith("_test.py") or name.endswith("_test.md"):
        return "operational"

    # Check for backup files (generated cache - temporary artifacts)
    if name.endswith(".backup") or "-backup-" in name.lower() or name.endswith(".bak"):
        return "generated_cache"

    # Default: unknown
    return "unknown"


def get_state_target_path(path: Path) -> Path | None:
    """Get the target path for a generated data item.

    IMPORTANT: Only suggests moves for generated_cache items (optional tool caches).
    generated_state items (required for Claude Code operation) return None.

    Rationale: Moving generated_state items like events.db would break Claude Code
    because their paths are configured in config.yaml. Only tool caches are safe
    to relocate without breaking the system.

    Args:
        path: Path to generated data item

    Returns:
        Target Path for relocation, or None if:
        - Item is operational (no move needed)
        - Item is generated_state (configured, don't move)
        - Item is unknown (no clear target)
    """
    if not isinstance(path, Path):
        path = Path(path)

    classification = classify_item(path)

    # Operational data has no target (no move needed)
    if classification == "operational":
        return None

    # Unknown data has no specific target
    if classification == "unknown":
        return None

    # generated_state items: DO NOT MOVE (configured paths, would break system)
    if classification == "generated_state":
        return None

    # generated_cache items: suggest OS-standard cache locations
    # These are tool-specific caches that can be safely relocated
    if classification == "generated_cache":
        # For tool caches, suggest leaving to tool defaults or OS cache dirs
        # We return None to indicate "use tool defaults" rather than forcing state/
        return None

    # Fallback: should not reach here with current classification logic
    return None


def check_content_conflict(source: str, target: str) -> dict:
    """Check if moving/deleting would cause data loss.

    Args:
        source: Source file/directory path
        target: Target path (for move operations)

    Returns:
        Dictionary with conflict analysis
    """
    source_path = Path(source)
    target_path = Path(target)
    result = {
        "conflict": False,
        "reason": "Safe to proceed",
        "action": "move",  # or "delete" or "skip"
    }

    # Check if source exists FIRST (if no source, nothing to do)
    if not source_path.exists():
        result["reason"] = "Source doesn't exist (will skip)"
        result["action"] = "skip"
        return result

    # Check if target exists
    if not target_path.exists():
        result["reason"] = "Target doesn't exist (safe to create)"
        return result

    # For directories, check if empty
    if source_path.is_dir():
        try:
            contents = list(source_path.iterdir())
            if not contents:
                result["reason"] = "Source directory is empty (safe to delete)"
                result["action"] = "delete"
                return result
        except Exception:
            pass  # Non-critical, continue

    # For files, check size conflict and content difference
    try:
        source_size = source_path.stat().st_size
        target_size = target_path.stat().st_size

        # Target is significantly larger (50%+ threshold)
        if target_size > source_size * 1.5:
            size_diff_pct = ((target_size - source_size) / source_size) * 100
            result["conflict"] = True
            result["reason"] = f"Target has {size_diff_pct:.0f}% more data"
            result["source_size"] = source_size
            result["target_size"] = target_size
            result["action"] = "ask_user"  # Require explicit decision
            return result

        # Source is slightly larger (within 10% threshold)
        if source_size > target_size * 1.1:
            size_diff_pct = ((source_size - target_size) / target_size) * 100
            result["conflict"] = True
            result["reason"] = f"Source has {size_diff_pct:.0f}% more data (stale target)"
            result["source_size"] = source_size
            result["target_size"] = target_size
            result["action"] = "ask_user"
            return result

        # Similar sizes - check if content is actually different
        if source_path.is_file() and target_path.is_file():
            try:
                source_content = source_path.read_text()
                target_content = target_path.read_text()

                if source_content != target_content:
                    result["conflict"] = True
                    result["reason"] = "Target exists with different content"
                    result["action"] = "ask_user"
                    return result
            except Exception:
                pass  # Content comparison failed, proceed with caution

    except Exception:
        pass  # Size check failed, proceed with caution

    # Database-specific warnings
    if source_path.suffix in (".db", ".sqlite", ".sqlite3"):
        result["db_warning"] = True

    # False positive: stdlib imports containing 'data'
    if source_path.suffix in (".py",):
        try:
            with open(source_path, encoding="utf-8") as f:
                content = f.read()
                # Check for 'dataclasses' import (stdlib, not project data/)
                if "from dataclasses import" in content:
                    result["stdlib_warning"] = True
                    result["reason"] = "Standard library import (dataclasses)"
        except Exception:
            pass

    return result


def detect_heuristic_violations(root_path: str = "P:\\\\\\") -> list[dict]:
    r"""Detect junk using heuristics instead of enumerated patterns.

    Categories detected:
    - Path chars in name (:, \, P: prefix)
    - Empty files (0 bytes)
    - Empty directories (0 items)
    - "Move to" stalled operations
    - Placeholder/generic names (test, temp, new, fake, custom, etc.)
    - Backup patterns (.backup, -backup-, .bak)

    Args:
        root_path: Root path to scan

    Returns:
        List of heuristic violations
    """
    root = Path(root_path)
    violations = []

    # Load policy from directory_policy.json (load once, reuse)
    policy_path = Path("P:\\\\\\.claude/hooks/config/directory_policy.json")
    policy_data = {}
    dotfile_check_list = [".coverage"]  # Default fallback
    dotfile_suggestions = {}  # Store suggestions for each dotfile
    allowed_config_files = []
    claude_dir_blocked_patterns = []  # Patterns for junk files in .claude/ directory

    if policy_path.exists():
        try:
            with open(policy_path) as f:
                policy_data = json.load(f)
                dotfile_policy = policy_data.get("workspace_root", {}).get("dotfile_policy", {})
                check_these_dotfiles = dotfile_policy.get("check_these_dotfiles", [])
                for item in check_these_dotfiles:
                    dotfile_check_list.append(item["pattern"])
                    dotfile_suggestions[item["pattern"]] = item.get(
                        "suggestion", "Review this file"
                    )
                allowed_config_files = policy_data.get("workspace_root", {}).get(
                    "allowed_config_files", []
                )
                # Load blocked patterns for .claude/ directory cleanup
                claude_dir = policy_data.get("claude_directory", {})
                blocked_root = claude_dir.get("blocked_root_patterns", {})
                claude_dir_blocked_patterns = blocked_root.get("patterns", [])
        except (OSError, json.JSONDecodeError, KeyError):
            pass  # Use default fallback

    # NEW: Type-based validation to detect whitelist bypass (ADR-20260320 Phase 1)
    # This catches .py files in config whitelist that should be in .claude/hooks/
    if TYPE_VALIDATOR_AVAILABLE and allowed_config_files:
        type_errors = validate_config_whitelist_entries(
            "workspace_root.allowed_config_files", allowed_config_files
        )
        for error in type_errors:
            # Get optimal location suggestion (Phase 2 integration)
            optimal_location = None
            optimal_reason = None
            if LOCATION_OPTIMIZER_AVAILABLE:
                try:
                    location_result = infer_optimal_location(error.file_path)
                    if location_result.get("action") == "move":
                        optimal_location = location_result.get("optimal_location")
                        optimal_reason = location_result.get("reason")
                except Exception:
                    pass  # Graceful fallback if location optimizer fails

            # Create violation for type mismatch
            violation = {
                "type": "TYPE_MISMATCH_CONFIG_WHITELIST",
                "rule": "TYPE_MISMATCH",
                "path": error.file_path,
                "message": (
                    f"{error.actual_type} '{error.file_path}' is in allowed_config_files "
                    f"whitelist but is a {error.expected_type}"
                ),
                "suggestion": error.suggestion,
            }

            # Add optimal location information if available
            if optimal_location:
                violation["optimal_location"] = optimal_location
            if optimal_reason:
                violation["optimal_reason"] = optimal_reason

            # Phase 1 enhancement: If infer_optimal_location returns "keep" (unknown type),
            # use trace_file_references to dynamically determine destination based on
            # consumer distribution. This prevents moving files to wrong locations.
            if optimal_location is None and LOCATION_OPTIMIZER_AVAILABLE:
                try:
                    ref_result = trace_file_references(error.file_path)
                    if ref_result.get("status") == "available" and ref_result.get("recommended_path"):
                        violation["optimal_location"] = ref_result["recommended_path"]
                        violation["optimal_reason"] = ref_result["reason"]
                        violation["consumer_count"] = ref_result.get("consumer_count", 0)
                        violation["dir_breakdown"] = ref_result.get("dir_breakdown", {})
                        violation["multi_purpose"] = ref_result.get("multi_purpose", False)
                except Exception:
                    pass  # Graceful fallback if reference tracing fails

            violations.append(violation)

    # Allowed directories at root (whitelist)
    # Note: tests/ at root is NOT allowed (should be __csf/tests/)
    allowed_dirs = {
        ".claude",
        ".git",
        ".github",
        ".vscode",
        "__csf",
        "__csf.nip",
        "packages",
        "projects",
        "backups",
        "data",
        "docs",
        "research",
        ".staging",
        ".cache",
        ".venv",
        "node_modules",
        ".ruff_cache",
        ".pytest_cache",
    }

    # Orphaned dot-directories that should be flagged as violations
    # These are blocked in directory_policy.json and should not exist at workspace root
    orphaned_dotdirs = {
        ".artifacts",
        ".claude-state",
        ".evidence",
        ".remember",
    }

    # Placeholder/generic name patterns
    placeholder_names = {
        "test",
        "tests",
        "temp",
        "new",
        "new_directory",
        "fake",
        "custom",
        "output",
        "current",
        "nonexistent",
        "random",
        "stuff",
        "files",
        "misc",
        "other",
        "work",
        "workspace",
    }

    try:
        for item in root.iterdir():
            # Skip allowed directories
            if item.is_dir() and item.name in allowed_dirs:
                continue

            # Skip hidden files/dirs (except those in dotfile_check_list from policy
            # and orphaned dotdirs that should be flagged as violations)
            if item.name.startswith(".") and item.name not in dotfile_check_list and item.name not in orphaned_dotdirs:
                continue

            item_name = item.name.lower()

            # Check: Dotfiles in check_these_dotfiles that aren't in allowed_config_files
            if (
                item.name.startswith(".")
                and item.name in dotfile_check_list
                and item.name not in allowed_config_files
            ):
                suggestion = dotfile_suggestions.get(item.name, "Move to appropriate location")
                violations.append(
                    {
                        "type": "DOTFILE_VIOLATION",
                        "rule": "DOTFILE_VIOLATION",
                        "path": str(item),
                        "message": f"Dotfile '{item.name}' at workspace root is not in allowed_config_files",
                        "suggestion": suggestion,
                    }
                )
                continue

            # Check: Orphaned dot-directories (blocked in directory_policy.json)
            if item.is_dir() and item.name in orphaned_dotdirs:
                violations.append(
                    {
                        "type": "BLOCKED_ROOT_DIRECTORY",
                        "rule": "ORPHANED_DOTDIR",
                        "path": str(item),
                        "message": f"Orphaned dot-directory '{item.name}' — should be deleted (canonical location is .claude/.claude-state/)",
                        "suggestion": f"Delete P:\\\\\\{item.name}/ — these directories are now blocked in directory_policy.json",
                    }
                )
                continue

            # Check: Unknown config files at root (not in whitelist)
            # This catches files like SPECS.md, listdisk.txt that aren't explicitly allowed
            if item.is_file() and item.name not in allowed_config_files:
                violations.append(
                    {
                        "type": "UNKNOWN_CONFIG_FILE",
                        "rule": "UNKNOWN_CONFIG_FILE",
                        "path": str(item),
                        "message": f"File '{item.name}' at workspace root is not in allowed_config_files",
                        "suggestion": "Move to appropriate location (docs/, __csf/data/, etc.) or add to allowed_config_files if needed at root",
                    }
                )
                continue

            # Check: Git worktrees and nested git repos at root
            # Git worktrees have .git as a FILE (not directory)
            # Nested git repos have .git as a DIRECTORY with remotes
            if item.is_dir() and not item.name.startswith("."):
                git_dir = item / ".git"
                if git_dir.exists():
                    # Determine if this is a worktree or a nested repo
                    if git_dir.is_file():
                        # .git is a file = worktree pointer OR bare repo
                        # Verify it's actually a worktree (contains "gitdir:" pointing to worktrees)
                        try:
                            gitdir_content = git_dir.read_text(
                                encoding="utf-8", errors="ignore"
                            ).strip()
                            if gitdir_content.startswith("gitdir:"):
                                # Extract the gitdir path from "gitdir: /path/to/..."
                                gitdir_path_str = gitdir_content[len("gitdir:") :].strip()
                                gitdir_path = Path(gitdir_path_str)

                                # Verify the referenced gitdir path actually exists
                                # If it doesn't exist, this is likely a synthetic/fake .git file
                                if not gitdir_path.exists():
                                    # Synthetic .git file - don't flag as violation
                                    continue

                                if "worktrees" in gitdir_content:
                                    # This is a legitimate git worktree
                                    violations.append(
                                        {
                                            "type": "WORKTREE_AT_ROOT",
                                            "rule": "UNAUTHORIZED_ROOT_DIRECTORY",
                                            "path": str(item),
                                            "message": f"Git worktree '{item.name}' at workspace root",
                                            "suggestion": "Worktrees should be in .claude/worktrees/ or another designated directory, not at workspace root.",
                                        }
                                    )
                                    continue
                                else:
                                    # .git is a file with gitdir: but no worktrees = bare repo (not worktree)
                                    # Bare repository at root - not a worktree but still violates policy
                                    violations.append(
                                        {
                                            "type": "DETACHED_GIT_REPO",
                                            "rule": "DETACHED_GIT_REPO",
                                            "path": str(item),
                                            "message": f"Bare git repository '{item.name}' at workspace root",
                                            "suggestion": "Move to packages/ if part of monorepo, or move outside P:\\\\\\ if external reference.",
                                        }
                                    )
                                    continue
                            # .git is a file but not a worktree pointer - could be a synthetic/fake .git
                            # Don't flag as violation - synthetic .git files are not worktrees or repos
                        except (OSError, UnicodeDecodeError):
                            pass
                    elif git_dir.is_dir():
                        # .git is a directory = regular git repo (nested repo)
                        git_config = git_dir / "config"
                        if git_config.exists():
                            try:
                                config_content = git_config.read_text(
                                    encoding="utf-8", errors="ignore"
                                )
                                # Has remote "url" = external/nested repo (not the main P:\\\\\\.git)
                                if "remote" in config_content and "url" in config_content:
                                    violations.append(
                                        {
                                            "type": "DETACHED_GIT_REPO",
                                            "rule": "DETACHED_GIT_REPO",
                                            "path": str(item),
                                            "message": f"Git repository '{item.name}' at workspace root (nested repo)",
                                            "suggestion": "Move to packages/ if part of monorepo, or move outside P:\\\\\\ if external reference. Git repos create confusion when nested at workspace root.",
                                        }
                                    )
                                    continue
                            except (OSError, UnicodeDecodeError):
                                pass

            # Check: Directories at root not in required_directories policy
            # Only folders explicitly allowed by workspace_root.required_directories should be at root
            if item.is_dir() and not item.name.startswith("."):
                # Skip Windows system folders
                if item.name in WINDOWS_SYSTEM_FOLDERS:
                    continue

                # Skip user home directory artifacts that should never be in workspace root
                if item.name == "Users":
                    violations.append(
                        {
                            "type": "UNAUTHORIZED_ROOT_DIRECTORY",
                            "rule": "UNAUTHORIZED_ROOT_DIRECTORY",
                            "path": str(item),
                            "message": "Directory 'Users' at workspace root is a user home artifact - should never be in P:\\\\\\",
                            "suggestion": "Delete - user home directories do not belong in workspace root",
                        }
                    )
                    continue

                # Load policy to get allowed_root_patterns
                try:
                    policy_path = root / ".claude" / "hooks" / "config" / "directory_policy.json"
                    if policy_path.exists():
                        policy = json.loads(policy_path.read_text(encoding="utf-8"))
                        allowed_patterns = policy.get("workspace_root", {}).get(
                            "allowed_root_patterns", []
                        )
                        allowed_root_dirs = {d.get("pattern", d) for d in allowed_patterns}

                        # Check if this directory is in the allowed list
                        if item.name not in allowed_root_dirs:
                            violations.append(
                                {
                                    "type": "UNAUTHORIZED_ROOT_DIRECTORY",
                                    "rule": "UNAUTHORIZED_ROOT_DIRECTORY",
                                    "path": str(item),
                                    "message": f"Directory '{item.name}' at workspace root is not in required_directories policy",
                                    "suggestion": "Move to appropriate location: packages/ if a library, projects/ if active work, __csf/data/ for data, or delete if obsolete",
                                }
                            )
                            continue
                except Exception:
                    pass  # Policy read failed, skip this check

            # Check 1: Path chars in name (Windows issues)
            # Detect both ASCII colon and Unicode lookalike colon (\uf03a)
            has_path_chars = (
                ":" in item.name
                or "\\" in item.name
                or "\uf03a" in item.name  # Unicode colon lookalike
                or item.name.startswith("P:")
                or (
                    item.name.startswith("P")
                    and len(item.name) > 1
                    and item.name[1] in (":", "\uf03a")
                )
            )
            if has_path_chars:
                violations.append(
                    {
                        "type": "HEURISTIC_PATH_CHARS",
                        "path": str(item),
                        "message": "Name contains path characters or P: prefix (including Unicode lookalikes)",
                        "suggestion": "Rename to proper filename (this looks like copy/paste error)",
                    }
                )
                continue

            # Check 2: "Move to" stalled operations
            if item.name.startswith("Move to") or item.name.startswith("move to"):
                violations.append(
                    {
                        "type": "HEURISTIC_STALE_MOVE",
                        "path": str(item),
                        "message": "Stale 'Move to' operation - cleanup was never completed",
                        "suggestion": "Complete the move operation or delete this",
                    }
                )
                continue

            # Check 3: Backup patterns
            if (
                item.name.endswith(".backup")
                or "-backup-" in item.name.lower()
                or item.name.endswith(".bak")
                or item.name.endswith(".old")
            ):
                violations.append(
                    {
                        "type": "HEURISTIC_BACKUP",
                        "path": str(item),
                        "message": "Backup file at root - belongs in backups/ or should be deleted",
                        "suggestion": "Move to backups/ or delete if obsolete",
                    }
                )
                continue

            # Check 4: Empty file
            if item.is_file() and item.stat().st_size == 0:
                violations.append(
                    {
                        "type": "HEURISTIC_EMPTY_FILE",
                        "path": str(item),
                        "message": "Empty file (0 bytes) - likely junk",
                        "suggestion": "Delete this file",
                    }
                )
                continue

            # Check 5: Empty directory
            if item.is_dir():
                try:
                    contents = list(item.iterdir())
                    if len(contents) == 0:
                        violations.append(
                            {
                                "type": "HEURISTIC_EMPTY_DIR",
                                "path": str(item),
                                "message": "Empty directory - no content",
                                "suggestion": "Delete this directory",
                            }
                        )
                        continue
                except PermissionError:
                    pass

            # Check 5.5: Misplaced test directories at root
            # Tests should be co-located with code (e.g., __csf/tests/)
            # A bare tests/ at root is usually a backup or migration artifact
            if item.name == "tests":
                violations.append(
                    {
                        "type": "HEURISTIC_MISPLACED_TESTS",
                        "path": str(item),
                        "message": "Test directory at root should be in __csf/tests/ (tests belong with their code)",
                        "suggestion": "Delete if this is a backup/migration artifact, or move to __csf/tests/ if active",
                    }
                )
                continue

            # Check 6: Placeholder/generic names
            if item_name in placeholder_names:
                violations.append(
                    {
                        "type": "HEURISTIC_PLACEHOLDER",
                        "path": str(item),
                        "message": f"Generic placeholder name '{item.name}' - not descriptive",
                        "suggestion": "Rename to meaningful name or delete if unused",
                    }
                )
                continue

            # Check 7: Analysis/report files at root
            if item.is_file() and item.suffix == ".md":
                name_without_ext = item.stem.lower()
                if any(
                    keyword in name_without_ext
                    for keyword in [
                        "analysis",
                        "report",
                        "summary",
                        "plan",
                        "debug",
                        "research",
                        "findings",
                        "audit",
                        "investigation",
                    ]
                ):
                    violations.append(
                        {
                            "type": "HEURISTIC_ANALYSIS_FILE",
                            "path": str(item),
                            "message": "Analysis/report file at root - belongs in docs/ or reports/",
                            "suggestion": "Move to docs/ or reports/",
                        }
                    )
                    continue

            # Check 8: Test files at root (should be in tests/)
            if item.is_file():
                name_lower = item.name.lower()
                name_stem = item.stem.lower()  # filename without extension
                # Match: test_*, test1.*, *_test.*, test*.py, test*.md, test*.txt, test*.json
                is_test_file = (
                    name_lower.startswith("test_")
                    or name_lower.endswith("_test.py")
                    or name_lower.endswith("_test.md")
                    or name_lower.endswith("_test.txt")
                    or name_lower.endswith("_test.json")
                    or
                    # test1.json, test_data.txt, etc.
                    (name_stem.startswith("test") and any(c.isdigit() for c in name_stem))
                )
                if is_test_file:
                    violations.append(
                        {
                            "type": "HEURISTIC_TEST_FILE",
                            "path": str(item),
                            "message": f"Test file '{item.name}' at root - belongs in tests/",
                            "suggestion": "tests/{filename}",
                        }
                    )
                    continue

            # Check 9: Log files at root (should be in logs/)
            if item.is_file() and item.suffix == ".log":
                violations.append(
                    {
                        "type": "HEURISTIC_LOG_FILE",
                        "path": str(item),
                        "message": f"Log file '{item.name}' at root - belongs in logs/",
                        "suggestion": "logs/{filename}",
                    }
                )
                continue

    except PermissionError as e:
        violations.append(
            {
                "type": "HEURISTIC_ERROR",
                "path": str(root),
                "message": f"Permission error scanning root: {e}",
                "suggestion": "Run as administrator or check permissions",
            }
        )

    return violations


def detect_internal_violations(
    root_path: str = "P:\\\\\\", claude_dir_blocked_patterns: list = None, claude_dir_allowed_subdirs: list = None
) -> list[dict]:
    r"""Detect junk inside authorized directories.

    Scans inside authorized directories like .claude/ for junk patterns:
    - Cache directories: .mypy_cache/, .pytest_cache/, .ruff_cache/
    - Backup files: *.backup, *-backup-*, .bak
    - Duplicate databases: *.db.backup, *.db.old
    - Nested duplicate structures (e.g., .claude/.claude/)

    Skips Claude Code v2.1.78 authorized directories and files.

    Args:
        root_path: Root path to scan

    Returns:
        List of internal violations
    """
    root = Path(root_path)
    violations = []

    # Check: enforce claude_directory.allowed_subdirectories from policy
    # Any top-level .claude/ directory not in the policy list is a violation
    if claude_dir_allowed_subdirs is not None:
        claude_dir = root / ".claude"
        if claude_dir.exists() and claude_dir.is_dir():
            # Build set of allowed top-level directory names from policy
            allowed_top_level = set()
            for entry in claude_dir_allowed_subdirs:
                path = entry.get("path", entry) if isinstance(entry, dict) else entry
                top_level = path.split("/")[0]  # "hooks/.state" -> "hooks"
                allowed_top_level.add(top_level)

            for item in claude_dir.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    if item.name not in allowed_top_level:
                        violations.append(
                            {
                                "type": "UNAUTHORIZED_CLAUDE_SUBDIR",
                                "rule": "CLAUDE_DIRECTORY_ALLOWED_SUBDIRS",
                                "path": str(item),
                                "message": f"Directory '{item.name}' in .claude/ is not in allowed_subdirectories policy",
                                "suggestion": "DELETE if not needed (policy changes require explicit user approval)",
                            }
                        )

    # Claude Code v2.1.78 authorized directories (these are created by Claude Code and should NOT be flagged)
    claude_code_authorized_dirs = {
        # Core functionality directories
        "hooks",
        "commands",
        "skills",
        "agents",
        # Runtime storage
        "state",
        "logs",
        "cache",
        "memory",
        # Data management
        "backups",
        "checkpoints",
        "file-history",
        # Working directories
        "data",
        "evidence",
        "debug",
        "ide",
        # Integration directories
        "cross_session_tracker",
        "cross_session_vectors",
        "completed",
        "event_queue",
        "fallback_events",
        "enhanced_cache",
        "downloads",
        "agent-memory",
        # Other runtime directories
        "__pycache__",
        ".benchmarks",
        ".cks",
        ".daemon_state",
        ".evidence",
        ".hypothesis",
        ".locks",
        ".staging",
        ".venv",
        ".ruff_cache",
        ".pytest_cache",
        "claude",
        "cognitive",
        "config",
        "arch_decisions",
        "arch_reviews",
        "artifacts",
        "audit",
        "_archive",
    }

    # Claude Code v2.1.78 authorized files (created by Claude Code, should NOT be flagged)
    claude_code_authorized_files = {
        # Configuration files
        "settings.json",
        "settings.local.json",
        ".credentials.json",
        ".mcp.json",
        ".notification_cooldowns.json",
        ".notification_state.json",
        # State and history files
        "history.jsonl",
        "history.jsonl.old",
        "history_faiss_index.bin",
        "events.db",
        "events.db.backup",
        # Documentation
        "CLAUDE.md",
        "README.md",
        # Other runtime files
        "context_debug.json",
        "gap_monitor_state.json",
        "hint_state.json",
        "llm-api-health.json",
        "llm-api-models.json",
        "llm-api-performance.jsonl",
        "model_debug.json",
        "mcp-needs-auth-cache.json",
        "notifications.json",
        "audit.log",
        "chutes_usage.json",
        # Project files (user-created, not Claude Code)
        "AGENTS.md",
        ".gitignore",
        "config.yaml",
        "architectural_pillars.yaml",
        # Analysis/documentation files
        "*.md",  # Allow all markdown files in .claude/
    }

    # Authorized directories to scan internally
    internal_scan_dirs = {
        ".claude": {
            "cache_patterns": [],  # Cache dirs are now authorized
            "backup_patterns": ["*.backup", "*-backup-*", "*.bak"],
            "db_backup_patterns": ["*.db.backup", "*.db.old"],
            "nested_duplicates": [".claude"],  # .claude/.claude/ is nested duplicate
            "authorized_dirs": claude_code_authorized_dirs,
            "authorized_files": claude_code_authorized_files,
        }
    }

    # Scan each authorized directory
    for scan_dir_name, patterns in internal_scan_dirs.items():
        scan_dir = root / scan_dir_name
        if not scan_dir.exists() or not scan_dir.is_dir():
            continue

        authorized_dirs = patterns.get("authorized_dirs", set())
        authorized_files = patterns.get("authorized_files", set())

        try:
            # Scan recursively for junk patterns
            for item in scan_dir.rglob("*"):
                # Get relative path from scan_dir for better checking
                try:
                    rel_path = item.relative_to(scan_dir)
                except ValueError:
                    # Can't make relative (different drive), skip
                    continue

                # Check: blocked patterns from directory_policy.json (e.g., nul, hooks", tmpclaude-*-cwd)
                # Note: special files (nul, hooks") exist but Path.is_file() returns False, so check exists()
                if claude_dir_blocked_patterns and (item.is_file() or item.exists()):
                    for blocked in claude_dir_blocked_patterns:
                        import fnmatch
                        if fnmatch.fnmatch(item.name, blocked["pattern"]):
                            violations.append(
                                {
                                    "type": "BLOCKED_JUNK_FILE",
                                    "rule": "POLICY_BLOCKED",
                                    "path": str(item),
                                    "message": blocked.get("reason", f"File '{item.name}' is blocked by policy"),
                                    "suggestion": blocked.get("action", "DELETE").upper() + " if confirmed junk",
                                }
                            )
                            break

                # Skip authorized directories
                if item.is_dir():
                    if item.name in authorized_dirs or any(
                        part in authorized_dirs for part in rel_path.parts
                    ):
                        continue

                    # Check for nested duplicate structures
                    if item.name in patterns.get("nested_duplicates", []):
                        # Check if this is actually a nested duplicate (parent has same name)
                        if item.parent.name == scan_dir_name:
                            violations.append(
                                {
                                    "type": "NESTED_DUPLICATE",
                                    "rule": "NESTED_DUPLICATE",
                                    "path": str(item),
                                    "message": f"Nested duplicate structure {scan_dir_name}/{item.name}/",
                                    "suggestion": f"Review contents and delete if duplicate of {scan_dir_name}/",
                                }
                            )
                            continue

                # Skip authorized files
                if item.is_file():
                    # Check if filename matches any authorized file pattern
                    if item.name in authorized_files:
                        continue

                    # Check if file is in an authorized directory
                    if any(
                        part in authorized_dirs for part in rel_path.parts[:-1]
                    ):  # Skip parent dirs
                        continue

                    # Check for backup files (only if not in authorized backups/ directory)
                if item.is_file() and "backups" not in rel_path.parts:
                    for backup_pattern in patterns.get("backup_patterns", []):
                        if item.match(backup_pattern):
                            violations.append(
                                {
                                    "type": "INTERNAL_BACKUP_FILE",
                                    "rule": "INTERNAL_BACKUP_FILE",
                                    "path": str(item),
                                    "message": f"Backup file '{item.name}' inside {scan_dir_name}/",
                                    "suggestion": "Delete if obsolete, or move to backups/ if needed",
                                }
                            )
                            break

                # Check for database backups (only if not in authorized backups/ directory)
                if item.is_file() and "backups" not in rel_path.parts:
                    for db_pattern in patterns.get("db_backup_patterns", []):
                        if item.match(db_pattern):
                            violations.append(
                                {
                                    "type": "INTERNAL_DB_BACKUP",
                                    "rule": "INTERNAL_DB_BACKUP",
                                    "path": str(item),
                                    "message": f"Database backup '{item.name}' inside {scan_dir_name}/",
                                    "suggestion": "Delete if obsolete, or move to backups/ if needed",
                                }
                            )
                            break

        except PermissionError:
            break

        except PermissionError as e:
            violations.append(
                {
                    "type": "INTERNAL_SCAN_ERROR",
                    "path": str(scan_dir),
                    "message": f"Permission error scanning {scan_dir_name}: {e}",
                    "suggestion": "Run as administrator or check permissions",
                }
            )

    return violations


def run_validator(root_path: str = "P:\\\\\\", max_files: int = 50) -> dict:
    """Run path_validator and return results.

    Args:
        root_path: Root path to validate
        max_files: Maximum violations to return

    Returns:
        Dictionary with validation results
    """
    hooks_dir = Path(root_path) / ".claude" / "hooks"

    # Add hooks directory to path for imports
    sys.path.insert(0, str(hooks_dir))

    if not hooks_dir.exists():
        return {
            "summary": {"violation_count": 0, "warning_count": 0},
            "violations": [],
            "error": f"Hooks directory not found: {hooks_dir}",
        }

    # Add hooks directory to path
    hooks_dir_str = str(hooks_dir)
    if hooks_dir_str not in sys.path:
        sys.path.insert(0, hooks_dir_str)

    try:
        # Import path_validator from __lib package (hooks directory already in sys.path)
        from __lib.path_validator import DirectoryPolicy, DirectoryValidator

        policy = DirectoryPolicy()
        validator = DirectoryValidator(policy)
        results = validator.validate_workspace(root_path)

        # Limit violations if requested
        violations = results.get("violations", [])
        if max_files and len(violations) > max_files:
            results["violations"] = violations[:max_files]
            results["summary"]["total_violations"] = len(violations)
            results["summary"]["showing"] = max_files

        return results

    except ImportError as e:
        return {
            "summary": {"violation_count": 0, "warning_count": 0},
            "violations": [],
            "error": f"Could not import path_validator: {e}",
        }


# Domain classification for violations
# Maps violation types and paths to semantic domains for better organization


def classify_violation(v: dict) -> tuple[str, str | None]:
    """Classify a violation into a domain and subdomain.

    Args:
        v: Violation dictionary with 'type' and 'path' keys

    Returns:
        (domain, subdomain) tuple
    """
    vtype = v.get("type", "")
    path = Path(v.get("path", ""))

    # Domain 1: Claude Code Runtime Artifacts
    # Misplaced .claude infrastructure that should be in P:\\\\\\.claude/
    if vtype == "BLOCKED_ROOT_DIRECTORY" and "__csf\\.claude" in str(path):
        return "Claude Code Runtime", "Misplaced infrastructure"

    if ".claude" in str(path):
        name = path.name
        if name == "agents":
            return "Claude Code Runtime", "Skills/Agents"
        if name == "hooks":
            return "Claude Code Runtime", "Hooks"
        if name == "plans":
            return "Claude Code Runtime", "Plans"
        return "Claude Code Runtime", None

    # Domain 2: Temporary/Transient Files
    if vtype in ("BLOCKED_ROOT_DIRECTORY", "UNAUTHORIZED_ROOT_DIRECTORY") and path.name == "temp":
        return "Temporary Files", None

    if vtype == "BLOCKED_ROOT_FILE" and path.name.startswith("test_"):
        return "Temporary Files", "Test evidence"

    # Domain 3: Plan Documentation
    if vtype == "UNKNOWN_CONFIG_FILE" and path.name.startswith("plan"):
        return "Plan Documentation", None

    # Domain 4: Test Files
    # Catches: test_*.py, test_*.txt, *_test.py, and test directories
    path_lower = str(path).lower()
    path_name_lower = path.name.lower()

    # Check for test indicators in name or path
    is_test_file = (
        "test" in path_name_lower
        or path_name_lower.startswith("test_")
        or path_name_lower.endswith("_test.py")
        or path_name_lower.endswith("_test.txt")
    )

    # Check for test directory indicators
    is_test_dir = (
        path_name_lower in ("tests", "test", "__tests__")
        or "/tests/" in path_lower
        or "/test/" in path_lower
        or "\\tests\\" in path_lower
        or "\\test\\" in path_lower
    )

    if is_test_file or is_test_dir:
        if path.suffix == ".txt":
            return "Test Files", "Test evidence/data"
        if path.suffix == ".py":
            return "Test Files", "Test code"
        if path.is_dir():
            return "Test Files", "Test directory"
        return "Test Files", None

    # Domain 6: Whitelist Bypass (Type Mismatch)
    # Python modules or wrong file types in config whitelist
    if vtype == "TYPE_MISMATCH_CONFIG_WHITELIST":
        return "Whitelist Bypass", "File type mismatch in config whitelist"

    # Domain 7: Project/Workspace Roots
    # Directories at root that need inspection to determine purpose
    if vtype == "UNAUTHORIZED_ROOT_DIRECTORY":
        name = path.name.lower()
        # Known project directories
        if name in ("memory", "custom", "claude"):
            return "Project Roots", f"Inspect: {path.name}"
        if name in ("nonexistent", "root"):
            return "Project Roots", "Potentially stale - inspect"
        return "Project Roots", None

    # Default: Other
    return "Other", None


def group_violations_by_domain(violations: list[dict]) -> dict[str, list[dict]]:
    """Group violations by domain for organized display.

    Args:
        violations: List of violation dictionaries

    Returns:
        Dict mapping domain names to lists of violations
    """
    domains = {}
    for v in violations:
        domain, subdomain = classify_violation(v)
        if domain not in domains:
            domains[domain] = []
        domains[domain].append(v)
    return domains


def inspect_directory_status(dir_path: str) -> dict:
    """Inspect a directory to determine if it's active, stale, or abandoned.

    Args:
        dir_path: Path to directory to inspect

    Returns:
        Dict with status and metadata:
        - status: "active" | "stale" | "abandoned" | "empty"
        - file_count: Number of files in directory
        - newest_file_age_days: Age of newest file in days
        - oldest_file_age_days: Age of oldest file in days
        - total_size_mb: Total size in MB
    """
    from datetime import datetime, timezone

    result = {
        "status": "unknown",
        "file_count": 0,
        "newest_file_age_days": None,
        "oldest_file_age_days": None,
        "total_size_mb": 0,
    }

    try:
        path = Path(dir_path)
        if not path.exists() or not path.is_dir():
            result["status"] = "nonexistent"
            return result

        # Get all files recursively
        files = list(path.rglob("*"))
        files = [f for f in files if f.is_file()]

        if not files:
            result["status"] = "empty"
            return result

        result["file_count"] = len(files)

        # Get file stats
        now = datetime.now(timezone.utc)
        mtimes = []
        total_size = 0

        for f in files:
            try:
                stat = f.stat()
                mtimes.append(stat.st_mtime)
                total_size += stat.st_size
            except Exception:
                pass

        if not mtimes:
            result["status"] = "empty"
            return result

        # Calculate ages
        newest_mtime = max(mtimes)
        oldest_mtime = min(mtimes)
        result["newest_file_age_days"] = (now.timestamp() - newest_mtime) / 86400
        result["oldest_file_age_days"] = (now.timestamp() - oldest_mtime) / 86400
        result["total_size_mb"] = total_size / (1024 * 1024)

        # Determine status based on file ages
        # Active: Modified within last 30 days
        # Stale: Modified 30-365 days ago
        # Abandoned: Modified >365 days ago
        if result["newest_file_age_days"] < 30:
            result["status"] = "active"
        elif result["newest_file_age_days"] < 365:
            result["status"] = "stale"
        else:
            result["status"] = "abandoned"

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    return result


def generate_recommended_actions(domain: str, violations: list[dict]) -> list[str]:
    """Generate recommended next steps for a domain.

    Args:
        domain: Domain name
        violations: List of violations in this domain

    Returns:
        List of recommended action strings
    """
    actions = []

    if domain == "Claude Code Runtime":
        actions.append("Move __csf\\.claude → P:\\\\\\\.claude\\ (infrastructure fix)")
        actions.append("Verify .claude/agents/ and .claude/hooks/ are correctly placed")

    elif domain == "Temporary Files":
        actions.append("Delete empty temp/ directories")
        actions.append("Move non-empty temp/ to __csf/temp/ if active work exists")
        actions.append("Review test_*.txt files - delete if obsolete evidence")

    elif domain == "Plan Documentation":
        actions.append("Move active plan*.md files to P:\\\\\\\.claude\\plans\\")
        actions.append("Archive completed plans to P:\\\\\\\.claude\\plans\\archive\\")
        actions.append("Or: Add to allowed_config_files if needed at root")

    elif domain == "Test Files":
        actions.append("Move test evidence (*.txt) to __csf\\tests\\fixtures\\ or delete")
        actions.append("Move test code (*.py) to __csf\\tests\\ or alongside source")

    elif domain == "Project Roots":
        # Special case: Users directory is always deleted (user home artifact, never valid in workspace)
        users_dirs = [v for v in violations if "Users" in v.get("path", "")]
        if users_dirs:
            actions.append("🗑️ DELETE (user home artifact): Users - user home directories do not belong in workspace root")

        # Automatic inspection of each remaining directory
        paths = [v["path"] for v in violations if "Users" not in v.get("path", "")]

        # Group by status after inspection
        active_dirs = []
        stale_dirs = []
        abandoned_dirs = []
        empty_dirs = []
        error_dirs = []

        for dir_path in paths:
            status_info = inspect_directory_status(dir_path)
            status = status_info.get("status", "unknown")
            dir_name = Path(dir_path).name

            if status == "active":
                active_dirs.append((dir_name, status_info))
            elif status == "stale":
                stale_dirs.append((dir_name, status_info))
            elif status == "abandoned":
                abandoned_dirs.append((dir_name, status_info))
            elif status == "empty":
                empty_dirs.append((dir_name, status_info))
            else:
                error_dirs.append((dir_name, status_info))

        # Generate specific actions based on inspection results
        if active_dirs:
            names = ", ".join(d[0] for d in active_dirs[:3])
            if len(active_dirs) > 3:
                names += f" + {len(active_dirs) - 3} more"
            actions.append(f"✓ KEEP (active): {names}")

        if stale_dirs:
            names = ", ".join(d[0] for d in stale_dirs[:3])
            if len(stale_dirs) > 3:
                names += f" + {len(stale_dirs) - 3} more"
            actions.append(f"⚠ REVIEW (stale): {names} - Archive or delete if no longer needed")

        if abandoned_dirs:
            names = ", ".join(d[0] for d in abandoned_dirs[:3])
            if len(abandoned_dirs) > 3:
                names += f" + {len(abandoned_dirs) - 3} more"
            actions.append(f"🗑️ DELETE (abandoned): {names} - No activity in >1 year")

        if empty_dirs:
            names = ", ".join(d[0] for d in empty_dirs[:3])
            if len(empty_dirs) > 3:
                names += f" + {len(empty_dirs) - 3} more"
            actions.append(f"🗑️ DELETE (empty): {names}")

        if error_dirs:
            names = ", ".join(d[0] for d in error_dirs[:3])
            if len(error_dirs) > 3:
                names += f" + {len(error_dirs) - 3} more"
            actions.append(f"⚠️ INSPECT MANUALLY (error): {names}")

        if not actions:
            actions.append("No project root violations found")

    else:
        actions.append("Review violations and determine appropriate action")

    return actions


def format_violation(v: dict) -> str:
    """Format a violation for display."""
    lines = []

    # Normalize path for display (Windows compatibility)
    display_path = v["path"]
    if display_path:
        try:
            # Normalize path separators and case for consistent display
            display_path = str(Path(display_path))
        except Exception:
            display_path = v["path"]  # Fallback to original

    lines.append(f"  [{v['type']}] {display_path}")
    lines.append(f"    {v['message']}")

    # Add optimal location suggestion (Phase 2 integration)
    if v.get("optimal_location") and v.get("optimal_location") != display_path:
        lines.append(f"    📍 Optimal location: {v['optimal_location']}")
        if v.get("optimal_reason"):
            lines.append(f"       Reason: {v['optimal_reason']}")

    # Add symlink warning if available
    if v.get("is_symlink"):
        lines.append(f"    🔗 Symlink detected → {v.get('symlink_target', 'unknown')}")
        lines.append("       Will NOT follow symlink automatically")

    # Add large file warning if available
    if v.get("is_large"):
        lines.append(f"    ⚠️  Large file: {v.get('file_size', 'unknown')}")
        lines.append("       Review before action")

    # Add build artifact warning if available
    if v.get("is_build_artifact"):
        lines.append(f"    🧱 Build artifact detected: {v.get('artifact_pattern', 'unknown')}")

    # Add conflict information if available
    if v.get("conflict"):
        lines.append(f"    ⚠️  {v['conflict']}")
    if v.get("source_size"):
        lines.append(f"       Source: {v['source_size']} bytes")
    if v.get("target_size"):
        lines.append(f"       Target: {v['target_size']} bytes")
    if v.get("db_warning"):
        lines.append("    ⚠️  Database file - special handling recommended")

    # Add reference warning if available
    if v.get("reference_warning"):
        lines.append(f"    {v['reference_warning']}")
        if v.get("reference_files"):
            # Show first few files that reference this directory
            files_to_show = v["reference_files"][:3]
            for ref_file in files_to_show:
                # Make path relative for cleaner display
                try:
                    rel_path = Path(ref_file).relative_to(Path("P:\\\\\\"))
                    lines.append(f"       • {rel_path}")
                except Exception:
                    lines.append(f"       • {ref_file}")
            if len(v["reference_files"]) > 3:
                lines.append(f"       ... and {len(v['reference_files']) - 3} more")
            lines.append("       ⚠️  Review before deleting - actively referenced!")

    if v.get("suggestion"):
        lines.append(f"    → {v['suggestion']}")

    return "\n".join(lines)


def display_violations(results: dict, show_all: bool = False) -> None:
    """Display violations grouped by domain with recommended next steps.

    Args:
        results: Validation results from run_validator
        show_all: If True, show all violations; otherwise limit to 20

    """
    violations = results.get("violations", [])
    if not violations:
        print("✅ No violations found!")
        return

    summary = results.get("summary", {})
    total = summary.get("total_violations", len(violations))

    # Group violations by domain
    domains = group_violations_by_domain(violations)

    print(f"\n{'=' * 60}")
    print(f"Found {total} filesystem violations")
    print(f"Organized by {len(domains)} domain{'s' if len(domains) != 1 else ''}")
    print(f"{'=' * 60}\n")

    # Display violations by domain
    domain_num = 0
    for domain_name, domain_violations in sorted(domains.items()):
        domain_num += 1
        print(f"📦 Domain {domain_num}: {domain_name}")
        print(f"   Violations: {len(domain_violations)}")
        print()

        # Show each violation in this domain
        for i, v in enumerate(domain_violations[:5], 1):  # Limit to 5 per domain for readability
            print(f"   {i}. {format_violation(v)}")
            print()

        if len(domain_violations) > 5:
            print(f"   ... and {len(domain_violations) - 5} more in this domain")
            print()

    # Display recommended next steps
    print("\n" + "=" * 60)
    print("Recommended Next Steps")
    print("=" * 60 + "\n")

    step_num = 1

    for domain_name, domain_violations in sorted(domains.items()):
        actions = generate_recommended_actions(domain_name, domain_violations)

        print(f"{step_num} ({domain_name})")
        action_idx = 0
        for action in actions:
            action_letter = chr(ord("a") + action_idx)
            print(f"   {step_num}{action_letter}: {action}")
            action_idx += 1
        step_num += 1
        print()

    print("0 - Do ALL recommended next steps (interactive)")
    print()


def find_import_references(file_path: str, search_root: str = "P:\\\\\\__csf") -> list[str]:
    """Search for imports referencing the target file using CDS backend.

    Args:
        file_path: File being moved (e.g., 'P:\\\\\\__csf/test_feature.py')
        search_root: Root directory to search for references

    Returns:
        List of files that import this module
    """
    try:
        # Derive module name from file path
        # P:\\\\\\__csf/test_feature.py -> src.test_feature
        # P:\\\\\\__csf/subdir/file.py -> subdir.file
        file_path_obj = Path(file_path).resolve()

        # Derive module name by stripping __csf container
        # __csf is a directory container, not part of import paths
        if "__csf" in file_path_obj.parts:
            csf_idx = file_path_obj.parts.index("__csf")
            # Get everything AFTER __csf (e.g., src/daemons/file.py)
            after_csf = file_path_obj.parts[csf_idx + 1 :]
            # Get everything AFTER __csf (e.g., src/daemons/file.py)
            if not after_csf:
                # File is directly at __csf root (edge case)
                module_candidates = []
            else:
                # Build module name from parts after __csf
                module_name = str(after_csf[-1]).replace(".py", "")
                if len(after_csf) > 1:
                    # Has subdirectories: src.daemons.module, daemons.module
                    full_path = ".".join(list(after_csf[:-1]) + [module_name])
                    without_first = (
                        ".".join(list(after_csf[1:-1]) + [module_name])
                        if len(after_csf) > 2
                        else module_name
                    )
                    module_candidates = [full_path, without_first]
                else:
                    # Single file after __csf
                    module_candidates = [module_name]
        else:
            # For non-__csf files, use relative path from P:\\\\\\
            try:
                rel_parts = file_path_obj.relative_to(Path("P:\\\\\\")).parts
                module_name = str(rel_parts[-1]).replace(".py", "")
                if len(rel_parts) > 1:
                    prefix = ".".join(rel_parts[:-1]) + "."
                    module_candidates = [f"{prefix}{module_name}"]
                else:
                    module_candidates = [module_name]
            except ValueError:
                # Fallback: filename only
                module_name = str(file_path_obj.name).replace(".py", "")
                module_candidates = [module_name]

        # Import CDSBackend for cached import lookup
        try:
            import sys

            cds_search_path = Path(search_root) / "src" / "search" / "backends"
            if str(cds_search_path) not in sys.path:
                sys.path.insert(0, str(cds_search_path))

            from cds_backend import CDSBackend

            # Initialize CDS with search roots
            search_paths = [
                str(Path(search_root) / "src"),
                str(Path(search_root).parent / ".claude"),
            ]
            cds = CDSBackend(root_paths=search_paths)

            # Query CDS for each module candidate
            references = []
            for candidate in module_candidates:
                importers = cds.find_importers(candidate)
                for imp in importers:
                    if imp not in references:
                        references.append(imp)

            return sorted(set(references))

        except ImportError:
            # Fallback to direct ripgrep scan if CDS unavailable
            import re

            references = []

            # Build regex patterns for actual Python import statements
            # Use word boundaries and proper import syntax
            patterns = []
            for candidate in module_candidates:
                # Escape ALL regex metacharacters in module name to prevent injection
                escaped = re.escape(candidate)
                patterns.extend(
                    [
                        # Match: from candidate import ...
                        rf"\bfrom\s+{escaped}(\s+|\.)",
                        # Match: import candidate or import candidate as ...
                        rf"\bimport\s+{escaped}\b",
                    ]
                )

            search_paths = [
                str(Path(search_root) / "src"),
                str(Path(search_root).parent / ".claude"),
            ]

            for search_path in search_paths:
                if not Path(search_path).exists():
                    continue

                for pattern in patterns:
                    try:
                        # Use ripgrep with regex mode for proper matching
                        cmd = [
                            "rg",
                            "--type",
                            "py",
                            "--files-with-matches",
                            "--no-ignore",
                            "--regexp",
                            pattern,
                            str(search_path),
                        ]
                        # Prevent blue console flash on Windows
                        creation_flags = 0x08000000 if sys.platform == "win32" else 0
                        result = subprocess.run(
                            cmd,
                            capture_output=True,
                            text=True,
                            timeout=5,
                            creationflags=creation_flags,
                        )

                        if result.returncode == 0 and result.stdout.strip():
                            for line in result.stdout.strip().split("\n"):
                                if line not in references:
                                    references.append(line)
                    except (FileNotFoundError, subprocess.TimeoutExpired):
                        try:
                            # Fallback: use Python regex for accurate matching
                            regex = re.compile(pattern)
                            for py_file in Path(search_path).rglob("*.py"):
                                try:
                                    content = py_file.read_text(errors="ignore")
                                    if regex.search(content):
                                        if str(py_file) not in references:
                                            references.append(str(py_file))
                                except Exception:
                                    continue
                        except Exception:
                            continue

            return sorted(set(references))

    except Exception:
        # Fail open - don't block cleanup if scan fails
        return []


def scan_test_directories(root_path: str = "P:\\\\\\") -> list[dict]:
    """Scan workspace for existing test directories.

    Returns a list of test directories with metadata:
    - path: Directory path
    - type: 'root' | 'package' | 'module'
    - package_name: Package name if applicable

    Args:
        root_path: Workspace root path

    Returns:
        List of test directory info dicts, sorted by priority
    """
    test_dirs = []
    root = Path(root_path).resolve()

    # Scan for test directories
    for tests_dir in root.rglob("tests"):
        if not tests_dir.is_dir():
            continue

        rel_path = tests_dir.relative_to(root)
        parts = rel_path.parts

        # Classify test directory type
        info = {"path": str(tests_dir), "type": "root", "package_name": None}

        if len(parts) == 1 and parts[0] == "tests":
            # Root-level tests/
            info["type"] = "root"
        elif parts[0] == "packages":
            # packages/{name}/tests/
            if len(parts) >= 2:
                info["type"] = "package"
                info["package_name"] = parts[1]
        elif parts[0].startswith("_") or parts[0] == "__csf":
            # Module-specific tests (e.g., __csf/tests/)
            info["type"] = "module"
            info["package_name"] = parts[0].lstrip("_")
        else:
            # Other nested tests/
            info["type"] = "nested"

        test_dirs.append(info)

    # Sort by priority: package > module > root > nested
    priority_order = {"package": 0, "module": 1, "root": 2, "nested": 3}
    test_dirs.sort(key=lambda x: priority_order.get(x["type"], 99))

    return test_dirs


def determine_test_destination(
    test_file: str, test_dirs: list[dict], root_path: str = "P:\\\\\\"
) -> tuple[str, str, str]:
    """Determine the best destination for a test file.

    Returns tuple of (destination, confidence, reason):
    - confidence: "HIGH" | "MEDIUM" | "LOW"
    - reason: Human-readable explanation

    Args:
        test_file: Path to the test file
        test_dirs: List of test directories from scan_test_directories()
        root_path: Workspace root path

    Returns:
        Tuple of (destination_path, confidence_level, reason)
    """
    filename = Path(test_file).name
    root = Path(root_path).resolve()
    name_stem = Path(test_file).stem.lower()

    # HIGH confidence: Package name match (excluding source's parent hierarchy)
    source_path = Path(test_file).resolve()
    for test_dir in test_dirs:
        pkg_name = test_dir.get("package_name")
        if pkg_name and pkg_name in name_stem:
            # Validate destination isn't nested within or identical to source
            dest_path = Path(test_dir["path"]).resolve()
            if dest_path == source_path or _is_ancestor(dest_path, source_path):
                continue  # Skip invalid destination
            dest = str(dest_path / filename)
            return dest, "HIGH", f"Package name match: {pkg_name}"

    # HIGH confidence: Root-level tests/ exists (excluding source hierarchy)
    for test_dir in test_dirs:
        if test_dir["type"] == "root":
            dest_path = Path(test_dir["path"]).resolve()
            if dest_path == source_path or _is_ancestor(dest_path, source_path):
                continue  # Skip invalid destination
            dest = str(dest_path / filename)
            return dest, "HIGH", "Root tests/ directory exists"

    # MEDIUM confidence: Use highest priority valid destination
    if test_dirs:
        for test_dir in test_dirs:
            dest_path = Path(test_dir["path"]).resolve()
            if dest_path == source_path or _is_ancestor(dest_path, source_path):
                continue  # Skip invalid destination
            dest = str(dest_path / filename)
            dir_type = test_dir["type"]
            return dest, "MEDIUM", f"Using existing {dir_type} tests/ directory"

    # LOW confidence: Would create new tests/ at root
    dest = str(root / "tests" / filename)
    return dest, "LOW", "Would create new tests/ directory"


def _is_ancestor(parent: Path, child: Path) -> bool:
    """Check if parent is an ancestor of child (parent is above child in hierarchy)."""
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def execute_move(source: str, target: str) -> bool:
    """Execute move operation with directory creation.

    Args:
        source: Source path
        target: Target path

    Returns:
        True if successful, False if rejected (path traversal)
    """
    try:
        source_path = Path(source)
        target_path = Path(target)

        # SECURITY: Validate target doesn't escape source's parent directory
        # This prevents path traversal attacks like ../../etc/passwd
        source_parent = source_path.parent.resolve()

        # Resolve target to check if it escapes allowed directory
        # For relative targets, resolve against source parent
        if not target_path.is_absolute():
            target_resolved = (source_parent / target_path).resolve()
        else:
            target_resolved = target_path.resolve()

        # Check if target is outside source parent (or its subdirectories)
        try:
            target_resolved.relative_to(source_parent)
        except ValueError:
            # Path escapes allowed directory
            print(f"    ⚠️  Path traversal rejected: {target} (escapes {source_parent})")
            return False

        target_path.parent.mkdir(parents=True, exist_ok=True)

        if source_path.is_dir():
            shutil.move(source, target)
        else:
            shutil.move(source, target)

        print(f"    ✅ Moved to: {target}")
        return True
    except Exception as e:
        print(f"    ❌ Move failed: {e}")
        return False


def _display_test_directories(test_dirs: list[dict]) -> None:
    """Display discovered test directories.

    Args:
        test_dirs: List of test directory info dicts
    """
    if test_dirs:
        print(f"   Found {len(test_dirs)} test directory(ies):")
        for td in test_dirs[:5]:  # Show first 5
            rel_path = Path(td["path"]).relative_to("P:\\\\\\")
            type_label = td["type"]
            pkg_info = f" ({td['package_name']})" if td.get("package_name") else ""
            print(f"     - [{type_label}]{pkg_info} {rel_path}")
        if len(test_dirs) > 5:
            print(f"     ... and {len(test_dirs) - 5} more")
    else:
        print("   No existing test directories found - will create tests/ at root")
    print()


def _handle_symlink_cleanup(file_path: str, v: dict, summary: dict) -> bool:
    """Handle symlink detection and cleanup.

    Args:
        file_path: Path to check
        v: Violation dict to update
        summary: Summary dict to update

    Returns:
        True if handled (should skip further processing), False otherwise
    """
    try:
        symlink_target = str(Path(file_path).readlink())
    except OSError as e:
        symlink_target = f"<error: {e}>"

    v["is_symlink"] = True
    v["symlink_target"] = symlink_target
    print(f"    🔗 Symlink detected → {symlink_target}")
    print("       Will NOT follow symlink automatically")
    print("       Options: [d]elete/[s]kip/[f]orce-follow/[q]uit")
    response = safe_input("  Choice: ", default="skip").lower()

    if response == "d":
        if execute_delete(file_path):
            summary["deleted"] += 1
            print("    Symlink deleted")
    elif response == "f":
        print("    ⚠️  Force-follow will delete symlink and recreate target")
        print("       Use only if you understand the implications")
        confirm = safe_input("  Confirm force-follow? [yes/N]: ", default="no").lower()
        if confirm in ("yes", "y"):
            try:
                target = Path(file_path).readlink()
                import tempfile

                with tempfile.TemporaryDirectory() as tmp_dir:
                    temp_path = tmp_dir / Path(file_path).name
                    if target.is_dir():
                        shutil.copytree(target, temp_path)
                    else:
                        shutil.copy2(target, temp_path)
                Path(file_path).unlink()
                shutil.move(str(temp_path), file_path)
                print(f"    ✅ Symlink replaced with actual content from: {symlink_target}")
                summary["deleted"] += 1
                summary["moved"] += 1
            except Exception as e:
                print(f"    ❌ Force-follow failed: {e}")
                summary["failed"] += 1
        else:
            summary["symlink_skipped"] += 1
            summary["skipped"] += 1
    print()
    return True  # Handled


def _handle_large_file(
    file_path: str, v: dict, summary: dict, large_threshold_mb: int, suggestion: str
) -> bool:
    """Handle large file warnings.

    Args:
        file_path: Path to check
        v: Violation dict to update
        summary: Summary dict to update
        large_threshold_mb: Threshold in MB
        suggestion: Suggested action

    Returns:
        True if handled (should skip further processing), False otherwise
    """
    is_large, size_mb, size_str = is_large_file(file_path, large_threshold_mb)
    if not is_large:
        return False

    v["is_large"] = True
    v["file_size"] = size_str
    print(f"    ⚠️  Large file: {size_str}")
    print("       Review before action")
    print("       Options: [d]elete/[m]ove/[s]kip/[q]uit")
    response = safe_input("  Choice: ", default="skip").lower()

    if response == "d":
        if execute_delete(file_path):
            summary["deleted"] += 1
            summary["large_file_skipped"] += 1
    elif response == "m":
        if suggestion and "Move to" in suggestion:
            if execute_move(file_path, suggestion):
                summary["moved"] += 1
        else:
            print("    ⚠️  Move requires suggestion with target")
            summary["skipped"] += 1
    else:
        summary["skipped"] += 1
        summary["large_file_skipped"] += 1
    print()
    return True


def _handle_build_artifact(file_path: str, v: dict, summary: dict) -> bool:
    """Handle build artifact detection and cleanup.

    Args:
        file_path: Path to check
        v: Violation dict to update
        summary: Summary dict to update

    Returns:
        True if handled (should skip further processing), False otherwise
    """
    is_artifact, artifact_pattern = is_build_artifact(file_path)
    if not is_artifact:
        return False

    v["is_build_artifact"] = True
    v["artifact_pattern"] = artifact_pattern
    print(f"    🧱 Build artifact detected: {artifact_pattern}")
    print("       Options: [d]elete/[s]kip/[q]uit")
    response = safe_input("  Choice: ", default="delete").lower()

    if response == "d":
        if execute_delete(file_path):
            summary["deleted"] += 1
            summary["build_artifact_cleaned"] += 1
            print("    ✅ Build artifact deleted")
    elif response == "s" or response == "q":
        summary["skipped"] += 1
    print()
    return True


def _check_import_protection(file_path: str, force: bool, summary: dict) -> bool:
    """Check if file has import references (protected from deletion).

    Args:
        file_path: Path to check
        force: If True, bypass import checks
        summary: Summary dict to update

    Returns:
        True if protected (should skip), False otherwise
    """
    if force or not file_path.endswith(".py"):
        return False

    import_refs = find_import_references(file_path)
    if import_refs:
        print(f"    ⚠️  Skipping (has {len(import_refs)} import references)")
        summary["import_protected"] += 1
        summary["skipped"] += 1
        print()
        return True
    return False


def _resolve_content_conflict(file_path: str, target_path: str, summary: dict) -> bool:
    """Resolve content conflict between source and target.

    Args:
        file_path: Source file path
        target_path: Target file path
        summary: Summary dict to update

    Returns:
        True if resolved (should skip further processing), False to continue
    """
    conflict_check = check_content_conflict(file_path, target_path)

    if not conflict_check["conflict"]:
        return False  # No conflict, continue

    # Show conflict information
    print(f"    ⚠️  {conflict_check['reason']}")
    if conflict_check.get("source_size"):
        print(f"       Source: {conflict_check['source_size']} bytes")
    if conflict_check.get("target_size"):
        print(f"       Target: {conflict_check['target_size']} bytes")
    if conflict_check.get("db_warning"):
        print("    ⚠️  Database file - special handling recommended")

    # Handle conflict action
    if conflict_check["action"] == "ask_user":
        print(f"    Action required: {conflict_check['reason']}")
        print("    Options: [k]eep target/[d]elete source/[s]kip/[q]uit")
        response = safe_input("  Choice: ").lower()
        if response == "k":
            summary["conflicts_avoided"] += 1
            summary["skipped"] += 1
            print("    Target preserved, source skipped")
            print()
            return True
        elif response == "d":
            summary["conflicts_avoided"] += 1
            summary["deleted"] += 1
            print("    Source deleted, target preserved")
            print()
            return True
        elif response in ("s", "q"):
            summary["skipped"] += 1
            print()
            return True
        # For 'ask_user' fallthrough - continue to normal flow
    elif conflict_check["action"] == "skip":
        summary["skipped"] += 1
        print("    Skipped")
        print()
        return True

    return False  # No resolution needed, continue


def _execute_cleanup_action(
    file_path: str, suggestion: str, test_dirs: list[dict], yes: bool, summary: dict
) -> None:
    """Execute the appropriate cleanup action based on suggestion type.

    Args:
        file_path: Path to clean up
        suggestion: Suggested action from validator
        test_dirs: List of test directories for smart destination logic
        yes: Auto-approve mode flag
        summary: Summary dict to update
    """
    if not suggestion:
        # No suggestion means delete
        if execute_delete(file_path):
            summary["deleted"] += 1
        else:
            summary["failed"] += 1
        return

    # Check if this is a deletion-type suggestion
    is_deletion_suggestion = (
        "delete" in suggestion.lower()
        or "remove" in suggestion.lower()
        or "rename to proper" in suggestion.lower()
        or "copy\\paste error" in suggestion.lower()
        or "path corruption" in suggestion.lower()
        or "not at the level" in suggestion.lower()
        or "belongs in" in suggestion.lower()
        or "should be in" in suggestion.lower()
    )

    # Check if it's a move suggestion
    is_move_suggestion = "Move to" in suggestion or "/" in suggestion or "{filename}" in suggestion

    if is_deletion_suggestion:
        if execute_delete(file_path):
            summary["deleted"] += 1
        else:
            summary["failed"] += 1
    elif is_move_suggestion:
        _handle_move_suggestion(file_path, suggestion, test_dirs, yes, summary)
    else:
        # Non-move suggestions get deleted
        if execute_delete(file_path):
            summary["deleted"] += 1
        else:
            summary["failed"] += 1


def _handle_move_suggestion(
    file_path: str, suggestion: str, test_dirs: list[dict], yes: bool, summary: dict
) -> None:
    """Handle move-type suggestions with smart destination logic.

    Args:
        file_path: Path to move
        suggestion: Move suggestion text
        test_dirs: List of test directories
        yes: Auto-approve mode flag
        summary: Summary dict to update
    """
    # Check if this is a test file move
    # Also check if file_path is a tests directory (robust for misclassified violations)
    is_test_move = (
        "tests/" in suggestion.lower()
        or "{filename}" in suggestion
        or Path(file_path).name in ("tests", "tests/")
    )

    if is_test_move:
        smart_dest, confidence, reason = determine_test_destination(file_path, test_dirs, "P:\\\\\\")
        rel_dest = Path(smart_dest).relative_to("P:\\\\\\")

        # In auto-approve mode, only move if HIGH confidence
        if yes and confidence != "HIGH":
            print(f"    ⚠️  Low confidence ({confidence}): {reason}")
            print(f"    → Deleting instead of moving to {rel_dest}")
            if execute_delete(file_path):
                summary["deleted"] += 1
            else:
                summary["failed"] += 1
        else:
            print(f"    📍 [{confidence}] {rel_dest}")
            print(f"       Reason: {reason}")
            if execute_move(file_path, smart_dest):
                summary["moved"] += 1
            else:
                summary["failed"] += 1
    else:
        # Non-test moves: use original suggestion logic
        move_target_raw = suggestion.replace("Move to ", "").strip()
        filename = Path(file_path).name

        # Check if suggestion is informational text, not a path
        is_informational = any(
            phrase in move_target_raw.lower()
            for phrase in ["appropriate location", "or add to", "etc.", "if needed", "unless they"]
        )

        looks_like_path = (
            "/" in move_target_raw or "\\" in move_target_raw
        ) and not is_informational

        if is_informational or not looks_like_path:
            print("    ⚠️  Informational suggestion (requires manual review):")
            print(f"       {suggestion[:80]}...")
            print("    → Skipping (safe to move manually if needed)")
            summary["skipped"] += 1
        else:
            move_target = move_target_raw.replace("{filename}", filename)

            # Validate move_target doesn't escape allowed directory
            move_target_path = Path(move_target)

            # Reject parent traversal and absolute paths
            if ".." in move_target_path.parts or move_target_path.is_absolute():
                print(f"    ⚠️  Unsafe path rejected: {move_target}")
                summary["skipped"] += 1
                return

            source_parent = Path(file_path).parent
            move_target_resolved = source_parent / move_target

            if execute_move(file_path, str(move_target_resolved)):
                summary["moved"] += 1
            else:
                summary["failed"] += 1


def execute_delete(file_path: str, force: bool = False, search_root: str = "P:\\\\\\") -> bool:
    """Execute delete operation with import reference checking for Python files.

    Args:
        file_path: Path to delete
        force: If True, skip reference checks (default: False)
        search_root: Root directory for reference search (default: "P:\\\\\\")

    Returns:
        True if successful, False if rejected due to active references
    """
    try:
        path = Path(file_path)

        # Safety check: Python files with active imports should not be deleted
        if path.suffix == ".py" and not force:
            try:
                references = find_import_references(str(path), search_root=search_root)
                if references:
                    print(f"    ⚠️   Import references found ({len(references)} files):")
                    for ref in references[:5]:  # Show first 5
                        print(f"       - {ref}")
                    if len(references) > 5:
                        print(f"       ... and {len(references) - 5} more")
                    print("    ❌ Delete rejected: Use --force to override")
                    return False
            except Exception as e:
                # Reference check failed - require explicit --force to proceed
                print(f"    ⚠️  Could not check references: {e}")
                if not force:
                    print("    ❌ Reference check failed - cannot delete safely")
                    print("    💡 Use --force to override (may break imports)")
                    return False
                print("    💡 Proceeding with deletion (--force flag set)")

        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()

        print("    ✅ Deleted")
        return True
    except Exception as e:
        print(f"    ❌ Delete failed: {e}")
        return False


def interactive_cleanup(
    violations: list[dict],
    yes: bool = False,
    force: bool = False,
    large_threshold_mb: int = LARGE_FILE_THRESHOLD_MB,
) -> dict:
    """Execute interactive cleanup with per-file confirmation.

    Enhanced with content conflict detection to prevent data loss
    when moving files between locations.

    Args:
        violations: List of violation dictionaries
        yes: If True, auto-approve all actions
        force: If True, bypass import reference checks
        large_threshold_mb: Large file threshold in MB (default: 100)

    Returns:
        Summary dict with action counts
    """
    summary = {
        "moved": 0,
        "deleted": 0,
        "skipped": 0,
        "failed": 0,
        "import_protected": 0,
        "conflicts_avoided": 0,  # Track how many conflicts were prevented
        "symlink_skipped": 0,  # Track symlink skips
        "large_file_skipped": 0,  # Track large file skips
        "build_artifact_cleaned": 0,  # Track build artifact cleanup
    }

    # Scan for test directories once at session start for smart destination logic
    print("🔍 Scanning workspace for test directories...")
    test_dirs = scan_test_directories("P:\\\\\\")
    _display_test_directories(test_dirs)

    if yes:
        # Auto-approve mode: execute all suggestions
        print("\n" + "=" * 60)
        print("AUTO-APPROVE MODE: Executing all suggested actions")
        print("=" * 60 + "\n")

        for v in violations:
            file_path = v["path"]
            suggestion = v.get("suggestion", "")

            print(f"[{v['type']}] {file_path}")
            print()

            # Early exit handlers for special cases
            if is_symlink_file(file_path):
                if _handle_symlink_cleanup(file_path, v, summary):
                    continue

            if _handle_large_file(file_path, v, summary, large_threshold_mb, suggestion):
                continue

            if _handle_build_artifact(file_path, v, summary):
                continue

            if _check_import_protection(file_path, force, summary):
                continue

            # Check for content conflicts before moving
            if suggestion and "Move to" in suggestion:
                target_path = suggestion.replace("Move to ", "").strip()
                if _resolve_content_conflict(file_path, target_path, summary):
                    continue

            # Execute the appropriate cleanup action
            _execute_cleanup_action(file_path, suggestion, test_dirs, yes, summary)
            print()

    return summary


def analyze_source_code_problems(violations: list[dict], search_root: str = "P:\\\\\\") -> dict:
    """Analyze violations to identify source code generating them.

    PRINCIPLE: Fix the source, not the symptom.
    This function identifies what code creates violations before suggesting file moves.

    Args:
        violations: List of violation dictionaries
        search_root: Root directory to search for source code

    Returns:
        Dictionary with:
            - source_problems: List of detected source code issues
            - violation_map: Map of violations to their source files
            - fixable_count: Number of violations with identifiable source fixes
    """
    source_problems = []
    violation_map = {}
    fixable_count = 0

    # Group violations by type
    coverage_violations = []
    test_evidence_violations = []
    data_misplacement_violations = []
    placeholder_violations = []

    for v in violations:
        path_str = v.get("path", "")

        # Coverage file violations
        if any(
            p in path_str.lower() for p in ["htmlcov", "coverage.xml", "coverage.json", ".coverage"]
        ):
            coverage_violations.append(v)

        # Test evidence violations
        if "tdd_evidence" in path_str.lower() or "test_shared_libs" in path_str.lower():
            test_evidence_violations.append(v)

        # Data directory violations
        if path_str.startswith("P:\\\\\\\data") or path_str.startswith("P:\\\\\\\__csf\\.claude"):
            data_misplacement_violations.append(v)

        # Placeholder directory violations (fake, current, output, etc.)
        if v.get("rule") == "HEURISTIC_PLACEHOLDER" or v.get("rule") == "HEURISTIC_EMPTY_DIR":
            placeholder_violations.append(v)

    # Helper function to group violations by module key for O(1) lookup
    def group_violations_by_module(violation_list):
        """Group violations by their module key (first 2 path components).

        This enables O(1) lookup when mapping violations to source files,
        avoiding O(n*m) complexity of calling is_related_violation for each source.
        """
        groups = {}
        for v in violation_list:
            try:
                path_obj = Path(v.get("path", ""))
                rel_path = path_obj.relative_to("P:\\\\\\")
                if len(rel_path.parts) >= 2:
                    module_key = "/".join(rel_path.parts[:2])
                    if module_key not in groups:
                        groups[module_key] = []
                    groups[module_key].append(v)
            except Exception:
                # If we can't extract a module key, skip this violation
                pass
        return groups

    # Helper function to get violations for a source file using pre-grouped data
    def get_related_violations(source_file, violation_groups):
        """Get violations related to a source file using O(1) dictionary lookup.

        This replaces the O(n) filter operation with O(1) lookup by using
        pre-computed groups.
        """
        try:
            source_path = Path(source_file)
            rel_source = source_path.relative_to("P:\\\\\\")
            if len(rel_source.parts) >= 2:
                module_key = "/".join(rel_source.parts[:2])
                return violation_groups.get(module_key, [])
        except Exception:
            pass
        return []

    # Pre-group violations by module for efficient lookup
    coverage_by_module = group_violations_by_module(coverage_violations)
    test_evidence_by_module = group_violations_by_module(test_evidence_violations)
    placeholder_by_module = group_violations_by_module(placeholder_violations)
    all_violations_by_module = group_violations_by_module(violations)

    # Search for source files generating coverage violations
    if coverage_violations:
        coverage_sources = find_coverage_sources(search_root)
        for source_file, issues in coverage_sources.items():
            related = get_related_violations(source_file, coverage_by_module)
            source_problems.append(
                {
                    "source_file": source_file,
                    "issue_type": "coverage_generation",
                    "description": "Generates coverage files in wrong location",
                    "fixes": issues,
                    "violations": [v["path"] for v in related],
                }
            )
            fixable_count += len(coverage_violations)

    # Search for source files generating test evidence violations
    if test_evidence_violations:
        evidence_sources = find_test_evidence_sources(search_root)
        for source_file, issues in evidence_sources.items():
            related = get_related_violations(source_file, test_evidence_by_module)
            source_problems.append(
                {
                    "source_file": source_file,
                    "issue_type": "test_evidence_generation",
                    "description": "Generates test evidence in wrong location",
                    "fixes": issues,
                    "violations": [v["path"] for v in related],
                }
            )
            fixable_count += len(test_evidence_violations)

    # Search for source files generating placeholder directory violations
    if placeholder_violations:
        # Extract directory names from violations
        dir_names = set()
        for v in placeholder_violations:
            path_obj = Path(v.get("path", ""))
            if path_obj.is_dir() or not path_obj.suffix:  # It's a directory
                dir_names.add(path_obj.name)
            elif path_obj.parent.name:  # Get parent directory name
                dir_names.add(path_obj.parent.name)

        placeholder_sources = find_placeholder_dir_sources(search_root, dir_names)
        for source_file, issues in placeholder_sources.items():
            related = get_related_violations(source_file, placeholder_by_module)
            source_problems.append(
                {
                    "source_file": source_file,
                    "issue_type": "placeholder_directory_creation",
                    "description": "Creates non-compliant placeholder directories at workspace root",
                    "fixes": issues,
                    "violations": [v["path"] for v in related],
                }
            )
            fixable_count += len(placeholder_violations)

    # Search for source files with root-level path construction bugs
    root_path_sources = find_root_path_construction_sources(search_root, violations)
    for source_file, issues in root_path_sources.items():
        related = get_related_violations(source_file, all_violations_by_module)
        source_problems.append(
            {
                "source_file": source_file,
                "issue_type": "root_path_construction",
                "description": "Constructs paths to workspace root (P:\\\\\\) instead of proper locations",
                "fixes": issues,
                "violations": [v["path"] for v in related],
            }
        )
        fixable_count += len(
            [
                v
                for v in violations
                if v.get("path", "").startswith("P:\\\\\\")
                and len(Path(v["path"]).relative_to("P:\\\\\\").parts) == 1
            ]
        )

    # Build violation map
    for problem in source_problems:
        for violation_path in problem["violations"]:
            if violation_path not in violation_map:
                violation_map[violation_path] = []
            violation_map[violation_path].append(problem["source_file"])

    return {
        "source_problems": source_problems,
        "violation_map": violation_map,
        "fixable_count": fixable_count,
        "total_violations": len(violations),
    }


def find_coverage_sources(search_root: str) -> dict[str, list[str]]:
    """Find source files generating coverage files.

    Args:
        search_root: Root directory to search

    Returns:
        Dict mapping source files to their issues
    """
    sources = {}
    search_path = Path(search_root)

    # Common patterns to search for
    patterns = [
        r"--cov-report",  # pytest coverage
        r"coverage\.report",  # coverage.py
        r"pytest\.main",  # pytest.main calls
    ]

    for pattern in patterns:
        try:
            cmd = ["rg", "--type", "py", "--files-with-matches", pattern, str(search_path)]
            CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10, creationflags=CREATE_NO_WINDOW
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line and line not in sources:
                        issues = analyze_coverage_file(line)
                        if issues:
                            sources[line] = issues

        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    return sources


def analyze_coverage_file(file_path: str) -> list[str]:
    """Analyze a Python file for coverage generation issues.

    Args:
        file_path: Path to Python file

    Returns:
        List of issues found with suggested fixes
    """
    issues = []
    try:
        content = Path(file_path).read_text(encoding="utf-8")

        # Check for --cov-report without proper directory
        if "--cov-report=html" in content and "--cov-report=html:reports/" not in content:
            issues.append("Change --cov-report=html to --cov-report=html:reports/htmlcov/")

        if "--cov-report=xml" in content and "--cov-report=xml:reports/" not in content:
            issues.append("Change --cov-report=xml to --cov-report=xml:reports/coverage.xml")

        if "--cov-report=term" in content and "--cov-report=term-missing" not in content:
            issues.append("Change --cov-report=term to --cov-report=term-missing for better output")

        # Check for coverage.report without output path
        if "coverage.report(" in content and "--format=json" in content:
            if "-o" not in content and "--output-file" not in content:
                issues.append("Add -o data/coverage.json to coverage.report command")

    except Exception:
        pass

    return issues


def find_test_evidence_sources(search_root: str) -> dict[str, list[str]]:
    """Find source files generating test evidence violations.

    Args:
        search_root: Root directory to search

    Returns:
        Dict mapping source files to their issues
    """
    sources = {}
    search_path = Path(search_root)

    # Search for TDD enforcer files
    try:
        tdd_enforcer = search_path / "__csf" / "src" / "core" / "tdd_enforcer.py"
        if tdd_enforcer.exists():
            issues = ["Configure evidence output to __csf/data/ instead of root"]
            sources[str(tdd_enforcer)] = issues

        quality_monitor = (
            search_path / "__csf" / "src" / "core" / "monitoring" / "code_quality_monitor.py"
        )
        if quality_monitor.exists():
            issues = ["Configure coverage JSON output to data/ instead of root"]
            sources[str(quality_monitor)] = issues

    except Exception:
        pass

    return sources


def find_root_path_construction_sources(
    search_root: str, violations: list[dict]
) -> dict[str, list[str]]:
    """Find source files that construct paths to workspace root directories.

    Detects patterns like:
    - Path / "dirname" (creates P:\\\\\\dirname)
    - project_root / "state" (creates P:\\\\\\state if project_root = P:\\\\\\)
    - .parent.parent.parent (might resolve to root)

    Args:
        search_root: Root directory to search
        violations: List of violations to check for

    Returns:
        Dict mapping source files to their issues with suggested fixes
    """
    sources = {}
    search_path = Path(search_root)

    # Extract root-level directory names from violations
    root_dir_names = set()
    for v in violations:
        path_obj = Path(v.get("path", ""))
        # Check if it's a direct child of P:\\\\\\
        try:
            rel_path = path_obj.relative_to("P:\\\\\\")
            if len(rel_path.parts) == 1 and not rel_path.suffix:  # Single-level directory
                root_dir_names.add(rel_path.name)
        except ValueError:
            continue

    if not root_dir_names:
        return sources

    # Build search patterns for path construction
    patterns = []
    for dir_name in root_dir_names:
        # Pattern 1: project_root / "dirname"
        patterns.append(rf'\w+\s*/\s*["\']?{re.escape(dir_name)}["\']?')
        # Pattern 2: Path / "dirname"
        patterns.append(rf'Path\s*/\s*["\']?{re.escape(dir_name)}["\']?')
        # Pattern 3: .parent chain with root dir
        patterns.append(rf'\.parent.*\s*/\s*["\']?{re.escape(dir_name)}["\']?')

    for pattern in patterns:
        try:
            cmd = ["rg", "--type", "py", "--files-with-matches", pattern, str(search_path)]
            CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10, creationflags=CREATE_NO_WINDOW
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line and line not in sources:
                        issues = analyze_root_path_file(line, root_dir_names)
                        if issues:
                            sources[line] = issues

        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    return sources


def analyze_root_path_file(file_path: str, dir_names: set[str]) -> list[str]:
    """Analyze a Python file for root-level path construction issues.

    Args:
        file_path: Path to Python file
        dir_names: Set of directory names that were created at root

    Returns:
        List of issues found with suggested fixes
    """
    issues = []
    try:
        content = Path(file_path).read_text(encoding="utf-8")

        # Check for .parent chains that might resolve to root
        if ".parent.parent.parent" in content or ".parent.parent.parent.parent" in content:
            issues.append(
                "Check .parent chain length - may resolve to workspace root (P:\\\\\\) instead of P:\\\\\\.claude"
            )

        # Check for common problematic patterns
        for dir_name in dir_names:
            if f'/{dir_name}"' in content or f"/{dir_name}'" in content:
                issues.append(
                    f"Path construction creates P:\\\\\\{dir_name} - should use P:\\\\\\.claude/{dir_name} instead"
                )

    except Exception:
        pass

    return issues


def find_placeholder_dir_sources(search_root: str, dir_names: set[str]) -> dict[str, list[str]]:
    """Find source files creating non-compliant placeholder directories.

    Dynamically searches for code that creates the specified directory names
    at workspace root using Path.cwd().

    ENHANCED: Searches multiple languages, patterns, and handles edge cases.

    Args:
        search_root: Root directory to search
        dir_names: Set of directory names to search for (e.g., {'output', 'fake', 'current'})

    Returns:
        Dict mapping source files to their issues with suggested fixes
    """
    sources = {}
    search_path = Path(search_root)

    # Build search patterns for each directory name
    for dir_name in dir_names:
        escaped_name = re.escape(dir_name)

        # === Python patterns ===
        python_patterns = [
            # Path.cwd() / "dirname" variations
            rf'Path\.cwd\(\)\s*/\s*["\']{escaped_name}["\']',
            rf'Path\.cwd\(\)\s*\.join\(\s*["\']{escaped_name}["\']',
            # os.mkdir and os.makedirs variations
            rf'os\.mkdir\([^)]*["\']{escaped_name}["\']',
            rf'os\.makedirs\([^)]*["\']{escaped_name}["\']',
            # shutil.mkdir variations
            rf'shutil\.mkdir\([^)]*["\']{escaped_name}["\']',
            # subprocess calls with mkdir
            rf'subprocess\.\w+\([^)]*mkdir[^)]*["\']{escaped_name}["\']',
            # Variable assignments
            rf'\w+\s*=\s*["\']{escaped_name}["\']',
        ]

        # === Shell script patterns (.sh, .bash) ===
        shell_patterns = [
            rf'mkdir\s+[-p]*\s*["\']?{escaped_name}["\']?',
            rf"\$\{{?\w+\}}?/*{escaped_name}",  # Variables with dirname
        ]

        # === Batch file patterns (.bat, .cmd) ===
        batch_patterns = [
            rf'mkdir\s+["\']?{escaped_name}["\']?',
            rf"%\w+%\\*{escaped_name}",
        ]

        # === PowerShell patterns (.ps1) ===
        powershell_patterns = [
            rf'New-Item\s+.*-Path\s+["\']?{escaped_name}["\']?',
            rf'mkdir\s+["\']?{escaped_name}["\']?',
            rf"\$\w+/*{escaped_name}",
        ]

        # === JavaScript/Node patterns ===
        js_patterns = [
            rf'fs\.mkdir\([^)]*["\']{escaped_name}["\']',
            rf'fs\.mkdirSync\([^)]*["\']{escaped_name}["\']',
        ]

        # === Makefile patterns ===
        makefile_patterns = [
            rf"mkdir\s+[-p]*\s*\$[*@]?[\w\-]*{escaped_name}",
        ]

        # All patterns grouped by file type
        all_patterns = [
            ("py", python_patterns),
            ("sh", shell_patterns),
            ("bash", shell_patterns),
            ("bat", batch_patterns),
            ("cmd", batch_patterns),
            ("ps1", powershell_patterns),
            ("js", js_patterns),
            ("mk", makefile_patterns),
            ("Makefile", makefile_patterns),
        ]

        # Search using ripgrep with fallback
        for file_type, patterns in all_patterns:
            for pattern in patterns:
                found_files = search_with_ripgrep(search_path, pattern, file_type)
                for file_path in found_files:
                    if file_path not in sources:
                        issues = analyze_placeholder_dir_file(file_path, dir_name, file_type)
                        if issues:
                            sources[file_path] = issues

    return sources


def search_with_ripgrep(search_path: Path, pattern: str, file_type: str) -> list[str]:
    """Search for pattern using ripgrep with fallback to glob.

    Addresses failure mode #4: ripgrep dependency
    """
    results = []

    # Try ripgrep first
    try:
        cmd = ["rg", "--type", file_type, "--files-with-matches", pattern, str(search_path)]
        CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=15, creationflags=CREATE_NO_WINDOW
        )

        if result.returncode == 0:
            results = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
            return results

    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # Fall through to glob search

    # Fallback: Use Python glob to search files
    try:
        # Common extensions by type
        extensions = {
            "py": ".py",
            "sh": ".sh",
            "bash": ".bash",
            "bat": ".bat",
            "cmd": ".cmd",
            "ps1": ".ps1",
            "js": ".js",
            "mk": ".mk",
            "Makefile": "",
        }

        ext = extensions.get(file_type, "")
        pattern_files = list(search_path.rglob(f"*{ext}" if ext else file_type))

        # Search within files using Python
        for file_path in pattern_files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                if re.search(pattern, content):
                    results.append(str(file_path))
            except Exception:
                pass

    except Exception:
        pass

    return results


def analyze_placeholder_dir_file(file_path: str, dir_name: str, file_type: str = "py") -> list[str]:
    """Analyze a file for placeholder directory creation issues.

    ENHANCED: Handles multiple languages and provides specific fixes.

    Args:
        file_path: Path to file
        dir_name: Directory name being created
        file_type: File type (py, sh, bat, ps1, js, mk, etc.)

    Returns:
        List of issues found with suggested fixes
    """
    issues = []
    try:
        content = Path(file_path).read_text(encoding="utf-8", errors="ignore")

        # Language-specific analysis
        if file_type in ("py", "python"):
            issues = analyze_python_file(content, file_path, dir_name)
        elif file_type in ("sh", "bash"):
            issues = analyze_shell_file(content, file_path, dir_name)
        elif file_type in ("bat", "cmd"):
            issues = analyze_batch_file(content, file_path, dir_name)
        elif file_type == "ps1":
            issues = analyze_powershell_file(content, file_path, dir_name)
        elif file_type in ("js", "javascript"):
            issues = analyze_js_file(content, file_path, dir_name)
        elif file_type in ("mk", "Makefile"):
            issues = analyze_makefile(content, file_path, dir_name)
        else:
            # Generic analysis for unknown types
            issues = analyze_generic_file(content, file_path, dir_name)

    except Exception:
        pass

    return issues


def analyze_python_file(content: str, _file_path: str, dir_name: str) -> list[str]:
    """Analyze Python file for directory creation issues."""
    issues = []

    # Path.cwd() / "dirname" pattern
    if f'Path.cwd() / "{dir_name}"' in content or f"Path.cwd() / '{dir_name}'" in content:
        issues.append(
            f'Change Path.cwd() / "{dir_name}" to Path.cwd() / "__csf" / "data" / "{dir_name}"'
        )

    # os.mkdir / os.makedirs patterns
    if dir_name in content and ("os.mkdir" in content or "os.makedirs" in content):
        lines = content.split("\n")
        for line in lines:
            if dir_name in line and "os.mkdir" in line:
                issues.append(
                    f'Use os.makedirs(Path.cwd() / "__csf" / "data" / "{dir_name}", exist_ok=True)'
                )
                break

    # shutil.mkdir patterns
    if dir_name in content and "shutil.mkdir" in content:
        issues.append(f"Move {dir_name} directory creation to __csf/data/")

    # subprocess with mkdir
    if "subprocess" in content and "mkdir" in content:
        lines = content.split("\n")
        for line in lines:
            if dir_name in line and "subprocess" in line:
                issues.append(
                    f"Replace subprocess mkdir with Path.mkdir() to __csf/data/{dir_name}"
                )
                break

    return issues


def analyze_shell_file(content: str, _file_path: str, dir_name: str) -> list[str]:
    """Analyze shell script for directory creation issues."""
    issues = []

    # Direct mkdir commands
    if re.search(rf'mkdir\s+[-p]*\s*["\']?{re.escape(dir_name)}', content):
        issues.append(f"Change mkdir {dir_name} to mkdir __csf/data/{dir_name}")

    # Variable-based mkdir
    if dir_name in content:
        lines = content.split("\n")
        for line in lines:
            if "mkdir" in line and dir_name in line:
                issues.append(
                    f"Update shell script: use $PWD/__csf/data/{dir_name} instead of {dir_name}"
                )
                break

    return issues


def analyze_batch_file(content: str, _file_path: str, dir_name: str) -> list[str]:
    """Analyze batch file for directory creation issues."""
    issues = []

    if dir_name in content and "mkdir" in content:
        lines = content.split("\n")
        for line in lines:
            if "mkdir" in line and dir_name in line:
                issues.append(f"Change mkdir {dir_name} to mkdir %CD%\\__csf\\data\\{dir_name}")
                break

    return issues


def analyze_powershell_file(content: str, _file_path: str, dir_name: str) -> list[str]:
    """Analyze PowerShell script for directory creation issues."""
    issues = []

    if dir_name in content and ("New-Item" in content or "mkdir" in content):
        lines = content.split("\n")
        for line in lines:
            if ("New-Item" in line or "mkdir" in line) and dir_name in line:
                issues.append(f'Use Join-Path $PWD "__csf" "data" "{dir_name}" for proper path')
                break

    return issues


def analyze_js_file(content: str, _file_path: str, dir_name: str) -> list[str]:
    """Analyze JavaScript file for directory creation issues."""
    issues = []

    if dir_name in content and ("fs.mkdir" in content or "fs.mkdirSync" in content):
        lines = content.split("\n")
        for line in lines:
            if ("mkdir" in line) and dir_name in line:
                issues.append(f'Use path.join(process.cwd(), "__csf", "data", "{dir_name}")')
                break

    return issues


def analyze_makefile(content: str, _file_path: str, dir_name: str) -> list[str]:
    """Analyze Makefile for directory creation issues."""
    issues = []

    if dir_name in content and "mkdir" in content:
        lines = content.split("\n")
        for line in lines:
            if "mkdir" in line and dir_name in line:
                issues.append(f"Change to: mkdir -p $(PWD)/__csf/data/{dir_name}")
                break

    return issues


def analyze_generic_file(content: str, _file_path: str, dir_name: str) -> list[str]:
    """Generic file analysis for unknown types."""
    issues = []

    if dir_name in content and "mkdir" in content.lower():
        issues.append(f"Review {_file_path}: directory creation should use __csf/data/{dir_name}")

    return issues


def is_related_violation(violation: dict, source_file: str) -> bool:
    """Check if a violation is related to a source file.

    Args:
        violation: Violation dictionary
        source_file: Source file path

    Returns:
        True if likely related
    """
    # Simple heuristic: same directory or module
    violation_path = Path(violation.get("path", ""))
    source_path = Path(source_file)

    try:
        # Check if source is in same module tree
        rel_violation = violation_path.relative_to(Path("P:\\\\\\"))
        rel_source = source_path.relative_to(Path("P:\\\\\\"))

        # If they share the first 2 path components, consider them related
        if len(rel_violation.parts) >= 2 and len(rel_source.parts) >= 2:
            return rel_violation.parts[:2] == rel_source.parts[:2]
    except Exception:
        pass

    return False


def find_directory_references(dir_path: str, search_root: str = "P:\\\\\\"):
    """Search for code that references a directory path.

    Checks if any code in the workspace references the given directory.
    This prevents accidental deletion of actively-used directories.

    Args:
        dir_path: Directory path to check (e.g., "P:\\\\\\\standalone", "P:\\\\\\claude")
        search_root: Root directory to search (default: P:\\\\\\)

    Returns:
        Dict with:
            - 'count': Number of files referencing this directory
            - 'files': List of files that reference this directory
            - 'safe': True if no references found, False otherwise
    """
    dir_name = Path(dir_path).name
    search_path = Path(search_root)

    # Skip searching in .claude (self-references are expected)
    skip_dirs = {".claude", "__pycache__", ".git", "node_modules"}

    # Build search patterns for this directory
    patterns = [
        rf"P:\\\\\\\\\\{re.escape(dir_name)}\\b",  # P:\\\\\\dirname (with word boundary)
        rf"P:\\\\\\\{re.escape(dir_name)}\\b",  # P:\\\\\\dirname (forward slashes)
        rf'["\']{re.escape(dir_name)}["\']',  # "dirname" or 'dirname' (string literal)
    ]

    references = []

    # Search in Python files
    try:
        for pattern in patterns:
            cmd = ["rg", "--type", "py", "--files-with-matches", pattern, str(search_path)]
            CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10, creationflags=CREATE_NO_WINDOW
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        file_path = Path(line)
                        # Skip results in .claude, __pycache__, etc.
                        if not any(skip_dir in file_path.parts for skip_dir in skip_dirs):
                            # Also skip the directory itself
                            if dir_name not in file_path.parts or file_path.parent != Path(
                                dir_path
                            ):
                                if str(file_path) not in references:
                                    references.append(str(file_path))

    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Search in JSON files
    try:
        for pattern in patterns:
            cmd = ["rg", "--type", "json", "--files-with-matches", pattern, str(search_path)]
            CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10, creationflags=CREATE_NO_WINDOW
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        file_path = Path(line)
                        if not any(skip_dir in file_path.parts for skip_dir in skip_dirs):
                            if dir_name not in file_path.parts or file_path.parent != Path(
                                dir_path
                            ):
                                if str(file_path) not in references:
                                    references.append(str(file_path))

    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Search in Markdown files
    try:
        for pattern in patterns:
            cmd = ["rg", "--type", "md", "--files-with-matches", pattern, str(search_path)]
            CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10, creationflags=CREATE_NO_WINDOW
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        file_path = Path(line)
                        if not any(skip_dir in file_path.parts for skip_dir in skip_dirs):
                            if dir_name not in file_path.parts or file_path.parent != Path(
                                dir_path
                            ):
                                if str(file_path) not in references:
                                    references.append(str(file_path))

    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return {
        "count": len(references),
        "files": sorted(references),  # Sort for consistent output
        "safe": len(references) == 0,
    }


def find_file_references(file_path: str, search_root: str = "P:\\\\\\"):
    """Search for code that references a file path.

    Checks if any code in the workspace references the given file.
    This prevents accidental deletion of actively-used files.

    Args:
        file_path: File path to check (e.g., "P:\\\\\\\standalone\\config.json", "P:\\\\\\claude/README.md")
        search_root: Root directory to search (default: P:\\\\\\)

    Returns:
        Dict with:
            - 'count': Number of files referencing this file
            - 'files': List of files that reference this file
            - 'safe': True if no references found, False otherwise
    """
    file_path_obj = Path(file_path)
    file_name = file_path_obj.name
    file_stem = file_path_obj.stem  # name without extension
    search_path = Path(search_root)

    # Skip searching in .claude (self-references are expected)
    skip_dirs = {".claude", "__pycache__", ".git", "node_modules"}

    # Build search patterns for this file
    patterns = [
        rf"P:\\\\\\\\\\{re.escape(file_name)}\\b",  # P:\\\\\\filename.ext (with word boundary)
        rf"P:\\\\\\\{re.escape(file_name)}\\b",  # P:\\\\\\filename.ext (forward slashes)
        rf'["\']{re.escape(file_name)}["\']',  # "filename.ext" or 'filename.ext' (string literal)
        rf'["\']{re.escape(file_stem)}["\']',  # "filename" or 'filename' (without extension)
    ]

    references = []

    # Search in Python files
    try:
        for pattern in patterns:
            cmd = ["rg", "--type", "py", "--files-with-matches", pattern, str(search_path)]
            CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10, creationflags=CREATE_NO_WINDOW
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        found_path = Path(line)
                        # Skip results in .claude, __pycache__, etc.
                        if not any(skip_dir in found_path.parts for skip_dir in skip_dirs):
                            # Skip the file itself
                            if found_path != file_path_obj:
                                if str(found_path) not in references:
                                    references.append(str(found_path))

    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Search in JSON files
    try:
        for pattern in patterns:
            cmd = ["rg", "--type", "json", "--files-with-matches", pattern, str(search_path)]
            CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10, creationflags=CREATE_NO_WINDOW
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        found_path = Path(line)
                        if not any(skip_dir in found_path.parts for skip_dir in skip_dirs):
                            if found_path != file_path_obj:
                                if str(found_path) not in references:
                                    references.append(str(found_path))

    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Search in Markdown files
    try:
        for pattern in patterns:
            cmd = ["rg", "--type", "md", "--files-with-matches", pattern, str(search_path)]
            CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10, creationflags=CREATE_NO_WINDOW
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        found_path = Path(line)
                        if not any(skip_dir in found_path.parts for skip_dir in skip_dirs):
                            if found_path != file_path_obj:
                                if str(found_path) not in references:
                                    references.append(str(found_path))

    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return {
        "count": len(references),
        "files": sorted(references),  # Sort for consistent output
        "safe": len(references) == 0,
    }


def display_source_analysis(analysis: dict, violations: list[dict]) -> None:
    """Display source code problem analysis.

    ENHANCED: Reports when violations exist but no source was found (manual/unknown).

    Args:
        analysis: Result from analyze_source_code_problems
        violations: List of all violations found
    """
    problems = analysis.get("source_problems", [])
    total_violations = analysis.get("total_violations", len(violations))

    print("\n" + "=" * 60)
    print("🔍 SOURCE CODE ANALYSIS - FIX THE SOURCE, NOT THE SYMPTOM")
    print("=" * 60)

    if not problems:
        # Check if there are violations we couldn't trace
        if total_violations > 0:
            print(f"⚠️  Found {total_violations} violations, but could not detect creating code.")
            print()
            print("This means the violations are likely:")
            print("  • Manually created (user typed 'mkdir', IDE created folders)")
            print("  • Created dynamically (variables, config-based paths)")
            print("  • Old remnants from previous work")
            print()
            print("⚠️  These violations will RECUR on every run unless resolved.")
            print("    Before Phase 2, investigate each remaining violation:")
            print("      - List contents of the flagged path (ls/Glob)")
            print("      - Determine: stale debris (delete) or intentional (add to policy)")
            print("    Do NOT skip to Phase 2 without making a determination.")
        else:
            print("✅ No source code problems detected.")
        print()
        print("Proceeding with file-based cleanup.")
        return

    print(
        f"Found {len(problems)} source code issues causing {analysis.get('fixable_count', 0)} violations:"
    )
    print()

    for i, problem in enumerate(problems, 1):
        print(f"{i}. {problem['source_file']}")
        print(f"   Issue: {problem['description']}")
        print(f"   Type: {problem['issue_type']}")

        if problem["fixes"]:
            print("   Suggested fixes:")
            for fix in problem["fixes"]:
                print(f"     • {fix}")

        if problem["violations"]:
            print("   Causing violations:")
            for v in problem["violations"][:3]:  # Show first 3
                print(f"     • {v}")
            if len(problem["violations"]) > 3:
                print(f"     • ... and {len(problem['violations']) - 3} more")
        print()

    print("=" * 60)
    print("RECOMMENDATION: Fix source code first, then re-run /cleanup")
    print("=" * 60)


def _categorize_violation(violation: dict) -> tuple[str, str]:
    """Categorize a violation for pattern aggregation.

    Args:
        violation: Violation dict with 'type', 'path', 'message' keys

    Returns:
        Tuple of (category_key, suggested_pattern) where:
        - category_key: Stable identifier for the violation category
        - suggested_pattern: Glob pattern that would match this violation type
    """
    v_type = violation.get("type", "UNKNOWN")
    path = violation.get("path", "")

    # Extract filename and extension
    filename = Path(path).name if path else ""

    # Category mapping based on violation type
    if v_type == "DOTFILE_VIOLATION":
        # e.g., ".coverage" -> "*_coverage" or ".env" -> ".env"
        if filename.startswith("."):
            return (f"DOTFILE:{filename}", filename)
        return (f"DOTFILE:{filename}", f"*{filename}")

    elif v_type == "UNKNOWN_CONFIG_FILE":
        # e.g., "SPECS.md" -> "SPECS.md"
        return (f"CONFIG:{filename}", filename)

    elif v_type == "WORKTREE_AT_ROOT":
        # e.g., "worktree_name" -> "*worktree_name*"
        return (f"WORKTREE:{filename}", f"*{filename}*")

    elif v_type == "DETACHED_GIT_REPO":
        return (f"GIT_REPO:{filename}", f"*{filename}*")

    elif v_type == "CACHE_DIR":
        return (f"CACHE:{filename}", f"*{filename}*")

    elif v_type == "BACKUP_FILE":
        # e.g., "old_script.py.bak" -> "*.bak"
        suffix = Path(filename).suffix
        return (f"BACKUP:{suffix}", f"*{suffix}")

    elif v_type == "BUILD_ARTIFACT":
        return (f"BUILD:{filename}", f"*{filename}*")

    elif v_type == "AI_GENERATED":
        # Preserve the pattern that was matched
        pattern = violation.get("matched_pattern", f"*{filename}*")
        return (f"AI_GEN:{pattern}", pattern)

    elif v_type == "TYPE_MISMATCH_CONFIG_WHITELIST":
        # e.g., "script.py" in allowed but is Python
        return (f"TYPE_MISMATCH:{filename}", filename)

    elif v_type == "NESTED_STRUCTURE":
        return (f"NESTED:{filename}", f"*{filename}*")

    else:
        # Fallback: use type + filename (avoid overly broad patterns like "*")
        # Only suggest if we have a meaningful filename
        if filename:
            return (f"OTHER:{v_type}:{filename}", filename)
        # If no filename, skip this violation (can't create meaningful pattern)
        return (f"OTHER:{v_type}:unknown", "")


def _infer_purpose(violation_type: str, filename: str) -> str:
    """Infer the 'purpose' field for a suggested pattern.

    Args:
        violation_type: The violation type category
        filename: The filename

    Returns:
        Human-readable purpose string
    """
    v_type = violation_type.split(":")[0] if ":" in violation_type else violation_type

    purpose_map = {
        "DOTFILE": "Dotfile that should be reviewed",
        "CONFIG": "Configuration file at workspace root",
        "WORKTREE": "Git worktree directory",
        "GIT_REPO": "Git repository",
        "CACHE": "Cache directory",
        "BACKUP": "Backup file",
        "BUILD": "Build artifact",
        "AI_GEN": "AI-generated artifact",
        "TYPE_MISMATCH": "Type mismatch in config whitelist",
        "NESTED": "Nested directory structure",
    }

    base = purpose_map.get(v_type, "Unknown violation type")
    return f"{base}: {filename}"


def _infer_suggested_location(violation_type: str, _filename: str) -> str:
    """Infer the 'suggested_location' field for a suggested pattern.

    Args:
        violation_type: The violation type category
        _filename: The filename (unused, kept for API consistency)

    Returns:
        Suggested location path
    """
    v_type = violation_type.split(":")[0] if ":" in violation_type else violation_type

    location_map = {
        "DOTFILE": ".claude/",
        "CONFIG": "docs/ or __csf/data/",
        "WORKTREE": ".claude/worktrees/",
        "GIT_REPO": "packages/",
        "CACHE": ".claude/cache/ or .cache/",
        "BACKUP": ".staging/ or backups/",
        "BUILD": ".staging/ or build/ directory",
        "AI_GEN": ".staging/ or reports/",
        "TYPE_MISMATCH": ".claude/hooks/",
        "NESTED": "Parent directory",
    }

    return location_map.get(v_type, ".staging/")


def analyze_feedback_patterns(violations: list[dict], threshold: int = 3) -> list[dict]:
    """Analyze violations and suggest patterns for policy addition.

    Aggregates violations by category and suggests ai_generated_patterns
    entries for categories that exceed the occurrence threshold.

    Args:
        violations: List of violation dicts from cleanup scan
        threshold: Minimum occurrences to trigger a suggestion (default: 3)

    Returns:
        List of suggestion dicts with keys: pattern, purpose, max_age_days,
        auto_cleanup, suggested_location
    """
    if not violations:
        return []

    # Aggregate violations by category
    category_counts: dict[str, list[dict]] = {}

    for v in violations:
        category_key, _ = _categorize_violation(v)
        if category_key not in category_counts:
            category_counts[category_key] = []
        category_counts[category_key].append(v)

    # Generate suggestions for categories exceeding threshold
    suggestions = []

    for category_key, category_violations in category_counts.items():
        count = len(category_violations)

        if count < threshold:
            continue

        # Get a sample violation for context
        sample = category_violations[0]
        filename = Path(sample.get("path", "")).name

        # Extract the pattern from the first violation
        _, pattern = _categorize_violation(sample)

        # Skip if pattern is empty or too broad (like just "*")
        if not pattern or pattern == "*":
            continue

        # Determine max_age_days based on violation type
        v_type = sample.get("type", "")
        if "AI_GENERATED" in v_type or "session-*.json" in pattern:
            max_age_days = 1  # Session debris is short-lived
        elif "BACKUP" in category_key:
            max_age_days = 7  # Backups can linger a bit
        else:
            max_age_days = 7  # Default

        suggestion = {
            "pattern": pattern,
            "purpose": _infer_purpose(category_key, filename),
            "max_age_days": max_age_days,
            "auto_cleanup": True,
            "suggested_location": _infer_suggested_location(category_key, filename),
        }

        suggestions.append(suggestion)

    return suggestions


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Safe filesystem cleanup with approval (ENHANCED with content conflict detection)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive cleanup (default)
  python cleanup.py

  # Show violations only (dry run)
  python cleanup.py --dry-run

  # Limit to 20 violations
  python cleanup.py --max 20

  # Auto-approve all actions (use with caution!)
  python cleanup.py --yes

NEW FEATURES:
  -- Content conflict detection prevents data loss when moving files
  -- Size comparison warns before overwriting larger files
  -- Database-specific warnings for .db/.sqlite files
  -- Shows conflict statistics in summary
  -- Build artifact detection (__pycache__, .pytest_cache, dist/, build/, etc.)
  -- Large file warnings (>100 MB threshold, configurable)
  -- Symlink handling with force-follow option
        """,
    )

    parser.add_argument(
        "--max",
        type=int,
        default=50,
        metavar="N",
        help="Maximum violations to process (default: 50)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show violations without executing cleanup"
    )
    parser.add_argument(
        "--yes", action="store_true", help="Auto-approve all cleanup actions (use with caution!)"
    )
    parser.add_argument("--root", default="P:\\\\\\", help="Root path to validate (default: P:\\\\\\)")
    parser.add_argument(
        "--force", action="store_true", help="Bypass import reference checks (use with caution!)"
    )
    parser.add_argument(
        "--large-threshold",
        type=int,
        default=LARGE_FILE_THRESHOLD_MB,
        metavar="MB",
        help=f"Large file threshold in MB (default: {LARGE_FILE_THRESHOLD_MB})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output violations in JSON format for programmatic consumption",
    )
    parser.add_argument(
        "--export-patterns",
        action="store_true",
        help="Output suggested pattern additions for ai_generated_patterns in JSONL format",
    )
    parser.add_argument(
        "--validate-policy",
        action="store_true",
        help="Validate directory_policy.json is valid JSON before suggesting additions",
    )
    parser.add_argument(
        "--feedback-loop",
        action="store_true",
        help="Enable feedback loop: track violations and suggest policy additions after 3+ occurrences",
    )

    args = parser.parse_args()

    # Load claude_directory policy once for reuse
    policy_path = Path("P:\\\\\\.claude/hooks/config/directory_policy.json")
    claude_dir_blocked_patterns = []
    claude_dir_allowed_subdirs = []
    if policy_path.exists():
        try:
            with open(policy_path) as f:
                policy_data = json.load(f)
                claude_dir = policy_data.get("claude_directory", {})
                blocked_root = claude_dir.get("blocked_root_patterns", {})
                claude_dir_blocked_patterns = blocked_root.get("patterns", [])
                claude_dir_allowed_subdirs = claude_dir.get("allowed_subdirectories", [])
        except (OSError, json.JSONDecodeError, KeyError):
            pass

    # JSON mode: output violations only and exit
    if args.json:
        # Run validator (policy-based violations)
        results = run_validator(args.root, args.max)

        if "error" in results:
            json.dump({"error": results["error"]}, sys.stdout)
            sys.exit(1)

        violations = results.get("violations", [])

        # Run heuristic detection
        heuristic_violations = detect_heuristic_violations(args.root)

        # Run internal directory violation detection (NEW)
        internal_violations = detect_internal_violations(args.root, claude_dir_blocked_patterns, claude_dir_allowed_subdirs)

        # Merge all violation types
        all_violations = violations + heuristic_violations + internal_violations

        # Output JSON with violation summary
        json.dump(
            {
                "violations_count": len(all_violations),
                "violations": all_violations[: args.max],  # Respect --max limit
                "summary": {
                    "total_violations": len(all_violations),
                    "policy_count": len(violations),
                    "heuristic_count": len(heuristic_violations),
                    "internal_count": len(internal_violations),
                },
            },
            sys.stdout,
            indent=2,
        )
        sys.exit(0)

    # Export patterns mode: output suggested additions to ai_generated_patterns
    if args.export_patterns:
        if args.validate_policy:
            policy_path = Path(args.root) / ".claude" / "hooks" / "config" / "directory_policy.json"
            if not policy_path.exists():
                print(f"❌ ERROR: Policy file not found: {policy_path}")
                sys.exit(1)
            try:
                with open(policy_path) as f:
                    json.load(f)
                print(f"✅ Policy file is valid JSON: {policy_path}")
            except json.JSONDecodeError as e:
                print(f"❌ ERROR: Policy file is not valid JSON: {e}")
                sys.exit(1)

        # Run all violation detection
        results = run_validator(args.root, args.max)
        heuristic_violations = detect_heuristic_violations(args.root)
        internal_violations = detect_internal_violations(args.root, claude_dir_blocked_patterns, claude_dir_allowed_subdirs)
        policy_violations = results.get("violations", [])
        all_violations = policy_violations + heuristic_violations + internal_violations

        # Analyze patterns and suggest additions
        suggestions = analyze_feedback_patterns(all_violations)

        if not suggestions:
            print("No patterns detected that warrant policy addition.")
            sys.exit(0)

        print("VIOLATION PATTERN DETECTED:")
        for suggestion in suggestions:
            print("\nConsider adding to directory_policy.json ai_generated_patterns:")
            print(json.dumps(suggestion, indent=2))

        print(
            "\nTo auto-add: python cleanup.py --export-patterns --validate-policy >> directory_policy.json"
        )
        print(
            "NOTE: The >> appends JSON lines which corrupts the file. Use a JSON merge tool instead."
        )
        sys.exit(0)

    # Block dangerous --yes --force combination
    if args.yes and args.force:
        print("❌ ERROR: --yes and --force cannot be used together")
        print("   This combination bypasses all safety checks.")
        sys.exit(1)

    print("=" * 60)
    print("FILESYSTEM CLEANUP")
    print("=" * 60)
    print(f"Scanning: {args.root}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Run validator (policy-based violations)
    results = run_validator(args.root, args.max)

    if "error" in results:
        print(f"\n❌ Error: {results['error']}")
        sys.exit(1)

    violations = results.get("violations", [])

    # Run heuristic detection (junk detection)
    print("\n🔍 Detecting heuristic violations (junk files, bad names, etc.)...")
    heuristic_violations = detect_heuristic_violations(args.root)

    # Run internal directory violation detection (NEW)
    print("\n🔍 Detecting internal violations (cache dirs, backups, etc.)...")
    internal_violations = detect_internal_violations(args.root, claude_dir_blocked_patterns)

    # Merge all violation types
    all_violations = violations + heuristic_violations + internal_violations

    if not all_violations:
        print("\n✅ Workspace is compliant!")
        sys.exit(0)

    # Update results with merged violations
    results["violations"] = all_violations
    if heuristic_violations:
        results["summary"]["heuristic_count"] = len(heuristic_violations)
    if internal_violations:
        results["summary"]["internal_count"] = len(internal_violations)

    # SESSION STATE: Check if we can resume from a previous session
    # This provides compact-event immunity and multi-terminal isolation
    session_state = None
    resumed_from_checkpoint = False

    if not args.yes:  # Don't resume in auto-approve mode - always fresh run
        saved_state = load_session_state()
        if is_session_state_valid(saved_state, len(all_violations)):
            session_state = saved_state
            resumed_from_checkpoint = True
            print(f"\n🔄 Resuming session from checkpoint (terminal {get_terminal_id()[:8]})")
            print(f"   {len(saved_state['approved_actions'])} actions previously taken")
            print(f"   {len(saved_state['skipped_items'])} items previously skipped")
        else:
            # Fresh scan - invalidate any stale state
            invalidate_session_state("fresh_scan")

    # Build set of already-processed paths for quick lookup
    processed_paths: set[str] = set()
    if session_state:
        for action in session_state["approved_actions"]:
            processed_paths.add(action.get("path", ""))
        for path in session_state["skipped_items"]:
            processed_paths.add(path)

    # REFERENCE CHECK: Verify violations aren't actively referenced
    print("\n" + "=" * 60)
    print("🔍 REFERENCE CHECK: Searching for active references")
    print("=" * 60)

    reference_check_summary = {"checked": 0, "with_references": 0, "safe": 0, "skipped": 0}

    for v in all_violations:
        violation_path = v["path"]
        is_directory = Path(violation_path).is_dir() if Path(violation_path).exists() else False

        # Check references based on violation type
        ref_info = None
        if is_directory:
            # Directory reference check
            ref_info = find_directory_references(violation_path, args.root)
        else:
            # File reference check (for config files, test files, etc.)
            ref_info = (
                find_file_references(violation_path, args.root)
                if "file" in v.get("type", "").lower()
                else None
            )

        reference_check_summary["checked"] += 1

        if ref_info:
            if ref_info["count"] > 0:
                reference_check_summary["with_references"] += 1
                v["reference_warning"] = f"⚠️ REFERENCED BY {ref_info['count']} FILE(S)"
                v["reference_files"] = ref_info["files"][:5]  # Show first 5
                v["reference_safe"] = False
            else:
                reference_check_summary["safe"] += 1
                v["reference_safe"] = True
                v["reference_info"] = "✅ No references found - safe to move/delete"
        else:
            reference_check_summary["skipped"] += 1
            v["reference_info"] = "⊘ Reference check not available for this type"

    # Display reference check summary
    print(f"  Checked:      {reference_check_summary['checked']} violations")
    print(f"  Safe:        {reference_check_summary['safe']} (no references)")
    print(f"  Referenced:  {reference_check_summary['with_references']} (has references!)")
    if reference_check_summary["skipped"] > 0:
        print(f"  Skipped:     {reference_check_summary['skipped']} (check not available)")
    print()

    # SOURCE-CODE-FIRST ANALYSIS: Identify what's generating violations
    print("\n" + "=" * 60)
    print("🔍 PHASE 1: SOURCE CODE ANALYSIS")
    print("=" * 60)
    print("Identifying source code problems before suggesting file moves...")
    print()

    analysis = analyze_source_code_problems(all_violations, args.root)
    display_source_analysis(analysis, all_violations)

    # Now display the violations
    print("\n" + "=" * 60)
    print("📋 PHASE 2: VIOLATION DETAILS")
    print("=" * 60)
    display_violations(results, show_all=False)

    violations = results.get("violations", [])
    if not violations:
        print("\n✅ Workspace is compliant!")
        sys.exit(0)

    # Dry-run mode
    if args.dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN MODE - No actions executed")
        print("=" * 60)
        sys.exit(0)

    # Ask for approval
    if not args.yes:
        print("\n" + "=" * 60)
        response = safe_input("Proceed with cleanup? [yes/N]: ", default="no").strip().lower()
        if response not in ("yes", "y"):
            print("Cleanup cancelled.")
            sys.exit(0)

    # Log --force usage for audit trail
    if args.force:
        print("\n⚠️  --force flag active: Import checks bypassed")
        # Try to log to hooks state if available
        try:
            hooks_dir = Path(args.root) / ".claude" / "hooks"
            if (hooks_dir / "shared_utils.py").exists():
                hooks_dir_str = str(hooks_dir)
                if hooks_dir_str not in sys.path:
                    sys.path.insert(0, hooks_dir_str)
                from shared_utils import log_hook_event

                log_hook_event(
                    "cleanup",
                    "force_used",
                    {"violations_count": len(violations), "timestamp": datetime.now().isoformat()},
                )
        except Exception:
            # Logging failure is not critical
            pass

    # Execute cleanup (pass session state for resume, processed_paths to skip)
    summary = interactive_cleanup(
        violations,
        yes=args.yes,
        force=args.force,
        large_threshold_mb=args.large_threshold,
        session_state=session_state,
        processed_paths=processed_paths,
    )

    # Save final session state for compact-event immunity
    if session_state is not None and not args.yes:
        session_state["approved_actions"].extend(
            summary.get("session_state", {}).get("approved_actions", [])
        )
        session_state["scan_timestamp"] = datetime.now().isoformat()
        session_state["violations_snapshot"] = [v["path"] for v in violations]
        save_session_state(session_state)

    # Show summary
    print("\n" + "=" * 60)
    print("CLEANUP SUMMARY")
    print("=" * 60)
    print(f"  Moved:              {summary['moved']}")
    print(f"  Deleted:            {summary['deleted']}")
    print(f"  Skipped:            {summary['skipped']}")
    if summary["import_protected"] > 0:
        print(f"  (import-protected:  {summary['import_protected']})")
    if summary["conflicts_avoided"] > 0:
        print(f"  Conflicts avoided:  {summary['conflicts_avoided']}")
    print(f"  Failed:             {summary['failed']}")
    print()

    # Verify compliance
    print("Verifying compliance after cleanup...")
    final_results = run_validator(args.root, args.max)
    final_summary = final_results.get("summary", {})
    final_violations = final_summary.get("violation_count", 0)

    if final_violations == 0:
        print("✅ Workspace is now compliant!")
    else:
        print(f"⚠️  {final_violations} violations remain")
        print("   Run /cleanup again to review remaining items")


if __name__ == "__main__":
    main()
