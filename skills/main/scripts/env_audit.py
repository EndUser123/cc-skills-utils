#!/usr/bin/env python3
"""env_audit.py - fail-fast check for P:/.env presence and required keys.

Invoked by main_health.py as a subprocess check (regen_cap-style), so this file
can be developed and tested independently of the main_health monolith.

Exit codes:
  0  = healthy (env file present, all required keys present)
  2  = critical (file missing, unreadable, or required keys missing)
  1  = invocation error
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ENV_FILE_PATH = Path("P:/.env")
REQUIRED_ENV_KEYS: tuple[str, ...] = (
    "MINIMAX_CONSOLE_COOKIE",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "MINIMAX_API_KEY",
    "BIFROST_API_KEY",
)


def _parse_present_keys(raw: str) -> set[str]:
    present: set[str] = set()
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key:
            present.add(key)
    return present


def run() -> dict:
    """Return a result dict (also exits 0/2 for the subprocess caller)."""
    path = ENV_FILE_PATH

    if not path.exists():
        return _exit(2, {
            "name": "env_audit",
            "status": "critical",
            "message": f"P:/.env not found at {path}",
            "details": [
                f"Path: {path}",
                "Required for: /mm-quota (Layer 1 console scrape), cc-bifrost routing, /mm-quota setup",
                "Fix: create P:/.env with the required keys (see references/health-check-commands.md)",
            ],
            "fixable": [{"action": "create_dotenv_template", "target": str(path)}],
        })

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return _exit(2, {
            "name": "env_audit",
            "status": "critical",
            "message": f"P:/.env unreadable: {exc}",
            "details": [f"Path: {path}"],
        })

    present = _parse_present_keys(raw)
    missing = [k for k in REQUIRED_ENV_KEYS if k not in present]

    if missing:
        return _exit(2, {
            "name": "env_audit",
            "status": "critical",
            "message": f"P:/.env missing {len(missing)} required key(s)",
            "details": [f"Missing: {', '.join(missing)}", f"Path: {path}"],
            "fixable": [{"action": "append_missing_env_keys", "target": str(path)}],
        })

    return _exit(0, {
        "name": "env_audit",
        "status": "healthy",
        "message": f"All {len(REQUIRED_ENV_KEYS)} required env keys present",
    })


def _exit(code: int, payload: dict) -> dict:
    """Print JSON to stdout, exit with code, and return payload for testability."""
    print(json.dumps(payload))
    sys.exit(code)


if __name__ == "__main__":
    run()
