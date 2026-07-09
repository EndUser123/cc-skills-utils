"""Integration tests for /go commit-boundary enforcement in Stop auto-commit (#1256).

Root cause these pin: auto-commit staged the whole working tree
(``git add --ignore-removal .`` / grouped ``git add -- <paths>``) with zero
ownership check at commit time, so concurrent workstreams sharing one working
tree were swept into the active /go session's commit (2026-07-08 #1332
recurrence). Mutation-time ownership was enforced by /go's PreToolUse gate;
commit-time ownership was blind. This fix bounds staging to the active /go
run's owned files (session_id -> pointer -> state_dir -> run_id -> owned set).

These tests drive ``auto_commit`` against a REAL temp git repo with real
pointer/state artifacts — the contract lives at the git/state boundary, so a
unit test of pure logic could not prove it. They exercise the ownership-
resolution path, the owned/not-owned split, owned-deletion commits, the
plugin-bump-when-declared rule, and the no-pointer preservation behavior.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

HOOK = (
    Path(__file__).resolve().parents[1]
    / "hooks"
    / "cc-skills-utils_Stop_auto_commit.py"
)


def _load_ac():
    spec = importlib.util.spec_from_file_location("ac_boundary", HOOK)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ac_boundary"] = mod
    spec.loader.exec_module(mod)
    return mod


ac = _load_ac()


def _git(args, cwd):
    return subprocess.run(
        ["git"] + args, capture_output=True, text=True, cwd=str(cwd),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0,
    )


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A real git repo; the hook's PROJECT_ROOT + debounce state isolated to it."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(["init", "-q"], root)
    _git(["config", "user.email", "t@t"], root)
    _git(["config", "user.name", "t"], root)
    _git(["config", "commit.gpgsign", "false"], root)
    (root / "README.md").write_text("init", encoding="utf-8")
    _git(["add", "."], root)
    _git(["commit", "-q", "-m", "init"], root)
    # Point the hook at this repo + its own state dirs under tmp_path.
    state_root = tmp_path / "state"
    artifacts_root = state_root / "artifacts"
    monkeypatch.setattr(ac, "PROJECT_ROOT", root, raising=False)
    monkeypatch.setattr(ac, "_ARTIFACTS_ROOT", artifacts_root, raising=False)
    monkeypatch.setattr(ac, "_SESSIONS_DIR", artifacts_root / "go-sessions", raising=False)
    monkeypatch.setattr(ac, "_DEBOUNCE_DIR", state_root / "debounce", raising=False)
    monkeypatch.setattr(ac, "_TELEMETRY_DIR", state_root / "telemetry", raising=False)
    monkeypatch.delenv("GO_AUTO_COMMIT_FAIL_CLOSED", raising=False)
    yield root, artifacts_root


def _write_pointer(artifacts_root, session_id, state_dir, run_id):
    (artifacts_root / "go-sessions").mkdir(parents=True, exist_ok=True)
    (artifacts_root / "go-sessions" / f"{session_id}.json").write_text(
        json.dumps({
            "go_state_dir": str(state_dir),
            "run_id": run_id,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }),
        encoding="utf-8",
    )


def _write_owned(state_dir, run_id, owned_files, diff_files=None):
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / f"diff-summary_{run_id}.json").write_text(
        json.dumps({"files": diff_files if diff_files is not None else owned_files}),
        encoding="utf-8",
    )
    (state_dir / f"claude-task-result_{run_id}.json").write_text(
        json.dumps({"files_touched": owned_files}), encoding="utf-8",
    )


def _committed_files(repo):
    """Files changed in the most recent commit (name-only, vs HEAD~1)."""
    r = _git(["diff", "--name-only", "HEAD~1", "HEAD"], repo)
    return sorted(p for p in r.stdout.splitlines() if p.strip())


def _staged_files(repo):
    r = _git(["diff", "--cached", "--name-only"], repo)
    return sorted(p for p in r.stdout.splitlines() if p.strip())


def _unstaged_files(repo):
    """Dirty in the working tree but not committed (uncommitted/untracked)."""
    r = _git(["status", "--porcelain"], repo)
    return sorted(line[3:].strip().strip('"') for line in r.stdout.splitlines() if line.strip())


def _commit(repo, **kw):
    """Call auto_commit twice. The debounce (_should_commit_now) defers the
    first call (path set is new vs prior=[]); quiescence is reached on the
    second call, mirroring how the real Stop hook commits on the second Stop
    after the tree goes stable. Returns the second call's result."""
    ac.auto_commit(repo, **kw)
    return ac.auto_commit(repo, **kw)


class TestGoBoundaryHoldsUnrelated:
    """Acceptance #1: unrelated unstaged file is not swept into the commit."""

    def test_unstaged_unrelated_not_committed(self, repo):
        root, artifacts = repo
        # owned + unrelated both dirty
        (root / "owned_a.py").write_text("a", encoding="utf-8")
        (root / "unrelated_b.py").write_text("b", encoding="utf-8")
        state_dir = artifacts / "go-state"
        _write_pointer(artifacts, "sess-1", state_dir, "run-1")
        _write_owned(state_dir, "run-1", ["owned_a.py"])
        boundary = ac._resolve_go_boundary("sess-1")
        committed = _commit(root, boundary=boundary)
        assert committed is True
        assert _committed_files(root) == ["owned_a.py"]
        # unrelated_b.py remains uncommitted in the working tree
        assert "unrelated_b.py" in _unstaged_files(root)

    def test_boundary_violation_artifact_written(self, repo):
        root, artifacts = repo
        (root / "owned_a.py").write_text("a", encoding="utf-8")
        (root / "unrelated_b.py").write_text("b", encoding="utf-8")
        state_dir = artifacts / "go-state"
        _write_pointer(artifacts, "sess-1", state_dir, "run-1")
        _write_owned(state_dir, "run-1", ["owned_a.py"])
        _commit(root, boundary=ac._resolve_go_boundary("sess-1"))
        vpath = state_dir / "boundary-violation_run-1.json"
        assert vpath.is_file()
        data = json.loads(vpath.read_text(encoding="utf-8"))
        assert data["decision"] == "held_unrelated"
        assert data["mine_for_this_task"] == ["owned_a.py"]
        assert data["not_owned"] == ["unrelated_b.py"]


class TestGoBoundaryHoldsStagedUnrelated:
    """Acceptance #2: a staged unrelated file is not committed by auto-commit."""

    def test_staged_unrelated_not_included(self, repo):
        root, artifacts = repo
        (root / "owned_a.py").write_text("a", encoding="utf-8")
        (root / "unrelated_b.py").write_text("b", encoding="utf-8")
        _git(["add", "unrelated_b.py"], root)  # pre-staged by another session
        state_dir = artifacts / "go-state"
        _write_pointer(artifacts, "sess-1", state_dir, "run-1")
        _write_owned(state_dir, "run-1", ["owned_a.py"])
        _commit(root, boundary=ac._resolve_go_boundary("sess-1"))
        # The /go commit contains only owned_a.py
        assert _committed_files(root) == ["owned_a.py"]


class TestGoBoundaryOwnedDeletion:
    """Acceptance #3: an owned deletion is committed (boundary makes it safe)."""

    def test_owned_deletion_commits(self, repo):
        root, artifacts = repo
        # A tracked file that the run owns and deletes.
        (root / "stale_doc.md").write_text("x", encoding="utf-8")
        _git(["add", "stale_doc.md"], root)
        _git(["commit", "-q", "-m", "add stale"], root)
        (root / "stale_doc.md").unlink()
        state_dir = artifacts / "go-state"
        _write_pointer(artifacts, "sess-1", state_dir, "run-1")
        _write_owned(state_dir, "run-1", ["stale_doc.md"])
        _commit(root, boundary=ac._resolve_go_boundary("sess-1"))
        # Deletion landed in the new commit
        r = _git(["diff", "--name-status", "HEAD~1", "HEAD"], root)
        assert "D\tstale_doc.md" in r.stdout


class TestGoBoundaryPluginJsonRule:
    """Acceptance #4 + #5: plugin.json included only when owned."""

    def _setup_plugin_json(self, root):
        pj = root / ".claude-plugin" / "plugin.json"
        pj.parent.mkdir(parents=True, exist_ok=True)
        pj.write_text(json.dumps({"name": "x", "version": "1.0.0"}), encoding="utf-8")
        _git(["add", ".claude-plugin/plugin.json"], root)
        _git(["commit", "-q", "-m", "add plugin.json"], root)
        # dirty it
        pj.write_text(json.dumps({"name": "x", "version": "1.0.1"}), encoding="utf-8")

    def test_plugin_json_not_owned_held_back(self, repo):
        root, artifacts = repo
        self._setup_plugin_json(root)
        (root / "owned_a.py").write_text("a", encoding="utf-8")
        state_dir = artifacts / "go-state"
        _write_pointer(artifacts, "sess-1", state_dir, "run-1")
        _write_owned(state_dir, "run-1", ["owned_a.py"])  # plugin.json NOT owned
        _commit(root, boundary=ac._resolve_go_boundary("sess-1"))
        assert _committed_files(root) == ["owned_a.py"]
        assert ".claude-plugin/plugin.json" in _unstaged_files(root)

    def test_plugin_json_owned_included(self, repo):
        root, artifacts = repo
        self._setup_plugin_json(root)
        state_dir = artifacts / "go-state"
        _write_pointer(artifacts, "sess-1", state_dir, "run-1")
        _write_owned(state_dir, "run-1", [".claude-plugin/plugin.json"])
        _commit(root, boundary=ac._resolve_go_boundary("sess-1"))
        assert ".claude-plugin/plugin.json" in _committed_files(root)


class TestNoPointerPreservesBehavior:
    """Acceptance #6: no /go pointer -> current broad auto-commit preserved."""

    def test_no_pointer_broad_commit(self, repo):
        root, artifacts = repo
        (root / "a.py").write_text("a", encoding="utf-8")
        (root / "b.py").write_text("b", encoding="utf-8")
        # No pointer written -> boundary None
        assert ac._resolve_go_boundary("sess-absent") is None
        committed = _commit(root, boundary=None)
        assert committed is True
        # Both files committed (legacy broad behavior, no ownership filter)
        assert _committed_files(root) == ["a.py", "b.py"]


class TestAllDeclaredSingleTask:
    """Acceptance #7: every changed file declared -> one clean commit, like today."""

    def test_all_declared_commits_cleanly(self, repo):
        root, artifacts = repo
        (root / "owned_a.py").write_text("a", encoding="utf-8")
        (root / "owned_b.py").write_text("b", encoding="utf-8")
        state_dir = artifacts / "go-state"
        _write_pointer(artifacts, "sess-1", state_dir, "run-1")
        _write_owned(state_dir, "run-1", ["owned_a.py", "owned_b.py"])
        committed = _commit(root, boundary=ac._resolve_go_boundary("sess-1"))
        assert committed is True
        assert _committed_files(root) == ["owned_a.py", "owned_b.py"]
        # No boundary-violation artifact when nothing was held
        assert not (state_dir / "boundary-violation_run-1.json").is_file()


class TestOwnershipUnresolvableFailsClosed:
    """Acceptance #6b: active /go pointer but owned-set empty -> no broad commit."""

    def test_empty_owned_set_no_commit(self, repo):
        root, artifacts = repo
        (root / "a.py").write_text("a", encoding="utf-8")
        state_dir = artifacts / "go-state"
        _write_pointer(artifacts, "sess-1", state_dir, "run-1")
        _write_owned(state_dir, "run-1", [])  # pointer live, no owned files yet
        committed = _commit(root, boundary=ac._resolve_go_boundary("sess-1"))
        assert committed is False
        # Nothing committed; file still dirty in the working tree
        assert "a.py" in _unstaged_files(root)
