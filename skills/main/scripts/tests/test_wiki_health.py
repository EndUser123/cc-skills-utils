# test_wiki_health.py — Tests for the wiki diagnostic + safe-repair engine
"""Run with: pytest P:/packages/.claude-marketplace/plugins/cc-skills-utils/skills/main/scripts/tests/test_wiki_health.py -v

Covers four modes of wiki_health_check.py: check (graph + staleness), --fix
(safe fuzzy-match repair, no orphan/red-link deletion), --stale, --json.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import wiki_health_check as w  # noqa: E402


# --- Fixtures ---

@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """Minimal vault: one target page + one source page with a broken link."""
    v = tmp_path / "wiki"
    v.mkdir()
    (v / "hook-architecture.md").write_text(
        "---\ntitle: Hook Architecture\n---\nbody\n", encoding="utf-8"
    )
    # Source with three links: fuzzy-fixable, unknown (red-link), exact-match
    (v / "source.md").write_text(
        "---\ntitle: Source\n---\n"
        "See [[Hook Architecture]] and [[Unknown Page]] here.\n",
        encoding="utf-8",
    )
    return v


@pytest.fixture
def stale_vault(tmp_path: Path) -> Path:
    v = tmp_path / "wiki"
    v.mkdir()
    (v / "fresh.md").write_text("---\ntitle: Fresh\n---\nbody\n", encoding="utf-8")
    (v / "old.md").write_text("---\ntitle: Old\n---\nbody\n", encoding="utf-8")
    old = time.time() - 100 * 86400  # 100d old
    import os
    os.utime(v / "old.md", (old, old))
    return v


# --- run_check (graph) ---

def test_run_check_detects_broken_link(vault: Path):
    r = w.run_check(vault)
    targets = {t for _, t in r["broken"]}
    assert "Hook Architecture" in targets  # case-mismatch → broken
    assert "Unknown Page" in targets        # genuinely missing
    assert r["n_pages"] == 2


def test_run_check_detects_orphans(vault: Path):
    r = w.run_check(vault)
    # Both pages have zero inbound (the only outbound is to a missing target).
    assert "hook-architecture" in r["orphans"]
    assert "source" in r["orphans"]


def test_run_check_detects_duplicate_stems(tmp_path: Path):
    v = tmp_path / "wiki"
    (v / "concepts").mkdir(parents=True)
    (v / "concepts" / "dup.md").write_text("---\ntitle: Dup\n---\nx\n", encoding="utf-8")
    (v / "sessions").mkdir(parents=True)
    (v / "sessions" / "dup.md").write_text("---\ntitle: Dup2\n---\ny\n", encoding="utf-8")
    r = w.run_check(v)
    assert "dup" in r["duplicate_stems"]


def test_run_check_missing_vault(tmp_path: Path):
    r = w.run_check(tmp_path / "nonexistent")
    assert r["exists"] is False
    assert r["n_pages"] == 0


# --- Staleness ---

def test_stale_detection(stale_vault: Path):
    r = w.run_check(stale_vault, max_age_days=90)
    stale_stems = {s for s, _ in r["stale"]}
    assert "old" in stale_stems
    assert "fresh" not in stale_stems
    # age in days ≈ 100
    age_by_stem = dict(r["stale"])
    assert age_by_stem["old"] >= 99


def test_stale_default_threshold_excludes_recent(stale_vault: Path):
    # With default 90d threshold, only 'old' qualifies.
    r = w.run_check(stale_vault, max_age_days=w.DEFAULT_MAX_AGE_DAYS)
    assert len(r["stale"]) == 1


# --- Safe fix (fuzzy match) ---

def test_fix_repairs_unique_fuzzy_match(vault: Path):
    fixes = w.apply_safe_fixes(vault, dry_run=False)
    assert any("Hook Architecture" in f and "hook-architecture" in f for f in fixes)
    # File now contains the lowercased slug; broken count drops.
    text = (vault / "source.md").read_text(encoding="utf-8")
    assert "[[hook-architecture]]" in text
    # 'Unknown Page' must NOT have been touched (no candidate).
    assert "[[Unknown Page]]" in text


def test_fix_dry_run_does_not_write(vault: Path):
    before = (vault / "source.md").read_text(encoding="utf-8")
    fixes = w.apply_safe_fixes(vault, dry_run=True)
    after = (vault / "source.md").read_text(encoding="utf-8")
    assert before == after
    assert any("[DRY-RUN]" in f for f in fixes)


def test_fix_skips_ambiguous_match(tmp_path: Path):
    """Two candidate slugs both ≥ cutoff → no rewrite (ambiguous)."""
    v = tmp_path / "wiki"
    v.mkdir()
    (v / "hook-architecture.md").write_text("---\ntitle: A\n---\nx\n", encoding="utf-8")
    (v / "hook-architectures.md").write_text("---\ntitle: B\n---\nx\n", encoding="utf-8")
    (v / "src.md").write_text("---\ntitle: S\n---\n[[Hook Architecture]]\n", encoding="utf-8")
    fixes = w.apply_safe_fixes(v, dry_run=False)
    # Ambiguous → no fix line for this target.
    assert not any("Hook Architecture" in f for f in fixes)


def test_fix_never_deletes_orphans_or_redlinks(vault: Path):
    """Policy guard: orphan pages and unknown red-links must survive --fix."""
    files_before = {p.name for p in vault.rglob("*.md")}
    w.apply_safe_fixes(vault, dry_run=False)
    files_after = {p.name for p in vault.rglob("*.md")}
    assert files_before == files_after  # no deletions
    text = (vault / "source.md").read_text(encoding="utf-8")
    assert "[[Unknown Page]]" in text  # red-link preserved


# --- Fuzzy match helper ---

def test_unique_fuzzy_match_exact_after_slugify():
    m = w._unique_fuzzy_match("Hook Architecture", ["hook-architecture", "other"])
    assert m == "hook-architecture"


def test_unique_fuzzy_match_rejects_low_confidence():
    m = w._unique_fuzzy_match("Totally Different", ["hook-architecture"])
    assert m is None


# --- Needs-based gate signal ---

def test_vault_fingerprint_stable_when_unchanged(vault: Path):
    a = w.vault_fingerprint(vault)
    b = w.vault_fingerprint(vault)
    assert a == b
    assert a != "missing"


def test_vault_fingerprint_changes_on_edit(vault: Path):
    import os, time as _time
    before = w.vault_fingerprint(vault)
    # Bump mtime of a page by writing + setting mtime to be safe on coarse-grained FSes.
    (vault / "hook-architecture.md").write_text(
        "---\ntitle: Hook Architecture\n---\nbody v2\n", encoding="utf-8"
    )
    future = _time.time() + 60
    os.utime(vault / "hook-architecture.md", (future, future))
    after = w.vault_fingerprint(vault)
    assert before != after


def test_vault_fingerprint_missing_vault(tmp_path: Path):
    assert w.vault_fingerprint(tmp_path / "nope") == "missing"


# --- JSON / stale CLI smoke (subprocess) ---

def test_cli_json_shape(vault: Path):
    import subprocess, json
    r = subprocess.run(
        [sys.executable, str(Path(w.__file__).resolve()), "--vault", str(vault), "--json"],
        capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 0
    payload = json.loads(r.stdout)
    for key in ("broken", "orphans", "duplicate_stems", "stale", "n_pages"):
        assert key in payload


def test_cli_stale_mode(stale_vault: Path):
    import subprocess
    r = subprocess.run(
        [sys.executable, str(Path(w.__file__).resolve()), "--vault", str(stale_vault),
         "--stale", "--max-age", "90"],
        capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 0
    assert "old" in r.stdout
    assert "fresh" not in r.stdout
