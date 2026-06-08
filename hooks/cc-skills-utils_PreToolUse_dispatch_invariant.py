"""PreToolUse gate: enforce the router.py-XOR-hooks.json dispatch invariant.

A plugin dispatches its hooks via EITHER __lib/router.py (registered in
settings.json) OR hooks/hooks.json — never both. If both dispatch, every hook
fires twice. This gate blocks the edit at the moment it would introduce the
violation.

Fires only when ALL of:
  - tool is Edit/Write/MultiEdit
  - target path is a plugin's hooks/hooks.json
  - that plugin has __lib/router.py (committed to the router pattern)
  - the incoming content carries a dispatch entry (contains '"command"')

Legacy plugins that dispatch via hooks.json and have NO router.py are untouched.

Output: permissionDecision=deny (surfaced to the model; legacy decision/block is not).
Fails open on any error — never block on a bug in the gate.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_GATED_TOOLS = {"Edit", "Write", "MultiEdit"}


def _is_plugin_hooks_json(path: Path) -> bool:
    return path.name == "hooks.json" and path.parent.name == "hooks"


def _plugin_root(path: Path) -> Path | None:
    """Walk up to the dir containing .claude-plugin/plugin.json."""
    for parent in path.parents:
        if (parent / ".claude-plugin" / "plugin.json").is_file():
            return parent
    return None


def _incoming_text(tool_name: str, tool_input: dict) -> str:
    """The text this edit would introduce into the file."""
    if tool_name == "Write":
        return tool_input.get("content", "")
    if tool_name == "Edit":
        return tool_input.get("new_string", "")
    if tool_name == "MultiEdit":
        return " ".join(
            e.get("new_string", "") for e in tool_input.get("edits", [])
        )
    return ""


def _deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def main() -> None:
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    if tool_name not in _GATED_TOOLS:
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    raw_path = tool_input.get("file_path", "")
    if not raw_path:
        sys.exit(0)

    try:
        path = Path(raw_path).resolve()
    except Exception:
        sys.exit(0)

    if not _is_plugin_hooks_json(path):
        sys.exit(0)

    root = _plugin_root(path)
    if root is None:
        sys.exit(0)

    # Invariant only applies once a plugin has committed to router.py
    if not (root / "__lib" / "router.py").is_file():
        sys.exit(0)

    # A dispatch entry always contains a "command" key; empty {"hooks": {}} does not.
    if '"command"' in _incoming_text(tool_name, tool_input):
        _deny(
            f"Dispatch invariant: '{root.name}' dispatches via __lib/router.py "
            f"(registered in settings.json), so its hooks.json MUST stay "
            f'{{"hooks": {{}}}}. Adding a dispatch entry here double-fires every '
            f"hook. Add the hook to __lib/router.py's DISPATCH instead. "
            f"(CLAUDE.md -> Plugin Mutation Checklist -> Dispatch invariant)"
        )

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # Fail open
    sys.exit(0)
