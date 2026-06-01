"""PostToolUse advisory hook: remind developer to bump plugin after editing source.

Fires when the Write tool edits a file under the plugin marketplace source tree.
Emits a one-time-per-session advisory to run `plugin-audit-and-fix.py --bump`
and `/reload-plugins`.

Design fixes applied (from RCA p3.md re-audit):
- F1: Plugin name via .claude-plugin/plugin.json parent walk (not path split)
- F2: File-based session dedup (hooks spawn fresh processes)
- F3: Emit UNKNOWN fallback on extraction failure
- F5: Write-only matcher (not Edit+Write)
- M1: Inverted path matching (fire on all plugin paths except cache)
- M2: Suppress for local .claude/hooks/ paths
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# ── Constants ─────────────────────────────────────────────────────────
MARKETPLACE_ROOT = Path(r"P:/packages/.claude-marketplace/plugins")
LOCAL_HOOKS_DIR_PREFIX = Path(r"P:/.claude/hooks")
SESSION_STATE_DIR = Path(r"P:/.claude/.artifacts") / "plugin_reminder"
WARNED_FILENAME = "warned.jsonl"

# Path prefixes that should NOT trigger the advisory.
_SUPPRESS_PREFIXES: list[Path] = [LOCAL_HOOKS_DIR_PREFIX]


def _resolve_plugin_name(file_path: str) -> str | None:
    """Walk parent directories upward to find .claude-plugin/plugin.json.

    Returns the directory name containing plugin.json, or None if not found.
    """
    try:
        p = Path(file_path).resolve()
    except Exception:
        return None

    for parent in p.parents:
        manifest = parent / ".claude-plugin" / "plugin.json"
        if manifest.is_file():
            return parent.name
    return None


def _is_plugin_source_path(file_path: str) -> bool:
    """True if the file is under the marketplace plugins source tree.

    Uses inverted matching: fire on anything under MARKETPLACE_ROOT
    except paths containing '/cache/' (cache directories).
    """
    try:
        resolved = Path(file_path).resolve()
    except Exception:
        return False

    # Suppress local hooks directory
    for prefix in _SUPPRESS_PREFIXES:
        try:
            resolved.relative_to(prefix)
            return False  # Under a suppressed prefix
        except ValueError:
            pass

    # Must be under marketplace root
    try:
        resolved.relative_to(MARKETPLACE_ROOT)
    except ValueError:
        return False

    # Skip cache directories
    if "cache" in resolved.parts:
        return False

    return True


def _session_id() -> str | None:
    """Get current session ID from environment."""
    return os.environ.get("CLAUDE_CODE_SESSION_ID")


def _already_warned(plugin_name: str, session_id: str | None) -> bool:
    """Check if we already warned for this plugin in this session.

    Uses a JSONL file in the session directory for cross-invocation persistence.
    Each line: {"plugin": "<name>", "ts": <epoch>}
    """
    if not session_id:
        return False  # Can't persist, always warn

    warned_file = SESSION_STATE_DIR / session_id / WARNED_FILENAME
    if not warned_file.exists():
        return False

    try:
        for line in warned_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("plugin") == plugin_name:
                return True
    except (json.JSONDecodeError, OSError):
        pass
    return False


def _record_warning(plugin_name: str, session_id: str | None) -> None:
    """Record that we warned for this plugin in this session."""
    if not session_id:
        return

    session_dir = SESSION_STATE_DIR / session_id
    try:
        session_dir.mkdir(parents=True, exist_ok=True)
        warned_file = session_dir / WARNED_FILENAME
        entry = json.dumps({"plugin": plugin_name, "ts": __import__("time").time()})
        with open(warned_file, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except OSError:
        pass  # Best-effort persistence


def _emit_advisory(plugin_name: str) -> None:
    """Print advisory to stderr (non-blocking, exit 0)."""
    msg = (
        f"\n📌 Plugin source edited: '{plugin_name}'\n"
        f"   The running system loads from cache. To apply changes:\n"
        f"   1. Run: plugin-audit-and-fix.py --bump {plugin_name}\n"
        f"   2. Then: /reload-plugins\n"
    )
    print(msg, file=sys.stderr)


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw:
            sys.exit(0)
        data = json.loads(raw)
    except Exception:
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    if tool_name != "Write":
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path: str = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    # Check if this is a plugin source path
    if not _is_plugin_source_path(file_path):
        sys.exit(0)

    # Resolve plugin name
    plugin_name = _resolve_plugin_name(file_path)
    if plugin_name is None:
        # F3: Emit with UNKNOWN rather than silent suppression
        plugin_name = "UNKNOWN"
        _emit_advisory(plugin_name)
        sys.exit(0)

    # F2: Session dedup
    sid = _session_id()
    if _already_warned(plugin_name, sid):
        sys.exit(0)

    _record_warning(plugin_name, sid)
    _emit_advisory(plugin_name)
    sys.exit(0)


if __name__ == "__main__":
    main()
