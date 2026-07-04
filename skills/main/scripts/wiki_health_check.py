#!/usr/bin/env python3
"""Wiki vault health check for /main.

Deterministic subset of /wiki lint:
  - broken [[wikilinks]] (target page not present in vault)
  - orphan pages (zero inbound links, excluding index.md / log.md)
  - pages missing required frontmatter (title)

Judgment-based lint (contradictions, stale claims) stays in /wiki lint; this
check is pure graph analysis and runs in the always-on /main probe.

Output contract: lines containing "❌"/"critical" -> critical status,
"⚠️"/"warning" -> warning, else healthy. Parsed by run_check() in main_health.py.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

VAULT_ENV = "WIKI_VAULT"
DEFAULT_VAULT = Path("P:/.data/wiki")
REQUIRED_FRONTMATTER = ("title",)
# index.md and log.md are structural, not concept pages — never count as orphans
# and should not themselves be required to have inbound links.
NON_CONTENT_STEMS = {"index", "log"}
# A real wikilink target is a slug: letters/digits/spaces/dash/underscore/slash/@.
# Reject bash test expressions like [[ "$OS" == "Darwin" ]] and anything with
# quotes, $, backticks, ==, or parens.
LINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")
BAD_LINK_CHARS = set('"$`()*=<>|&;!#')


def _is_real_link_target(target: str) -> bool:
    if not target.strip():
        return False
    if any(c in target for c in BAD_LINK_CHARS):
        return False
    return True


def _strip_type_suffix(target: str) -> str:
    # [[Page]]@supports -> Page
    return target.split("@", 1)[0].strip()


def _normalize_target(target: str) -> str:
    # Links may use display text ([[Page|Display]]) or subpaths ([[dir/Page]]).
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


def main() -> int:
    vault = Path(os.environ.get(VAULT_ENV, str(DEFAULT_VAULT)))
    if not vault.is_dir():
        print(f"⚠️ Wiki vault not found: {vault} (set {VAULT_ENV} to override)")
        return 0

    md_files = list(vault.rglob("*.md"))
    if not md_files:
        print(f"⚠️ Wiki vault has no .md pages: {vault}")
        return 0

    # stem -> path (first occurrence wins; duplicates reported separately)
    pages: dict[str, Path] = {}
    duplicate_stems: list[str] = []
    frontmatter: dict[str, dict[str, str]] = {}
    for path in md_files:
        stem = path.stem
        if stem in pages:
            duplicate_stems.append(stem)
            continue
        pages[stem] = path
        try:
            frontmatter[stem] = _parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            frontmatter[stem] = {}

    # Extract outbound + count inbound links
    outbound: dict[str, set[str]] = {stem: set() for stem in pages}
    inbound: dict[str, int] = {stem: 0 for stem in pages}
    broken: list[tuple[str, str]] = []  # (source_stem, target)
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

    # Orphans: content pages with zero inbound links. Note: this count is
    # inflated by intentional speculative red-links (/wiki SKILL.md policy:
    # pages linking forward to not-yet-created pages). The ratio is a
    # vault-maintenance signal, not a broken-link claim.
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
    n_content = max(1, n_pages - len(NON_CONTENT_STEMS & set(pages)))
    orphan_ratio = len(orphans) / n_content

    # Status: broken links are always a warning; high orphan ratio (>50%) too;
    # missing frontmatter is informational unless widespread (>25%).
    issues: list[str] = []
    if broken:
        issues.append(f"{len(broken)} broken wikilink(s)")
    if orphan_ratio > 0.5:
        issues.append(f"{len(orphans)} orphan page(s) ({orphan_ratio:.0%} of vault)")
    if duplicate_stems:
        issues.append(f"{len(duplicate_stems)} duplicate slug(s)")
    if len(missing_fm) / n_content > 0.25:
        issues.append(f"{len(missing_fm)} page(s) missing required frontmatter")

    if issues:
        print(f"⚠️ Wiki vault: {'; '.join(issues)} — {n_pages} pages in {vault}")
    else:
        print(f"✅ Wiki vault healthy ({n_pages} pages, {len(broken)} broken links, "
              f"{len(orphans)} orphans)")

    for src, tgt in broken[:15]:
        print(f"• [[{tgt}]] from {src}")
    if len(broken) > 15:
        print(f"• ... and {len(broken) - 15} more broken link(s)")
    for s in orphans[:10]:
        print(f"• orphan: {s}")
    if len(orphans) > 10:
        print(f"• ... and {len(orphans) - 10} more orphan(s)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
