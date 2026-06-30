#!/usr/bin/env python3
"""Check tracked GitHub repos for upstream changes.

Iterates P:/packages/.github_repos/*, fetches origin, and reports
which local clones are behind their upstream branch.

Usage:
    python repo_upstream_check.py              # Full check with fetch
    python repo_upstream_check.py --quick       # Skip fetch, only check known divergence
    python repo_upstream_check.py --fix         # Pull updates for stale repos
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

REPOS_DIR = Path("P:/packages/.github_repos")

# Extra git checkouts to track alongside .github_repos. These are marketplace
# clones whose upstream matters because a local fork is derived from them — when
# they advance, the fork may need re-syncing. keyed by (path, display_label).
EXTRA_TRACKED_REPOS = [
    (Path("C:/Users/brsth/.claude/plugins/marketplaces/zai-coding-plugins"), "zai-coding-plugins (upstream of glm-plan-usage fork)"),
]


def _check_one(repo: Path, quick: bool, label: str | None = None) -> str | None:
    """Check a single repo. Returns status line if stale, None if up-to-date."""
    name = label or repo.name
    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=10,
            cwd=str(repo),
        ).stdout.strip()

        if not quick:
            subprocess.run(
                ["git", "fetch", "--quiet", "origin"],
                capture_output=True, timeout=30,
                cwd=str(repo),
            )

        remote_ref = f"origin/{branch}" if branch != "HEAD" else "origin/main"
        local_rev = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=str(repo),
        ).stdout.strip()
        remote_rev = subprocess.run(
            ["git", "rev-parse", remote_ref],
            capture_output=True, text=True, cwd=str(repo),
        ).stdout.strip()

        if local_rev and remote_rev and local_rev != remote_rev:
            behind = subprocess.run(
                ["git", "rev-list", "--count", f"{local_rev}..{remote_rev}"],
                capture_output=True, text=True, cwd=str(repo),
            ).stdout.strip()
            if behind and int(behind) > 0:
                return f"• {name}: {behind} commit(s) behind {remote_ref}"

    except subprocess.TimeoutExpired:
        return f"• {name}: timeout during fetch"
    except Exception as e:
        return f"• {name}: error — {e}"

    return None


def check_repos(quick: bool = False) -> list[str]:
    """Check all repos in parallel. Returns list of stale-repo detail lines."""
    repos: list[tuple[Path, str | None]] = sorted(
        (d, None) for d in REPOS_DIR.iterdir()
        if d.is_dir() and (d / ".git").exists()
    )
    for path, label in EXTRA_TRACKED_REPOS:
        if path.is_dir() and (path / ".git").exists():
            repos.append((path, label))
    results: list[str] = []

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_check_one, r, quick, lbl): r for r, lbl in repos}
        for future in as_completed(futures):
            line = future.result()
            if line:
                results.append(line)

    return sorted(results)


def pull_repos(stale_details: list[str]) -> list[str]:
    """Pull updates for repos listed in stale details. Returns action log."""
    pulled = []
    for detail in stale_details:
        name = detail.split(":")[0].replace("• ", "")
        repo = REPOS_DIR / name
        if not repo.is_dir():
            # Extra tracked repo (e.g. a fork's upstream marketplace clone) —
            # informational only; not auto-pulled. Re-sync the fork by hand.
            pulled.append(f"• {name}: tracked-for-info only (fork upstream) — re-sync fork manually")
            continue
        try:
            result = subprocess.run(
                ["git", "pull", "--ff-only"],
                capture_output=True, text=True, timeout=60,
                cwd=str(repo),
            )
            if result.returncode == 0:
                pulled.append(f"✓ {name}: pulled")
            else:
                pulled.append(f"✗ {name}: pull failed — {result.stderr.strip()[:120]}")
        except Exception as e:
            pulled.append(f"✗ {name}: error — {e}")
    return pulled


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true",
                        help="Skip fetch, only report known divergence")
    parser.add_argument("--fix", action="store_true",
                        help="Pull updates for stale repos")
    args = parser.parse_args()

    start = time.time()
    stale = check_repos(quick=args.quick)
    elapsed = int((time.time() - start) * 1000)

    if not stale:
        print("✅ All repos up to date")
        return 0

    for line in stale:
        print(line)
    print(f"⚠️ {len(stale)} repo(s) behind upstream [{elapsed}ms]")

    if args.fix:
        actions = pull_repos(stale)
        for a in actions:
            print(f"   {a}")
    elif not args.quick:
        print("   💡 Run with --fix to pull updates, or --quick to skip fetch next time")

    return 1


if __name__ == "__main__":
    sys.exit(main())
