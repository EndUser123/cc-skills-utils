#!/usr/bin/env python3
"""
Unified /main health check runner.

Runs all health checks with consolidated output and optional auto-fix.

Usage:
    python main_health.py              # All checks, summary view
    python main_health.py --quick      # Skip slow checks (<5s)
    python main_health.py --fix        # Auto-remediate safe issues
    python main_health.py --dry-run    # Preview what --fix would do
    python main_health.py --json       # Machine-readable output
    python main_health.py --deps       # Include dependency audit
    python main_health.py --skip-cve   # Skip CVE remediation check
    python main_health.py --quiet      # Just pass/fail status line
    python main_health.py --history    # Show health score trend
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

# Paths
TOOLS_DIR = Path(__file__).parent
SKILLS_DIR = TOOLS_DIR.parent.parent
CLAUDE_DIR = SKILLS_DIR.parent
PROJECT_ROOT = Path("P:\\\\\\")
HISTORY_FILE = CLAUDE_DIR / "session_data" / "health_history.jsonl"
ENV_STATE_FILE = CLAUDE_DIR / "session_data" / "env_vars_state.json"
BASELINE_FILE = CLAUDE_DIR / "session_data" / "health_baseline.json"


@dataclass
class HealthBaseline:
    """Tracks acknowledged sizes to suppress duplicate warnings."""

    hook_log_size_mb: float | None = None
    cks_size_mb: float | None = None
    updated_at: str | None = None
    updated_by: str | None = None  # "cleanup", "manual", "acknowledge"


def load_baseline() -> HealthBaseline:
    """Load health baseline from file."""
    if not BASELINE_FILE.exists():
        return HealthBaseline()
    try:
        with open(BASELINE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return HealthBaseline(
            hook_log_size_mb=data.get("hook_log_size_mb"),
            cks_size_mb=data.get("cks_size_mb"),
            updated_at=data.get("updated_at"),
            updated_by=data.get("updated_by"),
        )
    except (json.JSONDecodeError, KeyError):
        return HealthBaseline()


def save_baseline(baseline: HealthBaseline, updated_by: str = "manual") -> None:
    """Save health baseline to file."""
    BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    baseline.updated_at = datetime.now().isoformat()
    baseline.updated_by = updated_by
    with open(BASELINE_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {
                "hook_log_size_mb": baseline.hook_log_size_mb,
                "cks_size_mb": baseline.cks_size_mb,
                "updated_at": baseline.updated_at,
                "updated_by": baseline.updated_by,
            },
            f,
            indent=2,
        )


def _extract_size_from_details(details: list[str], pattern: str) -> float | None:
    """Extract size (MB) from details lines matching pattern."""
    import re
    for line in details:
        if pattern in line:
            # Try to extract number followed by MB (handles "52.0MB" or "52.0 MB")
            match = re.search(r"(\d+\.?\d*)\s*MB", line, re.IGNORECASE)
            if match:
                return float(match.group(1))
    return None


def _apply_baseline(checks: list[CheckResult], baseline: HealthBaseline) -> list[CheckResult]:
    """Apply baseline comparison to suppress duplicate warnings for stable sizes."""
    for check in checks:
        if check.name == "hooks":
            current_size = _extract_size_from_details(check.details, "Log dir:")
            if current_size is not None and baseline.hook_log_size_mb is not None:
                if current_size <= baseline.hook_log_size_mb:
                    # Size is stable or reduced - suppress warning
                    if check.status == "warning":
                        check.status = "healthy"
                        # Update message to show stable state
                        check.message = f"Log dir: {current_size:.1f}MB (stable, baseline: {baseline.hook_log_size_mb:.1f}MB)"
                elif current_size > baseline.hook_log_size_mb:
                    # Regression - flag it
                    delta = current_size - baseline.hook_log_size_mb
                    check.details.append(f"⚠️  REGRESSION: +{delta:.1f}MB since baseline ({baseline.updated_at})")
            # Update baseline with current size if not set
            if baseline.hook_log_size_mb is None and current_size is not None:
                baseline.hook_log_size_mb = current_size

        elif check.name == "cks":
            current_size = _extract_size_from_details(check.details, "Database size:")
            if current_size is not None and baseline.cks_size_mb is not None:
                if current_size <= baseline.cks_size_mb:
                    # Size is stable or reduced - suppress warning
                    if check.status == "warning":
                        check.status = "healthy"
                        check.message = f"Database size: {current_size:.1f}MB (stable, baseline: {baseline.cks_size_mb:.1f}MB)"
                elif current_size > baseline.cks_size_mb:
                    # Regression - flag it
                    delta = current_size - baseline.cks_size_mb
                    check.details.append(f"⚠️  REGRESSION: +{delta:.1f}MB since baseline ({baseline.updated_at})")
            # Update baseline with current size if not set
            if baseline.cks_size_mb is None and current_size is not None:
                baseline.cks_size_mb = current_size

    return checks


@dataclass
class CheckResult:
    """Result from a single health check."""

    name: str
    status: str  # "healthy", "warning", "critical"
    message: str
    details: list[str] = field(default_factory=list)
    fixable: list[dict] = field(default_factory=list)  # {"action": str, "target": str}
    duration_ms: int = 0
    suggestions: list[str] = field(default_factory=list)  # skill suggestions, e.g. ["/skill-ship"]


@dataclass
class HealthReport:
    """Aggregated health report."""

    timestamp: str
    overall_status: str
    score: int  # 0-100
    checks: list[CheckResult]
    duration_ms: int = 0


@dataclass(frozen=True)
class HealthFinding:
    """Structured health finding with skill suggestion."""
    check_name: str
    status: str  # "warning" or "critical"
    message: str
    suggested_skill: str
    rationale: str
    category: str  # "correctness", "quality", "knowledge", etc.


# ── Suggestion Map ─────────────────────────────────────────────────────────────
# Maps (check_name, pattern_key) → list of suggestion dicts.
# pattern_key is matched against check details/message text (case-insensitive).
# None = always match for this check (catch-all).

_SUGGESTION_MAP: dict[tuple[str, str | None], list[dict]] = {
    # spec_drift: script referenced in SKILL.md doesn't exist
    ("spec_drift", "NOT FOUND"): [
        {
            "skill": "/skill-ship",
            "rationale": "Creates and validates skill execution paths, fixing drift between SKILL.md and actual scripts",
            "category": "correctness",
        },
        {
            "skill": "/similarity",
            "rationale": "Finds existing skills with correct execution paths",
            "category": "discovery",
        },
    ],
    # skill_deps: missing skill directory
    ("skill_deps", "SKILL DIR NOT FOUND"): [
        {
            "skill": "/skill-ship",
            "rationale": "Validates and creates missing skill directories and SKILL.md files",
            "category": "correctness",
        },
        {
            "skill": "/similarity",
            "rationale": "Finds existing skills that match the missing dependency",
            "category": "discovery",
        },
    ],
    # skill_deps: SKILL.md missing required fields
    ("skill_deps", "SKILL.MD MISSING"): [
        {
            "skill": "/skill-ship",
            "rationale": "Generates complete SKILL.md with required frontmatter fields",
            "category": "correctness",
        },
    ],
    # skill_deps: SKILL.md missing required fields
    ("skill_deps", "SKILL.md missing"): [
        {
            "skill": "/av",
            "rationale": "Analyzes and validates SKILL.md frontmatter completeness",
            "category": "quality",
        },
    ],
    # hooks: timeout issues
    ("hooks", "timeout"): [
        {
            "skill": "/hook-obs",
            "rationale": "Inspects hook timeout and latency patterns from diagnostics data",
            "category": "observability",
        },
    ],
    # hooks: syntax errors
    ("hooks", "syntax"): [
        {
            "skill": "/hook-obs",
            "rationale": "Surfaces failing hooks and recent diagnostics context",
            "category": "correctness",
        },
    ],
    # hooks: log directory bloat
    ("hooks", "log"): [
        {
            "skill": "/cleanup",
            "rationale": "Cleans up log directory bloat in hook observability files",
            "category": "maintenance",
        },
    ],
    # cks: low entry count or stale
    ("cks", None): [
        {
            "skill": "/reflect",
            "rationale": "Runs reflection prompts that add entries to CKS",
            "category": "knowledge",
        },
        {
            "skill": "/garden",
            "rationale": "Performs knowledge hygiene, consolidating and curating CKS entries",
            "category": "knowledge",
        },
    ],
    # filesystem: violations detected
    ("filesystem", "violation"): [
        {
            "skill": "/cleanup",
            "rationale": "Removes filesystem violations and restores structure",
            "category": "maintenance",
        },
    ],
    # settings: size bloat
    ("settings", "bloat"): [
        {
            "skill": "/standards",
            "rationale": "Reviews settings against CSF/NIP standards for bloat",
            "category": "quality",
        },
    ],
    # settings: orphaned env vars
    ("settings", "orphaned"): [
        {
            "skill": "/standards",
            "rationale": "Reviews settings against CSF/NIP standards, identifies unused env vars",
            "category": "quality",
        },
    ],
    # skill_quality: YAML/frontmatter issues
    ("skill_quality", "frontmatter"): [
        {
            "skill": "/av",
            "rationale": "Analyzes skill quality including YAML frontmatter validation",
            "category": "quality",
        },
    ],
    # skill_quality: TODO/FIXME detected
    ("skill_quality", "TODO"): [
        {
            "skill": "/critique",
            "rationale": "Reviews code and identifies technical debt items",
            "category": "quality",
        },
    ],
    # dependencies: vulnerabilities found
    ("dependencies", "vulnerab"): [
        {
            "skill": "/deps",
            "rationale": "Manages dependency updates and vulnerability remediation",
            "category": "security",
        },
    ],
    # cve_remediation: fixable vulnerabilities
    ("cve_remediation", "would install"): [
        {
            "skill": "/deps",
            "rationale": "Applies safe dependency upgrades to fix CVEs",
            "category": "security",
        },
    ],
    # workspace: uncommitted changes
    ("workspace", "uncommitted"): [
        {
            "skill": "/git",
            "rationale": "Commits or reverts workspace changes",
            "category": "vcs",
        },
    ],
}

# QUAL-001: Kill criterion — SUGGESTION_MAP must not exceed size limit
_MAX_SUGGESTION_MAP_SIZE = 50
assert len(_SUGGESTION_MAP) <= _MAX_SUGGESTION_MAP_SIZE, (
    f"SUGGESTION_MAP has {len(_SUGGESTION_MAP)} entries, "
    f"exceeds limit of {_MAX_SUGGESTION_MAP_SIZE} — redesign to GTO-based approach required"
)


def _match_suggestions(check_name: str, details_text: str, message_text: str) -> list[str]:
    """Return list of suggested skill triggers for a check result.

    Matches against SUGGESTION_MAP using check_name + case-insensitive pattern.
    """
    suggestions: list[str] = []
    details_lower = details_text.lower()
    message_lower = message_text.lower()

    for (cname, pattern), findings in _SUGGESTION_MAP.items():
        if cname != check_name:
            continue
        if pattern is None:
            # Catch-all: always suggest for this check if it failed
            for f in findings:
                if f["skill"] not in suggestions:
                    suggestions.append(f["skill"])
        elif pattern.lower() in details_lower or pattern.lower() in message_lower:
            for f in findings:
                if f["skill"] not in suggestions:
                    suggestions.append(f["skill"])

    return suggestions[:3]  # Cap at 3 suggestions per check


def _check_to_findings(check: CheckResult) -> list[HealthFinding]:
    """Convert a CheckResult with suggestions into HealthFinding list."""
    if check.status == "healthy":
        return []
    details_text = " ".join(check.details)
    message_text = check.message
    skill_list = _match_suggestions(check.name, details_text, message_text)
    findings = []
    for skill in skill_list:
        for (cname, pattern), mapping in _SUGGESTION_MAP.items():
            if cname != check.name:
                continue
            for f in mapping:
                if f["skill"] == skill:
                    findings.append(HealthFinding(
                        check_name=check.name,
                        status=check.status,
                        message=check.message,
                        suggested_skill=skill,
                        rationale=f["rationale"],
                        category=f["category"],
                    ))
                    break
    return findings


def run_check(name: str, script: Path, timeout: int = 30) -> CheckResult:
    """Run a health check script and parse output."""
    start = time.time()

    try:
        # Use pythonw.exe on Windows to prevent console flash
        python_exe = sys.executable
        if sys.platform == "win32" and python_exe.endswith("python.exe"):
            python_exe = python_exe.replace("python.exe", "pythonw.exe")

        result = subprocess.run(
            [python_exe, str(script)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

        duration_ms = int((time.time() - start) * 1000)
        output = result.stdout + result.stderr

        # Parse output for status
        status = "healthy"
        fixable = []
        details = []

        for line in output.splitlines():
            line_lower = line.lower()
            if "❌" in line or "critical" in line_lower or "error" in line_lower:
                status = "critical"
            elif "⚠️" in line or "warning" in line_lower:
                if status != "critical":
                    status = "warning"

            # Detect fixable issues
            if "watcher.log" in line and "runaway" in line_lower:
                fixable.append(
                    {"action": "truncate", "target": "P:\\\\\\.claude/hooks/logs/watcher.log"}
                )
            if "RESTORE_CONTEXT.md" in line and "exists" in line_lower:
                fixable.append({"action": "delete", "target": "P:\\\\\\.claude/RESTORE_CONTEXT.md"})
            if "stale lock" in line_lower:
                # Extract lock file path
                if ".git" in line:
                    for part in line.split():
                        if ".lock" in part:
                            fixable.append({"action": "delete", "target": part})

            if line.strip() and not line.startswith("Run:"):
                details.append(line.strip())

        # Get first meaningful line as message
        message_lines = [line for line in details if line and not line.startswith("•")]
        message = message_lines[0] if message_lines else "Check completed"

        # Populate skill suggestions based on check result
        suggestions = _match_suggestions(name, " ".join(details), message)

        return CheckResult(
            name=name,
            status=status,
            message=message,
            details=details,
            fixable=fixable,
            duration_ms=duration_ms,
            suggestions=suggestions,
        )

    except subprocess.TimeoutExpired:
        suggestions = _match_suggestions(name, f"timeout after {timeout}s", "")
        return CheckResult(
            name=name,
            status="warning",
            message=f"Timeout after {timeout}s",
            duration_ms=timeout * 1000,
            suggestions=suggestions,
        )
    except Exception as e:
        suggestions = _match_suggestions(name, str(e), "")
        return CheckResult(
            name=name,
            status="critical",
            message=f"Error: {e}",
            duration_ms=int((time.time() - start) * 1000),
            suggestions=suggestions,
        )


def run_dependency_audit() -> CheckResult:
    """Run pip-audit for dependency vulnerabilities."""
    start = time.time()
    details = []

    try:
        # Check if pip-audit is available
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", "pip-audit"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

        if result.returncode != 0:
            return CheckResult(
                name="dependencies",
                status="warning",
                message="pip-audit not installed (pip install pip-audit)",
                duration_ms=int((time.time() - start) * 1000),
            )

        # Run pip-audit
        result = subprocess.run(
            [sys.executable, "-m", "pip_audit", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

        duration_ms = int((time.time() - start) * 1000)

        if result.returncode == 0:
            return CheckResult(
                name="dependencies",
                status="healthy",
                message="No vulnerabilities found",
                duration_ms=duration_ms,
            )

        # Parse vulnerabilities
        try:
            vulns = json.loads(result.stdout)
            critical = sum(
                1 for v in vulns if v.get("severity", "").lower() in ("critical", "high")
            )
            medium = sum(1 for v in vulns if v.get("severity", "").lower() == "medium")

            for v in vulns:
                details.append(f"{v.get('name')}: {v.get('severity')} - {v.get('id')}")

            status = "critical" if critical > 0 else "warning" if medium > 0 else "healthy"
            message = f"{len(vulns)} vulnerabilities ({critical} critical/high, {medium} medium)"

            return CheckResult(
                name="dependencies",
                status=status,
                message=message,
                details=details,
                duration_ms=duration_ms,
            )
        except json.JSONDecodeError:
            details = result.stderr.splitlines()[:5]
            return CheckResult(
                name="dependencies",
                status="warning",
                message="pip-audit output parse error",
                details=details,
                duration_ms=duration_ms,
            )

    except subprocess.TimeoutExpired:
        return CheckResult(
            name="dependencies",
            status="warning",
            message="pip-audit timeout (>120s)",
            duration_ms=120000,
        )
    except Exception as e:
        return CheckResult(
            name="dependencies",
            status="warning",
            message=f"Error: {e}",
            duration_ms=int((time.time() - start) * 1000),
        )


def _summarize_hook_health(hooks_dir: Path) -> dict:
    """Read latest hook health summary from diagnostics output."""
    health_file = hooks_dir / "logs" / "diagnostics" / "hook_health.json"
    if not health_file.exists():
        return {"status": "unavailable", "failing_count": 0, "failures": []}

    try:
        payload = json.loads(health_file.read_text(encoding="utf-8"))
        failures = payload.get("failures", [])
        if not isinstance(failures, list):
            failures = []
        return {
            "status": str(payload.get("status", "unknown")).lower(),
            "failing_count": len(failures),
            "failures": [str(item) for item in failures],
        }
    except (json.JSONDecodeError, OSError):
        return {"status": "unavailable", "failing_count": 0, "failures": []}


def _summarize_router_runtime_errors(hooks_dir: Path, days: int) -> dict:
    """Summarize HOOK_RUNTIME_ERROR and HOOK_NON_JSON_OUTPUT events."""
    decisions_dir = hooks_dir / "session_data"
    if not decisions_dir.exists():
        return {"total": 0, "runtime_error": 0, "non_json_output": 0, "by_hook": []}

    cutoff = datetime.now() - timedelta(days=days)
    runtime_error = 0
    non_json_output = 0
    by_hook: Counter[str] = Counter()

    for file_path in sorted(decisions_dir.glob("hook_decisions_*.jsonl")):
        try:
            with open(file_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    ts = entry.get("timestamp")
                    if not ts:
                        continue
                    try:
                        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                        if dt.tzinfo is not None:
                            dt = dt.astimezone().replace(tzinfo=None)
                        if dt < cutoff:
                            continue
                    except ValueError:
                        continue

                    reason = str(entry.get("reason", ""))
                    hook_name = str(entry.get("hook_name", "unknown"))
                    matched = False
                    if "HOOK_RUNTIME_ERROR" in reason:
                        runtime_error += 1
                        matched = True
                    if "HOOK_NON_JSON_OUTPUT" in reason:
                        non_json_output += 1
                        matched = True
                    if matched:
                        by_hook[hook_name] += 1
        except OSError:
            continue

    return {
        "total": runtime_error + non_json_output,
        "runtime_error": runtime_error,
        "non_json_output": non_json_output,
        "by_hook": by_hook.most_common(5),
    }


def run_cve_remediation_check() -> CheckResult:
    """Run pip-audit --fix --dry-run to show CVE remediation options.

    Shows what packages would be upgraded to fix vulnerabilities, without
    actually making changes (dry-run mode for safety).
    """
    start = time.time()
    details = []

    try:
        # Check if pip-audit is available
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", "pip-audit"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

        if result.returncode != 0:
            return CheckResult(
                name="cve_remediation",
                status="warning",
                message="pip-audit not installed (pip install pip-audit)",
                duration_ms=int((time.time() - start) * 1000),
            )

        # Run pip-audit with --fix --dry-run to see what would be fixed
        result = subprocess.run(
            [sys.executable, "-m", "pip_audit", "--fix", "--dry-run"],
            capture_output=True,
            text=True,
            timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

        duration_ms = int((time.time() - start) * 1000)

        # Check if pip-audit supports --fix (v3.0+)
        if (
            "unrecognized arguments: --fix" in result.stderr
            or "no such option" in result.stderr.lower()
        ):
            return CheckResult(
                name="cve_remediation",
                status="warning",
                message="pip-audit v3.0+ required for --fix (current: old version)",
                details=["Upgrade: pip install --upgrade pip-audit"],
                duration_ms=duration_ms,
            )

        # Parse output for what would be fixed
        output_lines = result.stdout.splitlines()

        # Look for "Would install" or similar indicators
        fixable_packages = []
        for line in output_lines:
            line_lower = line.lower()
            if (
                "would install" in line_lower
                or "would upgrade" in line_lower
                or "install" in line_lower
            ):
                # Extract package names (format varies)
                if "→" in line or "->" in line or " to " in line_lower:
                    fixable_packages.append(line.strip())

        if result.returncode == 0:
            # No vulnerabilities to fix
            if not fixable_packages:
                return CheckResult(
                    name="cve_remediation",
                    status="healthy",
                    message="No CVE fixes needed",
                    duration_ms=duration_ms,
                )

        # Build details from output
        details = []
        for line in output_lines:
            line = line.strip()
            if line and not line.startswith("Found ") and not line.startswith("Affected"):
                details.append(line)

        status = "critical" if "Found" in result.stdout and "CVE" in result.stdout else "warning"
        message = (
            f"{len(fixable_packages)} package(s) can be upgraded"
            if fixable_packages
            else "Check CVE remediation options"
        )

        return CheckResult(
            name="cve_remediation",
            status=status,
            message=message,
            details=details[:15],  # Limit output
            duration_ms=duration_ms,
        )

    except subprocess.TimeoutExpired:
        return CheckResult(
            name="cve_remediation",
            status="warning",
            message="pip-audit timeout (>120s)",
            duration_ms=120000,
        )
    except Exception as e:
        return CheckResult(
            name="cve_remediation",
            status="warning",
            message=f"Error: {e}",
            duration_ms=int((time.time() - start) * 1000),
        )


def run_hook_syntax_check() -> CheckResult:
    """Validate Python syntax for all hook files.

    Two-layer check:
    1. py_compile — catches SyntaxError (hard failures, won't parse)
    2. warnings-as-errors compile — catches SyntaxWarning (e.g. invalid
       escape sequences like "\\." that emit to stderr and trigger
       Claude Code's "hook error" false positive)
    """
    import py_compile
    import warnings

    start = time.time()
    hooks_dir = CLAUDE_DIR / "hooks"

    if not hooks_dir.exists():
        return CheckResult(
            name="hook_syntax",
            status="warning",
            message="Hooks directory not found",
            duration_ms=int((time.time() - start) * 1000),
        )

    broken_hooks = []
    warning_hooks = []
    checked_count = 0

    for hook_file in hooks_dir.rglob("*.py"):
        # Skip __pycache__, test files, migration backups, and archives
        path_str = str(hook_file)
        # Use relative path for checking (works with both / and \ separators)
        try:
            rel_path = hook_file.relative_to(hooks_dir)
        except ValueError:
            rel_path = hook_file

        rel_str = str(rel_path).replace("\\", "/")

        if (
            hook_file.name.startswith("__")
            or "tests/" in rel_str
            or "/tests/" in rel_str
            or ".migration_backup" in path_str
            or "/designive/" in rel_str
            or "/_archive/" in rel_str
            or "/_archived/" in rel_str
            or rel_str.startswith("archive/")
            or rel_str.startswith("_archive/")
            or rel_str.startswith("_archived/")
            or "/.benchmarks/" in rel_str
            or rel_str.startswith(".benchmarks/")
            or "/damage-control/" in rel_str
            or rel_str.startswith("damage-control/")
        ):
            continue

        checked_count += 1

        # Layer 1: Hard syntax errors
        try:
            py_compile.compile(str(hook_file), doraise=True)
        except py_compile.PyCompileError as e:
            error_msg = str(e).split("\n")[-1] if "\n" in str(e) else str(e)
            broken_hooks.append(f"{hook_file.name}: {error_msg[:80]}")
            continue  # No need to check warnings if it won't even compile

        # Layer 2: SyntaxWarning (invalid escapes, etc.)
        # These compile fine but emit to stderr, triggering "hook error".
        # Note: filterwarnings("error") promotes SyntaxWarning → SyntaxError,
        # so we catch SyntaxError here. Real SyntaxErrors were already caught
        # by py_compile in Layer 1, so any SyntaxError here is a promoted warning.
        try:
            source = hook_file.read_text(encoding="utf-8")
            with warnings.catch_warnings():
                warnings.filterwarnings("error", category=SyntaxWarning)
                compile(source, str(hook_file), "exec")
        except (SyntaxWarning, SyntaxError) as e:
            warning_hooks.append(f"{hook_file.name}: SyntaxWarning: {e}")
        except Exception:
            pass  # Unexpected error, Layer 1 covers compilation failures

    duration_ms = int((time.time() - start) * 1000)

    if broken_hooks:
        return CheckResult(
            name="hook_syntax",
            status="critical",
            message=f"{len(broken_hooks)} hook(s) have syntax errors",
            details=broken_hooks[:10],
            duration_ms=duration_ms,
        )

    if warning_hooks:
        return CheckResult(
            name="hook_syntax",
            status="warning",
            message=f"{len(warning_hooks)} hook(s) emit SyntaxWarning (causes 'hook error' in Claude Code)",
            details=warning_hooks[:10],
            duration_ms=duration_ms,
        )

    return CheckResult(
        name="hook_syntax",
        status="healthy",
        message=f"All {checked_count} hooks pass syntax check (errors + warnings)",
        duration_ms=duration_ms,
    )


def run_hook_stats_check() -> CheckResult:
    """Summarize hook diagnostics activity with health and runtime context."""
    start = time.time()
    hooks_dir = CLAUDE_DIR / "hooks"
    diag_db = hooks_dir / "logs" / "diagnostics" / "diagnostics.db"

    if not diag_db.exists():
        return CheckResult(
            name="hook_stats",
            status="healthy",
            message="Hook stats: no diagnostics DB yet. Run /hook-obs stats when hooks start logging.",
            duration_ms=int((time.time() - start) * 1000),
        )

    try:
        if str(hooks_dir) not in sys.path:
            sys.path.insert(0, str(hooks_dir))
        from cc_diagnostic_logger import query_hook_invocations
        rows = query_hook_invocations(days=7, limit=200)
        duration_ms = int((time.time() - start) * 1000)

        total = len(rows)
        blocks = sum(1 for row in rows if row.get("action") == "block")
        injects = sum(1 for row in rows if row.get("action") == "inject")
        warns = sum(1 for row in rows if row.get("action") == "warn")
        passes = sum(1 for row in rows if row.get("action") == "pass")
        turns = len({row.get("turn_id") for row in rows if row.get("turn_id")})
        top_blockers = Counter(
            row.get("hook_name", "unknown")
            for row in rows
            if row.get("action") == "block"
        )
        top_injectors = Counter(
            row.get("hook_name", "unknown")
            for row in rows
            if row.get("action") == "inject"
        )

        health_summary = _summarize_hook_health(hooks_dir)
        runtime_summary = _summarize_router_runtime_errors(hooks_dir, days=7)

        status = "healthy"
        if health_summary["status"] == "fail" or runtime_summary["total"] > 0:
            status = "warning"

        health_label = "pass"
        if health_summary["status"] == "fail":
            health_label = f"{health_summary['failing_count']} failing hook(s)"
        elif health_summary["status"] == "unavailable":
            health_label = "unavailable"

        message = (
            f"Hook stats (7d): {total} events "
            f"({injects} inject/{blocks} block/{warns} warn/{passes} pass), "
            f"{turns} turns; health: {health_label}; "
            f"validator errors: {runtime_summary['total']}."
            " Run /hook-obs stats --turn <turn-id> for drill-down."
        )

        details = []
        if top_blockers:
            blockers = ", ".join(f"{name} ({count})" for name, count in top_blockers.most_common(3))
            details.append(f"• Top blockers: {blockers}")
        if top_injectors:
            injectors = ", ".join(f"{name} ({count})" for name, count in top_injectors.most_common(3))
            details.append(f"• Top injectors: {injectors}")
        if health_summary["status"] == "fail" and health_summary["failures"]:
            details.append(
                "⚠️ Failing hooks: "
                + ", ".join(health_summary["failures"][:3])
            )
        if runtime_summary["by_hook"]:
            hotspots = ", ".join(f"{name} ({count})" for name, count in runtime_summary["by_hook"][:3])
            details.append(f"⚠️ Validator error hotspots: {hotspots}")
        details.append("• Use /hook-obs health for full hook health details")

        return CheckResult(
            name="hook_stats",
            status=status,
            message=message,
            details=details,
            duration_ms=duration_ms,
        )
    except Exception as e:
        return CheckResult(
            name="hook_stats",
            status="warning",
            message=f"Hook stats unavailable: {e}",
            details=["• Run /hook-obs stats"],
            duration_ms=int((time.time() - start) * 1000),
        )


def run_cleanup_check() -> dict | None:
    """Run cleanup.py --json to detect filesystem violations.

    Returns None if cleanup.py is not available or errors.
    """
    cleanup_script = SKILLS_DIR / "cleanup" / "scripts" / "cleanup.py"

    if not cleanup_script.exists():
        return None

    try:
        result = subprocess.run(
            [sys.executable, str(cleanup_script), "--json", "--max", "100"],
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

        if result.returncode != 0:
            return None

        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
        return None


def run_filesystem_check() -> CheckResult:
    """Run filesystem structure check using cleanup.py."""
    start = time.time()

    cleanup_result = run_cleanup_check()

    if not cleanup_result:
        return CheckResult(
            name="filesystem",
            status="warning",
            message="cleanup.py unavailable",
            duration_ms=int((time.time() - start) * 1000),
        )

    violation_count = cleanup_result.get("violations_count", 0)
    cleanup_violations = cleanup_result.get("violations", [])

    details = []
    if violation_count > 0:
        from collections import Counter

        details.append(f"[WARN] {violation_count} filesystem violations (run /cleanup)")
        violation_types = Counter(v.get("type", "unknown") for v in cleanup_violations)
        for vtype, count in violation_types.most_common(5):
            details.append(f"• {vtype}: {count} violations")

    return CheckResult(
        name="filesystem",
        status="warning" if violation_count > 0 else "healthy",
        message=f"{violation_count} filesystem violations (run /cleanup)"
        if violation_count > 0
        else "No filesystem violations",
        details=details,
        duration_ms=int((time.time() - start) * 1000),
    )


def run_spec_drift_check() -> CheckResult:
    """Check SKILL.md documented execution paths against actual files.

    Parses ## EXECUTION DIRECTIVE sections in SKILL.md files for
    'python X' and 'bash X' patterns, then verifies the referenced
    scripts exist. Catches spec drift where documentation refers to
    non-existent files.
    """
    start = time.time()
    details = []
    missing_count = 0

    # Find all SKILL.md files
    skills_skill_dirs = [
        SKILLS_DIR,  # P:\\\\\\.claude/skills/
        CLAUDE_DIR / "packages",  # P:\\\\\\packages/
    ]

    import re

    # Patterns to match execution directives
    # Require path indicators: /, \, .py, .sh, or drive letter prefix
    python_pattern = re.compile(r"\bpython\s+([^\s]*(?:[/.\\][^\s]*)+)", re.IGNORECASE)
    bash_pattern = re.compile(r"\bbash\s+([^\s]*(?:[/.\\][^\s]*)+)", re.IGNORECASE)

    for skills_dir in skills_skill_dirs:
        if not skills_dir.exists():
            continue

        for skill_md in skills_dir.rglob("SKILL.md"):
            try:
                content = skill_md.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            # Find EXECUTION DIRECTIVE section
            exec_directive_match = re.search(
                r"(?:^|\n)##\s+EXECUTION\s+DIRECTIVE\s*\n(.*?)(?=\n##\s|\Z)",
                content,
                re.IGNORECASE | re.DOTALL,
            )
            if not exec_directive_match:
                continue

            exec_section = exec_directive_match.group(1)

            # Find python and bash invocations
            skill_rel = skill_md.relative_to(skills_dir.parent.parent)
            skill_name = skill_rel.parent.name

            for match in python_pattern.finditer(exec_section):
                path_str = match.group(1).strip()
                # Resolve relative to skill directory
                script_path = (skill_md.parent / path_str).resolve()
                if not script_path.exists():
                    missing_count += 1
                    details.append(f"{skill_name}: python {path_str} → NOT FOUND")

            for match in bash_pattern.finditer(exec_section):
                path_str = match.group(1).strip()
                script_path = (skill_md.parent / path_str).resolve()
                if not script_path.exists():
                    missing_count += 1
                    details.append(f"{skill_name}: bash {path_str} → NOT FOUND")

    status = "warning" if missing_count > 0 else "healthy"
    message = (
        f"{missing_count} spec drift(s) detected"
        if missing_count > 0
        else "All execution paths valid"
    )

    return CheckResult(
        name="spec_drift",
        status=status,
        message=message,
        details=details[:20],
        duration_ms=int((time.time() - start) * 1000),
    )


def run_skill_dependency_check() -> CheckResult:
    """Check skill dependency references are valid.

    Parses depends_on_skills and suggest frontmatter in SKILL.md files
    and verifies referenced skills exist and have valid SKILL.md.
    """
    start = time.time()
    details = []
    missing_count = 0

    # All skill directories to scan
    skills_skill_dirs = [
        SKILLS_DIR,  # P:\\\\\\.claude/skills/
        CLAUDE_DIR / "packages",  # P:\\\\\\packages/
    ]

    import re

    for skills_dir in skills_skill_dirs:
        if not skills_dir.exists():
            continue

        for skill_md in skills_dir.rglob("SKILL.md"):
            try:
                content = skill_md.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            skill_rel = skill_md.relative_to(skills_dir.parent.parent)
            skill_name = skill_rel.parent.name

            # Parse YAML frontmatter
            frontmatter_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
            if not frontmatter_match:
                continue

            fm_text = frontmatter_match.group(1)

            # Extract depends_on_skills and suggest arrays
            deps_match = re.search(
                r"^depends_on_skills:\s*\[(.*?)\]"
                if fm_text.startswith("depends_on_skills")
                else r"\ndepends_on_skills:\s*\[(.*?)\]",
                fm_text,
                re.DOTALL,
            )
            suggest_match = re.search(
                r"^suggest:\s*\[(.*?)\]"
                if fm_text.startswith("suggest")
                else r"\nsuggest:\s*\[(.*?)\]",
                fm_text,
                re.DOTALL,
            )

            def parse_list_items(list_str: str) -> list[str]:
                """Parse comma or newline separated skill names."""
                items = re.sub(r"[,\n]+", ",", list_str).split(",")
                return [s.strip().strip("\"'") for s in items if s.strip()]

            depends = parse_list_items(deps_match.group(1)) if deps_match else []
            suggests = parse_list_items(suggest_match.group(1)) if suggest_match else []

            all_refs = depends + suggests

            for ref in all_refs:
                if not ref:
                    continue

                # ref can be skill name ("/search") or path ("skills/search")
                ref_clean = ref.lstrip("/")
                if ref_clean.startswith("skills/"):
                    ref_path = skills_dir.parent / ref_clean
                elif "/" in ref_clean:
                    ref_path = skills_dir.parent / "skills" / ref_clean.split("/")[-1]
                else:
                    # Just skill name - search for it
                    ref_path = skills_dir / ref_clean

                if not ref_path.exists():
                    missing_count += 1
                    details.append(f"{skill_name}: references {ref} → SKILL DIR NOT FOUND")
                    continue

                ref_skill_md = ref_path / "SKILL.md"
                if not ref_skill_md.exists():
                    missing_count += 1
                    details.append(f"{skill_name}: references {ref} → SKILL.MD MISSING")
                    continue

                # Check required frontmatter
                try:
                    ref_content = ref_skill_md.read_text(encoding="utf-8")
                    ref_fm_match = re.match(r"^---\s*\n(.*?)\n---", ref_content, re.DOTALL)
                    if ref_fm_match:
                        ref_fm_text = ref_fm_match.group(1)
                        missing_fields = []
                        for field in ["name", "description", "enforcement"]:
                            if not re.search(rf"^{field}:", ref_fm_text, re.MULTILINE):
                                missing_fields.append(field)
                        if missing_fields:
                            details.append(f"{skill_name}: {ref} SKILL.md missing {missing_fields}")
                except (OSError, UnicodeDecodeError):
                    pass

    status = "warning" if missing_count > 0 else "healthy"
    message = (
        f"{missing_count} invalid dependency reference(s)"
        if missing_count > 0
        else "All skill dependencies valid"
    )

    return CheckResult(
        name="skill_deps",
        status=status,
        message=message,
        details=details[:20],
        duration_ms=int((time.time() - start) * 1000),
    )


def apply_fixes(checks: list[CheckResult], dry_run: bool = False) -> list[str]:
    """Apply safe auto-fixes for detected issues."""
    fixed = []

    for check in checks:
        for fix in check.fixable:
            action = fix["action"]
            target = Path(fix["target"])

            if action == "truncate" and target.exists():
                if dry_run:
                    fixed.append(f"[DRY-RUN] Would truncate: {target}")
                else:
                    try:
                        # Size-based rotation: keep ~80% of threshold (8MB)
                        target_size_mb = target.stat().st_size / (1024 * 1024)
                        if target_size_mb > 10:
                            lines = target.read_text(errors="ignore").splitlines()
                            # Estimate line size and keep ~8MB worth
                            avg_line_size = sum(len(line) for line in lines[:100]) / min(
                                100, len(lines)
                            )
                            max_lines = int((8 * 1024 * 1024) / avg_line_size)
                            if max_lines < len(lines):
                                truncated = "\n".join(lines[-max_lines:]) + "\n"
                                target.write_text(truncated)
                                fixed.append(
                                    f"Rotated: {target} ({target_size_mb:.1f}MB → {max_lines} lines)"
                                )
                    except Exception as e:
                        fixed.append(f"Failed to truncate {target}: {e}")

            elif action == "delete":
                # SECURITY: Validate path stays within safe project boundaries before deletion
                safe_roots = [str(PROJECT_ROOT.resolve()), str(CLAUDE_DIR.resolve())]
                resolved = target.resolve()
                if not any(str(resolved).startswith(root) for root in safe_roots):
                    fixed.append(f"BLOCKED: Path {target} outside safe directory")
                    continue
                if target.exists():
                    if dry_run:
                        fixed.append(f"[DRY-RUN] Would delete: {target}")
                    else:
                        try:
                            target.unlink()
                            fixed.append(f"Deleted: {target}")
                        except Exception as e:
                            fixed.append(f"Failed to delete {target}: {e}")

    return fixed


def upgrade_packages(
    safe_only: bool = True,
    major_bumps: bool = False,
    dry_run: bool = False,
    limit: int | None = None,
) -> list[str]:
    """Upgrade outdated packages selectively.

    Args:
        safe_only: Only upgrade minor/patch versions (default: True)
        major_bumps: Include major version upgrades (default: False)
        dry_run: Show what would be upgraded without doing it
        limit: Max number of packages to upgrade (None = all)

    Returns:
        List of upgrade results
    """
    results = []
    safe_to_upgrade, major_bump_list, key_packages = get_outdated_packages()

    # Build package list based on options
    packages_to_upgrade = []

    if safe_only:
        # Only safe minor/patch updates
        packages_to_upgrade = safe_to_upgrade[:limit]
    elif major_bumps:
        # Everything including major bumps
        packages_to_upgrade = (safe_to_upgrade + major_bump_list + key_packages)[:limit]
    else:
        # Safe + key packages (but not other major bumps)
        packages_to_upgrade = (safe_to_upgrade + key_packages)[:limit]

    if not packages_to_upgrade:
        results.append("No packages to upgrade")
        return results

    # Build pip upgrade command
    package_names = [p["name"] for p in packages_to_upgrade]

    if dry_run:
        results.append(f"[DRY-RUN] Would upgrade {len(package_names)} package(s):")
        for p in packages_to_upgrade[:10]:
            results.append(f"  • {p['name']}: {p['version']} → {p['latest']}")
        if len(packages_to_upgrade) > 10:
            results.append(f"  ... and {len(packages_to_upgrade) - 10} more")
        return results

    # Perform upgrade
    try:
        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", *package_names]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

        # Parse output to show what actually upgraded
        for line in result.stdout.splitlines():
            if "Successfully installed" in line:
                results.append(f"✓ {line.strip()}")
            elif "Requirement already satisfied" in line:
                results.append(f"⊘ {line.strip()}")

        if result.returncode == 0:
            results.append(f"Upgraded {len(package_names)} package(s)")
        else:
            results.append(f"Some upgrades failed: {result.stderr.strip()[:200]}")

    except subprocess.TimeoutExpired:
        results.append("Upgrade timed out (>300s)")
    except Exception as e:
        results.append(f"Upgrade error: {e}")

    return results


def calculate_score(checks: list[CheckResult]) -> int:
    """Calculate overall health score (0-100)."""
    if not checks:
        return 100

    weights = {"healthy": 100, "warning": 60, "critical": 0}

    total = sum(weights.get(c.status, 50) for c in checks)
    return int(total / len(checks))


def save_history(report: HealthReport) -> None:
    """Append health report to history file."""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": report.timestamp,
        "score": report.score,
        "status": report.overall_status,
        "checks": {c.name: c.status for c in report.checks},
    }

    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def load_history(limit: int = 20) -> list[dict]:
    """Load recent health history entries."""
    if not HISTORY_FILE.exists():
        return []

    entries = []
    with open(HISTORY_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return entries[-limit:]


def show_history() -> None:
    """Display health score trend."""
    entries = load_history(20)

    if not entries:
        print("No health history recorded yet.")
        return

    print("📊 Health Score Trend (last 20 checks)")
    print("=" * 50)

    for entry in entries:
        ts = entry["timestamp"][:16].replace("T", " ")
        score = entry["score"]
        status = entry["status"]

        # Simple ASCII bar
        bar_len = score // 5
        bar = "█" * bar_len + "░" * (20 - bar_len)

        status_icon = "✅" if status == "healthy" else "⚠️" if status == "warning" else "❌"
        print(f"{ts} │ {bar} │ {score:3d}% {status_icon}")

    # Trend analysis
    if len(entries) >= 3:
        recent = entries[-3:]
        avg_recent = sum(e["score"] for e in recent) / 3
        older = entries[:-3] if len(entries) > 3 else entries[:1]
        avg_older = sum(e["score"] for e in older) / len(older)

        if avg_recent > avg_older + 5:
            print("\n📈 Trend: Improving")
        elif avg_recent < avg_older - 5:
            print("\n📉 Trend: Degrading")
        else:
            print("\n➡️  Trend: Stable")


def run_fap_layer_stats_check() -> CheckResult:
    """Report FAP detection layer hit rates (regex vs semantic)."""
    stats_file = CLAUDE_DIR / "hooks" / "logs" / "fap_layer_stats.json"
    if not stats_file.exists():
        return CheckResult(
            name="fap_layers",
            status="healthy",
            message="FAP layer stats: no data yet",
        )
    try:
        stats = json.loads(stats_file.read_text(encoding="utf-8"))
        regex_hits = stats.get("layer1_regex_hit", 0)
        semantic_hits = stats.get("layer2_semantic_hit", 0)
        semantic_misses = stats.get("layer2_semantic_miss", 0)
        total = regex_hits + semantic_hits
        parts = [f"regex={regex_hits}", f"semantic={semantic_hits}"]
        if semantic_misses:
            parts.append(f"semantic_miss={semantic_misses}")
        msg = f"FAP triggers ({total} total): {', '.join(parts)}"
        if semantic_hits == 0 and regex_hits > 20:
            msg += " — semantic layer has never triggered, consider removing"
            return CheckResult(name="fap_layers", status="warning", message=msg)
        return CheckResult(name="fap_layers", status="healthy", message=msg)
    except Exception as e:
        return CheckResult(
            name="fap_layers",
            status="warning",
            message=f"FAP layer stats: read error: {e}",
        )


def run_env_changes_check() -> CheckResult:
    """Check for environment variable changes in settings.json.

    Compares current env vars against stored snapshot from last run.
    Reports any additions, deletions, or value changes.
    """
    import hashlib

    start = time.time()
    settings_path = CLAUDE_DIR / "settings.json"

    if not settings_path.exists():
        return CheckResult(
            name="env_changes",
            status="warning",
            message="settings.json not found",
            duration_ms=int((time.time() - start) * 1000),
        )

    try:
        # Load current settings
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        current_env = settings.get("env", {})

        # Sort env vars for consistent comparison
        sorted_env = dict(sorted(current_env.items()))

        # Calculate hash of current env vars
        env_json = json.dumps(sorted_env, sort_keys=True)
        current_hash = hashlib.sha256(env_json.encode()).hexdigest()

        # Load previous state
        previous_state = {}
        if ENV_STATE_FILE.exists():
            try:
                previous_state = json.loads(ENV_STATE_FILE.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass

        previous_hash = previous_state.get("env_hash", "")
        previous_env = previous_state.get("env_vars", {})

        # Save current state for next run (SEC-002: atomic write via temp file)
        ENV_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _state_data = {
            "env_hash": current_hash,
            "env_vars": sorted_env,
            "timestamp": datetime.now().isoformat(),
        }
        # Write to temp file then rename — atomic on POSIX, reduces corruption risk on Windows
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", dir=ENV_STATE_FILE.parent, delete=False, encoding="utf-8"
        ) as _tmp:
            _tmp.write(json.dumps(_state_data))
            _tmp_path = Path(_tmp.name)
        _tmp_path.replace(ENV_STATE_FILE)

        duration_ms = int((time.time() - start) * 1000)

        # No previous state - first run
        if not previous_hash:
            return CheckResult(
                name="env_changes",
                status="healthy",
                message=f"Baseline recorded ({len(sorted_env)} env vars)",
                duration_ms=duration_ms,
            )

        # Hash unchanged - no changes
        if current_hash == previous_hash:
            return CheckResult(
                name="env_changes",
                status="healthy",
                message=f"No changes ({len(sorted_env)} env vars)",
                duration_ms=duration_ms,
            )

        # Detect changes
        changes = []

        # Added variables
        added = set(sorted_env.keys()) - set(previous_env.keys())
        if added:
            changes.append(f"Added: {', '.join(sorted(added))}")

        # Removed variables
        removed = set(previous_env.keys()) - set(sorted_env.keys())
        if removed:
            changes.append(f"Removed: {', '.join(sorted(removed))}")

        # Changed values
        changed = []
        for key in sorted_env.keys() & previous_env.keys():
            if sorted_env[key] != previous_env[key]:
                old_val = str(previous_env[key])[:30]
                new_val = str(sorted_env[key])[:30]
                changed.append(f"{key}: {old_val} → {new_val}")

        if changed:
            changes.append(f"Changed: {', '.join(changed[:5])}")
            if len(changed) > 5:
                changes.append(f"  ... and {len(changed) - 5} more")

        return CheckResult(
            name="env_changes",
            status="warning",
            message=f"{len(added) + len(removed) + len(changed)} env var(s) changed",
            details=changes,
            duration_ms=duration_ms,
        )

    except Exception as e:
        return CheckResult(
            name="env_changes",
            status="warning",
            message=f"Error: {e}",
            duration_ms=int((time.time() - start) * 1000),
        )


def get_outdated_packages() -> tuple[list[dict], list[dict], list[dict]]:
    """Get outdated packages categorized by safety.

    Returns:
        (safe_to_upgrade, major_bumps, key_packages)
        - safe_to_upgrade: Minor/patch version updates (low risk)
        - major_bumps: Major version changes (high risk, review needed)
        - key_packages: Critical packages that need attention
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--outdated", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

        if result.returncode != 0:
            return [], [], []

        try:
            packages = json.loads(result.stdout)
        except json.JSONDecodeError:
            return [], [], []

        safe_to_upgrade = []
        major_bumps = []
        key_packages = []

        key_package_names = {
            "anthropic",
            "pytest",
            "black",
            "ruff",
            "pip",
            "uv",
            "fastapi",
            "openai",
            "langchain",
            "transformers",
            "django",
            "flask",
            "requests",
            "numpy",
            "pandas",
        }

        for p in packages:
            name = p.get("name", "unknown")
            version = p.get("version", "?")
            latest = p.get("latest_version", "?")

            # Check for major version bump
            try:
                current_major = int(version.split(".")[0].lstrip("v"))
                latest_major = int(latest.split(".")[0].lstrip("v"))
                is_major_bump = current_major < latest_major
            except (ValueError, IndexError):
                is_major_bump = False

            entry = {
                "name": name,
                "version": version,
                "latest": latest,
                "is_major": is_major_bump,
                "is_key": name.lower() in key_package_names,
            }

            if is_major_bump:
                major_bumps.append(entry)
            elif name.lower() in key_package_names:
                key_packages.append(entry)
            else:
                safe_to_upgrade.append(entry)

        return safe_to_upgrade, major_bumps, key_packages

    except (subprocess.TimeoutExpired, Exception):
        return [], [], []


def run_outdated_packages_check() -> CheckResult:
    """Check for outdated packages using pip list --outdated."""
    start = time.time()
    details = []

    try:
        safe_to_upgrade, major_bumps, key_packages = get_outdated_packages()
        all_packages = safe_to_upgrade + major_bumps + key_packages

        duration_ms = int((time.time() - start) * 1000)

        if not all_packages:
            return CheckResult(
                name="outdated_packages",
                status="healthy",
                message="All packages up to date",
                duration_ms=duration_ms,
            )

        # Build details list - show most important updates first
        priority_details = []
        other_details = []

        for p in major_bumps + key_packages:
            entry = f"{p['name']}: {p['version']} \u2192 {p['latest']}"
            if p.get("is_major"):
                entry += " [MAJOR]"
            priority_details.append(entry)

        for p in safe_to_upgrade:
            entry = f"{p['name']}: {p['version']} \u2192 {p['latest']}"
            other_details.append(entry)

        # Combine: priority first, then others (limit total)
        details = priority_details + other_details[:15]

        if len(other_details) > 15:
            details.append(f"... and {len(other_details) - 15} more")

        # Count major bumps for severity
        major_count = len(major_bumps)
        status = (
            "critical" if major_count > 5 else "warning" if len(all_packages) > 10 else "warning"
        )

        return CheckResult(
            name="outdated_packages",
            status=status,
            message=f"{len(all_packages)} outdated package(s) ({major_count} major version bumps)",
            details=details,
            duration_ms=duration_ms,
        )

    except Exception as e:
        return CheckResult(
            name="outdated_packages",
            status="warning",
            message=f"Error: {e}",
            duration_ms=int((time.time() - start) * 1000),
        )


def run_all_checks(
    quick: bool = False,
    include_deps: bool = False,
    skip_cve: bool = False,
    include_outdated: bool = False,
) -> list[CheckResult]:
    """Run all health checks."""
    checks = []

    # Core checks (always run)
    core_checks = [
        ("settings", TOOLS_DIR / "settings_health_check.py"),
        ("hooks", TOOLS_DIR / "hook_health_check.py"),
        ("workspace", TOOLS_DIR / "workspace_state_check.py"),
    ]

    # Hook syntax check (fast, always run) - catches corrupted hooks early
    checks.append(run_hook_syntax_check())

    # Hook stats reminder (fast, always run) - surfaces diagnostics DB activity
    checks.append(run_hook_stats_check())

    # Env changes check (fast, always run) - detects settings.json env var changes
    checks.append(run_env_changes_check())

    # FAP layer stats (fast, always run) - tracks regex vs semantic hit rates
    checks.append(run_fap_layer_stats_check())

    # Slow checks (skip in quick mode)
    slow_checks = [
        ("cks", CLAUDE_DIR / "skills" / "cks" / "scripts" / "cks_health_check.py"),
        ("skills", TOOLS_DIR / "skill_collision_check.py"),
        (
            "skill_quality",
            TOOLS_DIR / "health_check.py",
        ),  # SKILL.md frontmatter, line count, TODO/FIXME
        (
            "competence",
            TOOLS_DIR / "competence_health_check.py",
        ),  # Competence Layer
    ]

    for name, script in core_checks:
        checks.append(run_check(name, script))

    # PERF-001: Parallelize non-core checks with overall timeout budget
    # Core checks (~1s) run first sequentially; all others run in parallel
    pending: list[tuple[str, Callable[[], CheckResult]]] = []

    if not quick:
        for name, script in slow_checks:
            pending.append((name, lambda s=script, n=name: run_check(n, s)))
        pending.append(("filesystem", lambda: run_filesystem_check()))
        pending.append(("spec_drift", lambda: run_spec_drift_check()))
        pending.append(("skill_deps", lambda: run_skill_dependency_check()))

    if include_deps:
        pending.append(("deps", lambda: run_dependency_audit()))
    if not skip_cve:
        pending.append(("cve", lambda: run_cve_remediation_check()))
    if include_outdated:
        pending.append(("outdated", lambda: run_outdated_packages_check()))

    if pending:
        overall_timeout = 120  # overall budget in seconds
        per_check_timeout = max(10, overall_timeout // len(pending))  # fair share, min 10s
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(func): name for name, func in pending}
            try:
                for future in as_completed(futures, timeout=overall_timeout):
                    name = futures[future]
                    try:
                        checks.append(future.result(timeout=per_check_timeout))
                    except Exception as e:
                        checks.append(CheckResult(
                            name=name, status="warning",
                            message=f"Check failed or timed out: {e}",
                        ))
            except TimeoutError:
                # Budget exceeded — remaining checks get warning result
                for name, _ in pending:
                    if not any(c.name == name for c in checks):
                        checks.append(CheckResult(
                            name=name, status="warning",
                            message=f"Check skipped: overall timeout budget ({overall_timeout}s) exceeded",
                        ))

    return checks


def main():
    parser = argparse.ArgumentParser(description="Unified /main health check")
    parser.add_argument("--quick", action="store_true", help="Skip slow checks")
    parser.add_argument("--fix", action="store_true", help="Auto-fix safe issues")
    parser.add_argument("--dry-run", action="store_true", help="Show what --fix would do")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--deps", action="store_true", help="Include dependency audit")
    parser.add_argument("--outdated", action="store_true", help="Check for outdated packages")
    parser.add_argument("--skip-cve", action="store_true", help="Skip CVE remediation check")
    parser.add_argument("--quiet", action="store_true", help="Just pass/fail status")
    parser.add_argument("--history", action="store_true", help="Show health score trend")
    parser.add_argument(
        "--upgrade", action="store_true", help="Upgrade outdated packages (safe minor/patch only)"
    )
    parser.add_argument(
        "--upgrade-all", action="store_true", help="Upgrade all packages including major versions"
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Limit number of packages to upgrade"
    )
    parser.add_argument(
        "--suggest", action="store_true", help="Show skill suggestions at end of run"
    )
    parser.add_argument(
        "--acknowledge",
        action="store_true",
        help="Mark current sizes as baseline - suppresses future warnings until regression",
    )
    args = parser.parse_args()

    # Upgrade mode - skip checks, just do upgrade
    if args.upgrade or args.upgrade_all:
        results = upgrade_packages(
            safe_only=not args.upgrade_all,
            major_bumps=args.upgrade_all,
            dry_run=args.dry_run,
            limit=args.limit,
        )
        print("\n📦 PACKAGE UPGRADE:")
        for r in results:
            print(f"   {r}")
        return 0

    # History mode
    if args.history:
        show_history()
        return 0

    # Cleanup mode - run cleanup.py --dry-run directly, skip all other checks
    cleanup_script = SKILLS_DIR / "cleanup" / "scripts" / "cleanup.py"
    if cleanup_script.exists():
        result = subprocess.run(
            [sys.executable, str(cleanup_script), "--dry-run"],
            capture_output=False,
            timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        return result.returncode

    start = time.time()

    # Load baseline for size tracking
    baseline = load_baseline()

    # Run checks
    checks = run_all_checks(
        quick=args.quick,
        include_deps=args.deps,
        skip_cve=args.skip_cve,
        include_outdated=args.outdated,
    )

    # Apply baseline comparison to suppress duplicate warnings for stable sizes
    checks = _apply_baseline(checks, baseline)

    # Calculate score and status
    score = calculate_score(checks)
    if score >= 80:
        overall_status = "healthy"
    elif score >= 50:
        overall_status = "warning"
    else:
        overall_status = "critical"

    duration_ms = int((time.time() - start) * 1000)

    report = HealthReport(
        timestamp=datetime.now().isoformat(),
        overall_status=overall_status,
        score=score,
        checks=checks,
        duration_ms=duration_ms,
    )

    # Save to history
    save_history(report)

    # Handle acknowledge flag - mark current sizes as baseline
    if args.acknowledge:
        # Re-run size extraction on the (possibly fixed) checks
        for check in checks:
            if check.name == "hooks":
                size = _extract_size_from_details(check.details, "Log dir:")
                if size is not None:
                    baseline.hook_log_size_mb = size
            elif check.name == "cks":
                size = _extract_size_from_details(check.details, "Database size:")
                if size is not None:
                    baseline.cks_size_mb = size
        save_baseline(baseline, updated_by="acknowledge")
        print("\n✅ Acknowledged current sizes as baseline:")
        if baseline.hook_log_size_mb is not None:
            print(f"   Hook logs: {baseline.hook_log_size_mb:.1f}MB")
        if baseline.cks_size_mb is not None:
            print(f"   CKS db: {baseline.cks_size_mb:.1f}MB")

    # Apply fixes if requested
    fixed = []
    if args.fix or args.dry_run:
        fixed = apply_fixes(checks, dry_run=args.dry_run)

    # Output
    if args.json:
        output = {
            "timestamp": report.timestamp,
            "overall_status": report.overall_status,
            "score": report.score,
            "duration_ms": report.duration_ms,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status,
                    "message": c.message,
                    "details": c.details,
                    "fixable": c.fixable,
                    "duration_ms": c.duration_ms,
                    "suggestions": c.suggestions,
                }
                for c in checks
            ],
            "fixed": fixed,
        }
        print(json.dumps(output, indent=2))

    elif args.quiet:
        status_icon = (
            "✅" if overall_status == "healthy" else "⚠️" if overall_status == "warning" else "❌"
        )
        print(f"{status_icon} Health: {score}% ({overall_status})")

    else:
        # Full output
        status_icon = (
            "✅" if overall_status == "healthy" else "⚠️" if overall_status == "warning" else "❌"
        )
        print(f"\n{status_icon} SYSTEM HEALTH: {score}% ({overall_status}) [{duration_ms}ms]")
        print("=" * 60)

        for check in checks:
            check_icon = (
                "✅" if check.status == "healthy" else "⚠️" if check.status == "warning" else "❌"
            )
            print(f"\n{check_icon} {check.name.upper()} [{check.duration_ms}ms]")
            print(f"   {check.message}")

            # Show critical/warning details
            # Special case: always show worktree details for workspace check
            # Special case: always show outdated packages (arrow → format)
            is_workspace_with_worktrees = (
                check.name == "workspace"
                and check.details
                and any("•" in d and (": refs/" in d or ": detached" in d) for d in check.details)
            )
            is_outdated_packages = check.name == "outdated_packages"

            if check.status != "healthy" or is_workspace_with_worktrees or is_outdated_packages:
                for detail in check.details[:10]:  # Show more for outdated packages
                    # For outdated packages, all details are relevant (no bullet filtering)
                    if is_outdated_packages:
                        print(f"   • {detail}")
                    elif "•" in detail or "❌" in detail or "⚠️" in detail:
                        print(f"   {detail}")

            # Show fixable issues
            if check.fixable:
                print(f"   🔧 Fixable: {len(check.fixable)} issue(s)")

            # Show skill suggestions inline
            if check.suggestions and check.status != "healthy":
                for suggestion in check.suggestions[:3]:
                    print(f"   💡 Run {suggestion}")

        if fixed:
            print("\n🔧 FIXES APPLIED:")
            for f in fixed:
                print(f"   {f}")

        # Show fix hint if issues found and not already fixed
        total_fixable = sum(len(c.fixable) for c in checks)
        if total_fixable > 0 and not args.fix:
            print(f"\n💡 Run with --fix to auto-remediate {total_fixable} issue(s)")
            print("   Or --dry-run to preview fixes")

        # Show upgrade hint if outdated packages found
        outdated_check = next((c for c in checks if c.name == "outdated_packages"), None)
        if (
            outdated_check
            and outdated_check.status != "healthy"
            and not (args.upgrade or args.upgrade_all)
        ):
            safe_to_upgrade, major_bumps, _key_packages = get_outdated_packages()
            safe_count = len(safe_to_upgrade)
            major_count = len(major_bumps)

            print(f"\n📦 {safe_count} safe upgrade(s) available (minor/patch versions)")
            if major_count > 0:
                print(f"   ⚠️  {major_count} major version bump(s) - review before upgrading")
            print("   💡 Run with --upgrade to apply safe upgrades")
            print("      Or --upgrade-all to include major versions")
            print("      Use --dry-run first to preview changes")

        # Show skill suggestion summary when --suggest is used
        if args.suggest:
            all_findings: list[HealthFinding] = []
            for check in checks:
                all_findings.extend(_check_to_findings(check))

            if all_findings:
                print("\n" + "=" * 60)
                print("💡 SKILL SUGGESTIONS")
                print("=" * 60)

                # Group by skill
                by_skill: dict[str, list[HealthFinding]] = {}
                for finding in all_findings:
                    if finding.suggested_skill not in by_skill:
                        by_skill[finding.suggested_skill] = []
                    by_skill[finding.suggested_skill].append(finding)

                for skill, skill_findings in sorted(by_skill.items()):
                    print(f"\n{skill}")
                    for finding in skill_findings:
                        print(
                            f"   [{finding.status.upper()}] {finding.check_name}: "
                            f"{finding.rationale}"
                        )

                print(
                    f"\nTotal: {len(all_findings)} suggestion(s) across "
                    f"{len(by_skill)} skill(s)"
                )

    # Exit code
    if overall_status == "critical":
        return 2
    elif overall_status == "warning":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
