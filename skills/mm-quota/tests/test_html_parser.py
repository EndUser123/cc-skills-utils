"""Tests for _layer1b_parse_html — uses the saved Usage.html as a fixture.

The fixture is a real copy of C:\\Users\\brsth\\Downloads\\Usage.html captured
on 2026-06-06. Asserting against its exact values catches both parser
regressions and silent DOM changes in MiniMax's console.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "Usage.html"
sys.path.insert(0, str(SCRIPTS))

import mm_quota  # noqa: E402


pytestmark = pytest.mark.skipif(
    not FIXTURE.exists(),
    reason=f"Usage.html fixture not present at {FIXTURE}",
)


# --- Happy path: real saved page --------------------------------------------


def test_parse_real_snapshot_succeeds():
    """Saved Usage.html must parse to source=html_snapshot, not skipped."""
    result = mm_quota._layer1b_parse_html(FIXTURE)
    assert result["source"] == "html_snapshot", (
        f"expected html_snapshot, got {result.get('source')!r} with reason: {result.get('reason')!r}"
    )
    assert result["reason"] == ""


def test_parse_real_snapshot_5h_window():
    """The page shows 89% used with 'Resets in 57 min' as of fixture capture."""
    result = mm_quota._layer1b_parse_html(FIXTURE)
    assert result["five_hour_pct"] == 89
    assert "Resets in" in (result["five_hour_reset"] or "")
    assert "min" in (result["five_hour_reset"] or "")


def test_parse_real_snapshot_weekly_is_unlimited():
    """Weekly limit is unlimited on the Plus plan."""
    result = mm_quota._layer1b_parse_html(FIXTURE)
    assert result["weekly"] == "Unlimited"


def test_parse_real_snapshot_monthly_total_quota():
    """Total quota row shows 100% (the monthly allotment is intact)."""
    result = mm_quota._layer1b_parse_html(FIXTURE)
    assert result["monthly"] is not None
    assert "100%" in result["monthly"]


def test_parse_real_snapshot_yesterday_tokens():
    """Yesterday's tokens stat is present (value-then-label DOM order)."""
    result = mm_quota._layer1b_parse_html(FIXTURE)
    assert result["yesterday_tokens"] is not None


def test_parse_real_snapshot_week_tokens():
    """Last 7 days stat is present."""
    result = mm_quota._layer1b_parse_html(FIXTURE)
    assert result["week_tokens"] is not None


def test_parse_real_snapshot_month_tokens():
    """Last 30 days stat is present."""
    result = mm_quota._layer1b_parse_html(FIXTURE)
    assert result["month_tokens"] is not None


def test_parse_real_snapshot_total_tokens():
    """Total tokens stat is present (separate stat card)."""
    result = mm_quota._layer1b_parse_html(FIXTURE)
    assert result["total_tokens"] is not None


# --- Failure paths ------------------------------------------------------------


def test_parse_missing_file_returns_skipped(tmp_path):
    """Nonexistent path → source='skipped', reason explains why, no exception."""
    missing = tmp_path / "does_not_exist.html"
    result = mm_quota._layer1b_parse_html(missing)
    assert result["source"] == "skipped"
    assert "not found" in result["reason"].lower()
    assert result["five_hour_pct"] is None
    assert result["weekly"] is None


def test_parse_empty_file_returns_skipped(tmp_path):
    """Empty HTML file → source='skipped', no crash."""
    empty = tmp_path / "empty.html"
    empty.write_text("", encoding="utf-8")
    result = mm_quota._layer1b_parse_html(empty)
    assert result["source"] == "skipped"
    assert result["reason"] != ""


def test_parse_garbage_file_returns_skipped(tmp_path):
    """HTML with no usage data → source='skipped', no crash."""
    garbage = tmp_path / "garbage.html"
    garbage.write_text("<html><body>not the usage page</body></html>", encoding="utf-8")
    result = mm_quota._layer1b_parse_html(garbage)
    assert result["source"] == "skipped"
    assert result["five_hour_pct"] is None
    assert result["yesterday_tokens"] is None


# --- Output format integration ------------------------------------------------


def test_format_output_with_html_snapshot_source():
    """When layer1 source is html_snapshot, output reflects that, not 'console scrape'."""
    layer1 = {
        "source": "html_snapshot",
        "five_hour_pct": 89,
        "five_hour_reset": "Resets in 57 min",
        "weekly": "Unlimited",
        "monthly": "Total quota 100%",
        "yesterday_tokens": "114.63M",
        "week_tokens": "1.16B",
        "month_tokens": "4.61B",
        "total_tokens": "24.38B",
    }
    layer3 = {"source": "probe_only", "input": 0, "output": 0}
    fallback = mm_quota._layer2_fallback_block()

    out = mm_quota._format_output(layer1, layer3, fallback)
    assert "89% used" in out
    assert "Resets in 57 min" in out
    assert "Unlimited" in out
    assert "Source: local HTML snapshot" in out
    assert "console scrape" not in out
    assert "114.63M" in out
    assert "1.16B" in out
    assert "4.61B" in out
    assert "24.38B" in out
    assert "Fallback: open" not in out
