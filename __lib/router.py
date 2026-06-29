#!/usr/bin/env python3
"""cc-skills-utils router — dispatches PostToolUse and Stop hooks.

Registered in settings.json. Replaces hooks.json-based dispatch.

Usage:
    python router.py <EventName>

Where EventName is PostToolUse or Stop.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = PLUGIN_ROOT / "hooks"

POSTTOOLUSE_HOOKS = [
    "cc-skills-utils_PostToolUse_cache_reminder.py",
]

STOP_HOOKS = [
    "cc-skills-utils_Stop_cache_reconciler.py",
    "cc-skills-utils_Stop_auto_commit.py",
]

# Per-hook subprocess timeout (seconds). Default 15s; auto_commit does git
# add+commit+push and needs the same 30s budget it had under main Stop.py.
HOOK_TIMEOUTS = {
    "cc-skills-utils_Stop_auto_commit.py": 30,
}

PRETOOLUSE_HOOKS = [
    "cc-skills-utils_PreToolUse_dispatch_invariant.py",
]

DISPATCH = {
    "PreToolUse": PRETOOLUSE_HOOKS,
    "PostToolUse": POSTTOOLUSE_HOOKS,
    "Stop": STOP_HOOKS,
}


def _is_deny(parsed: dict) -> bool:
    """True if a PreToolUse child returned a deny permission decision."""
    hso = parsed.get("hookSpecificOutput")
    if isinstance(hso, dict) and hso.get("permissionDecision") == "deny":
        return True
    return False


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(0)

    event = sys.argv[1]
    hooks = DISPATCH.get(event)
    if not hooks:
        sys.exit(0)

    input_data = sys.stdin.buffer.read()

    for hook_name in hooks:
        hook_path = HOOKS_DIR / hook_name
        if not hook_path.exists():
            continue

        try:
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            result = subprocess.run(
                [sys.executable, str(hook_path)],
                input=input_data,
                capture_output=True,
                timeout=HOOK_TIMEOUTS.get(hook_name, 15),
                creationflags=flags,
            )
        except (subprocess.TimeoutExpired, Exception):
            continue  # Fail open

        out = result.stdout.decode(errors="replace").strip()
        if not out:
            continue
        try:
            parsed = json.loads(out)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, dict):
            continue

        # PreToolUse: a deny short-circuits and is surfaced to the model.
        if event == "PreToolUse" and _is_deny(parsed):
            print(out)
            sys.exit(0)

        # Other events: forward advisory systemMessage.
        if parsed.get("systemMessage"):
            print(out)

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as _e:
        import traceback as _tb
        try:
            _lib = Path(__file__).resolve().parent.parent.parent / "__lib"
            if str(_lib) not in sys.path:
                sys.path.insert(0, str(_lib))
            from hook_error_sink import log_hook_error  # type: ignore[import-not-found]
            log_hook_error(__file__, str(_e), _tb.format_exc())
        except Exception:
            pass
        sys.exit(0)  # Fail open
