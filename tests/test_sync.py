"""Structural tests for sync.py features."""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'skills' / 'git'))
from sync import DRY_RUN, STAGING_EXCLUDE_PATTERNS

class TestStagingExcludePatterns:
    def test_artifact_pattern_has_recursive_wildcard(self):
        """Pattern .claude/.artifacts/** matches nested session artifacts."""
        has_recursive = any(p for p in STAGING_EXCLUDE_PATTERNS if ".claude/.artifacts/**" in p)
        assert has_recursive, "Expected .claude/.artifacts/** recursive pattern in STAGING_EXCLUDE_PATTERNS"

    def test_logs_pattern_has_recursive_wildcard(self):
        """Pattern logs/** matches nested log files."""
        has_recursive = any(p for p in STAGING_EXCLUDE_PATTERNS if p.startswith("logs/**"))
        assert has_recursive, "Expected logs/** recursive pattern in STAGING_EXCLUDE_PATTERNS"

    def test_exclude_patterns_not_empty(self):
        """STAGING_EXCLUDE_PATTERNS should not be empty."""
        assert len(STAGING_EXCLUDE_PATTERNS) > 0

class TestDRYRUN:
    def test_dry_run_flag_exists(self):
        """DRY_RUN constant should be defined."""
        assert DRY_RUN is not None

# Run: pytest tests/test_sync.py -v
