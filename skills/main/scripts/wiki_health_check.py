#!/usr/bin/env python3
"""Wiki vault health check + safe-repair engine for /main and /wiki lint.

Single source of truth for wiki diagnostics. Three modes share one engine:

  default (no args)  Graph checks (broken links, orphans, duplicate slugs,
                     missing frontmatter) + staleness scan. Text output with
                     ❌/⚠️ markers parsed by run_check() in main_health.py.
                     Back-compat: prints the same shape the existing probe did.
  --fix [--dry-run]  Apply ONLY safe deterministic repairs: fuzzy-match a
                     broken wikilink to a unique existing slug at >=0.9
                     confidence (single candidate, no ambiguity). Never prunes
                     orphans or red-links — wiki policy keeps speculative links.
  --stale            List stale pages (mtime older than --max-age days), newest
                     first, capped by --limit. Used by /wiki update.
  --json             Structured output (any mode).

Judgment-based lint (contradictions, stale claims, orphan merge) stays in the
/wiki lint LLM prose layer; this script is pure graph analysis + safe repair.

Output contract for default text mode: lines containing "❌"/"critical" ->
critical status, "⚠️"/"warning" -> warning, else healthy. Parsed by run_check().
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from difflib import SequenceMatcher
from pathlib import Path

VAULT_ENV = "WIKI_VAULT"
DEFAULT_VAULT = Path("P:/.data/wiki")
REQUIRED_FRONTMATTER = ("title",)
NON_CONTENT_STEMS = {"index", "log"}
LINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")
BAD_LINK_CHARS = set('"$`()*=<>|&;!#')

DEFAULT_MAX_AGE_DAYS = 90
DEFAULT_STALE_LIMIT = 20
# ponytail: strict single-candidate cutoff. Ambiguous matches (>=2 candidates
# above cutoff) skip — "intelligent" means don't guess when unclear.
FUZZY_CUTOFF = 0.9


def _is_real_link_target(target: str) -> bool:
    if not target.strip():
        return False
    if any(c in target for c in BAD_LINK_CHARS):
        return False
    return True


def _strip_type_suffix(target: str) -> str:
    return target.split("@", 1)[0].strip()


def _normalize_target(target: str) -> str:
    target = target.split("|", 1)[0].strip()
    target = target.rsplit("/", 1)[-1].strip()
    return _strip_type_suffix(target)


def _parse_frontmatter(text: str) -> dict[str, str]:
    fm: dict[str, str] = {}
    if not text.startswith("---"):
        return fm
    end = text.find("\n---", 3)
    if end == -1:
        return fm
    for line in text[3:end].splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip().lower()] = val.strip().strip('"').strip("'")
    return fm


def _slugify(target: str) -> str:
    """Lowercase kebab slug for fuzzy-match comparison against page stems."""
    return re.sub(r"[^a-z0-9]+", "-", target.lower()).strip("-")


def run_check(vault: Path, max_age_days: int = DEFAULT_MAX_AGE_DAYS) -> dict:
    """Run all graph + staleness checks. Returns structured result dict.

    Pure read-only analysis — no mutations. Shared by every output mode.
    """
    if not vault.is_dir():
        return {"vault": str(vault), "exists": False, "pages": [], "broken": [],
                "orphans": [], "duplicate_stems": [], "missing_frontmatter": [],
                "stale": [], "n_pages": 0, "n_content": 0, "orphan_ratio": 0.0}

    md_files = list(vault.rglob("*.md"))
    pages: dict[str, Path] = {}
    duplicate_stems: list[str] = []
    frontmatter: dict[str, dict[str, str]] = {}
    mtimes: dict[str, float] = {}
    for path in md_files:
        stem = path.stem
        if stem in pages:
            duplicate_stems.append(stem)
            continue
        pages[stem] = path
        try:
            frontmatter[stem] = _parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
            mtimes[stem] = path.stat().st_mtime
        except OSError:
            frontmatter[stem] = {}
            mtimes[stem] = 0.0

    outbound: dict[str, set[str]] = {stem: set() for stem in pages}
    inbound: dict[str, int] = {stem: 0 for stem in pages}
    broken: list[tuple[str, str]] = []  # (source_stem, normalized_target)
    broken_raw: list[tuple[str, str]] = []  # (source_stem, raw_link_text) for repair
    for stem, path in pages.items():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for raw in LINK_RE.findall(text):
            if not _is_real_link_target(raw):
                continue
            target = _normalize_target(raw)
            if not target:
                continue
            outbound[stem].add(target)
            if target in pages:
                inbound[target] += 1
            else:
                broken.append((stem, target))
                broken_raw.append((stem, raw))

    orphans = sorted(
        s for s in pages
        if s not in NON_CONTENT_STEMS and inbound[s] == 0
    )
    missing_fm = sorted(
        s for s, fm in frontmatter.items()
        if s not in NON_CONTENT_STEMS
        and not all(k in fm for k in REQUIRED_FRONTMATTER)
    )

    n_pages = len(pages)
    non_content_present = NON_CONTENT_STEMS & set(pages)
    n_content = max(1, n_pages - len(non_content_present))
    orphan_ratio = len(orphans) / n_content

    # Staleness: mtime is authoritative per wiki architecture doc.
    now = time.time()
    age_threshold = max_age_days * 86400
    stale: list[tuple[str, int]] = []  # (stem, age_days)
    for stem, mtime in mtimes.items():
        if stem in NON_CONTENT_STEMS or mtime <= 0:
            continue
        age_s = now - mtime
        if age_s >= age_threshold:
            stale.append((stem, int(age_s // 86400)))
    stale.sort(key=lambda x: -x[1])  # oldest first

    return {
        "vault": str(vault),
        "exists": True,
        "pages": sorted(pages),
        "page_paths": {s: str(pages[s]) for s in pages},
        "broken": broken,
        "broken_raw": broken_raw,
        "orphans": orphans,
        "duplicate_stems": sorted(set(duplicate_stems)),
        "missing_frontmatter": missing_fm,
        "stale": stale,
        "n_pages": n_pages,
        "n_content": n_content,
        "orphan_ratio": orphan_ratio,
        "frontmatter": frontmatter,
    }


def _unique_fuzzy_match(target: str, candidates: list[str], cutoff: float = FUZZY_CUTOFF) -> str | None:
    """Return the single candidate >= cutoff, or None if zero or ambiguous.

    Ambiguous (>=2 candidates above cutoff) returns None — we don't guess.
    Comparison is on slugified lowercase forms so [[Hooks Guide]] ~ hooks-guide.
    """
    t = _slugify(target)
    if not t:
        return None
    matches: list[tuple[float, str]] = []
    for cand in candidates:
        ratio = SequenceMatcher(None, t, _slugify(cand)).ratio()
        if ratio >= cutoff:
            matches.append((ratio, cand))
    if len(matches) == 1:
        return matches[0][1]
    return None


def vault_fingerprint(vault: Path) -> str:
    """Stable hash of vault mtime state. Changes on any edit/add/delete.

    Used by /main's needs-based gate: if the fingerprint matches the last
    fix attempt, no new work exists -> skip. Time-based throttles miss new
    broken links; this misses nothing.
    """
    if not vault.exists():
        return "missing"
    h = hashlib.md5()  # ponytail: not security, just a stable digest
    files = sorted(vault.rglob("*.md"))
    h.update(str(len(files)).encode())
    for f in files:
        try:
            st = f.stat()
        except OSError:
            continue
        h.update(f"{f.relative_to(vault)}|{int(st.st_mtime)}|{st.st_size}".encode())
    return h.hexdigest()


def apply_safe_fixes(vault: Path, dry_run: bool = False) -> list[str]:
    """Repair broken wikilinks via unique fuzzy match. Returns human-readable log lines.

    Conservative: only rewrites a broken link when exactly one existing page
    slug matches at >=0.9. Ambiguous or unmatched links are left untouched
    (speculative red-links are intentional per wiki policy).
    """
    result = run_check(vault)
    if not result["exists"]:
        return [f"Vault not found: {vault}"]

    candidates = result["pages"]
    fixes: list[str] = []
    # Group broken links by source page so we rewrite each file once.
    by_source: dict[str, list[tuple[str, str]]] = {}
    for (src, target), (src2, raw) in zip(result["broken"], result["broken_raw"]):
        match = _unique_fuzzy_match(target, candidates)
        if not match:
            continue
        by_source.setdefault(src, []).append((raw, match))
        fixes.append(f"{'[DRY-RUN] ' if dry_run else ''}{src}: [[{target}]] -> [[{match}]]")

    if dry_run or not by_source:
        return fixes

    for src, rewrites in by_source.items():
        path = Path(result["page_paths"][src])
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            fixes.append(f"FAILED read {src}: {e}")
            continue
        for raw, match in rewrites:
            # Preserve display text and type suffix: [[Target|Disp]]@type -> [[match|Disp]]@type
            display = ""
            if "|" in raw:
                display = "|" + raw.split("|", 1)[1]
            type_suffix = ""
            if "@" in raw:
                type_suffix = "@" + raw.split("@", 1)[1]
            new_link = f"[[{match}{display}{type_suffix}]]"
            text = text.replace(f"[[{raw}]]", new_link, 1)
        try:
            path.write_text(text, encoding="utf-8")
        except OSError as e:
            fixes.append(f"FAILED write {src}: {e}")
    return fixes


def _emit_text(result: dict, max_age_days: int) -> int:
    """Print default text-mode report. Returns exit code (always 0 — see docstring)."""
    if not result["exists"]:
        print(f"⚠️ Wiki vault not found: {result['vault']} (set {VAULT_ENV} to override)")
        return 0

    n_pages = result["n_pages"]
    n_content = result["n_content"]
    orphan_ratio = result["orphan_ratio"]
    broken = result["broken"]
    orphans = result["orphans"]
    duplicate_stems = result["duplicate_stems"]
    missing_fm = result["missing_frontmatter"]
    stale = result["stale"]

    issues: list[str] = []
    if broken:
        issues.append(f"{len(broken)} broken wikilink(s)")
    if orphan_ratio > 0.5:
        issues.append(f"{len(orphans)} orphan page(s) ({orphan_ratio:.0%} of vault)")
    if duplicate_stems:
        issues.append(f"{len(duplicate_stems)} duplicate slug(s)")
    if len(missing_fm) / n_content > 0.25:
        issues.append(f"{len(missing_fm)} page(s) missing required frontmatter")
    if stale:
        oldest = stale[0][1] if stale else 0
        issues.append(f"{len(stale)} stale page(s) (>{max_age_days}d, oldest {oldest}d)")

    if issues:
        print(f"⚠️ Wiki vault: {'; '.join(issues)} — {n_pages} pages in {result['vault']}")
    else:
        print(f"✅ Wiki vault healthy ({n_pages} pages, {len(broken)} broken links, "
              f"{len(orphans)} orphans, {len(stale)} stale)")

    for src, tgt in broken[:15]:
        print(f"• [[{tgt}]] from {src}")
    if len(broken) > 15:
        print(f"• ... and {len(broken) - 15} more broken link(s)")
    for s in orphans[:10]:
        print(f"• orphan: {s}")
    if len(orphans) > 10:
        print(f"• ... and {len(orphans) - 10} more orphan(s)")
    if stale:
        print(f"Run: /wiki update  ({len(stale)} stale page(s) >{max_age_days}d — refresh via subagents)")
    return 0


def _emit_stale(result: dict, limit: int) -> int:
    stale = result["stale"][:limit]
    if not result["exists"]:
        print(f"⚠️ Wiki vault not found: {result['vault']}")
        return 0
    print(f"Stale pages ({len(stale)} of {len(result['stale'])} shown, oldest first):")
    for stem, age in stale:
        print(f"{age}d\t{stem}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Wiki vault health check + safe repair")
    parser.add_argument("--vault", type=Path, default=None, help=f"Vault dir (default: $[{VAULT_ENV}] or {DEFAULT_VAULT})")
    parser.add_argument("--json", action="store_true", help="Structured JSON output")
    parser.add_argument("--fix", action="store_true", help="Apply safe deterministic repairs (fuzzy-match broken links)")
    parser.add_argument("--dry-run", action="store_true", help="With --fix: preview without writing")
    parser.add_argument("--stale", action="store_true", help="List stale pages (oldest first)")
    parser.add_argument("--max-age", type=int, default=DEFAULT_MAX_AGE_DAYS, help=f"Staleness threshold in days (default {DEFAULT_MAX_AGE_DAYS})")
    parser.add_argument("--limit", type=int, default=DEFAULT_STALE_LIMIT, help=f"Cap on stale list / fix candidates (default {DEFAULT_STALE_LIMIT})")
    parser.add_argument("--fingerprint", action="store_true", help="Print vault mtime fingerprint (needs-based gate signal for /main)")
    args = parser.parse_args()

    vault = args.vault or Path(os.environ.get(VAULT_ENV, str(DEFAULT_VAULT)))

    if args.fingerprint:
        print(vault_fingerprint(vault))
        return 0

    if args.fix:
        fixes = apply_safe_fixes(vault, dry_run=args.dry_run)
        if args.json:
            print(json.dumps({"fixes": fixes, "dry_run": args.dry_run}, indent=2))
        else:
            print(f"Wiki safe-fix {'(dry-run)' if args.dry_run else 'applied'}: {len(fixes)} repair(s)")
            for line in fixes:
                print(f"• {line}")
        return 0

    result = run_check(vault, max_age_days=args.max_age)

    if args.stale:
        if args.json:
            print(json.dumps({"stale": [{"stem": s, "age_days": a} for s, a in result["stale"][:args.limit]],
                              "total_stale": len(result["stale"])}, indent=2))
        else:
            _emit_stale(result, args.limit)
        return 0

    if args.json:
        payload = {k: v for k, v in result.items() if k != "frontmatter"}
        payload["stale"] = [{"stem": s, "age_days": a} for s, a in result["stale"]]
        print(json.dumps(payload, indent=2))
        return 0

    return _emit_text(result, args.max_age)


if __name__ == "__main__":
    sys.exit(main())
