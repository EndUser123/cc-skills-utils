#!/usr/bin/env python3
"""check_dream_cycle_findings.py - count outstanding /debrief dream-cycle findings.

A finding is "outstanding" when /debrief reviewed it more than threshold_days ago
(default 7) AND the user has not actioned it (last_actioned is False). This is a
read-only integration: the dream-state file is owned by /debrief.

Invoked by main_health.py as a subprocess check (env_audit-style). Output format:
    line 1: human message (parsed by run_check as the check message)
    line 2: JSON detail block (status + per-topic details)

Exit codes:
  0 = healthy or warning (findings exist but are informational)
  2 = critical (>3 outstanding findings)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# dream_state lives in the cc-skills-analysis /debrief plugin. Add its __lib
# dir to sys.path so the import works regardless of cwd.
_DREAM_LIB = (
    Path("P:/packages/.claude-marketplace/plugins/cc-skills-analysis")
    / "skills"
    / "debrief"
    / "__lib"
)
if str(_DREAM_LIB) not in sys.path:
    sys.path.insert(0, str(_DREAM_LIB))

import dream_state  # noqa: E402  (path set up above)


def run(threshold_days: int = 7) -> dict:
    findings = dream_state.list_outstanding_dream_findings(threshold_days=threshold_days)
    count = len(findings)

    if count == 0:
        status = "healthy"
        message = "Dream cycle: 0 outstanding findings."
    elif count <= 3:
        status = "warning"
        message = str(count) + " dream-cycle finding(s) outstanding. Run /main --dream for details."
    else:
        status = "critical"
        message = str(count) + " dream-cycle finding(s) outstanding. Run /main --dream for details."

    details = [f"{f['topic']} (age={f['age_days']}d, actioned=False)" for f in findings]
    return {
        "name": "dream_cycle",
        "status": status,
        "message": message,
        "count": count,
        "details": details,
        "findings": findings,
    }


def main() -> int:
    result = run()
    # Human message first (run_check takes the first non-bullet line as message),
    # then the JSON detail block.
    print(result["message"])
    print(json.dumps(result))
    if result["status"] == "critical":
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
