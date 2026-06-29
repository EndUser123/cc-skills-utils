#!/usr/bin/env python3
"""
Test for _index_has_gitlink — gates submodule init/orphan-recovery in sync.py.

The helper returns True only when the repo's index holds a mode-160000 gitlink,
so `git submodule update --init` (always-failing for gitlinks without .gitmodules)
is skipped for plain repos. Verifies: plain repo -> False, nested repo added as
gitlink -> True.

Run with: pytest tests/test_index_has_gitlink.py -v
"""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def sync_module():
    parent_dir = Path(__file__).parent.parent
    sys.path.insert(0, str(parent_dir))
    import sync
    return sync


def _git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def test_plain_repo_has_no_gitlink(sync_module, tmp_path):
    repo = tmp_path / "outer"
    repo.mkdir()
    _git("init", cwd=repo)
    (repo / "file.txt").write_text("hello")
    _git("add", "file.txt", cwd=repo)
    assert sync_module._index_has_gitlink(repo) is False


def test_nested_repo_registered_as_gitlink(sync_module, tmp_path):
    outer = tmp_path / "outer"
    outer.mkdir()
    _git("init", cwd=outer)
    inner = outer / "nested"
    inner.mkdir()
    _git("init", cwd=inner)
    (inner / "f.txt").write_text("x")
    _git("add", "f.txt", cwd=inner)
    _git("commit", "-m", "init", cwd=inner)
    # `git add` on a dir with its own committed .git records a gitlink (mode 160000).
    _git("add", "nested", cwd=outer)
    assert sync_module._index_has_gitlink(outer) is True
