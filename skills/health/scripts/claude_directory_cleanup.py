#!/usr/bin/env python3
"""
claude_directory_cleanup.py - Cleanup junk from .claude directory

Uses patterns from directory_policy.json to identify and remove junk files.
Safe by default - dry-run mode shows what would be deleted.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Configuration
CLAUDE_DIR = Path("P:\\\\\\.claude")
POLICY_FILE = CLAUDE_DIR / "hooks" / "config" / "directory_policy.json"
DRY_RUN = True  # Safe default - set to False to actually delete


def load_policy() -> dict[str, Any]:
    """Load directory policy from JSON config."""
    if not POLICY_FILE.exists():
        print(f"ERROR: Policy file not found: {POLICY_FILE}")
        sys.exit(1)

    with open(POLICY_FILE, encoding="utf-8") as f:
        return json.load(f)


def match_pattern(filename: str, pattern: str) -> bool:
    """Simple glob pattern matching (supports * wildcard)."""
    import fnmatch

    return fnmatch.fnmatch(filename, pattern)


def cleanup_files(policy: dict[str, Any], dry_run: bool = True) -> dict[str, list[str]]:
    """Clean up junk files based on policy patterns."""
    if not CLAUDE_DIR.exists():
        print(f"ERROR: .claude directory not found: {CLAUDE_DIR}")
        sys.exit(1)

    claude_policy = policy.get("claude_directory", {})
    blocked_patterns = claude_policy.get("blocked_root_patterns", {}).get("patterns", [])

    deleted = {"files": [], "directories": [], "skipped": []}

    # Check files
    for item in CLAUDE_DIR.iterdir():
        if item.is_file():
            for pattern_def in blocked_patterns:
                pattern = pattern_def.get("pattern", "")
                if match_pattern(item.name, pattern):
                    if dry_run:
                        deleted["files"].append(
                            f"{item.name} ({pattern_def.get('reason', 'No reason')})"
                        )
                    else:
                        try:
                            item.unlink()
                            deleted["files"].append(f"{item.name} (DELETED)")
                        except OSError as e:
                            deleted["skipped"].append(f"{item.name} ({e})")
                    break

    # Check cache directories
    cache_dirs = claude_policy.get("cache_directories", {}).get("directories", [])
    for cache_def in cache_dirs:
        cache_path = CLAUDE_DIR / cache_def["path"]
        if cache_path.exists() and cache_path.is_dir():
            if dry_run:
                deleted["directories"].append(
                    f"{cache_def['path']}/ ({cache_def.get('reason', 'No reason')})"
                )
            else:
                try:
                    import shutil

                    shutil.rmtree(cache_path)
                    deleted["directories"].append(f"{cache_def['path']}/ (DELETED)")
                except OSError as e:
                    deleted["skipped"].append(f"{cache_def['path']}/ ({e})")

    # Check backup directories
    backup_dirs = claude_policy.get("backup_directories", {}).get("directories", [])
    for backup_def in backup_dirs:
        # Handle glob patterns like agents.backup.*
        if "*" in backup_def["path"]:
            import fnmatch

            for item in CLAUDE_DIR.iterdir():
                if item.is_dir() and fnmatch.fnmatch(item.name, backup_def["path"]):
                    if dry_run:
                        deleted["directories"].append(
                            f"{item.name}/ ({backup_def.get('reason', 'No reason')})"
                        )
                    else:
                        try:
                            import shutil

                            shutil.rmtree(item)
                            deleted["directories"].append(f"{item.name}/ (DELETED)")
                        except OSError as e:
                            deleted["skipped"].append(f"{item.name}/ ({e})")
        else:
            backup_path = CLAUDE_DIR / backup_def["path"]
            if backup_path.exists() and backup_path.is_dir():
                if dry_run:
                    deleted["directories"].append(
                        f"{backup_def['path']}/ ({backup_def.get('reason', 'No reason')})"
                    )
                else:
                    try:
                        import shutil

                        shutil.rmtree(backup_path)
                        deleted["directories"].append(f"{backup_def['path']}/ (DELETED)")
                    except OSError as e:
                        deleted["skipped"].append(f"{backup_def['path']}/ ({e})")

    return deleted


def print_summary(deleted: dict[str, list[str]], dry_run: bool = True) -> None:
    """Print cleanup summary."""
    mode = "DRY RUN - No files will be deleted" if dry_run else "LIVE - Files will be deleted"

    print(f"\n{'=' * 60}")
    print(f".claude DIRECTORY CLEANUP - {mode}")
    print(f"{'=' * 60}\n")

    if deleted["files"]:
        print(f"Files ({len(deleted['files'])}):")
        for item in deleted["files"]:
            print(f"  • {item}")
        print()

    if deleted["directories"]:
        print(f"Directories ({len(deleted['directories'])}):")
        for item in deleted["directories"]:
            print(f"  • {item}")
        print()

    if deleted["skipped"]:
        print(f"Skipped ({len(deleted['skipped'])}):")
        for item in deleted["skipped"]:
            print(f"  • {item}")
        print()

    total = len(deleted["files"]) + len(deleted["directories"])
    print(f"Total: {total} item(s)")

    if dry_run:
        print("\nTo actually delete, run: python claude_directory_cleanup.py --execute")


def main() -> int:
    """Main entry point."""
    global DRY_RUN

    # Check for --execute flag
    if "--execute" in sys.argv:
        DRY_RUN = False

    # Load policy
    policy = load_policy()

    # Run cleanup
    deleted = cleanup_files(policy, dry_run=DRY_RUN)

    # Print summary
    print_summary(deleted, dry_run=DRY_RUN)

    return 0


if __name__ == "__main__":
    sys.exit(main())
