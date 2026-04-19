#!/usr/bin/env python3
"""
Tests for destructive git operation guard in sync.py.

Verifies that _check_destructive_git() correctly identifies and blocks
critical git operations that bypass PreToolUse hooks when run via skill subprocess.

Run with: pytest tests/test_destructive_git_guard.py -v
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestCheckDestructiveGit:
    """Tests for _check_destructive_git guard function."""

    @pytest.fixture
    def guard_function(self):
        """Import and return the _check_destructive_git function."""
        parent_dir = Path(__file__).parent.parent
        sys.path.insert(0, str(parent_dir))

        # Import sync module and extract the guard function
        import sync
        return sync._check_destructive_git

    # === Positive cases: should be blocked ===

    def test_blocks_git_reset_hard(self, guard_function):
        """git reset --hard should be blocked (CRITICAL severity)."""
        cmd = ["git", "reset", "--hard", "HEAD~1"]
        result = guard_function(cmd)
        assert result is not None, "git reset --hard must be detected"
        assert result["severity"] == "CRITICAL"
        assert result["subcommand"] == "reset"

    def test_blocks_git_reset_hard_with_commit(self, guard_function):
        """git reset --hard <commit> should be blocked."""
        cmd = ["git", "reset", "--hard", "origin/main"]
        result = guard_function(cmd)
        assert result is not None, "git reset --hard origin/main must be detected"
        assert result["severity"] == "CRITICAL"

    def test_blocks_git_clean_full(self, guard_function):
        """git clean -fd should be detected (HIGH severity)."""
        cmd = ["git", "clean", "-fd"]
        result = guard_function(cmd)
        assert result is not None, "git clean -fd must be detected"
        assert result["severity"] == "HIGH"
        assert result["subcommand"] == "clean"

    def test_blocks_git_stash_drop(self, guard_function):
        """git stash drop should be detected (HIGH severity)."""
        cmd = ["git", "stash", "drop", "stash@{0}"]
        result = guard_function(cmd)
        assert result is not None, "git stash drop must be detected"
        assert result["severity"] == "HIGH"
        assert result["subcommand"] == "stash"

    def test_blocks_git_stash_clear(self, guard_function):
        """git stash clear should be detected (HIGH severity)."""
        cmd = ["git", "stash", "clear"]
        result = guard_function(cmd)
        assert result is not None, "git stash clear must be detected"
        assert result["severity"] == "HIGH"

    # === Negative cases: should be allowed ===

    def test_allows_git_status(self, guard_function):
        """git status should NOT be blocked."""
        cmd = ["git", "status"]
        result = guard_function(cmd)
        assert result is None, "git status must not be flagged as destructive"

    def test_allows_git_add(self, guard_function):
        """git add should NOT be blocked."""
        cmd = ["git", "add", "."]
        result = guard_function(cmd)
        assert result is None, "git add must not be flagged as destructive"

    def test_allows_git_commit(self, guard_function):
        """git commit should NOT be blocked."""
        cmd = ["git", "commit", "-m", "chore: update"]
        result = guard_function(cmd)
        assert result is None, "git commit must not be flagged as destructive"

    def test_allows_git_push(self, guard_function):
        """git push should NOT be blocked."""
        cmd = ["git", "push", "origin", "main"]
        result = guard_function(cmd)
        assert result is None, "git push must not be flagged as destructive"

    def test_allows_git_pull(self, guard_function):
        """git pull (without --hard) should NOT be blocked."""
        cmd = ["git", "pull", "origin", "main"]
        result = guard_function(cmd)
        assert result is None, "git pull without --hard flag must not be blocked"

    def test_allows_git_reset_soft(self, guard_function):
        """git reset --soft should NOT be blocked."""
        cmd = ["git", "reset", "--soft", "HEAD~1"]
        result = guard_function(cmd)
        assert result is None, "git reset --soft must not be flagged"

    def test_allows_git_reset_mixed(self, guard_function):
        """git reset --mixed should NOT be blocked."""
        cmd = ["git", "reset", "--mixed", "HEAD~1"]
        result = guard_function(cmd)
        assert result is None, "git reset --mixed must not be flagged"

    def test_allows_git_clean_without_flags(self, guard_function):
        """git clean (without -f/-d) should NOT be blocked."""
        cmd = ["git", "clean"]
        result = guard_function(cmd)
        assert result is None, "git clean without danger flags must not be flagged"

    def test_allows_git_stash_pop(self, guard_function):
        """git stash pop (not drop/clear) should NOT be blocked."""
        cmd = ["git", "stash", "pop"]
        result = guard_function(cmd)
        assert result is None, "git stash pop must not be flagged"

    def test_allows_git_stash_push(self, guard_function):
        """git stash push should NOT be blocked."""
        cmd = ["git", "stash", "push", "-m", "WIP"]
        result = guard_function(cmd)
        assert result is None, "git stash push must not be flagged"

    # === Edge cases ===

    def test_returns_none_for_empty_list(self, guard_function):
        """Empty command list should return None."""
        result = guard_function([])
        assert result is None

    def test_returns_none_for_non_git_command(self, guard_function):
        """Non-git commands should return None."""
        result = guard_function(["ls", "-la"])
        assert result is None

    def test_returns_none_for_partial_git(self, guard_function):
        """Incomplete git commands (git only) should return None."""
        result = guard_function(["git"])
        assert result is None

    def test_returns_correct_command_string(self, guard_function):
        """Returned dict should contain the full command string."""
        cmd = ["git", "reset", "--hard", "origin/main"]
        result = guard_function(cmd)
        assert result["command"] == "git reset --hard origin/main"


class TestDestructiveGitRun:
    """Tests for run() function's blocking behavior on CRITICAL operations."""

    @pytest.fixture
    def run_function(self):
        """Import and return the run function."""
        parent_dir = Path(__file__).parent.parent
        sys.path.insert(0, str(parent_dir))
        import sync
        return sync.run

    def test_run_blocks_reset_hard(self, run_function):
        """run() should return error result for git reset --hard."""
        result = run_function(["git", "reset", "--hard", "origin/main"])
        assert result.returncode == 1
        assert "blocked" in result.stderr
        assert result.args == ["git", "reset", "--hard", "origin/main"]

    def test_run_blocks_git_clean_fd(self, run_function):
        """run() should return error result for git clean -fd (HIGH severity)."""
        result = run_function(["git", "clean", "-fd"])
        assert result.returncode == 1
        assert "blocked" in result.stderr
        assert result.args == ["git", "clean", "-fd"]

    def test_run_blocks_git_stash_drop(self, run_function):
        """run() should return error result for git stash drop (HIGH severity)."""
        result = run_function(["git", "stash", "drop", "stash@{0}"])
        assert result.returncode == 1
        assert "blocked" in result.stderr
        assert result.args == ["git", "stash", "drop", "stash@{0}"]

    def test_run_allows_safe_commands(self, run_function):
        """run() should execute normally for safe git commands."""
        # git status is safe in any repo
        result = run_function(["git", "status"])
        # returncode 0 means success or no repo - both are acceptable
        assert result.returncode in (0, 128)  # 128 = no repo


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
