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
# Keys required only by OPTIONAL features: mm-quota console scrape, CCR proxy
# routing, cc-bifrost. The core system runs without them. Absent is normal
# when those features aren't in use — surface as a non-blocking note, not a
# failure (previously these pinned /main to 0% via a false CRITICAL).
OPTIONAL_FEATURE_KEYS: tuple[str, ...] = (
    "MINIMAX_CONSOLE_COOKIE",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
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
    missing_optional = [k for k in OPTIONAL_FEATURE_KEYS if k not in present]

    if missing_optional:
        return _exit(0, {
            "name": "env_audit",
            "status": "healthy",
            "message": f"P:/.env present; {len(missing_optional)} optional feature key(s) absent",
            "details": [
                f"Optional (not required for core): {', '.join(missing_optional)}",
                "Needed only if using: /mm-quota console scrape, CCR proxy (cc-ccr), cc-bifrost",
                f"Path: {path}",
            ],
        })

    return _exit(0, {
        "name": "env_audit",
        "status": "healthy",
        "message": f"P:/.env present; all {len(OPTIONAL_FEATURE_KEYS)} optional feature keys present",
    })


def _exit(code: int, payload: dict) -> dict:
    """Print JSON to stdout, exit with code, and return payload for testability."""
    print(json.dumps(payload))
    sys.exit(code)


if __name__ == "__main__":
    run()
