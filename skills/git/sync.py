#!/usr/bin/env python3
"""
Smart Git Sync with Multi-Repo Discovery, Health Check, Worktree Management, and Conflict Resolution

Behavior:
- Non-main repos: auto-commit first so parent gitlinks can be updated cleanly
- Main repo (P:/.git): auto-commit after dependency repos, then auto-push
- All repos: auto-push after commits, with optional --select for manual control

Features:
- Detects all .git directories across the workspace
- Auto-resolves conflicts based on file type
- Dynamic push (detects remote name and branch automatically)
- Post-merge diff validation
- Context-aware output
"""

import subprocess
import sys
import json
import time
import argparse
import re
from pathlib import Path
from typing import Tuple, Optional, List, Dict, NamedTuple

# Import shared git guard config to prevent config divergence
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "hooks"))
from __lib.git_guard_config import DESTRUCTIVE_GIT_OPS
# Fail fast if shared config structure changes — defensive check
assert hasattr(DESTRUCTIVE_GIT_OPS["reset"], "danger_flags"), "git_guard_config structure changed"

# Import commit message parser
try:
    from commit_message_parser import (
        detect_file_type, detect_scope, detect_commit_type,
        generate_subject, generate_commit_body
    )
except ImportError:
    # Fallback if commit_message_parser is not available
    def detect_file_type(path): return "unknown"
    def detect_scope(files): return []
    def detect_commit_type(data): return "chore"
    def generate_subject(data): return "update files"
    def generate_commit_body(data): return ""

# Import sync utilities for commit message generation
sys.path.insert(0, str(Path(__file__).parent))
from sync_utils import generate_commit_message as generate_scoped_commit_message

# ============================================================
# CONFIGURATION
# ============================================================

MAIN_ROOT = Path("P:/")
if not MAIN_ROOT.exists():
    print("ERROR: P:/ drive not accessible", file=sys.stderr)
    sys.exit(1)
CLAUDE_DIR = MAIN_ROOT / ".claude"
WORKTREES_DIR = MAIN_ROOT / "worktrees"
MAIN_REPO_PATH = MAIN_ROOT / ".git"

# User home .claude directory (separate git repo, not under P:)
HOME_CLAUDE_DIR = Path.home() / ".claude"
HOME_REPO_GIT_DIR = HOME_CLAUDE_DIR / ".git"

# Repo classification
class RepoType:
    MAIN = "main"           # P:/.git - auto-push
    PACKAGE = "package"      # packages/*/.git
    MCP = "mcp"             # packages/.mcp/*/.git
    INTERNAL = "internal"   # .claude/hooks/.git, .claude/skills/*/.git
    NESTED = "nested"       # repos within other repos
    WORKTREE = "worktree"   # worktrees/*/.git
    HOME = "home"           # ~/.claude/ - user home git repo

# Conflict resolution strategies
CONFLICT_STRATEGIES = {
    # Session state is always local, never share
    ".claude/sessions/": "ours",

    # Committed code in main is source of truth
    ".py": "theirs",
    ".md": "theirs",
    ".ts": "theirs",
    ".js": "theirs",
    ".json": "theirs",
    ".yaml": "theirs",
    ".yml": "theirs",
    ".toml": "theirs",
    ".cfg": "theirs",
    ".ini": "theirs",

    # Config files may need both sides - manual
    ".env": "manual",
    ".env.local": "manual",
    ".env.production": "manual",
    "config.local": "manual",
}

# Parse arguments
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--verbose", "-v", action="store_true")
parser.add_argument("--health", action="store_true")
parser.add_argument("--fix", action="store_true")
parser.add_argument("--worktree", action="store_true")
parser.add_argument("--no-resolve", action="store_true")
parser.add_argument("--repos", default="all")  # all, packages, .claude, mcp
parser.add_argument("--select", default=None)  # comma-separated indices (e.g., "1,3" or "all")
parser.add_argument("worktree_action", nargs="?", default="list")
parser.add_argument("worktree_name", nargs="?", default=None)
args = parser.parse_args()

HEALTH_ONLY = args.health
AUTO_FIX = args.fix
VERBOSE = args.verbose
WORKTREE_MODE = args.worktree
WORKTREE_ACTION = args.worktree_action
WORKTREE_NAME = args.worktree_name
AUTO_RESOLVE = not args.no_resolve
REPOS_FILTER = args.repos
SELECT_REPOS = args.select

# ============================================================
# UTILITIES
# ============================================================

def _check_destructive_git(cmd_list: list) -> dict | None:
    """Check if git command is destructive. Returns danger info or None."""
    if not cmd_list or cmd_list[0] != "git" or len(cmd_list) < 2:
        return None

    subcommand = cmd_list[1].lower()
    if subcommand not in DESTRUCTIVE_GIT_OPS:
        return None

    op = DESTRUCTIVE_GIT_OPS[subcommand]
    # op is a DangerOp dataclass instance
    danger_flags = op.danger_flags or ()
    danger_subcommands = op.danger_subcommands or ()

    if danger_flags:
        has_danger_flag = any(flag in cmd_list for flag in danger_flags)
        if not has_danger_flag:
            return None
    elif danger_subcommands:
        if len(cmd_list) < 3 or cmd_list[2].lower() not in danger_subcommands:
            return None
    else:
        return None

    return {
        "subcommand": subcommand,
        "severity": op.severity,
        "command": " ".join(cmd_list),
    }

class _BlockedResult:
    """Result returned when a destructive git operation is blocked.

    Matches subprocess.CompletedProcess interface so callers that check
    returncode/stdout/stderr work correctly without knowing the operation
    was blocked.
    """
    def __init__(self):
        self.returncode = 1
        self.stdout = ""
        self.stderr = "blocked: destructive git operation"
        self.args: list[str] = []

    def check_returncode(self) -> None:
        if self.returncode != 0:
            raise subprocess.CalledProcessError(self.returncode, self.args)


def run(cmd, cwd=None, silent=False):
    """Run command and return result."""
    if isinstance(cmd, str):
        cmd = cmd.split()

    # Block destructive git operations from skill-internal subprocess calls
    # This closes the gap where PreToolUse hooks can't see skill subprocess git calls
    danger = _check_destructive_git(cmd)
    if danger and danger["severity"] in ("CRITICAL", "HIGH"):
        print(f"⛔ BLOCKED: Dangerous git operation via skill subprocess: {danger['command']}", file=sys.stderr)
        print("   Use explicit git commands in Claude Code instead.", file=sys.stderr)
        result = _BlockedResult()
        result.args = cmd
        return result

    # Prevent blue console flash on Windows
    creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    result = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, shell=False,
        creationflags=creation_flags
    )
    if VERBOSE and not silent and result.stdout:
        print(f"  {result.stdout.strip()}")
    return result

def color(text, status):
    """Color codes for output."""
    colors = {
        "success": "\033[92m",  # Green
        "error": "\033[91m",    # Red
        "warning": "\033[93m",  # Yellow
        "info": "\033[94m",     # Blue
        "repo": "\033[96m",     # Cyan - for repo names
        "reset": "\033[0m",
    }
    return f"{colors.get(status, '')}{text}{colors['reset']}"

def header(text):
    """Print section header."""
    print(f"\n{color('=' * 60, 'info')}")
    print(color(f"  {text}", "info"))
    print(color('=' * 60, 'info'))

def item(text, status, detail=""):
    """Print status item."""
    icons = {
        "ok": "✓",
        "error": "✗",
        "warning": "~",
        "info": "->",
        "pending": "o",
    }
    colored_text = color(f"{icons[status]} {text}", status)
    print(f"{colored_text}" + (f" ({detail})" if detail else ""))

# ============================================================
# MULTI-REPO DISCOVERY
# ============================================================

class RepoInfo(NamedTuple):
    path: Path
    git_dir: Path
    repo_type: str
    relative_path: str
    name: str

def is_nested_repo(repo: RepoInfo, all_repos: List[RepoInfo]) -> bool:
    """
    Check if repo is nested and should be excluded.
    Returns True if this repo should be excluded (it's inside another repo).

    A repo is nested if its path is a subdirectory of another repo's path.
    The main repo (P:/) is the exception - packages are legitimately under it.
    """
    # Main repo is never nested
    if repo.repo_type == RepoType.MAIN:
        return False

    # Normalize path for checking (replace backslashes with forward slashes)
    normalized_path = repo.relative_path.replace("\\", "/")

    # Repos inside .claude/ are always nested (should be part of main P: repo)
    if ".claude/" in normalized_path or normalized_path.startswith(".claude/"):
        return True

    # Repos inside packages/.mcp/ are nested (should be part of parent package or main)
    if "packages/.mcp/" in normalized_path:
        return True

    # Check if this repo is inside another package repo's working tree
    # For example: packages/gitready/skills/gitready is inside packages/gitready
    for other in all_repos:
        if other.repo_type == RepoType.MAIN:
            continue  # Main repo (P:/) contains everything legitimately

        if other == repo:
            continue  # Don't compare with self

        # Normalize other repo's path
        other_normalized = other.relative_path.replace("\\", "/")

        # Check if this repo's path starts with another repo's path
        # e.g., "packages/gitready/skills/gitready" starts with "packages/gitready"
        if normalized_path.startswith(other_normalized + "/"):
            return True  # This repo is nested inside another package repo

    return False

def find_all_git_repos() -> List[RepoInfo]:
    """Find all git repos under P:/"""
    repos = []
    seen_git_dirs = set()

    # Scan for all .git directories
    for git_dir in MAIN_ROOT.rglob(".git"):
        if git_dir in seen_git_dirs:
            continue
        seen_git_dirs.add(git_dir)

        repo_path = git_dir.parent

        # Skip system/administrative paths that are not real repos
        rel_path = str(repo_path.relative_to(MAIN_ROOT))
        if "$RECYCLE.BIN" in rel_path or "/tmp/" in rel_path or rel_path.startswith("tmp/"):
            continue

        # Determine repo type based on path

        if git_dir == MAIN_REPO_PATH:
            repo_type = RepoType.MAIN
            name = "main"
        elif ".claude/hooks" in rel_path:
            repo_type = RepoType.INTERNAL
            name = ".claude/hooks"
        elif ".claude/skills" in rel_path:
            repo_type = RepoType.INTERNAL
            name = rel_path.replace(".claude/skills/", "").split("/")[0] if "/" in rel_path else "skill"
        elif "packages/.mcp" in rel_path:
            repo_type = RepoType.MCP
            name = rel_path.replace("packages/.mcp/", "").split("/")[0]
        elif "packages/" in rel_path:
            repo_type = RepoType.PACKAGE
            name = rel_path.replace("packages/", "").split("/")[0]
        elif "worktrees/" in rel_path:
            repo_type = RepoType.WORKTREE
            name = rel_path.replace("worktrees/", "").split("/")[0]
        else:
            repo_type = RepoType.NESTED
            name = rel_path.split("/")[-1]

        repos.append(RepoInfo(
            path=repo_path,
            git_dir=git_dir,
            repo_type=repo_type,
            relative_path=rel_path,
            name=name
        ))

    # Also check user home .claude repo (separate git repo, not under P:/)
    if HOME_REPO_GIT_DIR.exists():
        repos.append(RepoInfo(
            path=HOME_CLAUDE_DIR,
            git_dir=HOME_REPO_GIT_DIR,
            repo_type=RepoType.HOME,
            relative_path="~/.claude",
            name="~/.claude"
        ))

    # Filter out nested repos (repos inside other repos' working trees)
    # This catches unintended nested .git folders like .claude/hooks/.git
    non_nested_repos = []
    for repo in repos:
        if is_nested_repo(repo, repos):
            # Skip this nested repo - it's inside another repo
            continue
        non_nested_repos.append(repo)

    return non_nested_repos

def filter_repos(repos: List[RepoInfo], filter_type: str) -> List[RepoInfo]:
    """Filter repos by type"""
    if filter_type == "all":
        return repos
    elif filter_type == "packages":
        return [r for r in repos if r.repo_type == RepoType.PACKAGE]
    elif filter_type == ".claude":
        return [r for r in repos if r.repo_type == RepoType.INTERNAL]
    elif filter_type == "mcp":
        return [r for r in repos if r.repo_type == RepoType.MCP]
    elif filter_type == "home":
        return [r for r in repos if r.repo_type == RepoType.HOME]
    elif filter_type == "non-main":
        return [r for r in repos if r.repo_type != RepoType.MAIN]
    return repos

def get_repo_status(repo: RepoInfo) -> Tuple[bool, int, int]:
    """Check if repo has unpushed commits. Returns (has_remote, commits_ahead, commits_behind)

    - commits_ahead > 0 and commits_behind == 0: simple ahead (can push)
    - commits_ahead == 0 and commits_behind > 0: simple behind (can pull)
    - commits_ahead > 0 and commits_behind > 0: diverged (need manual resolution)
    - commits_ahead == 0 and commits_behind == 0: up-to-date
    """
    # Check if repo has a remote
    remote_result = run(["git", "remote"], cwd=repo.path, silent=True)
    has_remote = remote_result.returncode == 0 and bool(remote_result.stdout.strip())

    if not has_remote:
        return False, 0, 0

    # Get current branch
    branch_result = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo.path, silent=True)
    branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "HEAD"

    # Check commits ahead of remote/branch
    remote_name = remote_result.stdout.strip().split("\n")[0]  # Use first remote

    # Local commits not on remote (ahead)
    ahead_result = run(
        ["git", "rev-list", "--count", f"origin/{branch}..HEAD"],
        cwd=repo.path,
        silent=True
    )

    # Remote commits not on local (behind)
    behind_result = run(
        ["git", "rev-list", "--count", f"HEAD..origin/{branch}"],
        cwd=repo.path,
        silent=True
    )

    commits_ahead = int(ahead_result.stdout.strip()) if ahead_result.returncode == 0 else -1
    commits_behind = int(behind_result.stdout.strip()) if behind_result.returncode == 0 else -1

    return True, commits_ahead, commits_behind

# ============================================================
# COMMIT MESSAGE GENERATION
# ============================================================

def generate_commit_message_for_repo(repo: RepoInfo) -> str:
    """
    Generate semantic commit message based on changed files in a specific repo.
    Uses path-based scope detection.
    """
    # Get list of changed files
    result = run(["git", "diff", "--name-only", "HEAD"], cwd=repo.path, silent=True)

    if result.returncode != 0 or not result.stdout.strip():
        return "chore: update files"

    # Parse changed files
    changed_files = result.stdout.strip().split("\n")

    # Build file data structure
    files_data = []
    for file_path in changed_files:
        if not file_path:
            continue
        file_type = detect_file_type(file_path)
        files_data.append({"path": file_path, "type": file_type})

    # Detect commit type and scope
    commit_type = detect_commit_type({"files": files_data})
    scopes = detect_scope([f["path"] for f in files_data])

    # Use repo-relative path as scope if no scope detected
    if not scopes:
        # Extract meaningful scope from repo path
        if repo.repo_type == RepoType.PACKAGE:
            scopes = [repo.name]
        elif repo.repo_type == RepoType.MCP:
            scopes = [f"mcp/{repo.name}"]
        elif repo.repo_type == RepoType.INTERNAL:
            scopes = [f".claude/{repo.name}"]
        else:
            scopes = [repo.name]

    # Generate subject
    if scopes:
        primary_scope = scopes[0] if len(scopes) == 1 else ",".join(scopes[:2])
        subject = f"update {primary_scope}"
    else:
        subject = "update files"

    # Format semantic commit message
    if scopes:
        return f"{commit_type}({scopes[0]}): {subject}"
    else:
        return f"{commit_type}: {subject}"

# ============================================================
# PUSH FUNCTIONS
# ============================================================

def get_push_target(repo_path: Path) -> Tuple[Optional[str], Optional[str], str]:
    """
    Get the remote and branch to push to.
    Returns: (remote, branch, error_msg)
    """
    # Get remote name
    remote_result = run(["git", "remote"], cwd=repo_path, silent=True)
    if remote_result.returncode != 0 or not remote_result.stdout.strip():
        return None, None, "No remote configured"
    remote = remote_result.stdout.strip().split("\n")[0]

    # Get current branch
    branch_result = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path, silent=True)
    if branch_result.returncode != 0:
        return None, None, "Cannot determine current branch"
    branch = branch_result.stdout.strip()

    # Get remote URL for error messages
    url_result = run(["git", "remote", "get-url", remote], cwd=repo_path, silent=True)
    remote_url = url_result.stdout.strip() if url_result.returncode == 0 else "unknown"

    return remote, branch, remote_url

def push_repo(repo: RepoInfo, silent: bool = False) -> Tuple[bool, str]:
    """
    Push a repo to its remote.
    Returns: (success, message)
    """
    remote, branch, remote_url = get_push_target(repo.path)

    if not remote or not branch:
        return False, f"{remote_url}"

    # Check if we have commits to push
    check_result = run(
        ["git", "rev-list", "--count", f"{remote}/{branch}..HEAD"],
        cwd=repo.path,
        silent=True
    )

    if check_result.returncode != 0:
        return False, f"Cannot determine commits ahead"

    commits_ahead = int(check_result.stdout.strip())
    if commits_ahead == 0:
        return True, "Already up-to-date"

    # Perform push
    push_result = run(
        ["git", "push", remote, branch],
        cwd=repo.path,
        silent=silent
    )

    if push_result.returncode == 0:
        return True, f"Pushed {commits_ahead} commit(s) to {remote}/{branch}"
    else:
        error = push_result.stderr.strip()
        # Provide actionable error messages
        if "authentication" in error.lower() or "credential" in error.lower():
            action = f"Run 'git push' manually in {repo.path} to authenticate"
        elif "rejected" in error.lower():
            action = f"Push rejected - remote has commits that local doesn't. Pull first in {repo.path}"
        elif "not found" in error.lower():
            action = f"Remote branch {branch} not found. Create it with 'git push {remote} {branch}'"
        else:
            action = f"Run 'git push' manually in {repo.path} to diagnose"
        return False, f"{error}. {action}"

# ============================================================
# INTERACTIVE SELECTION (like /rns)
# ============================================================

def parse_selection(selection: str, max_idx: int) -> List[int]:
    """Parse user selection string like '1,3', '1-3', 'all', '*'"""
    selection = selection.strip().lower()

    if selection in ("all", "*"):
        return list(range(1, max_idx + 1))

    indices = set()

    # Handle comma-separated
    for part in selection.split(","):
        part = part.strip()
        if not part:
            continue

        # Handle ranges
        if "-" in part:
            start_end = part.split("-")
            if len(start_end) == 2:
                try:
                    start = int(start_end[0])
                    end = int(start_end[1])
                    indices.update(range(start, end + 1))
                except ValueError:
                    pass
        else:
            # Single number
            try:
                indices.add(int(part))
            except ValueError:
                pass

    # Filter valid indices
    return sorted([i for i in indices if 1 <= i <= max_idx])

def interactive_select_repos(repos: List[RepoInfo]) -> List[RepoInfo]:
    """
    Present numbered list for Claude to present to the user.
    Returns empty list - Claude handles user selection via --select flag.
    """
    if not repos:
        return []

    print(f"\nNon-main repos with unpushed commits:\n")

    for i, repo in enumerate(repos, 1):
        has_remote, commits_ahead, commits_behind = get_repo_status(repo)
        if not has_remote:
            status = color("no remote", "warning")
        elif commits_ahead > 0 and commits_behind > 0:
            status = color(f"diverged ({commits_ahead} ahead, {commits_behind} behind)", "error")
        elif commits_ahead > 0:
            status = f"{commits_ahead} commit(s) ahead"
        elif commits_behind > 0:
            status = color(f"behind {commits_behind}", "warning")
        else:
            status = "up-to-date"
        full_path = str(repo.path)
        print(f"  {i} {full_path} - {status}")

    print(f"\n0 — Push all ({len(repos)} repos)")
    print(f"\nUse /git --select <numbers> to push selected repos")
    print(f"Example: /git --select 1,3 or /git --select all")

    return []

# ============================================================
# WORKTREE MANAGEMENT
# ============================================================

def worktree_list():
    """List all worktrees."""
    result = run(["git", "worktree", "list"], cwd=MAIN_ROOT, silent=False)
    if result.returncode == 0:
        lines = result.stdout.strip().split("\n")
        header(f"WORKTREES ({len(lines)})")
        for line in lines:
            parts = line.split()
            if len(parts) >= 3:
                path, commit, branch = parts[0], parts[1], " ".join(parts[2:])
                branch = branch.strip("[]")
                # Check if this is the current worktree
                is_current = Path.cwd() == Path(path)
                prefix = "* " if is_current else "  "
                print(f"{prefix}{branch}")
                print(f"     Path: {path}")
                print(f"     Commit: {commit[:8]}")
    else:
        print(f"X Failed to list worktrees: {result.stderr}")
    sys.exit(0)

def worktree_add(name: str):
    """Create a new worktree."""
    if not name:
        print("X Error: worktree name required")
        print("  Usage: /git --worktree add <name>")
        sys.exit(1)

    worktree_path = WORKTREES_DIR / name
    branch_name = name.replace("-", "/")

    header(f"CREATE WORKTREE: {name}")

    if worktree_path.exists():
        item("Worktree path", "error", f"Already exists: {worktree_path}")
        sys.exit(1)

    # Create worktree
    result = run([
        "git", "worktree", "add",
        str(worktree_path),
        "-b", branch_name
    ], cwd=MAIN_ROOT, silent=not VERBOSE)

    if result.returncode == 0:
        item("Worktree created", "ok", f"Path: {worktree_path}")
        item("Branch", "ok", branch_name)
        print("\nNext steps:")
        print(f"  cd {worktree_path}")
        print("  /git  # Sync when ready")
    else:
        item("Failed", "error", result.stderr.strip())
        sys.exit(1)
    sys.exit(0)

def worktree_remove(name: str):
    """Remove a worktree."""
    if not name:
        print("X Error: worktree name required")
        print("  Usage: /git --worktree remove <name>")
        sys.exit(1)

    worktree_path = WORKTREES_DIR / name

    header(f"REMOVE WORKTREE: {name}")

    if not worktree_path.exists():
        item("Worktree path", "error", f"Not found: {worktree_path}")
        sys.exit(1)

    # Remove worktree
    result = run([
        "git", "worktree", "remove",
        str(worktree_path)
    ], cwd=MAIN_ROOT, silent=not VERBOSE)

    if result.returncode == 0:
        item("Worktree removed", "ok", f"Path: {worktree_path}")
        print(f"\nNote: Branch '{name.replace('-', '/')}' still exists.")
        print(f"      Delete it with: git branch -d {name.replace('-', '/')}")
    else:
        item("Failed", "error", result.stderr.strip())
        print("\nTip: Worktree may have uncommitted changes.")
        print(f"     cd {worktree_path}")
        print("     git stash  # or commit changes")
        sys.exit(1)
    sys.exit(0)

def worktree_prune():
    """Prune stale worktrees."""
    header("PRUNE STALE WORKTREES")

    result = run(["git", "worktree", "prune"], cwd=MAIN_ROOT, silent=not VERBOSE)

    if result.returncode == 0:
        item("Pruned", "ok", "Stale worktrees cleaned up")
        print("\nRun '/git --worktree' to see remaining worktrees.")
    else:
        item("Failed", "error", result.stderr.strip())
        sys.exit(1)
    sys.exit(0)

# ============================================================
# CONFLICT RESOLUTION
# ============================================================

def get_conflict_strategy(file_path: str) -> str:
    """Determine conflict resolution strategy for a file."""
    # Check for exact path matches first
    for pattern, strategy in CONFLICT_STRATEGIES.items():
        if pattern.startswith('.'):
            # Extension match
            if file_path.endswith(pattern):
                return strategy
        elif file_path.startswith(pattern):
            # Path prefix match
            return strategy
        elif pattern in file_path:
            # Contains pattern
            return strategy

    # Default: manual resolution for unknown files
    return "manual"

def detect_conflicts(repo: Path) -> List[str]:
    """Detect conflicted files in repo."""
    result = run(["git", "diff", "--name-only", "--diff-filter=U"], cwd=repo, silent=True)
    if result.returncode == 0:
        return result.stdout.strip().split("\n") if result.stdout.strip() else []
    return []

def resolve_conflicts(repo: Path, conflicts: List[str]) -> Tuple[int, int, List[str]]:
    """
    Auto-resolve conflicts based on file type.
    Returns: (resolved_count, manual_count, unresolved_files)
    """
    resolved = 0
    manual = 0
    unresolved = []

    for conflicted_file in conflicts:
        strategy = get_conflict_strategy(conflicted_file)

        if strategy == "ours":
            run(["git", "checkout", "--ours", conflicted_file], cwd=repo, silent=not VERBOSE)
            run(["git", "add", conflicted_file], cwd=repo, silent=True)
            item(f"Resolved: {conflicted_file}", "ok", "Kept local (ours)")
            resolved += 1
        elif strategy == "theirs":
            run(["git", "checkout", "--theirs", conflicted_file], cwd=repo, silent=not VERBOSE)
            run(["git", "add", conflicted_file], cwd=repo, silent=True)
            item(f"Resolved: {conflicted_file}", "ok", "Used incoming (theirs)")
            resolved += 1
        else:  # manual
            item(f"Manual: {conflicted_file}", "warning", "Requires review")
            manual += 1
            unresolved.append(conflicted_file)

    return resolved, manual, unresolved

def ensure_diff3_config() -> None:
    """Ensure git is configured for three-way merge conflicts."""
    result = run(["git", "config", "merge.conflictstyle"], silent=True)
    if result.returncode == 0:
        current = result.stdout.strip()
        if current != "diff3":
            run(["git", "config", "merge.conflictstyle", "diff3"], silent=not VERBOSE)
            if VERBOSE:
                print("-> Set merge.conflictstyle=diff3 (shows BASE marker in conflicts)")
    else:
        run(["git", "config", "merge.conflictstyle", "diff3"], silent=not VERBOSE)

# ============================================================
# SYNC FUNCTIONS
# ============================================================

def sync_single_repo(repo: RepoInfo, is_main: bool = False) -> bool:
    """
    Sync a single repo: commit if needed, optionally push.
    Returns True if sync succeeded.
    """
    worktree = repo.path

    # Check for unstaged or untracked changes (not just any output from status --short)
    if _has_uncommitted_worktree_changes(repo):
        run("git add -A", cwd=worktree, silent=not VERBOSE)

        # Generate scoped commit message
        commit_msg = generate_commit_message_for_repo(repo)

        run([
            "git", "commit", "-m", commit_msg
        ], cwd=worktree, silent=not VERBOSE)

        if VERBOSE:
            print(f"  Committed: {commit_msg}")

    # Push if main repo (auto-push)
    if is_main:
        success, msg = push_repo(repo, silent=not VERBOSE)
        if success:
            item(f"Push to origin", "ok", msg)
        else:
            item(f"Push to origin", "warning", msg)

    return True


def _has_uncommitted_worktree_changes(repo: RepoInfo) -> bool:
    """Return True when a repo has unstaged modifications or untracked files.

    Ignores staged changes that are already on origin — only flags new changes
    that haven't been committed yet. This prevents noise like 'still dirty' after
    a commit that correctly captured all new changes.
    """
    # --porcelain gives stable machine-readable output
    status = run(
        ["git", "status", "--porcelain"],
        cwd=repo.path,
        silent=True,
    )
    if status.returncode != 0:
        return False

    for line in status.stdout.splitlines():
        if not line:
            continue
        # Porcelain format: XY filename
        # X = index/staged status, Y = worktree status
        # "  " = clean in both (never happens here since stdout.strip() is non-empty)
        # "??" = untracked file in worktree (new, not in index)
        # X != space = staged change (already tracked, not "uncommitted" in the dirty sense)
        # Y != space = worktree differs from index → unstaged modification
        if line.startswith("??"):
            return True  # untracked file — new change not in git
        col2 = line[1:2]
        if col2 != " ":
            return True  # worktree modification — unstaged change
        # col1 != space (staged change) is already on origin or in a prior commit — ignore
    return False


def repo_has_worktree_changes(repo: RepoInfo) -> bool:
    """Return True when a repo has uncommitted worktree changes."""
    return _has_uncommitted_worktree_changes(repo)

# ============================================================
# PHASE 0: WORKTREE MODE (exits early)
# ============================================================

if WORKTREE_MODE:
    if WORKTREE_ACTION == "list":
        worktree_list()
    elif WORKTREE_ACTION == "add":
        worktree_add(WORKTREE_NAME)
    elif WORKTREE_ACTION == "remove":
        worktree_remove(WORKTREE_NAME)
    elif WORKTREE_ACTION == "prune":
        worktree_prune()
    else:
        print(f"X Unknown worktree action: {WORKTREE_ACTION}")
        print("  Valid actions: list, add, remove, prune")
        sys.exit(1)

# ============================================================
# PHASE 1: MULTI-REPO DISCOVERY
# ============================================================

all_repos = find_all_git_repos()
non_main_repos = [r for r in all_repos if r.repo_type != RepoType.MAIN]
main_repo = next((r for r in all_repos if r.repo_type == RepoType.MAIN), None)

if VERBOSE:
    print(f"Discovered {len(all_repos)} git repos:")
    for repo in all_repos:
        print(f"  [{repo.repo_type}] {repo.relative_path}")

# ============================================================
# PHASE 2: HEALTH CHECK (always shown)
# ============================================================

header("GIT REPOS HEALTH")

for repo in all_repos:
    has_remote, commits_ahead, commits_behind = get_repo_status(repo)
    is_dirty = repo_has_worktree_changes(repo)
    detail_parts = []
    if is_dirty:
        detail_parts.append("dirty")
    if not has_remote:
        status = "warning"
        detail_parts.append("no remote")
    elif commits_ahead > 0 and commits_behind > 0:
        status = "error"
        detail_parts.append(f"diverged ({commits_ahead} ahead, {commits_behind} behind)")
    elif commits_ahead > 0:
        status = "warning"
        detail_parts.append(f"{commits_ahead} ahead")
    elif commits_behind > 0:
        status = "warning"
        detail_parts.append(f"behind {commits_behind}")
    else:
        status = "ok"
        detail_parts.append("ok")
    if is_dirty and status == "ok":
        status = "warning"
    detail = ", ".join(detail_parts)
    item(repo.relative_path, status, detail)

# Worktree listing
result = run(["git", "worktree", "list"], cwd=MAIN_ROOT, silent=True)
if result.returncode == 0 and result.stdout.strip():
    print()
    print("  Worktrees:")
    for line in result.stdout.strip().split("\n"):
        parts = line.split()
        if len(parts) >= 3:
            path, commit = parts[0], parts[1]
            branch = parts[2].strip("[]") if len(parts) > 2 else "?"
            is_current = Path.cwd().resolve() == Path(path).resolve()
            prefix = "  * " if is_current else "    "
            print(f"{prefix}{branch} at {path}")

if HEALTH_ONLY:
    sys.exit(0)

# ============================================================
# PHASE 3: AUTO-FIX
# ============================================================

if AUTO_FIX:
    header("AUTO-FIX")
    # Placeholder for future auto-fix logic
    pass

# ============================================================
# PHASE 4: SYNC NON-MAIN REPOS (COMMIT FIRST)
# ============================================================

header("SYNC NON-MAIN REPOS")

non_main_scope = non_main_repos
if REPOS_FILTER != "all":
    non_main_scope = filter_repos(non_main_scope, REPOS_FILTER)

if non_main_scope:
    for repo in non_main_scope:
        sync_single_repo(repo, is_main=False)
else:
    print("  No non-main repos selected.")

# ============================================================
# PHASE 5: SYNC MAIN REPO (AFTER NON-MAIN COMMITS)
# ============================================================

header("SYNC MAIN REPO")

if main_repo:
    print(f"  Committing {color('main', 'repo')} after dependency repos...")

    # Ensure git is configured for three-way merge conflicts
    ensure_diff3_config()

    sync_single_repo(main_repo, is_main=False)
else:
    item("Main repo", "error", "Not found at P:/.git")

# ============================================================
# PHASE 6: PUSH NON-MAIN REPOS
# ============================================================

# Find non-main repos that have remotes and commits to push
# Exclude diverged repos (ahead AND behind) since they need manual resolution
issues = []  # Track issues for Recommended Next Steps
repos_with_pushes = []
for repo in non_main_scope:
    has_remote, commits_ahead, commits_behind = get_repo_status(repo)
    if has_remote and commits_ahead > 0 and commits_behind == 0:
        repos_with_pushes.append(repo)

if repos_with_pushes:
    # Use --select flag if provided, otherwise push all repos by default
    if SELECT_REPOS is not None:
        # Parse --select argument
        selected_indices = parse_selection(SELECT_REPOS, len(repos_with_pushes))
        selected_repos = [repos_with_pushes[i - 1] for i in selected_indices]
    else:
        selected_repos = repos_with_pushes

    if selected_repos:
        header("PUSHING SELECTED REPOS")
        for repo in selected_repos:
            print(f"  Pushing {color(repo.relative_path, 'repo')}...")
            success, msg = push_repo(repo, silent=False)
            if success:
                item("Push", "ok", msg)
            else:
                item("Push", "warning", msg)
                # Offer specific solutions based on error type
                error_lower = msg.lower()
                if "repository not found" in error_lower or "remote branch" in error_lower:
                    repo_name = repo.name.replace("\\", "/")
                    issues.append(("push_failed", repo, f"Remote repo missing — create it: gh repo create {repo_name} --public\n"
                        f"    Or remove remote: cd {repo.path} && git remote remove origin"))
                elif "authentication" in error_lower or "credential" in error_lower:
                    issues.append(("push_failed", repo, f"Auth failed — run 'git push' manually to authenticate"))
                else:
                    issues.append(("push_failed", repo, f"Push failed — {msg.split(' — ')[-1] if ' — ' in msg else msg}"))
    else:
        print("\nNo repos selected - skipping non-main pushes.")
elif VERBOSE:
    print("\nNo non-main repos have unpushed commits.")

# ============================================================
# PHASE 7: PUSH MAIN REPO
# ============================================================

if main_repo:
    print(f"\n  Pushing {color('main', 'repo')}...")
    success, msg = push_repo(main_repo, silent=not VERBOSE)
    if success:
        item("Push to origin", "ok", msg)
    else:
        item("Push to origin", "warning", msg)

# ============================================================
# PHASE 8: POST-SYNC CLEANLINESS CHECK
# ============================================================

remaining_dirty = [repo for repo in all_repos if repo_has_worktree_changes(repo)]
if remaining_dirty:
    issues.append((
        "dirty",
        None,
        "Uncommitted changes remain after sync:\n"
        + "\n".join(f"    - {repo.relative_path}" for repo in remaining_dirty)
    ))

# ============================================================
# PHASE 6: RECOMMENDED NEXT STEPS
# ============================================================

# Collect issues for actionable recommendations (push failures added during Phase 5)
stash_count = 0

# Check for stashes in main repo
if main_repo:
    stash_result = run(["git", "stash", "list"], cwd=main_repo.path, silent=True)
    if stash_result.returncode == 0 and stash_result.stdout.strip():
        stashes = stash_result.stdout.strip().split("\n")
        stash_count = len(stashes)

# Check for repos needing attention
for repo in all_repos:
    has_remote, commits_ahead, commits_behind = get_repo_status(repo)
    if not has_remote and repo.repo_type == RepoType.PACKAGE:
        issues.append(("no_remote", repo, f"No remote — add one with: cd {repo.path} && git remote add origin <url>"))
    elif commits_ahead > 0 and commits_behind > 0:
        issues.append(("diverged", repo, f"Diverged — resolve with: cd {repo.path} && git pull --rebase"))
    elif commits_behind > 0:
        issues.append(("behind", repo, f"Behind remote — pull with: cd {repo.path} && git pull"))

if stash_count > 0:
    issues.append(("stash", None, f"Stash available — apply with: git stash pop"))

if issues:
    print(f"\n{color('=' * 60, 'info')}")
    print(f"\n{color('RECOMMENDED NEXT STEPS:', 'info')}")
    for issue_type, repo, recommendation in issues:
        status = "✗" if issue_type in ("diverged", "no_remote", "dirty") else "~"
        name = repo.name if repo else "main"
        print(f"  {status} {name}: {recommendation}")
    print(f"{color('=' * 60, 'info')}\n")
else:
    print(f"\n{color('=' * 60, 'info')}")
    print(f"  {color('✓', 'success')} All repos in sync")
    print(f"{color('=' * 60, 'info')}\n")
