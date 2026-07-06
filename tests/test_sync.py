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


# ---------------------------------------------------------------------------
# Tests for dynamic read-only auto-quarantine (#1009)
# ---------------------------------------------------------------------------

import subprocess
from unittest.mock import patch as _monkeypatch_if_needed  # noqa: F401 — we use monkeypatch fixture, not Mock

import sync as sync_mod


def _make_local_repo(tmp_path: Path, with_commit: bool = True) -> Path:
    """Create a real local git repo with a fake remote. No network.
    When with_commit=True, seeds an initial commit on `main` so HEAD/branch
    resolution works."""
    repo = tmp_path / "fakerepo"
    repo.mkdir()
    for cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@t"],
        ["git", "config", "user.name", "t"],
        ["git", "remote", "add", "origin", "https://example.invalid/owner/repo.git"],
    ):
        subprocess.run(cmd, cwd=repo, capture_output=True, text=True, check=True)
    if with_commit:
        (repo / "f.txt").write_text("x")
        subprocess.run(["git", "add", "f.txt"], cwd=repo, capture_output=True, text=True, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, capture_output=True, text=True, check=True)
    return repo


def _completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["git"], returncode=returncode, stdout=stdout, stderr=stderr)


class TestReadOnlySentinel:
    def test_sentinel_already_set_skips_push(self, tmp_path, monkeypatch):
        """Pre-existing no_push pushurl → get_push_target returns skip(read-only)."""
        repo = _make_local_repo(tmp_path)
        subprocess.run(["git", "remote", "set-url", "--push", "origin", "no_push"],
                       cwd=repo, capture_output=True, text=True, check=True)
        # Use the real run() (no monkeypatch) — exercises actual git config.
        remote, branch, msg = sync_mod.get_push_target(repo)
        assert remote is None and branch is None
        assert "skip (read-only" in msg

    def test_push_403_writes_sentinel(self, tmp_path, monkeypatch):
        """Permanent permission denial (403) → push_repo writes the no_push sentinel."""
        repo = _make_local_repo(tmp_path)
        # Add a SECOND commit so HEAD~1 exists, then point origin/main at it so
        # the repo looks 1-ahead and the push is actually attempted.
        (repo / "g.txt").write_text("y")
        subprocess.run(["git", "add", "g.txt"], cwd=repo, capture_output=True, text=True, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "second"], cwd=repo, capture_output=True, text=True, check=True)
        subprocess.run(["git", "update-ref", "refs/remotes/origin/main", "HEAD~1"],
                       cwd=repo, capture_output=True, text=True, check=True)

        repo_info = sync_mod.RepoInfo(
            path=repo, git_dir=repo / ".git",
            repo_type="PACKAGE", relative_path="packages/fakerepo", name="fakerepo",
        )

        # Fake run(): route only push to a 403 denial; everything else hits real git.
        real_run = sync_mod.run

        def fake_run(cmd, cwd=None, silent=False):
            if isinstance(cmd, list) and cmd[:2] == ["git", "push"]:
                return _completed(returncode=1, stderr=(
                    "ERROR: Permission to owner/repo.git denied to user.\n"
                    "fatal: Could not read from remote repository."
                ))
            return real_run(cmd, cwd=cwd, silent=silent)

        monkeypatch.setattr(sync_mod, "run", fake_run)
        monkeypatch.setattr(sync_mod, "VERBOSE", False, raising=False)

        ok, msg = sync_mod.push_repo(repo_info)
        assert ok is False
        assert "auto-quarantined" in msg
        # Verify the sentinel was actually persisted to git config.
        pushurl = subprocess.run(
            ["git", "config", "--get", "remote.origin.pushurl"],
            cwd=repo, capture_output=True, text=True, check=False,
        )
        assert pushurl.stdout.strip() == "no_push"

    def test_transient_auth_failure_not_quarantined(self, tmp_path, monkeypatch):
        """Bad credentials is transient → routes to auth branch, NOT auto-quarantine."""
        repo = _make_local_repo(tmp_path)
        # Add a SECOND commit so HEAD~1 exists, then point origin/main at it.
        (repo / "g.txt").write_text("y")
        subprocess.run(["git", "add", "g.txt"], cwd=repo, capture_output=True, text=True, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "second"], cwd=repo, capture_output=True, text=True, check=True)
        subprocess.run(["git", "update-ref", "refs/remotes/origin/main", "HEAD~1"],
                       cwd=repo, capture_output=True, text=True, check=True)

        repo_info = sync_mod.RepoInfo(
            path=repo, git_dir=repo / ".git",
            repo_type="PACKAGE", relative_path="packages/fakerepo", name="fakerepo",
        )

        real_run = sync_mod.run

        def fake_run(cmd, cwd=None, silent=False):
            if isinstance(cmd, list) and cmd[:2] == ["git", "push"]:
                return _completed(returncode=1, stderr="remote: Invalid username or token.\nbad credentials")
            return real_run(cmd, cwd=cwd, silent=silent)

        monkeypatch.setattr(sync_mod, "run", fake_run)
        monkeypatch.setattr(sync_mod, "VERBOSE", False, raising=False)

        ok, msg = sync_mod.push_repo(repo_info)
        assert ok is False
        assert "auto-quarantined" not in msg
        # Auth branch tells the user to authenticate manually.
        assert "authenticate" in msg.lower()
        # Sentinel must NOT have been written.
        pushurl = subprocess.run(
            ["git", "config", "--get", "remote.origin.pushurl"],
            cwd=repo, capture_output=True, text=True, check=False,
        )
        assert pushurl.stdout.strip() != "no_push"

    def test_undo_read_only_clears_sentinel(self, tmp_path):
        """undo_read_only on a sentinel-marked repo clears it; returns (True, ...)."""
        repo = _make_local_repo(tmp_path)
        subprocess.run(["git", "remote", "set-url", "--push", "origin", "no_push"],
                       cwd=repo, capture_output=True, text=True, check=True)
        cleared, msg = sync_mod.undo_read_only(repo, "origin")
        assert cleared is True
        pushurl = subprocess.run(
            ["git", "config", "--get", "remote.origin.pushurl"],
            cwd=repo, capture_output=True, text=True, check=False,
        )
        assert pushurl.returncode != 0 or pushurl.stdout.strip() == ""

    def test_undo_read_only_noop_without_sentinel(self, tmp_path):
        """undo_read_only on a clean repo is a no-op (False, ...)."""
        repo = _make_local_repo(tmp_path)
        cleared, msg = sync_mod.undo_read_only(repo, "origin")
        assert cleared is False
