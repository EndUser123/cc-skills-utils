"""Unit, regression, integration, and smoke tests for main_review.

Run with:
    pytest P:/packages/.claude-marketplace/plugins/cc-skills-utils/skills/main-review/scripts/tests/test_main_review.py -v
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import main_review as mr  # noqa: E402
from main_review import (  # noqa: E402
    Config,
    Finding,
    TranscriptEvent,
    analyze_promotions,
    collect_error_signatures,
    detect_gate_health,
    detect_history_regressions,
    detect_negative_existence,
    detect_receipt_mismatches,
    detect_regression_candidates,
    detect_unsupported_claims,
    extract_matches,
    finalize,
    parse_transcript,
    report_to_dict,
    run,
)


# ── Unit: verdict pattern coverage + FP guard ────────────────────────────────
@pytest.mark.parametrize("text", [
    "Root Cause: missing env",
    "The fix is to add the import",
    "This works because the cache is warm",
    "Confirmed working now.",
    "Verified.",
    "Fixed.\n",
    "Resolved:",
    "Done.\n",
])
def test_verdict_patterns_hit(text):
    assert extract_matches(text, mr.VERDICT_PATTERNS), f"no match for: {text!r}"


@pytest.mark.parametrize("text", [
    "I verified the path exists and is readable.",          # no trailing punct anchor
    "We fixed it together last week.",                       # "fixed it" not anchored
    "Please confirm working as expected when you can.",     # not anchored
    "The cause is a missing env var.",                       # "cause" not "Root Cause"
])
def test_verdict_patterns_no_fp_on_benign(text):
    assert extract_matches(text, mr.VERDICT_PATTERNS) == [], f"unexpected match: {text!r}"


# ── Unit: negative-existence pattern coverage ────────────────────────────────
@pytest.mark.parametrize("text", [
    "the helper is unused",
    "those functions are unused",
    "no consumers call into it",
    "no callers remain",
    "no references to this module",
    "this attribute is never called",
    "the file doesn't exist on disk",
    "the module does not exist",
    "it is not used anywhere",
])
def test_negative_existence_patterns_hit(text):
    assert extract_matches(text, mr.NEGATIVE_EXISTENCE_PATTERNS), f"no match: {text!r}"


# ── Unit: detect_unsupported_claims ──────────────────────────────────────────
def _ev(kind: str, text: str = "", tools=None, results=None, idx: int = 0):
    return TranscriptEvent(
        kind=kind,
        text=text,
        tool_uses=list(tools or []),
        tool_results=list(results or []),
        index=idx,
    )


def test_unsupported_claim_fires_when_no_tool_in_window():
    events = [
        _ev("user", "what broke?"),
        _ev("assistant", "Root Cause: the env var was unset. Fixed.", idx=1),
    ]
    findings = detect_unsupported_claims(events, "transcript:t.jsonl", lookback=6)
    assert len(findings) >= 1
    f = findings[0]
    assert f.severity == "high"
    assert f.category == "claims"
    assert f.source_refs == ["transcript:t.jsonl#entry1"]
    assert "Root Cause" in f.evidence[0]


def test_unsupported_claim_does_not_fire_when_tool_present():
    events = [
        _ev("assistant", "checking env...", tools=["Bash"], idx=0),
        _ev("assistant", "Root Cause: env unset.", idx=1),
    ]
    findings = detect_unsupported_claims(events, "transcript:t.jsonl", lookback=6)
    assert findings == []


# ── Regression: reproduces the failure class (mirror of rca_iron_law) ────────
def test_regression_unsupported_root_cause_with_hedge_is_caught():
    """A 'Root Cause' verdict with hedging (likely) and no tool receipt MUST fire."""
    events = [
        _ev("user", "why did the deploy fail?"),
        _ev("assistant", "Root Cause: it is probably the env var (likely).", idx=1),
    ]
    findings = detect_unsupported_claims(events, "transcript:deploy.jsonl", lookback=6)
    assert findings, "verdict-without-receipt regression: must fire even when hedged"
    assert findings[0].severity == "high"


# ── Unit: detect_negative_existence ──────────────────────────────────────────
def test_negative_existence_fires_without_search_tool():
    events = [
        _ev("assistant", "the helper is unused, removing it.", idx=0, tools=["Bash"]),
    ]
    findings = detect_negative_existence(events, "transcript:t.jsonl", lookback=6)
    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert findings[0].category == "claims"


def test_negative_existence_silent_when_grep_was_used():
    events = [
        _ev("assistant", "checking for references...", tools=["Grep"], idx=0),
        _ev("assistant", "the helper is unused, removing it.", idx=1),
    ]
    findings = detect_negative_existence(events, "transcript:t.jsonl", lookback=6)
    assert findings == []


# ── Unit: detect_receipt_mismatches (highest confidence) ─────────────────────
def test_receipt_mismatch_fires_on_traceback_before_verdict():
    events = [
        _ev("assistant", "trying to import foo", tools=["Bash"], idx=0),
        _ev("user", results=["Traceback (most recent call last): ModuleNotFoundError: no foo"], idx=1),
        _ev("assistant", "Confirmed working now.", idx=2),
    ]
    findings = detect_receipt_mismatches(events, "transcript:t.jsonl", lookback=6)
    assert len(findings) == 1
    f = findings[0]
    assert f.severity == "critical"
    assert f.category == "receipts"
    assert "Traceback" in f.evidence[1] or "ModuleNotFoundError" in f.evidence[1]


# ── Unit: parse_transcript + collect_error_signatures ────────────────────────
def test_parse_transcript_extracts_tools_and_results(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join([
        json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text": "Root Cause: foo"},
            {"type": "tool_use", "name": "Grep"},
        ]}}),
        json.dumps({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "content": "Traceback (most recent call last):\n  ModuleNotFoundError: foo"},
        ]}}),
    ]), encoding="utf-8")
    events = parse_transcript(p)
    assert len(events) == 2
    assert events[0].tool_uses == ["Grep"]
    assert "Traceback" in events[1].tool_results[0]
    sigs = collect_error_signatures(events)
    assert any("ModuleNotFoundError" in s for s in sigs)


# ── Unit: detect_gate_health ─────────────────────────────────────────────────
def test_gate_health_inert_when_registered_but_not_invoked():
    findings = detect_gate_health(rows=[], registered={"ghost.py"})
    assert any("ghost.py" in f.title and f.severity == "medium" for f in findings)


def test_gate_health_fail_open_when_gate_class_never_blocks():
    rows = [{"hook": "rca_gate", "action": "allow"}] * 6
    findings = detect_gate_health(rows, registered=set())
    f = next((x for x in findings if "never blocks" in x.title), None)
    assert f is not None
    assert f.severity == "high"


def test_gate_health_error_dominated_hook():
    rows = [{"hook": "broken", "action": "error"}] * 6
    findings = detect_gate_health(rows, registered=set())
    f = next((x for x in findings if "error-dominated" in x.title), None)
    assert f is not None
    assert f.severity == "high"


# ── Unit: regression candidates ──────────────────────────────────────────────
def test_regression_candidate_only_when_recurrence_met():
    sigs = {"t1": ["sigA"], "t2": ["sigA"], "t3": ["sigA"]}
    findings = detect_regression_candidates(sigs, recurrence=3)
    assert findings and findings[0].severity == "high"
    assert findings[0].proposed_test


def test_history_regressions_detect_flapping_check():
    history = [{"checks": {"cks": "healthy"}}, {"checks": {"cks": "critical"}},
               {"checks": {"cks": "healthy"}}, {"checks": {"cks": "critical"}}]
    findings = detect_history_regressions(history, recurrence=2)
    assert any("cks" in f.title for f in findings)


# ── Unit: promotion requires recurrence ──────────────────────────────────────
def test_promotion_requires_distinct_sources():
    f1 = Finding(
        id="MR-0001", severity="high", category="claims",
        title="Confident verdict without a supporting tool receipt",
        evidence=["verdict phrase: x"], confidence=0.8,
        source_refs=["transcript:a.jsonl#entry1"],
        recommended_action="x",
    )
    f2 = Finding(
        id="MR-0002", severity="high", category="claims",
        title="Confident verdict without a supporting tool receipt",
        evidence=["verdict phrase: y"], confidence=0.8,
        source_refs=["transcript:a.jsonl#entry5"],  # same source
        recommended_action="x",
    )
    findings = analyze_promotions([f1, f2], Config(promotion_recurrence=2))
    assert findings == []
    f3 = Finding(
        id="MR-0003", severity="high", category="claims",
        title="Confident verdict without a supporting tool receipt",
        evidence=["verdict phrase: z"], confidence=0.8,
        source_refs=["transcript:b.jsonl#entry1"],
        recommended_action="x",
    )
    findings = analyze_promotions([f1, f2, f3], Config(promotion_recurrence=2))
    assert any(x.promotion_ready and "verdict-without-receipt" in x.title for x in findings)


# ── Unit: Finding round-trip + finalize severity guard ───────────────────────
def test_finding_round_trip_all_required_keys():
    f = Finding(
        id="MR-X", severity="high", category="claims",
        title="t", evidence=["e"], confidence=0.7,
        source_refs=["ref"], recommended_action="a",
        promotion_ready=True, proposed_test="T", proposed_runtime_gate="G",
    )
    d = f.to_dict()
    assert all(k in d for k in (
        "id", "severity", "category", "title", "evidence", "confidence",
        "source_refs", "recommended_action", "rationale", "promotion_ready",
        "proposed_test", "proposed_runtime_gate",
    ))
    assert Finding.from_dict(d) == f


def test_finalize_downgrades_critical_without_evidence():
    f = Finding(id="X", severity="critical", category="claims",
                title="t", evidence=[], confidence=0.9,
                source_refs=["ref"], recommended_action="a")
    out = finalize([f])
    assert out[0].severity == "high"
    assert "downgraded" in out[0].rationale


# ── Integration: run() over a synthetic telemetry root ───────────────────────
def test_run_synthetic_fixture_produces_eight_required_sections(tmp_path):
    cfg = mr.build_self_test_root(tmp_path)
    report = run(cfg)
    d = report_to_dict(report)
    for k in ("scope", "summary", "findings", "unsupported_claims",
              "gate_health_findings", "regression_candidates",
              "promotion_candidates", "recommended_actions"):
        assert k in d, f"missing section: {k}"
    assert report.scope["transcripts_scanned"] == 2
    assert report.scope["diagnostics_rows"] >= 12
    sevs = {f.severity for f in report.findings}
    assert "critical" in sevs, "fixture must produce at least one critical finding"
    cats = {f.category for f in report.findings}
    for c in ("claims", "gates", "receipts", "regression", "promotion"):
        assert c in cats, f"fixture missing category: {c}"


# ── Integration: defensive gatherers (missing source => info, not crash) ─────
def test_run_with_no_sources_emits_info_and_does_not_crash(tmp_path):
    cfg = Config(
        since_days=30,
        transcripts_root=tmp_path / "no-such-transcripts",
        diagnostics_db=tmp_path / "no-such-db.sqlite",
        health_history=tmp_path / "no-such-history.jsonl",
        registered_hooks_roots=[tmp_path / "no-such-hooks-root"],
        history_file=tmp_path / "review_history.jsonl",
        save_history=False,
    )
    report = run(cfg)
    assert report.findings, "missing sources should yield at least info notes"
    assert all(f.severity in ("info",) for f in report.findings)


# ── Smoke: --self-test exits nonzero and JSON is valid ───────────────────────
def test_self_test_cli_returns_nonzero_with_valid_json():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "main_review.py"),
         "--self-test", "--json", "--no-history"],
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 2, (proc.returncode, proc.stdout, proc.stderr)
    payload = json.loads(proc.stdout)
    assert payload["summary"]["by_severity"]["critical"] >= 1
    for k in ("scope", "summary", "findings", "unsupported_claims",
              "gate_health_findings", "regression_candidates",
              "promotion_candidates", "recommended_actions"):
        assert k in payload