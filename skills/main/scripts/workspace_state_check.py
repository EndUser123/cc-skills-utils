#!/usr/bin/env python3
"""
workspace_state_check.py - Check workspace state health

Run: python P:/.claude/skills/_tools/workspace_state_check.py
Returns exit code 0 if healthy, 1 if issues found

Checks:
1. RESTORE_CONTEXT.md presence (incomplete compaction recovery)
2. Git worktree health (detached heads, stale locks, prunable)
3. Uncommitted changes in worktrees
"""

import subprocess
import sys
from pathlib import Path

# Paths
PROJECT_ROOT = Path(r"P:/")
CLAUDE_DIR = PROJECT_ROOT / ".claude"
RESTORE_CONTEXT_PATH = CLAUDE_DIR / "RESTORE_CONTEXT.md"


def check_restore_context() -> tuple[bool, str | None]:
    """Check if RESTORE_CONTEXT.md exists (should not during normal operation)."""
    if RESTORE_CONTEXT_PATH.exists():
        size = RESTORE_CONTEXT_PATH.stat().st_size
        return True, f"RESTORE_CONTEXT.md exists ({size} bytes) - incomplete recovery"
    return False, None


def get_git_worktrees() -> list[dict]:
    """Get list of git worktrees with their state."""
    worktrees = []
    try:
        # Add CREATE_NO_WINDOW on Windows to prevent console flash
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        result = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=creation_flags,
        )
        if result.returncode != 0:
            return []

        current = {}
        for line in result.stdout.splitlines():
            if line.startswith("worktree "):
                if current:
                    worktrees.append(current)
                current = {"path": line[9:]}
            elif line.startswith("HEAD "):
                current["head"] = line[5:]
            elif line.startswith("branch "):
                current["branch"] = line[7:]
            elif line == "detached":
                current["detached"] = True
            elif line == "locked":
                current["locked"] = True
            elif line == "prunable":
                current["prunable"] = True

        if current:
            worktrees.append(current)

    except Exception:
        pass

    return worktrees


def check_worktree_uncommitted(worktree_path: str) -> int:
    """Check for uncommitted changes in a worktree."""
    try:
        # Add CREATE_NO_WINDOW on Windows to prevent console flash
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        result = subprocess.run(
            ["git", "-C", worktree_path, "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=creation_flags,
        )
        if result.returncode == 0:
            return len([l for l in result.stdout.splitlines() if l.strip()])
    except Exception:
        pass
    return 0


def check_git_locks() -> list[str]:
    """Check for stale git lock files."""
    locks = []
    git_dir = PROJECT_ROOT / ".git"
    if git_dir.exists():
        for lock in git_dir.rglob("*.lock"):
            locks.append(str(lock.relative_to(PROJECT_ROOT)))
    return locks


def main():
    issues = []
    warnings = []

    # 1. Check RESTORE_CONTEXT.md
    has_restore, restore_msg = check_restore_context()
    if has_restore:
        issues.append(restore_msg)

    # 2. Check git worktrees
    worktrees = get_git_worktrees()
    detached = [w for w in worktrees if w.get("detached")]
    locked = [w for w in worktrees if w.get("locked")]
    prunable = [w for w in worktrees if w.get("prunable")]

    if detached:
        for w in detached:
            warnings.append(f"Detached HEAD: {w['path']}")

    if locked:
        for w in locked:
            warnings.append(f"Locked worktree: {w['path']}")

    if prunable:
        for w in prunable:
            issues.append(f"Prunable worktree: {w['path']} (run: git worktree prune)")

    # 3. Check for stale locks
    locks = check_git_locks()
    if locks:
        for lock in locks[:5]:
            warnings.append(f"Stale lock: {lock}")

    # 4. Check uncommitted changes in main worktree
    uncommitted = check_worktree_uncommitted(str(PROJECT_ROOT))
    if uncommitted > 20:
        warnings.append(f"Main worktree: {uncommitted} uncommitted changes")

    # Output
    print(f"Worktrees: {len(worktrees)} | Uncommitted: {uncommitted}")

    # Always show worktree details for visibility (use bullet points for visibility in /main)
    if worktrees:
        for w in worktrees:
            branch = w.get("branch", "detached")
            flags = []
            if w.get("detached"):
                flags.append("DETACHED")
            if w.get("locked"):
                flags.append("LOCKED")
            if w.get("prunable"):
                flags.append("PRUNABLE")
            flag_str = f" [{', '.join(flags)}]" if flags else ""
            print(f"• {w['path']}: {branch}{flag_str}")

    if issues or warnings:
        if issues:
            for i in issues:
                print(f"• {i}")

        if warnings:
            for w in warnings:
                print(f"• {w}")

        if has_restore:
            print("• Run: /restore or delete P:/.claude/RESTORE_CONTEXT.md")
        return 1
    else:
        return 0


if __name__ == "__main__":
    sys.exit(main())
