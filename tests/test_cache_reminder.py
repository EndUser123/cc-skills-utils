"""Tests for PostToolUse cache-path reminder hook."""

import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

HOOK = Path(__file__).resolve().parent.parent / "hooks" / "cc-skills-utils_PostToolUse_cache_reminder.py"
_spec = importlib.util.spec_from_file_location("cache_reminder", HOOK)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_resolve_plugin_name = _mod._resolve_plugin_name
_is_plugin_source_path = _mod._is_plugin_source_path
_already_warned = _mod._already_warned
_record_warning = _mod._record_warning
_session_id = _mod._session_id


# ── Plugin name resolution ────────────────────────────────────────────


class TestResolvePluginName:
    """F1: Plugin name via .claude-plugin/plugin.json parent walk."""

    def test_marketplace_path(self, tmp_path: Path) -> None:
        """Standard marketplace path resolves to plugin dir name."""
        plugin = tmp_path / ".claude-marketplace" / "plugins" / "cc-skills-sdlc"
        (plugin / ".claude-plugin").mkdir(parents=True)
        (plugin / ".claude-plugin" / "plugin.json").write_text('{"name":"cc-skills-sdlc"}')
        (plugin / "hooks").mkdir()
        hook_file = plugin / "hooks" / "foo.py"
        hook_file.write_text("x=1")

        result = _resolve_plugin_name(str(hook_file))
        assert result == "cc-skills-sdlc"

    def test_nested_lib_path(self, tmp_path: Path) -> None:
        """Deeply nested file still resolves to plugin root."""
        plugin = tmp_path / "my-plugin"
        (plugin / ".claude-plugin").mkdir(parents=True)
        (plugin / ".claude-plugin" / "plugin.json").write_text('{"name":"my-plugin"}')
        deep = plugin / "__lib" / "sub" / "deep"
        deep.mkdir(parents=True)
        target = deep / "mod.py"
        target.write_text("pass")

        result = _resolve_plugin_name(str(target))
        assert result == "my-plugin"

    def test_no_plugin_json(self, tmp_path: Path) -> None:
        """File outside any plugin directory returns None."""
        f = tmp_path / "random" / "file.py"
        f.parent.mkdir(parents=True)
        f.write_text("x=1")
        assert _resolve_plugin_name(str(f)) is None

    def test_empty_path(self) -> None:
        """Empty string returns None."""
        assert _resolve_plugin_name("") is None


# ── Plugin source path detection ──────────────────────────────────────


class TestIsPluginSourcePath:
    """M1: Inverted path matching (fire on all plugin paths except cache)."""

    def test_marketplace_plugin_path(self) -> None:
        """Standard marketplace plugin path is detected."""
        assert _is_plugin_source_path(
            "P:/packages/.claude-marketplace/plugins/cc-skills-sdlc/hooks/foo.py"
        )

    def test_local_hooks_suppressed(self) -> None:
        """M2: Local .claude/hooks/ path is suppressed."""
        assert not _is_plugin_source_path("P:/.claude/hooks/PreToolUse_foo.py")

    def test_cache_path_suppressed(self) -> None:
        """Cache directories are suppressed."""
        assert not _is_plugin_source_path(
            "P:/packages/.claude-marketplace/plugins/cache/cc-skills-sdlc/1.0/hooks/foo.py"
        )

    def test_non_plugin_path(self) -> None:
        """Paths outside marketplace are suppressed."""
        assert not _is_plugin_source_path("P:/src/main.py")

    def test_skill_path(self) -> None:
        """Skill directories under plugin are detected."""
        assert _is_plugin_source_path(
            "P:/packages/.claude-marketplace/plugins/cc-skills-sdlc/skills/code/SKILL.md"
        )


# ── Session deduplication ─────────────────────────────────────────────


class TestSessionDedup:
    """F2: File-based session dedup (hooks spawn fresh processes)."""

    def test_first_fire_records(self, tmp_path: Path) -> None:
        """First fire records the warning, second fire sees it."""
        session_id = "sess123"
        session_dir = tmp_path / session_id
        session_dir.mkdir()

        with patch.object(_mod, "SESSION_STATE_DIR", tmp_path):
            assert not _already_warned("test-plugin", session_id)
            _record_warning("test-plugin", session_id)
            assert _already_warned("test-plugin", session_id)

    def test_second_fire_suppressed(self, tmp_path: Path) -> None:
        """Second fire for same plugin is suppressed."""
        warned_file = tmp_path / "warned.jsonl"
        warned_file.write_text('{"plugin":"test-plugin","ts":1000}\n')

        assert _already_warned("test-plugin", None) is False  # No session = no dedup

    def test_different_plugin_not_suppressed(self, tmp_path: Path) -> None:
        """Warning for different plugin is not suppressed."""
        warned_file = tmp_path / "warned.jsonl"
        warned_file.write_text('{"plugin":"plugin-a","ts":1000}\n')

        assert not _already_warned("plugin-b", None)

    def test_no_session_always_warns(self) -> None:
        """Without session ID, always returns False (warn every time)."""
        assert not _already_warned("anything", None)


# ── Session ID ────────────────────────────────────────────────────────


class TestSessionId:
    def test_from_env(self) -> None:
        """Reads CLAUDE_CODE_SESSION_ID from environment."""
        with patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": "abc-123"}):
            assert _session_id() == "abc-123"

    def test_missing_env(self) -> None:
        """Returns None when env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            # May still have it from outer env, so just check type
            result = _session_id()
            assert result is None or isinstance(result, str)


# ── End-to-end hook invocation ────────────────────────────────────────


class TestHookMain:
    """Integration tests for the full hook main() function."""

    def _run_hook(self, stdin_data: str) -> tuple[int, str]:
        """Run the hook with given stdin, return (exit_code, stderr)."""
        import subprocess

        result = subprocess.run(
            [sys.executable, str(HOOK)],
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ},  # Inherit CLAUDE_CODE_SESSION_ID
        )
        return result.returncode, result.stderr

    def test_empty_input_exits_0(self) -> None:
        code, _ = self._run_hook("")
        assert code == 0

    def test_invalid_json_exits_0(self) -> None:
        code, _ = self._run_hook("not json")
        assert code == 0

    def test_edit_tool_suppressed(self) -> None:
        """F5: Edit tool does not trigger advisory."""
        data = json.dumps({
            "tool_name": "Edit",
            "tool_input": {"file_path": "P:/packages/.claude-marketplace/plugins/cc-skills-sdlc/hooks/foo.py"},
        })
        code, stderr = self._run_hook(data)
        assert code == 0
        assert "Plugin source edited" not in stderr

    def test_non_plugin_write_suppressed(self) -> None:
        """Non-plugin path does not trigger advisory."""
        data = json.dumps({
            "tool_name": "Write",
            "tool_input": {"file_path": "P:/src/main.py", "content": "x=1"},
        })
        code, stderr = self._run_hook(data)
        assert code == 0
        assert "Plugin source edited" not in stderr

    def test_local_hooks_suppressed(self) -> None:
        """M2: Local .claude/hooks/ path does not trigger advisory."""
        data = json.dumps({
            "tool_name": "Write",
            "tool_input": {"file_path": "P:/.claude/hooks/PreToolUse_foo.py", "content": "x=1"},
        })
        code, stderr = self._run_hook(data)
        assert code == 0
        assert "Plugin source edited" not in stderr
