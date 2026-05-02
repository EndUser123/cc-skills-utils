---
name: crawl
description: |
  Ingest websites into QMD collections using Crawl4AI for semantic search.
  FAIL FAST if crawl4ai or qmd not available.

  Use when:
  - Building a searchable local knowledge base from web sources
  - Capturing documentation for offline reference
  - Creating wiki content from blog posts, docs, or articles
  - Researching a topic by ingesting multiple sources

  Triggers: /crawl, "crawl url", "ingest website", "scrape to qmd"
version: "1.0.0"
status: experimental
category: ingest
enforcement: strict
triggers:
  - /crawl
  - 'crawl url'
  - 'crawl url'
  - 'scrape to qmd'
workflow_steps:
  - check_dependencies
  - fetch_content
  - compute_hash
  - check_dedup
  - save_with_frontmatter
  - find_related_pages
  - inject_wikilinks
  - log_ingest
  - update_qmd_index
---

# Crawl-Ingest

## Purpose

Ingest websites into QMD collections for semantic search via `/search` and `/explore`.

**Requirements:**
- `crawl4ai` Python package
- `qmd` CLI tool
- Obsidian vault configured in `~/.config/qmd/index.yml`

## Pipeline

Complete workflow with 9 steps:

1. **Check dependencies** — Verify crawl4ai and qmd are installed (fail-fast)
2. **Fetch** — Crawl4AI extracts content as Markdown
3. **Compute hash** — SHA256 of content for deduplication
4. **Check dedup** — Skip if hash exists in log.md
5. **Save** — Write to `wiki/sources/{domain}/{slug}.md` with frontmatter
6. **Find related** — QMD search for semantically similar pages
7. **Inject wikilinks** — Add `[[Page]]@related` links to related pages
8. **Log ingest** — Append entry to `log.md` with SHA256 for traceability
9. **Update index** — Run `qmd update <collection>` to rebuild search index

## Usage

```bash
/crawl-ingest https://example.com --max-pages 5      # Crawl up to 5 pages
/crawl-ingest https://example.com --collection wiki   # Explicit collection
/crawl-ingest https://example.com --collection docs   # Custom collection
```

## Output Format

```markdown
---
source:
  url: https://example.com/page
  crawled_at: 2026-04-29
  hash: abc123...
title: Page Title
tags:
  - web-ingested
---

Content extracted by Crawl4AI...

## Related

[[Related Page 1]]@related
[[Related Page 2]]@related
```

## Deduplication

Content is deduplicated via SHA256 hash:
- Hash stored in frontmatter (`hash` field)
- Logged to `log.md` with date, URL, SHA256
- Re-crawling same URL skips already-ingested content

## Validation Checklist

After ingestion, verify:

```bash
# 1. Frontmatter check - has hash field
head -10 wiki/sources/example.com/*.md | grep "hash:"

# 2. Log entry exists
grep "SHA256:" wiki/log.md

# 3. QMD search finds content
qmd search --collection wiki "query from page" --format json

# 4. Wikilinks are valid pages
grep "@related" wiki/sources/example.com/*.md
```

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `crawl4ai not installed` | Missing Python package | `pip install crawl4ai` |
| `qmd CLI not found` | Missing QMD | `pip install qmd` |
| `qmd CLI failed` | Wrong qmd command | Try `qmd-py` or `qmd` |
| Collection not found | QMD not configured | Check `~/.config/qmd/index.yml` |
| Vault not found | Wrong path in config | Verify vault path exists |
| Timeout | Site slow to respond | Increase wait in crawl config |
| Could not log to log.md | No write permission | Create log.md or check path |

## Examples

### Ingest Claude Code Hooks Guide

```bash
/crawl-ingest https://claudefa.st/blog/tools/hooks/hooks-guide --max-pages 3
```

### Ingest Python Documentation

```bash
/crawl-ingest https://docs.python.org/3/ --max-pages 10
```

### Ingest FastAPI Docs

```bash
/crawl-ingest https://fastapi.tiangolo.com/ --max-pages 5
```

## Configuration

**Vault location**: Read from `~/.config/qmd/index.yml`
**Log location**: `{vault_root}/log.md`
**Max pages**: Default 10, adjust based on site size

See [references/qmd-config.md](references/qmd-config.md) for QMD configuration details.

## Related Skills

- `/search` — Search all backends including QMD_WIKI
- `/explore` — Unified search with semantic filtering
- `/wiki` — Full wiki ingest workflow with SHA256 logging
