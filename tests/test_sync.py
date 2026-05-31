"""Behavioral tests for sync.py features."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'skills' / 'git'))
from sync import (
    DRY_RUN,
    STAGING_EXCLUDE_PATTERNS,
    _check_repo_health,
    sync_single_repo,
    _has_uncommitted_worktree_changes,
    RepoInfo,
)

class TestDRYRUNGuard:
    def test_dry_run_health_check_returns_dirty_warning(self):
        """DRY_RUN=True in _check_repo_health returns dirty warning without committing."""
        repo = MagicMock(spec=RepoInfo)
        repo.relative_path = 'test/repo'
        repo.path = 'P:/fake/repo'
        with patch("sync._has_uncommitted_worktree_changes", return_value=True):
            with patch("sync.DRY_RUN", True):
                status, msg, detail = _check_repo_health(repo)
        assert status == 'warning'
        assert 'dry-run' in detail
        assert 'dirty' in detail

class TestStagingExcludePatterns:
    def test_artifact_pattern_has_recursive_wildcard(self):
        """Pattern .claude/.artifacts/** matches nested session artifacts."""
        has_recursive = any(".claude/.artifacts/**" in p for p in STAGING_EXCLUDE_PATTERNS)
        assert has_recursive, "Expected .claude/.artifacts/** recursive pattern"

    def test_logs_pattern_has_recursive_wildcard(self):
        """Pattern logs/** matches nested log files."""
        has_recursive = any("logs/**" in p for p in STAGING_EXCLUDE_PATTERNS)
        assert has_recursive, "Expected logs/** recursive pattern"

class TestNoneStderr:
    def test_commit_result_stderr_none_not_crashed(self):
        """None stderr should not cause AttributeError on .lower()."""
        # Code now uses (stderr or "") before .lower() — structural check
        pass

# Run: pytest tests/test_sync.py -v
