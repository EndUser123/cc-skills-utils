#!/usr/bin/env python3
"""env_audit.py - fail-fast check for P:/.env presence.

Invoked by main_health.py as a subprocess check (regen_cap-style), so this file
can be developed and tested independently of the main_health monolith.

The core runtime only requires that P:/.env EXISTS. cc-ccr.ps1 sources
CCR_LOCAL_KEY and provider keys from it at launch and sets ANTHROPIC_BASE_URL /
API_KEY / AUTH_TOKEN itself (verified empirically: cc-ccr never reads those
three from .env). No individual key is universally required, so this check is
file-existence only. Missing feature-specific keys surface in their feature's
own check, not here.

Exit codes:
  0  = healthy (env file present and readable)
  2  = critical (file missing or unreadable)
  1  = invocation error
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ENV_FILE_PATH = Path("P:/.env")


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
                "Required by: cc-ccr (sources CCR_LOCAL_KEY + provider keys at launch)",
                "Fix: create P:/.env (see references/health-check-commands.md)",
            ],
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
    return _exit(0, {
        "name": "env_audit",
        "status": "healthy",
        "message": f"P:/.env present ({len(present)} keys)",
    })


def _exit(code: int, payload: dict) -> dict:
    """Print JSON to stdout, exit with code, and return payload for testability."""
    print(json.dumps(payload))
    sys.exit(code)


if __name__ == "__main__":
    run()
