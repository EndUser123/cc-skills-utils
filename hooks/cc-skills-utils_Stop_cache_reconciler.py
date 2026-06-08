"""Stop hook: verify plugin cache == source for all plugins touched this session.

Reads the session's warned.jsonl written by cc-skills-utils_PostToolUse_cache_reminder.py,
checks the cache==source invariant for each touched plugin, and emits a systemMessage
if any plugin's cache is stale or missing.

Invariant: for plugin P at version V (from source plugin.json):
  ~/.claude/plugins/cache/local/P/V/ must exist AND
  cache hooks/hooks.json content must match source hooks/hooks.json

This is a closed-loop check — it asserts the end-state, not the procedure. It catches:
  - Missing cache rebuild after hook file deletion/addition
  - Version bump without cache rebuild
  - hooks.json drift between source and cache
  - Any combination of the above

Fails open on all errors — plugin cache drift is advisory, never blocking.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

MARKETPLACE_ROOT = Path("P:/packages/.claude-marketplace/plugins")
CACHE_ROOT = Path.home() / ".claude/plugins/cache/local"
SESSION_STATE_DIR = Path("P:/.claude/.artifacts/plugin_reminder")
WARNED_FILENAME = "warned.jsonl"
AUDIT_SCRIPT = "P:/packages/.claude-marketplace/plugins/cc-skills-utils/scripts/plugin-audit-and-fix.py"


def _session_id() -> str | None:
    return os.environ.get("CLAUDE_CODE_SESSION_ID")


def _read_touched_plugins(session_id: str) -> list[str]:
    """Read plugin names written by the PostToolUse reminder this session."""
    warned_file = SESSION_STATE_DIR / session_id / WARNED_FILENAME
    if not warned_file.exists():
        return []
    plugins: list[str] = []
    try:
        for line in warned_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            name = entry.get("plugin")
            if name and name not in plugins:
                plugins.append(name)
    except Exception:
        pass
    return plugins


def _find_source_dir(plugin_name: str) -> Path | None:
    candidate = MARKETPLACE_ROOT / plugin_name
    return candidate if candidate.is_dir() else None


def _normalized_json_hash(path: Path) -> str:
    """SHA256 of normalized JSON (sorted keys, no whitespace variation)."""
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
        canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()
    except Exception:
        # Fall back to raw bytes if JSON parse fails
        return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_plugin(plugin_name: str) -> str | None:
    """Return an actionable error string if cache != source, else None."""
    source_dir = _find_source_dir(plugin_name)
    if source_dir is None:
        return None  # Can't locate source — skip silently

    # Read current version from source manifest
    manifest = source_dir / ".claude-plugin" / "plugin.json"
    if not manifest.exists():
        return None
    try:
        version = json.loads(manifest.read_text(encoding="utf-8"))["version"]
    except Exception:
        return None

    # Check 1: cache directory for current version must exist
    cache_dir = CACHE_ROOT / plugin_name / version
    if not cache_dir.exists():
        return (
            f"  • {plugin_name} v{version}: cache directory missing\n"
            f"    Fix: python \"{AUDIT_SCRIPT}\" --bump {plugin_name}"
        )

    # Check 2: cache hooks.json must match source hooks.json
    source_hooks = source_dir / "hooks" / "hooks.json"
    cache_hooks = cache_dir / "hooks" / "hooks.json"

    if source_hooks.exists():
        if not cache_hooks.exists():
            return (
                f"  • {plugin_name} v{version}: cache hooks.json missing\n"
                f"    Fix: python \"{AUDIT_SCRIPT}\" --bump {plugin_name}"
            )
        if _normalized_json_hash(source_hooks) != _normalized_json_hash(cache_hooks):
            return (
                f"  • {plugin_name} v{version}: cache hooks.json is stale\n"
                f"    Fix: python \"{AUDIT_SCRIPT}\" --bump {plugin_name}"
            )

    return None  # Invariant satisfied


def main() -> None:
    sid = _session_id()
    if not sid:
        sys.exit(0)

    touched = _read_touched_plugins(sid)
    if not touched:
        sys.exit(0)

    violations: list[str] = []
    for plugin_name in touched:
        if plugin_name == "UNKNOWN":
            continue
        err = _check_plugin(plugin_name)
        if err:
            violations.append(err)

    if violations:
        body = "\n".join(violations)
        msg = (
            "⚠️ Plugin cache drift — session changes not yet in cache:\n"
            f"{body}\n"
            "Run the fix command(s) above, then /reload-plugins."
        )
        print(json.dumps({"systemMessage": msg}))

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # Fail open — never block on this
    sys.exit(0)
