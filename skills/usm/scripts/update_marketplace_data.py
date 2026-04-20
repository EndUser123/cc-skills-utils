#!/usr/bin/env python3
"""
update_marketplace_data.py — Universal Skills Manager

Queries all live marketplace and API sources, reconciles against the existing
marketplace-data.json, updates the JSON, and regenerates the
marketplace-comparison/index.html dashboard.

Run: python3 scripts/update_marketplace_data.py [--dry-run] [--html-only]

--dry-run   Print what would change without writing files.
--html-only Update HTML only (skip source queries).
"""

import argparse
import copy
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ── paths ────────────────────────────────────────────────────────────────────
SKILL_DIR = Path(__file__).resolve().parents[1]
JSON_PATH = SKILL_DIR / "resources" / "marketplace-data.json"
HTML_PATH = SKILL_DIR / "resources" / "marketplace-comparison" / "index.html"
CSS_PATH = (
    Path(__file__).resolve().parents[1] / "resources" / "marketplace-comparison" / "style.css"
)
JS_PATH = Path(__file__).resolve().parents[1] / "resources" / "marketplace-comparison" / "app.js"

# ── helpers ───────────────────────────────────────────────────────────────────
HEADERS = {"User-Agent": "Universal-Skills-Manager/1.0"}
_GITHUB_TOKEN = os.environ.get("GITHUB_API_TOKEN")


def get(url: str, timeout: float = 10.0) -> str | None:
    """Fetch URL with timeout. Returns None on failure."""
    headers = dict(HEADERS)
    if _GITHUB_TOKEN and "api.github.com" in url:
        headers["Authorization"] = f"token {_GITHUB_TOKEN}"
    try:
        with urlopen(Request(url, headers=headers), timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        if e.code == 403 and "api.github.com" in url:
            print(
                f"  [WARN] {url} → 403 rate limit (set GITHUB_API_TOKEN for 5000 req/hr)",
                file=sys.stderr,
            )
        elif e.code == 404:
            print(f"  [WARN] {url} → 404 not found", file=sys.stderr)
        else:
            print(f"  [WARN] {url} → HTTP {e.code}", file=sys.stderr)
        return None
    except (URLError, TimeoutError, OSError) as e:
        print(f"  [WARN] {url} → {e}", file=sys.stderr)
        return None


def get_json(url: str, timeout: float = 10.0) -> dict | None:
    raw = get(url, timeout)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  [WARN] {url} JSON parse error: {e}", file=sys.stderr)
        return None


def parallel_get(urls: list[str], timeout: float = 10.0) -> list[tuple[str, str | None]]:
    """Fetch multiple URLs sequentially (not threads — avoids dependency on concurrent.futures)."""
    return [(u, get(u, timeout)) for u in urls]


# ── source queries ────────────────────────────────────────────────────────────
def query_skillsmp(api_key: str | None) -> dict | None:
    """SkillsMP: total skill count from pagination.total."""
    if api_key:
        url = "https://skillsmp.com/api/v1/skills/search?q=*&limit=1"
        body = get_json(url, timeout=15.0)
        if body and body.get("success"):
            total = body.get("data", {}).get("pagination", {}).get("total")
            return {"listings": total, "source": "SkillsMP"}
    # Fallback: no-key search
    body = get_json("https://skillsmp.com/api/v1/skills/search?q=*&limit=1", timeout=15.0)
    if body and body.get("success"):
        total = body.get("data", {}).get("pagination", {}).get("total")
        return {"listings": total, "source": "SkillsMP"}
    return None


def query_skillhub() -> dict | None:
    """SkillHub: total skill count from pagination.total."""
    body = get_json("https://skills.palebluedot.live/api/skills?limit=1")
    if body:
        total = body.get("pagination", {}).get("total")
        return {"listings": total, "source": "SkillHub"}
    return None


def query_clawhub() -> dict | None:
    """ClawHub: total skill count from pagination.total."""
    body = get_json("https://clawhub.ai/api/v1/skills?limit=1")
    if body:
        total = body.get("pagination", {}).get("total")
        return {"listings": total, "source": "ClawHub"}
    return None


def query_skillssh() -> dict | None:
    """skills.sh: count entries in the skills-index repository."""
    body = get_json("https://api.github.com/repos/skills-sh/skills-index/contents?ref=main")
    if body and isinstance(body, list):
        # skills.sh indexes repos; count top-level dirs as proxy
        return {"listings": len(body), "source": "skills.sh"}
    return None


def query_official_plugins() -> dict | None:
    """claude-plugins-official: count entries in marketplace.json + GitHub stars."""
    body = get_json(
        "https://api.github.com/repos/anthropics/claude-plugins-official/contents/marketplace.json"
    )
    if body and isinstance(body, list):
        # marketplace.json is an array of plugin entries
        listings = len(body)
        stars_raw = get("https://api.github.com/repos/anthropics/claude-plugins-official")
        stars = None
        if stars_raw:
            try:
                stars = json.loads(stars_raw).get("stargazers_count")
            except Exception:
                pass
        return {
            "listings": listings,
            "stars": stars,
            "source": "claude-plugins-official",
        }
    return None


def query_claudemarketplaces() -> dict | None:
    """claudemarketplaces.com: parse total skills + MCP servers from homepage HTML."""
    html = get("https://claudemarketplaces.com", timeout=15.0)
    if html is None:
        return None
    listings = None
    # Look for patterns like "2,315 skills" or "skills" count in text
    m = re.search(r"([\d,]+)\s+skills?", html, re.I)
    if m and m.group(1):
        try:
            listings = int(m.group(1).replace(",", ""))
        except ValueError:
            listings = None
    # Also try to find MCP servers
    mcp_m = re.search(r"([\d,]+)\s+MCP", html, re.I)
    mcp_count = None
    if mcp_m and mcp_m.group(1):
        try:
            mcp_count = int(mcp_m.group(1).replace(",", ""))
        except ValueError:
            mcp_count = None
    return {
        "listings": listings,
        "mcp_servers": mcp_count,
        "source": "claudemarketplaces.com",
    }


def query_skillsdirectory() -> dict | None:
    """skillsdirectory.com: parse total scanned skills from homepage."""
    html = get("https://skillsdirectory.com", timeout=15.0)
    if html is None:
        return None
    listings = None
    m = re.search(r"([\d,]+)\s+total\s+scanned", html, re.I)
    if m and m.group(1):
        try:
            listings = int(m.group(1).replace(",", ""))
        except ValueError:
            listings = None
    else:
        # Try alternative pattern
        m = re.search(r"([\d,]+)\s+skills?", html, re.I)
        if m and m.group(1):
            try:
                listings = int(m.group(1).replace(",", ""))
            except ValueError:
                listings = None
    return {"listings": listings, "source": "skillsdirectory.com"}


def query_composio() -> dict | None:
    """ComposioHQ/awesome-claude-skills: GitHub stars + file count as listings proxy."""
    body = get_json("https://api.github.com/repos/ComposioHQ/awesome-claude-skills")
    if body:
        stars = body.get("stargazers_count")
        # Count files in repo as listings proxy
        contents = get_json(
            "https://api.github.com/repos/ComposioHQ/awesome-claude-skills/contents"
        )
        file_count = len(contents) if isinstance(contents, list) else None
        return {
            "listings": file_count,
            "stars": stars,
            "source": "ComposioHQ/awesome-claude-skills",
        }
    return None


def query_claudemarketplaces_stats() -> dict | None:
    """claudemarketplaces.com: parse marketplace, skill, MCP counts."""
    html = get("https://claudemarketplaces.com", timeout=15.0)
    if html is None:
        return None
    skills_m = re.search(r"([\d,]+)\s+skills", html, re.I)
    mcp_m = re.search(r"([\d,]+)\s+MCP\s+servers", html, re.I)
    mp_m = re.search(r"([\d,]+)\s+marketplaces", html, re.I)

    def _safe_int(m, fallback=None):
        if m and m.group(1):
            try:
                return int(m.group(1).replace(",", ""))
            except ValueError:
                return fallback
        return fallback

    return {
        "skills": _safe_int(skills_m),
        "mcp_servers": _safe_int(mcp_m),
        "marketplaces": _safe_int(mp_m),
    }


# ── schema validation ─────────────────────────────────────────────────────────
def _validate_schema(data: dict) -> list[str]:
    """Validate marketplace-data.json structure. Returns list of error strings (empty = valid)."""
    errors = []
    if not isinstance(data.get("sources"), list):
        errors.append("sources must be a list")
        return errors  # can't check further without sources

    known_ids = set()
    for i, src in enumerate(data["sources"]):
        sid = src.get("id")
        if not sid:
            errors.append(f"sources[{i}]: missing 'id'")
        elif sid in known_ids:
            errors.append(f"sources: duplicate id '{sid}'")
        else:
            known_ids.add(sid)

        if "name" not in src:
            errors.append(f"sources[{i}]: missing 'name'")
        if "type" not in src:
            errors.append(f"sources[{i}]: missing 'type'")

        listings = src.get("listings")
        if listings is not None and not isinstance(listings, int):
            errors.append(
                f"sources[{i}].listings: must be int or null, got {type(listings).__name__}"
            )

        stars = src.get("stars")
        if stars is not None and not isinstance(stars, int):
            errors.append(f"sources[{i}].stars: must be int or null, got {type(stars).__name__}")

    if "lastUpdated" in data and not isinstance(data["lastUpdated"], str):
        errors.append("lastUpdated: must be a string")

    totals = data.get("totals", {})
    for field in ("totalListingsIndexed", "totalGitHubStars"):
        val = totals.get(field)
        if val is not None and not isinstance(val, int):
            errors.append(f"totals.{field}: must be int or null, got {type(val).__name__}")

    return errors


# ── diff & report ─────────────────────────────────────────────────────────────
def diff_value(old, new, key):
    """Return a short diff string or None if unchanged."""
    if old == new:
        return None
    if old is None and new is not None:
        return f"{key}: — → {new}"
    if new is None:
        return f"{key}: {old} → — (unavailable)"
    return f"{key}: {old:,} → {new:,}"


def _touch_source(sources: list, source_id: str) -> None:
    """Stamp source with today's date if it returned data (listings is not None)."""
    src = next((s for s in sources if s["id"] == source_id), None)
    if src and src.get("listings") is not None:
        src["lastSuccessfulQuery"] = str(date.today())


# ── HTML generation ────────────────────────────────────────────────────────────
def build_data_js(data: dict) -> str:
    """Build the JS `const DATA = {...}` object from marketplace-data.json.

    Matches the structure expected by resources/marketplace-comparison/index.html.
    """

    d = copy.deepcopy(data)
    # Remove internal fields not needed in the frontend
    for src in d.get("sources", []):
        src.pop("url", None)
        src.pop("installs", None)
        src.pop("securityGradePct", None)
    d.pop("totals", None)
    d.pop("updateInstructions", None)
    return f"const DATA = {json.dumps(d, indent=2)};"


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--html-only", action="store_true")
    args = ap.parse_args()

    # Load existing JSON
    if not JSON_PATH.exists():
        print(f"[ERROR] {JSON_PATH} not found. Run from skill directory.", file=sys.stderr)
        sys.exit(1)

    with open(JSON_PATH, encoding="utf-8") as f:
        old_data = json.load(f)

    new_data = json.loads(json.dumps(old_data))  # deep copy
    new_data["lastUpdated"] = str(date.today())
    diffs = []

    # ── query sources ──────────────────────────────────────────────────────────
    if not args.html_only:
        print("Querying live sources...")

        # Gather API key once before threading
        api_key = os.environ.get("SKILLSMP_API_KEY")
        if not api_key:
            cfg = SKILL_DIR / "config.json"
            if cfg.exists():
                try:
                    api_key = json.loads(cfg.read_text()).get("skillsmp_api_key")
                except Exception:
                    pass

        # Run all source queries concurrently via ThreadPoolExecutor
        def _run_queries():
            with ThreadPoolExecutor(max_workers=8) as pool:
                futures = {
                    "skillsmp": pool.submit(query_skillsmp, api_key),
                    "skillhub": pool.submit(query_skillhub),
                    "clawhub": pool.submit(query_clawhub),
                    "skillssh": pool.submit(query_skillssh),
                    "claude-plugins-official": pool.submit(query_official_plugins),
                    "claudemarketplaces": pool.submit(query_claudemarketplaces),
                    "skillsdirectory": pool.submit(query_skillsdirectory),
                    "composio": pool.submit(query_composio),
                }
                return {k: f.result() for k, f in futures.items()}

        results = _run_queries()

        # ── apply results sequentially ───────────────────────────────────────
        r = results.get("skillsmp")
        if r:
            old_v = next((s for s in new_data["sources"] if s["id"] == "skillsmp"), {}).get(
                "listings"
            )
            new_v = r.get("listings")
            d = diff_value(old_v, new_v, "SkillsMP listings")
            if d:
                diffs.append(d)
            _src = next((s for s in new_data["sources"] if s["id"] == "skillsmp"), None)
            if _src:
                _src["listings"] = new_v
                _touch_source(new_data["sources"], "skillsmp")

        r = results.get("skillhub")
        if r:
            old_v = next((s for s in new_data["sources"] if s["id"] == "skillhub"), {}).get(
                "listings"
            )
            new_v = r.get("listings")
            d = diff_value(old_v, new_v, "SkillHub listings")
            if d:
                diffs.append(d)
            _src = next((s for s in new_data["sources"] if s["id"] == "skillhub"), None)
            if _src:
                _src["listings"] = new_v
                _touch_source(new_data["sources"], "skillhub")

        r = results.get("clawhub")
        if r:
            old_v = next((s for s in new_data["sources"] if s["id"] == "clawhub"), {}).get(
                "listings"
            )
            new_v = r.get("listings")
            d = diff_value(old_v, new_v, "ClawHub listings")
            if d:
                diffs.append(d)
            _src = next((s for s in new_data["sources"] if s["id"] == "clawhub"), None)
            if _src:
                _src["listings"] = new_v
                _touch_source(new_data["sources"], "clawhub")

        r = results.get("skillssh")
        if r:
            old_v = next((s for s in new_data["sources"] if s["id"] == "skillssh"), {}).get(
                "listings"
            )
            new_v = r.get("listings")
            d = diff_value(old_v, new_v, "skills.sh listings")
            if d:
                diffs.append(d)
            _src = next((s for s in new_data["sources"] if s["id"] == "skillssh"), None)
            if _src:
                _src["listings"] = new_v
                _touch_source(new_data["sources"], "skillssh")

        r = results.get("claude-plugins-official")
        if r:
            old_listings = next(
                (s for s in new_data["sources"] if s["id"] == "claude-plugins-official"),
                {},
            ).get("listings")
            old_stars = next(
                (s for s in new_data["sources"] if s["id"] == "claude-plugins-official"),
                {},
            ).get("stars")
            new_listings = r.get("listings")
            new_stars = r.get("stars")
            d1 = diff_value(old_listings, new_listings, "Official plugins listings")
            d2 = diff_value(old_stars, new_stars, "Official plugins stars")
            if d1:
                diffs.append(d1)
            if d2:
                diffs.append(d2)
            _src = next(
                (s for s in new_data["sources"] if s["id"] == "claude-plugins-official"),
                None,
            )
            if _src:
                if new_listings is not None:
                    _src["listings"] = new_listings
                if new_stars is not None:
                    _src["stars"] = new_stars
                _touch_source(new_data["sources"], "claude-plugins-official")

        r = results.get("claudemarketplaces")
        if r:
            old_v = next(
                (s for s in new_data["sources"] if s["id"] == "claudemarketplaces"), {}
            ).get("listings")
            new_v = r.get("listings")
            d = diff_value(old_v, new_v, "claudemarketplaces.com listings")
            if d:
                diffs.append(d)
            _src = next(
                (s for s in new_data["sources"] if s["id"] == "claudemarketplaces"),
                None,
            )
            if _src and new_v is not None:
                _src["listings"] = new_v
                _touch_source(new_data["sources"], "claudemarketplaces")

        r = results.get("skillsdirectory")
        if r:
            old_v = next((s for s in new_data["sources"] if s["id"] == "skillsdirectory"), {}).get(
                "listings"
            )
            new_v = r.get("listings")
            d = diff_value(old_v, new_v, "skillsdirectory.com listings")
            if d:
                diffs.append(d)
            _src = next((s for s in new_data["sources"] if s["id"] == "skillsdirectory"), None)
            if _src and new_v is not None:
                _src["listings"] = new_v
                _touch_source(new_data["sources"], "skillsdirectory")

        r = results.get("composio")
        if r:
            old_listings = next((s for s in new_data["sources"] if s["id"] == "composio"), {}).get(
                "listings"
            )
            old_stars = next((s for s in new_data["sources"] if s["id"] == "composio"), {}).get(
                "stars"
            )
            new_listings = r.get("listings")
            new_stars = r.get("stars")
            d1 = diff_value(old_listings, new_listings, "Composio listings")
            d2 = diff_value(old_stars, new_stars, "Composio stars")
            if d1:
                diffs.append(d1)
            if d2:
                diffs.append(d2)
            _src = next((s for s in new_data["sources"] if s["id"] == "composio"), None)
            if _src:
                if new_listings is not None:
                    _src["listings"] = new_listings
                if new_stars is not None:
                    _src["stars"] = new_stars
                _touch_source(new_data["sources"], "composio")

        # Recalculate totals
        new_data["totals"]["totalListingsIndexed"] = sum(
            s.get("listings") or 0 for s in new_data["sources"]
        )
        new_data["totals"]["totalGitHubStars"] = sum(
            s.get("stars") or 0 for s in new_data["sources"]
        )
        diffs.append(
            f"Total listings: {old_data['totals']['totalListingsIndexed']:,} → {new_data['totals']['totalListingsIndexed']:,}"
        )
    else:
        print("HTML-only mode — skipping source queries.")

    # ── report ────────────────────────────────────────────────────────────────
    if diffs:
        print("\n--- Changes detected ---")
        for d in diffs:
            print(f"  {d}")
    else:
        print("\nNo changes detected.")

    if args.dry_run:
        print("\n[Dry-run — no files written]")
        return

    # ── write JSON ─────────────────────────────────────────────────────────────
    if not args.html_only:
        # Validate before writing — fail fast on schema corruption
        schema_errors = _validate_schema(new_data)
        if schema_errors:
            print(
                "[ERROR] marketplace-data.json schema validation failed:",
                file=sys.stderr,
            )
            for err in schema_errors:
                print(f"  {err}", file=sys.stderr)
            sys.exit(1)
        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=2, ensure_ascii=False)
        print(f"\nUpdated {JSON_PATH}")

    # ── regenerate HTML ──────────────────────────────────────────────────────
    if HTML_PATH.exists():
        html = HTML_PATH.read_text(encoding="utf-8")

        # Replace/insert DATA JS block
        data_js = build_data_js(new_data)
        # Replace the DATA block in the HTML
        pat = re.compile(r"const DATA\s*=\s*\{.*?\n\};", re.DOTALL)
        _data_match_before = pat.search(html)
        if _data_match_before:
            html = pat.sub(data_js, html, count=1)
        else:
            # Fallback: replace the entire DATA object spanning multiple lines
            html = re.sub(r"const DATA\s*=\s*\{[^}]+\}[^;]*;", data_js, html, flags=re.DOTALL)
        # ── POST-WRITE: verify DATA block was actually replaced ─────────────────
        if not _data_match_before and pat.search(html) is None:
            print(
                "  [WARN] DATA block regex found no match before or after replacement"
                " — DATA may be stale in HTML",
                file=sys.stderr,
            )

        # Replace totals in KPI elements by ID
        # ── PRE-WRITE: verify all target IDs exist ─────────────────────────────
        _ids_to_write = [
            "kpi-total-listings",
            "kpi-official-plugins",
            "kpi-security-scanned",
            "kpi-github-stars",
            "kpi-security-grade",
        ]
        for _id in _ids_to_write:
            if f'id="{_id}"' not in html:
                print(
                    f'  [WARN] ID "{_id}" not found in HTML — html.replace() will silently no-op',
                    file=sys.stderr,
                )
        total_listings = new_data["totals"]["totalListingsIndexed"]
        total_stars = new_data["totals"]["totalGitHubStars"]
        sec_scanned = new_data["totals"].get("totalSecurityScanned", 0)
        sec_grade = "A"
        for src in new_data["sources"]:
            if src.get("securityScanned"):
                sec_grade = src.get("securityGrade", "A")
                break

        for old, new in [
            (
                'id="kpi-total-listings"',
                f'id="kpi-total-listings" data-raw="{total_listings}"',
            ),
            (
                'id="kpi-official-plugins"',
                f'id="kpi-official-plugins" data-raw="{next((s.get("listings") for s in new_data["sources"] if s["id"] == "claude-plugins-official"), 0)}"',
            ),
            (
                'id="kpi-security-scanned"',
                f'id="kpi-security-scanned" data-raw="{sec_scanned}"',
            ),
            (
                'id="kpi-github-stars"',
                f'id="kpi-github-stars" data-raw="{total_stars}"',
            ),
            (
                'id="kpi-security-grade"',
                f'id="kpi-security-grade" data-raw="94% Grade {sec_grade}"',
            ),
        ]:
            html = html.replace(old, new, 1)

        HTML_PATH.write_text(html, encoding="utf-8")
        print(f"Updated {HTML_PATH}")
    else:
        print(f"[WARN] {HTML_PATH} not found — skipping HTML update.")

    print(f"\nDone. Last updated: {new_data['lastUpdated']}")


if __name__ == "__main__":
    main()
