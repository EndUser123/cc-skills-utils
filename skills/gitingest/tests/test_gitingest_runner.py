"""Tests for gitingest_runner.py — focusing on logic-heavy changes from GTO review."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Import the module under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from gitingest_runner import (
    get_existing_sources,
    _wait_for_delete_confirmed,
    cleanup_clone,
    RepoSpec,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_notebooklm_id():
    return "test-notebook-123"


# ---------------------------------------------------------------------------
# get_existing_sources tests
# ---------------------------------------------------------------------------

class TestGetExistingSources:
    """ACT-2: get_existing_sources now returns (dict, bool) — API error is surfaced."""

    def test_returns_tuple(self, mock_notebooklm_id):
        """Return type is tuple[dict, bool], not just dict."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps([{"title": "src.py", "id": "abc123"}]),
            )
            result = get_existing_sources(mock_notebooklm_id)
            assert isinstance(result, tuple), "Should return tuple"
            assert len(result) == 2

    def test_api_error_returns_true_second(self, mock_notebooklm_id):
        """Non-zero returncode → (empty_dict, True)."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="auth error", stdout="")
            sources, api_error = get_existing_sources(mock_notebooklm_id)
            assert sources == {}
            assert api_error is True

    def test_valid_response_returns_false_second(self, mock_notebooklm_id):
        """Valid JSON → (sources_dict, False)."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps([
                    {"title": "src1.md", "id": "id1"},
                    {"title": "src2.md", "id": "id2"},
                ]),
            )
            sources, api_error = get_existing_sources(mock_notebooklm_id)
            assert sources == {"src1.md": "id1", "src2.md": "id2"}
            assert api_error is False

    def test_malformed_json_returns_error_true(self, mock_notebooklm_id):
        """JSON decode error → (empty_dict, True)."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="not valid json{")
            sources, api_error = get_existing_sources(mock_notebooklm_id)
            assert sources == {}
            assert api_error is True

    def test_missing_title_field_returns_error_true(self, mock_notebooklm_id):
        """Source missing 'title' key → (empty_dict, True)."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps([{"id": "abc123"}]),  # no title
            )
            sources, api_error = get_existing_sources(mock_notebooklm_id)
            assert sources == {}
            assert api_error is True


# ---------------------------------------------------------------------------
# _wait_for_delete_confirmed tests
# ---------------------------------------------------------------------------

class TestWaitForDeleteConfirmed:
    """Poll loop confirms source deletion before proceeding to re-add."""

    def test_confirms_after_one_poll(self, mock_notebooklm_id):
        """Source gone on first poll → returns True immediately."""
        with patch("gitingest_runner.get_existing_sources") as mock_get:
            # sources is {title: id}; id "abc" is in values on second poll
            mock_get.side_effect = [
                ({"src.md": "abc"}, False),  # source still present
                ({}, False),                  # source confirmed gone
            ]
            result = _wait_for_delete_confirmed(mock_notebooklm_id, "abc")
            assert result is True
            assert mock_get.call_count == 2

    def test_gives_up_after_max_attempts(self, mock_notebooklm_id):
        """Source never disappears → returns False after max_attempts."""
        with patch("gitingest_runner.get_existing_sources") as mock_get:
            mock_get.return_value = ({"src.md": "abc"}, False)  # id still in values
            result = _wait_for_delete_confirmed(mock_notebooklm_id, "abc", max_attempts=3)
            assert result is False
            assert mock_get.call_count == 3

    def test_confirms_on_second_attempt(self, mock_notebooklm_id):
        """Source confirmed gone on second poll."""
        with patch("gitingest_runner.get_existing_sources") as mock_get:
            mock_get.side_effect = [
                ({"src.md": "abc"}, False),  # still present
                ({}, False),                  # gone
            ]
            result = _wait_for_delete_confirmed(mock_notebooklm_id, "abc")
            assert result is True
            assert mock_get.call_count == 2


# ---------------------------------------------------------------------------
# cleanup_clone tests
# ---------------------------------------------------------------------------

class TestCleanupClone:
    """ACT-1: cleanup_clone no longer uses ignore_errors=True."""

    def test_calls_rmtree_without_ignore_errors(self, tmp_path):
        """shutil.rmtree is called without ignore_errors — OSError surfaces."""
        spec = RepoSpec(owner="test", repo="proj")
        clone_root = tmp_path / "clones"
        clone_root.mkdir()
        dest = clone_root / "test__proj"
        dest.mkdir()

        with patch("gitingest_runner.shutil.rmtree") as mock_rmtree:
            mock_rmtree.return_value = None
            cleanup_clone(clone_root, spec)
            mock_rmtree.assert_called_once()
            call_args = mock_rmtree.call_args
            # First positional arg should be dest (a Path)
            assert call_args.args[0] == dest
            # ignore_errors must NOT be passed as True
            assert call_args.kwargs.get("ignore_errors") is not True

    def test_warns_on_rmtree_failure(self, tmp_path, capsys):
        """OSError from rmtree → warning is printed."""
        spec = RepoSpec(owner="test", repo="proj")
        clone_root = tmp_path / "clones"
        clone_root.mkdir()
        dest = clone_root / "test__proj"
        dest.mkdir()

        with patch("shutil.rmtree") as mock_rmtree:
            mock_rmtree.side_effect = OSError("permission denied")
            cleanup_clone(clone_root, spec)
            captured = capsys.readouterr()
            assert "permission denied" in captured.out
            assert "cleanup failed" in captured.out
