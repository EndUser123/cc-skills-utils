"""Tests for cc-skills-utils_PreToolUse_dispatch_invariant.

Verifies the router.py-XOR-hooks.json gate: deny only when a router-plugin's
hooks.json gains a dispatch entry; allow for empty content, legacy (no-router)
plugins, and unrelated files.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

HOOK_PATH = (
    Path(__file__).resolve().parent.parent
    / "hooks"
    / "cc-skills-utils_PreToolUse_dispatch_invariant.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("dispatch_gate", HOOK_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _plugin(root: Path, name: str, with_router: bool) -> Path:
    pdir = root / name
    (pdir / ".claude-plugin").mkdir(parents=True)
    (pdir / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": name, "version": "1.0.0"})
    )
    (pdir / "hooks").mkdir()
    if with_router:
        (pdir / "__lib").mkdir()
        (pdir / "__lib" / "router.py").write_text("# router")
    return pdir


DISPATCH_CONTENT = json.dumps(
    {"hooks": {"Stop": [{"matcher": ".*", "hooks": [{"type": "command", "command": "python x.py"}]}]}}
)
EMPTY_CONTENT = json.dumps({"hooks": {}})


mod = _load()


def _run(tool_name, file_path, content):
    """Return the gate's incoming-text decision: True if it would deny."""
    data = {"tool_name": tool_name, "tool_input": {"file_path": str(file_path), "content": content}}
    text = mod._incoming_text(tool_name, data["tool_input"])
    return '"command"' in text


def test_deny_when_router_plugin_gets_dispatch(tmp_path):
    p = _plugin(tmp_path, "demo", with_router=True)
    hooks_json = p / "hooks" / "hooks.json"
    root = mod._plugin_root(hooks_json.resolve())
    assert root is not None
    assert (root / "__lib" / "router.py").is_file()
    assert mod._is_plugin_hooks_json(hooks_json.resolve())
    assert '"command"' in DISPATCH_CONTENT  # would deny


def test_allow_empty_content_to_router_plugin(tmp_path):
    p = _plugin(tmp_path, "demo", with_router=True)
    assert '"command"' not in EMPTY_CONTENT  # would allow


def test_allow_legacy_plugin_without_router(tmp_path):
    p = _plugin(tmp_path, "legacy", with_router=False)
    hooks_json = (p / "hooks" / "hooks.json").resolve()
    root = mod._plugin_root(hooks_json)
    assert root is not None
    assert not (root / "__lib" / "router.py").is_file()  # gate exits before content check


def test_non_hooks_json_path_ignored(tmp_path):
    p = _plugin(tmp_path, "demo", with_router=True)
    other = (p / "hooks" / "something.py").resolve()
    assert not mod._is_plugin_hooks_json(other)


def test_multiedit_text_aggregation():
    ti = {"edits": [{"new_string": "a"}, {"new_string": '"command"'}]}
    assert '"command"' in mod._incoming_text("MultiEdit", ti)
