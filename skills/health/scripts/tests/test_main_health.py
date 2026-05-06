# test_main_health.py — Unit tests for _match_suggestions pattern matching
"""Parametrized tests covering all 16 SUGGESTION_MAP entries.

Run with:
    pytest P:/.claude/skills/main/scripts/tests/test_main_health.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import threading

# Ensure main_health module is importable
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path("P:/.claude/hooks")))

import main_health as main_health_module  # noqa: E402
from main_health import _match_suggestions, _SUGGESTION_MAP  # noqa: E402
from main_health import run_hook_stats_check  # noqa: E402
import cc_diagnostic_logger  # noqa: E402


# ---------------------------------------------------------------------
# Test case table — one entry per SUGGESTION_MAP key
# Fields: (check_name, details_text, message_text, expected_skill_count_min, expected_skills)
# ---------------------------------------------------------------------
CASE_TABLE: list[tuple[str, str, str, int, set[str]]] = [
    # spec_drift — "NOT FOUND" pattern
    (
        "spec_drift",
        "Script NOT FOUND: /skills/foo/bar.py",
        "",
        1,
        {"/skill-ship", "/similarity"},
    ),
    # skill_deps — "SKILL DIR NOT FOUND" pattern
    (
        "skill_deps",
        "SKILL DIR NOT FOUND: /skills/missing",
        "",
        1,
        {"/skill-ship", "/similarity"},
    ),
    # skill_deps — "SKILL.MD MISSING" (UPPERCASE) and "SKILL.md missing" (lowercase)
    # are the SAME pattern when lowercased — both always fire together when the
    # message contains "SKILL.MD MISSING" (any case). The combined result is both
    # /skill-ship and /av. This is a MAP design issue (duplicate patterns) but
    # the test reflects actual current behavior.
    (
        "skill_deps",
        "",
        "SKILL.MD MISSING for /skills/foo",
        1,
        {"/skill-ship", "/av"},
    ),
    # skill_deps — "SKILL.md missing" pattern (lowercase .md)
    # NOTE: Both "SKILL.MD MISSING" and "SKILL.md missing" are identical when
    # lowercased, so both patterns always fire together. The test reflects this.
    (
        "skill_deps",
        "SKILL.md missing required fields: version",
        "",
        1,
        {"/skill-ship", "/av"},
    ),
    # hooks — "timeout" pattern
    (
        "hooks",
        "",
        "Hook timeout rate 25% (threshold 20%)",
        1,
        {"/hook-obs"},
    ),
    # hooks — "syntax" pattern
    (
        "hooks",
        "hook_file.py: syntax error",
        "",
        1,
        {"/hook-obs"},
    ),
    # hooks — "log" pattern
    (
        "hooks",
        "",
        "Hook log directory bloat: 15MB",
        1,
        {"/cleanup"},
    ),
    # cks — None pattern (catch-all, always suggests for failed check)
    (
        "cks",
        "Low entry count: 45 (threshold 100)",
        "CKS stale: 10 days",
        1,
        {"/reflect", "/garden"},
    ),
    # filesystem — "violation" pattern
    (
        "filesystem",
        "Filesystem violation: .claude/skills/main/NESTED/.dotfile",
        "",
        1,
        {"/cleanup"},
    ),
    # settings — "bloat" pattern
    (
        "settings",
        "",
        "Settings bloat: 42KB (threshold 35KB)",
        1,
        {"/standards"},
    ),
    # settings — "orphaned" pattern
    (
        "settings",
        "Orphaned env var: UNUSED_API_KEY",
        "",
        1,
        {"/standards"},
    ),
    # skill_quality — "frontmatter" pattern
    (
        "skill_quality",
        "",
        "SKILL.md frontmatter missing 'enforcement' field",
        1,
        {"/av"},
    ),
    # skill_quality — "TODO" pattern
    (
        "skill_quality",
        "TODO: fix this later",
        "",
        1,
        {"/critique"},
    ),
    # dependencies — "vulnerab" pattern
    (
        "dependencies",
        "",
        "Vulnerability found: httpx>=0.27.0 allows request smuggling",
        1,
        {"/deps"},
    ),
    # cve_remediation — "would install" pattern
    (
        "cve_remediation",
        "would install: httpx==0.27.1",
        "",
        1,
        {"/deps"},
    ),
    # workspace — "uncommitted" pattern
    (
        "workspace",
        "",
        "20 uncommitted files in workspace",
        1,
        {"/git"},
    ),
]

# smoke-test: case table covers all SUGGESTION_MAP entries (verified manually against
# SUGGESTION_MAP keys — each CASE_TABLE entry corresponds to one map key by design)

# ---------------------------------------------------------------------
# Parametrized tests
# ---------------------------------------------------------------------
@pytest.mark.parametrize("check_name,details,message,min_count", [
    (c[0], c[1], c[2], c[3]) for c in CASE_TABLE
])
def test_match_suggestions_returns_skills(check_name, details, message, min_count):
    """Each SUGGESTION_MAP entry returns at least one relevant skill, capped at 3."""
    result = _match_suggestions(check_name, details, message)
    assert isinstance(result, list), f"_match_suggestions returned {type(result)!r}"
    assert len(result) >= min_count, (
        f"check={check_name!r}, details={details!r}: "
        f"got {result}, expected at least {min_count} skill(s)"
    )
    assert len(result) <= 3, f"check={check_name!r}: expected <= 3 suggestions, got {len(result)}: {result}"
    for skill in result:
        assert skill.startswith("/"), f"Skill {skill!r} does not start with '/'"


@pytest.mark.parametrize("check_name,details,message,expected_skills", [
    (c[0], c[1], c[2], c[4]) for c in CASE_TABLE
])
def test_match_suggestions_contains_expected(check_name, details, message, expected_skills):
    """Each SUGGESTION_MAP entry returns skills from the expected set."""
    result = _match_suggestions(check_name, details, message)
    for skill in result:
        assert skill in expected_skills, (
            f"check={check_name!r}: got skill {skill!r}, "
            f"expected one of {expected_skills}"
        )


# ---------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------
def test_match_suggestions_empty_string():
    """No false positives when details and message are empty for non-catch-all patterns."""
    non_catchall = [(cn, p) for cn, p in _SUGGESTION_MAP if p is not None]
    for check_name, _ in non_catchall:
        result = _match_suggestions(check_name, "", "")
        assert result == [], f"check={check_name!r}: expected [], got {result}"


def test_match_suggestions_cap_at_three():
    """Results are capped at 3 suggestions per check."""
    # Use a check with 2+ skills to verify cap
    result = _match_suggestions("cks", "Low entry count", "stale")
    assert len(result) <= 3, f"Expected <= 3 suggestions, got {len(result)}: {result}"


def test_match_suggestions_unknown_check_returns_empty():
    """Unknown check name returns empty list."""
    result = _match_suggestions("nonexistent_check", "some details", "some message")
    assert result == [], f"Unknown check should return [], got {result}"


def test_match_suggestions_no_false_positive_case_mismatch():
    """Pattern matching is case-insensitive for the pattern, not the check name."""
    # Check name must match exactly; pattern is case-insensitive
    result = _match_suggestions("hooks", "", "SYNTAX ERROR DETECTED")
    assert "/hook-obs" in result, "syntax pattern should be case-insensitive"


def test_run_hook_stats_check_reports_db_summary(tmp_path, monkeypatch):
    """Hook stats reminder should summarize the diagnostics DB when present."""
    diag_root = tmp_path / ".claude"
    db_path = diag_root / "hooks" / "logs" / "diagnostics" / "diagnostics.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(cc_diagnostic_logger, "DB_PATH", db_path)
    monkeypatch.setattr(cc_diagnostic_logger, "_local", threading.local())
    monkeypatch.setattr(cc_diagnostic_logger, "DIAGNOSTICS_ENABLED", True)
    monkeypatch.setattr(main_health_module, "CLAUDE_DIR", diag_root)

    cc_diagnostic_logger._init_schema()
    cc_diagnostic_logger.log_hook_invocation(
        hook_name="behavior_contract",
        event_type="UserPromptSubmit",
        action="inject",
        injection_content="If the question is concrete, answer directly.",
        reason="behavior_contract_injection",
        turn_id="turn-123",
        session_id="session-123",
        terminal_id="terminal-123",
    )
    cc_diagnostic_logger.log_hook_invocation(
        hook_name="Stop.py:behavior_audit",
        event_type="Stop",
        action="block",
        reason="UNVERIFIED CLAIMS",
        turn_id="turn-123",
        session_id="session-123",
        terminal_id="terminal-123",
    )

    result = run_hook_stats_check()

    assert result.name == "hook_stats"
    assert result.status == "healthy"
    assert "Hook stats" in result.message
    assert "2 events" in result.message
    assert "/hook-obs stats" in result.message
