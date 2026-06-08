"""Tests for cc-skills-utils_Stop_cache_reconciler.

Verifies the cache==source invariant check: missing cache dir, missing/stale
hooks.json, and the satisfied (no-drift) case. Monkeypatches the module's
path constants so no live state is touched.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

HOOK_PATH = (
    Path(__file__).resolve().parent.parent
    / "hooks"
    / "cc-skills-utils_Stop_cache_reconciler.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("cache_reconciler", HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_plugin(root: Path, name: str, version: str, hooks_obj: dict) -> Path:
    """Create a minimal plugin source tree under root."""
    pdir = root / name
    (pdir / ".claude-plugin").mkdir(parents=True)
    (pdir / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": name, "version": version})
    )
    (pdir / "hooks").mkdir()
    (pdir / "hooks" / "hooks.json").write_text(json.dumps(hooks_obj))
    return pdir


def _make_cache(root: Path, name: str, version: str, hooks_obj: dict | None) -> Path:
    cdir = root / name / version
    cdir.mkdir(parents=True)
    if hooks_obj is not None:
        (cdir / "hooks").mkdir()
        (cdir / "hooks" / "hooks.json").write_text(json.dumps(hooks_obj))
    return cdir


@pytest.fixture
def mod(monkeypatch, tmp_path):
    m = _load_module()
    src = tmp_path / "src"
    cache = tmp_path / "cache"
    src.mkdir()
    cache.mkdir()
    monkeypatch.setattr(m, "MARKETPLACE_ROOT", src)
    monkeypatch.setattr(m, "CACHE_ROOT", cache)
    return m, src, cache


def test_no_drift_when_cache_matches_source(mod):
    m, src, cache = mod
    hooks = {"hooks": {"Stop": [{"matcher": ".*", "hooks": []}]}}
    _make_plugin(src, "demo", "1.0.0", hooks)
    _make_cache(cache, "demo", "1.0.0", hooks)
    assert m._check_plugin("demo") is None


def test_drift_when_cache_dir_missing(mod):
    m, src, cache = mod
    _make_plugin(src, "demo", "1.0.0", {"hooks": {}})
    # no cache created
    err = m._check_plugin("demo")
    assert err is not None
    assert "cache directory missing" in err
    assert "--bump demo" in err


def test_drift_when_hooks_json_stale(mod):
    m, src, cache = mod
    src_hooks = {"hooks": {"Stop": [{"matcher": ".*", "hooks": []}]}}
    cache_hooks = {"hooks": {}}  # stale — source added a Stop entry
    _make_plugin(src, "demo", "1.0.0", src_hooks)
    _make_cache(cache, "demo", "1.0.0", cache_hooks)
    err = m._check_plugin("demo")
    assert err is not None
    assert "stale" in err


def test_drift_when_version_bumped_without_rebuild(mod):
    m, src, cache = mod
    hooks = {"hooks": {}}
    _make_plugin(src, "demo", "2.0.0", hooks)  # source at 2.0.0
    _make_cache(cache, "demo", "1.0.0", hooks)  # cache stuck at 1.0.0
    err = m._check_plugin("demo")
    assert err is not None
    assert "cache directory missing" in err  # no 2.0.0 cache dir


def test_unknown_plugin_skipped(mod):
    m, src, cache = mod
    assert m._check_plugin("does-not-exist") is None


def test_json_hash_ignores_formatting(mod):
    m, src, cache = mod
    a = src / "a.json"
    b = src / "b.json"
    a.write_text('{"hooks":{},"x":1}')
    b.write_text('{\n  "x": 1,\n  "hooks": {}\n}')  # same data, different format
    assert m._normalized_json_hash(a) == m._normalized_json_hash(b)
