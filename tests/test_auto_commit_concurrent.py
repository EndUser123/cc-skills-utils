"""Tests for concurrent-session fail-closed auto-commit gate.

Tests use real temp directories and real session registry files (anti-mock
stance per repo testing rules). No mocking of os or json.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import importlib.util

HOOK_PATH = Path(__file__).resolve().parent.parent / "hooks" / "cc-skills-utils_Stop_auto_commit.py"
spec = importlib.util.spec_from_file_location("auto_commit_hook", HOOK_PATH)
assert spec and spec.loader
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


def _make_registry_entry(session_id: str, cwd: str, age_seconds: float = 0) -> dict:
    """Create a session_registry.jsonl entry with a controlled timestamp."""
    ts = datetime.now(timezone.utc).isoformat()
    if age_seconds > 0:
        ts_dt = datetime.now(timezone.utc).timestamp() - age_seconds
        ts = datetime.fromtimestamp(ts_dt, tz=timezone.utc).isoformat()
    return {
        "ts": ts,
        "session_id": session_id,
        "cwd": cwd,
        "terminal_id": "test-terminal",
    }


def _write_registry(registry_path: Path, entries: list[dict]) -> None:
    """Write entries to session_registry.jsonl."""
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with open(registry_path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def test_no_registry_returns_false(tmp_path: Path) -> None:
    """No registry file → solo session → _other_session_active returns False."""
    result = hook._other_session_active(tmp_path)
    assert result is False


def test_only_self_in_registry_returns_false(tmp_path: Path) -> None:
    """Registry has only this session → solo → returns False."""
    os.environ["CLAUDE_SESSION_ID"] = "my-session-123"
    os.environ["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    registry = tmp_path / ".claude" / ".artifacts" / "session_registry.jsonl"
    _write_registry(registry, [_make_registry_entry("my-session-123", str(tmp_path))])
    try:
        result = hook._other_session_active(tmp_path)
        assert result is False
    finally:
        os.environ.pop("CLAUDE_SESSION_ID", None)
        os.environ.pop("CLAUDE_PROJECT_DIR", None)


def test_concurrent_session_returns_true(tmp_path: Path) -> None:
    """Another live session on same repo → returns True."""
    os.environ["CLAUDE_SESSION_ID"] = "my-session-123"
    os.environ["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    registry = tmp_path / ".claude" / ".artifacts" / "session_registry.jsonl"
    entries = [
        _make_registry_entry("my-session-123", str(tmp_path)),
        _make_registry_entry("other-session-456", str(tmp_path)),
    ]
    _write_registry(registry, entries)
    try:
        result = hook._other_session_active(tmp_path)
        assert result is True
    finally:
        os.environ.pop("CLAUDE_SESSION_ID", None)
        os.environ.pop("CLAUDE_PROJECT_DIR", None)


def test_stale_session_returns_false(tmp_path: Path) -> None:
    """Another session but older than TTL → stale → returns False."""
    os.environ["CLAUDE_SESSION_ID"] = "my-session-123"
    os.environ["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    registry = tmp_path / ".claude" / ".artifacts" / "session_registry.jsonl"
    entries = [
        _make_registry_entry("my-session-123", str(tmp_path)),
        _make_registry_entry("old-session-789", str(tmp_path), age_seconds=600),  # 10 min > 300s TTL
    ]
    _write_registry(registry, entries)
    try:
        result = hook._other_session_active(tmp_path)
        assert result is False
    finally:
        os.environ.pop("CLAUDE_SESSION_ID", None)
        os.environ.pop("CLAUDE_PROJECT_DIR", None)


def test_different_repo_returns_false(tmp_path: Path) -> None:
    """Another session but on a different repo path → returns False."""
    os.environ["CLAUDE_SESSION_ID"] = "my-session-123"
    os.environ["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    registry = tmp_path / ".claude" / ".artifacts" / "session_registry.jsonl"
    other_repo = str(tmp_path / "other-repo")
    entries = [
        _make_registry_entry("my-session-123", str(tmp_path)),
        _make_registry_entry("other-session-456", other_repo),
    ]
    _write_registry(registry, entries)
    try:
        result = hook._other_session_active(tmp_path)
        assert result is False
    finally:
        os.environ.pop("CLAUDE_SESSION_ID", None)
        os.environ.pop("CLAUDE_PROJECT_DIR", None)


def test_corrupt_registry_returns_false(tmp_path: Path) -> None:
    """Corrupt JSON in registry → fail-open → returns False."""
    os.environ["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    registry = tmp_path / ".claude" / ".artifacts" / "session_registry.jsonl"
    _write_registry(registry, [])
    registry.write_text("not valid json\n{also broken\n", encoding="utf-8")
    try:
        result = hook._other_session_active(tmp_path)
        assert result is False
    finally:
        os.environ.pop("CLAUDE_PROJECT_DIR", None)


def test_mixed_entries_only_live_other_counts(tmp_path: Path) -> None:
    """Multiple entries: self + stale other + live other → returns True."""
    os.environ["CLAUDE_SESSION_ID"] = "my-session"
    os.environ["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    registry = tmp_path / ".claude" / ".artifacts" / "session_registry.jsonl"
    entries = [
        _make_registry_entry("my-session", str(tmp_path)),
        _make_registry_entry("stale-session", str(tmp_path), age_seconds=600),
        _make_registry_entry("live-other", str(tmp_path), age_seconds=10),
    ]
    _write_registry(registry, entries)
    try:
        result = hook._other_session_active(tmp_path)
        assert result is True
    finally:
        os.environ.pop("CLAUDE_SESSION_ID", None)
        os.environ.pop("CLAUDE_PROJECT_DIR", None)


def test_no_session_id_env_still_works(tmp_path: Path) -> None:
    """When CLAUDE_SESSION_ID is not set, all entries are 'other' → any live entry returns True."""
    os.environ.pop("CLAUDE_SESSION_ID", None)
    os.environ["CLAUDE_PROJECT_DIR"] = str(tmp_path)
    registry = tmp_path / ".claude" / ".artifacts" / "session_registry.jsonl"
    _write_registry(registry, [_make_registry_entry("some-session", str(tmp_path))])
    try:
        result = hook._other_session_active(tmp_path)
        assert result is True
    finally:
        os.environ.pop("CLAUDE_PROJECT_DIR", None)
