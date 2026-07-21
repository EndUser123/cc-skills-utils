"""End-to-end smoke test: runs `qmd search` and asserts >=1 result with score > 0.1.

Slow (~5-15s for sentence-transformers model load on cold cache).
Marked ``@pytest.mark.slow`` so the default ``pytest`` run stays <1s. Run with::

    pytest tests/test_qmd_search_smoke.py -v -m slow

This complements ``test_qmd_patches_applied.py`` (which checks the patch is
*present* in source). The smoke test checks the patch *works* — that the
LLM backend actually loads and vector search returns scored results.

Skip conditions:
- If ``~/.config/qmd/qmd.db`` does not exist or has 0 active wiki documents,
  the test skips (cannot meaningfully assert result counts on an empty DB).

Source: /design run 10d616f8 (2026-07-20).
See P:/.data/wiki/concepts/qmd-patch-durability-strategy.md.
"""
import json
import sqlite3
import subprocess
from pathlib import Path

import pytest


QMD_DB = Path.home() / ".config" / "qmd" / "qmd.db"


def _wiki_db_has_documents() -> bool:
    """Return True if the wiki DB exists and has >=1 active wiki document."""
    if not QMD_DB.exists():
        return False
    try:
        conn = sqlite3.connect(str(QMD_DB))
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE collection = 'wiki' AND active = 1"
            ).fetchone()[0]
        finally:
            conn.close()
        return count > 0
    except sqlite3.Error:
        return False


@pytest.mark.slow
@pytest.mark.skipif(
    not _wiki_db_has_documents(),
    reason=(
        "wiki DB empty or unreadable — smoke test requires indexed content; "
        "run `qmd update` and `qmd embed --collection wiki` first"
    ),
)
def test_qmd_search_returns_semantic_results():
    """qmd search against the wiki corpus must return >=1 result with score > 0.1.

    A failing assertion here means semantic search is broken end-to-end —
    either the LLM backend patch is missing (run test_qmd_patches_applied.py
    to confirm) or the wiki DB embeddings are stale (run
    `qmd embed --collection wiki --force`).
    """
    proc = subprocess.run(
        [
            "qmd", "search",
            "--collection", "wiki",
            "--limit", "5",
            "--format", "json",
            "wiki",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, (
        f"qmd search exited {proc.returncode}: stderr={proc.stderr!r}"
    )

    # Parse JSON output. Skip any non-JSON prefix (loguru may emit INFO lines
    # to stdout in some configurations; the wiki_after_write caller already
    # tolerates this via out.find('[')).
    out = proc.stdout
    idx = out.find("[")
    assert idx >= 0, (
        f"no JSON array marker '[' in stdout (first 200 chars): {out[:200]!r}"
    )
    try:
        results = json.loads(out[idx:])
    except json.JSONDecodeError as e:
        pytest.fail(
            f"could not parse qmd search JSON output: {e}. "
            f"First 200 chars after '[': {out[idx:idx+200]!r}"
        )

    assert len(results) > 0, (
        "expected >=1 search result for query 'wiki' against the wiki collection; "
        "got 0. Either the DB is empty (skipif should have caught this), the "
        "query doesn't match any indexed content, or semantic search is broken."
    )

    max_score = max((r.get("score", 0) for r in results), default=0)
    assert max_score > 0.1, (
        f"all result scores <= 0.1 (max={max_score:.3f}). Embeddings may not be "
        f"queried — check that qmd_cli_main.patch is applied. Top 3: "
        f"{results[:3]}"
    )
