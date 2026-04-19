#!/usr/bin/env python3
"""
Utilities for git sync script.

This module contains helper functions that can be imported and tested
without triggering the main sync script execution.
"""

import subprocess
from pathlib import Path
from typing import List, Dict, Union, Optional

# Constants for commit message generation
DEFAULT_COMMIT_MESSAGE = "chore: update files"
DEFAULT_SCOPE = "misc"
SCOPE_KEYWORDS = {
    "config": ("settings", "config"),
    "src": ("src/",),
    "tests": ("test",),
}


# =============================================================================
# Import commit message parser with fallback implementations
# =============================================================================

def _fallback_detect_file_type(path: str) -> str:
    """Fallback file type detection when commit_message_parser is unavailable."""
    if path.endswith(".py"):
        return "python"
    elif path.endswith(".md"):
        return "markdown"
    return "unknown"


def _fallback_detect_scope(files: List[str]) -> List[str]:
    """Fallback scope detection when commit_message_parser is unavailable."""
    return []


def _fallback_detect_commit_type(data: Dict) -> str:
    """Fallback commit type detection when commit_message_parser is unavailable."""
    return "chore"


# Try to import from commit_message_parser, use fallbacks if unavailable
try:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "hooks"))
    from commit_message_parser import (
        detect_file_type,
        detect_scope,
        detect_commit_type,
    )
except ImportError:
    detect_file_type = _fallback_detect_file_type
    detect_scope = _fallback_detect_scope
    detect_commit_type = _fallback_detect_commit_type


# =============================================================================
# Command execution
# =============================================================================

def run(
    cmd: Union[str, List[str]],
    cwd: Optional[Path] = None,
    silent: bool = False,
) -> subprocess.CompletedProcess:
    """
    Run a command and return the completed process result.

    Args:
        cmd: Command to run (string or list of strings)
        cwd: Working directory for command execution
        silent: If True, suppress output (unused, kept for API compatibility)

    Returns:
        subprocess.CompletedProcess object with returncode, stdout, stderr
    """
    if isinstance(cmd, str):
        cmd = cmd.split()
    # Prevent blue console flash on Windows
    import sys
    creation_flags = 0x08000000 if sys.platform == 'win32' else 0
    result = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, shell=False,
        creationflags=creation_flags
    )
    return result


# =============================================================================
# Commit message generation
# =============================================================================

def _infer_scope_from_path(file_path: str) -> Optional[str]:
    """
    Infer commit scope from a file path using keyword matching.

    Args:
        file_path: Path to examine for scope keywords

    Returns:
        Detected scope name or None if no match found
    """
    fp_lower = file_path.lower()
    for scope_name, keywords in SCOPE_KEYWORDS.items():
        if any(keyword in fp_lower for keyword in keywords):
            return scope_name
    return None


def generate_commit_message(repo_path: Optional[Path] = None) -> str:
    """
    Generate semantic commit message based on changed files.

    Args:
        repo_path: Path to git repository (defaults to current directory)

    Returns:
        Semantic commit message in format: type(scope): subject
    """
    if repo_path is None:
        repo_path = Path.cwd()

    # Get list of changed files
    result = run(["git", "diff", "--name-only", "HEAD"], cwd=repo_path, silent=True)

    if result.returncode != 0 or not result.stdout.strip():
        return DEFAULT_COMMIT_MESSAGE

    # Parse changed files
    changed_files = result.stdout.strip().split("\n")

    # Build file data structure with proper attributes
    files_data = []
    for file_path in changed_files:
        if not file_path:
            continue
        file_type = detect_file_type(file_path)
        files_data.append({
            "path": file_path,
            "type": file_type,
            "new": False,  # Can't determine from name-only diff
            "deleted": False
        })

    # Detect commit type and scope from parser
    commit_type = detect_commit_type({"files": files_data})
    scopes = detect_scope([f["path"] for f in files_data])

    # Infer scope from file paths if not detected
    if not scopes:
        for file_path in changed_files:
            if file_path:
                inferred = _infer_scope_from_path(file_path)
                if inferred:
                    scopes = [inferred]
                    break

    # Generate subject and format commit message
    if scopes:
        primary_scope = scopes[0]
        subject = f"update {primary_scope}"
        return f"{commit_type}({primary_scope}): {subject}"
    else:
        # Use generic scope if none detected
        subject = "update files"
        return f"{commit_type}({DEFAULT_SCOPE}): {subject}"
