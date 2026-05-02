#!/usr/bin/env python3
"""
Crawl4AI to QMD ingestion pipeline.

Crawl a website → Markdown files with frontmatter → QMD collection.

Usage: python crawl_to_qmd.py https://example.com --max-pages 10
       python crawl_to_qmd.py https://example.com --max-pages 10 --collection wiki

Fail-fast: exits with clear error if crawl4ai or qmd not installed.

Wiki integration:
- Computes SHA256 hash for deduplication via log.md
- Adds hash to frontmatter
- Logs entries to wiki log.md
- Finds and injects [[wikilinks]] to related pages
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import yaml

QMD_CONFIG_PATH = Path.home() / ".config" / "qmd" / "index.yml"
def _get_wiki_root() -> Path:
    """Get wiki root from QMD config."""
    try:
        with open(QMD_CONFIG_PATH, "r") as f:
            data = yaml.safe_load(f)
        collections = data.get("collections", {})
        if "wiki" in collections:
            path = collections["wiki"].get("path")
            if path:
                return Path(os.path.expanduser(path))
    except (OSError, ValueError, AttributeError):
        pass
    return Path("P:/.data/wiki")
def _get_wiki_log_path() -> Path:
    """Get log.md path."""
    return _get_wiki_root() / "log.md"


def _check_already_ingested(content_hash: str) -> bool:
    """Check if hash already exists in log.md."""
    try:
        log_path = _get_wiki_log_path()
        with open(log_path, "r", encoding="utf-8") as f:
            return content_hash in f.read()
    except OSError:
        return False


def _log_ingest(title: str, url: str, filepath: str, content_hash: str, collection: str) -> None:
    """Append entry to wiki log.md."""
    try:
        log_path = _get_wiki_log_path()
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n## {datetime.now().strftime('%Y-%m-%d')}\n")
            f.write(f"- **{title}** ({filepath})\n")
            f.write(f"  - URL: {url}\n")
            f.write(f"  - SHA256: {content_hash}\n")
            f.write(f"  - Source: crawl-ingest\n")
    except OSError as e:
        print(f"Warning: Could not log to log.md: {e}", file=sys.stderr)


def _find_related_pages(title: str, collection: str, limit: int = 5) -> list[str]:
    """Find related wiki pages via QMD search."""
    try:
        result = subprocess.run(
            ["qmd", "search", title, "--collection", collection,
             "--format", "json", "--limit", str(limit * 2)],
            capture_output=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []
        data = json.loads(result.stdout.decode())
        return [r["title"][:60] for r in data[:limit]]
    except (OSError, json.JSONDecodeError):
        return []


class CrawlIngestError(Exception):
    """Raised when crawl-ingest fails."""
    pass


class DependencyError(CrawlIngestError):
    """Raised when a required dependency is missing."""
    pass


def _check_dependencies() -> None:
    """Fail-fast: verify crawl4ai and qmd are available."""
    # Check crawl4ai
    try:
        import crawl4ai  # noqa: F401
    except ImportError:
        raise DependencyError(
            "crawl4ai not installed.\n"
            "Install: pip install crawl4ai"
        )

    # Check qmd CLI
    try:
        result = subprocess.run(
            ["qmd-py", "version"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            raise DependencyError(
                "qmd CLI failed.\n"
                "Install: pip install qmd\n"
                "Docs: https://github.com/tobi/qmd"
            )
    except FileNotFoundError:
        # Fallback: try 'qmd' directly
        try:
            result = subprocess.run(
                ["qmd", "version"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode != 0:
                raise DependencyError(
                    "qmd CLI failed.\n"
                    "Install: pip install qmd\n"
                    "Docs: https://github.com/tobi/qmd"
                )
        except FileNotFoundError:
            raise DependencyError(
                "qmd CLI not found.\n"
                "Install: pip install qmd\n"
                "Docs: https://github.com/tobi/qmd"
            )


def _get_vault_path(collection: str) -> Path:
    """Get vault path for a QMD collection."""
    try:
        with open(QMD_CONFIG_PATH, "r") as f:
            data = yaml.safe_load(f)
        collections = data.get("collections", {})
        if collection in collections:
            path = collections[collection].get("path")
            if path:
                return Path(os.path.expanduser(path))
    except (OSError, ValueError, AttributeError):
        pass

    return VAULT_BASE / collection


def _slug_from_url(url: str) -> str:
    """Create URL-safe slug from URL."""
    parsed = urlparse(url)
    path = parsed.path.strip("/").replace("/", "-") or "index"
    domain = parsed.netloc.replace(":", "-").replace(".", "-")

    slug = f"{domain}-{path}"
    slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in slug)
    slug = slug[:100].strip("-_")
    return slug or "page"


async def crawl_site(
    root_url: str,
    collection: str = "wiki",
    max_pages: int = 10,
) -> dict:
    """Crawl site and ingest into QMD collection.

    Args:
        root_url: Root URL to crawl
        collection: QMD collection name
        max_pages: Max pages to fetch
        headless: Use headless browser

    Returns:
        Dict with ingestion stats
    """
    _check_dependencies()

    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig
    from crawl4ai import DefaultMarkdownGenerator
    from crawl4ai import CacheMode

    vault_path = _get_vault_path(collection)
    output_dir = vault_path / "sources"

    if not vault_path.exists():
        raise CrawlIngestError(
            f"Vault path does not exist: {vault_path}\n"
            "Configure your QMD collection in ~/.config/qmd/index.yml"
        )

    stats = {
        "url": root_url,
        "collection": collection,
        "pages_fetched": 0,
        "pages_saved": 0,
        "pages_skipped": 0,
        "files_written": [],
        "crawl_errors": [],
        "write_errors": [],
    }

    # Parse domain for folder
    domain = urlparse(root_url).netloc.replace("www.", "")

    markdown_gen = DefaultMarkdownGenerator()
    config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        markdown_generator=markdown_gen,
        wait_until="networkidle",
        delay_before_return_html=1.0,
    )

    async with AsyncWebCrawler() as crawler:
        # Initial crawl
        result = await crawler.arun(url=root_url, config=config)
        if result.success:
            stats["pages_fetched"] += 1
            saved = await _save_md(result, output_dir, domain, 0, collection, stats)
            if saved:
                stats["pages_saved"] += 1
            elif saved is None:
                stats["pages_skipped"] += 1

            # Follow internal links (limit to domain)
            urls_to_crawl = [
                link for link in result.links
                if urlparse(link).netloc == domain
            ][: max_pages - 1]

            for i, url in enumerate(urls_to_crawl):
                if stats["pages_fetched"] >= max_pages:
                    break
                try:
                    result = await crawler.arun(url=url, config=config)
                    if result.success:
                        stats["pages_fetched"] += 1
                        saved = await _save_md(result, output_dir, domain, i + 1, collection, stats)
                        if saved:
                            stats["pages_saved"] += 1
                        elif saved is None and not any(e.startswith(url) for e in stats["crawl_errors"]):
                            stats["pages_skipped"] += 1
                except Exception as e:
                    stats["crawl_errors"].append(f"{url}: {str(e)}")

    # Update QMD index
    try:
        subprocess.run(
            ["qmd", "update", collection],
            capture_output=True,
            timeout=30,
            check=True,
        )
        stats["index_updated"] = True
        # Verify index is fresh
        index_path = vault_path / ".qmd" / "index.db"
        if index_path.exists():
            index_mtime = index_path.stat().st_mtime
            # Check if any saved file is newer than index
            for f in stats["files_written"]:
                f_path = Path(f)
                if f_path.exists() and f_path.stat().st_mtime > index_mtime:
                    stats["index_stale"] = True
                    break
    except subprocess.TimeoutExpired:
        stats["crawl_errors"].append("QMD index update timed out")
    except subprocess.CalledProcessError as e:
        stats["crawl_errors"].append(f"QMD index update failed: {e.stderr.decode()}")

    return stats


async def _save_md(
    result,
    output_dir: Path,
    domain: str,
    index: int,
    collection: str,
    stats: dict,
) -> str | None:
    """Save filtered Markdown with frontmatter to file.

    Returns file path on success, None on failure (crawl/no-content/already-ingested).
    Write errors are logged but don't abort the loop.
    """
    url = result.url
    metadata = result.metadata or {}
    title = metadata.get("title", url.split("/")[-1] or "Untitled")
    md_content = result.markdown or result.extracted_content or ""

    if not md_content:
        return None

    # Compute SHA256 for deduplication
    content_hash = hashlib.sha256(md_content.encode()).hexdigest()

    # Check if already ingested
    if _check_already_ingested(content_hash):
        print(f"Skipping (already ingested): {url}")
        return None

    # Slugify URL for filename
    slug = re.sub(r"[^\w\-]", "-", urlparse(url).path.strip("/"))[:50]
    filename = f"{index:03d}-{slug}.md"
    filepath = output_dir / domain / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Find related pages for wikilinks
    related = _find_related_pages(title, collection)
    related_section = ""
    if related:
        related_links = "\n".join(f"[[{t}]]@related" for t in related)
        related_section = f"\n\n## Related\n{related_links}\n"

    # Frontmatter with hash
    today = datetime.now().strftime("%Y-%m-%d")
    frontmatter = f"""---
source:
  url: {url}
  crawled_at: {today}
  hash: {content_hash}
title: {title}
tags:
  - web-ingested
---

"""

    try:
        filepath.write_text(frontmatter + md_content + related_section, encoding="utf-8")
        print(f"Saved: {filename} ({len(md_content)} chars)")
        stats["files_written"].append(str(filepath))
    except OSError as e:
        stats["write_errors"].append(f"{filepath.name}: {str(e)}")
        print(f"Write failed: {filepath.name} — {e}", file=sys.stderr)
        return None

    # Log to wiki log.md
    _log_ingest(title, url, str(filepath), content_hash, collection)

    return str(filepath)


async def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Crawl site → QMD-ready Markdown")
    parser.add_argument("url", help="Root URL to crawl")
    parser.add_argument("--collection", default="wiki", help="QMD collection name")
    parser.add_argument("--max-pages", type=int, default=10, help="Max pages to fetch")
    args = parser.parse_args()

    try:
        stats = await crawl_site(
            args.url,
            collection=args.collection,
            max_pages=args.max_pages,
        )

        print(f"\n=== SUMMARY ===")
        print(f"Pages fetched: {stats['pages_fetched']}")
        print(f"Pages saved: {stats['pages_saved']}")
        print(f"Pages skipped: {stats['pages_skipped']}")
        print(f"Collection: {stats['collection']}")
        print(f"Index updated: {stats.get('index_updated', False)}")
        if stats.get("index_stale"):
            print("WARNING: Index may be stale — some files are newer than index")
        if stats["crawl_errors"]:
            print(f"Crawl errors ({len(stats['crawl_errors'])}):")
            for err in stats["crawl_errors"][:5]:
                print(f"  - {err}")
        if stats["write_errors"]:
            print(f"Write errors ({len(stats['write_errors'])}):")
            for err in stats["write_errors"][:5]:
                print(f"  - {err}")

    except DependencyError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except CrawlIngestError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
