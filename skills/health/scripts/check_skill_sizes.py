#!/usr/bin/env python3
"""Scan all SKILL.md files and report line counts vs thresholds.

Usage:
    python check_skill_sizes.py [--fix-list]

Reports:
    - WARN: SKILL.md > 300 lines (should extract to references/)
    - FAIL: SKILL.md > 500 lines (must extract to references/)

Exit codes:
    0 = all pass
    1 = one or more FAIL
"""

import sys
from pathlib import Path

# Import validator from skill-ship package
_SKILL_SHIP_DIR = Path("P:/") / ".claude" / "skills" / "skill-ship"
sys.path.insert(0, str(_SKILL_SHIP_DIR))

from validators.context_size import validate_context_size

# Scan roots
_ROOTS: list[Path] = [
    Path("P:/") / ".claude" / "skills",
    Path("P:/") / ".claude" / "agents",
    Path.home() / ".claude" / "skills",
    Path.home() / ".claude" / "agents",
]


def scan_all_skills() -> dict[str, tuple[str, int, list[str]]]:
    """Scan all SKILL.md files and return results.

    Returns:
        Dict of {skill_path: (status, line_count, findings)}
    """
    results: dict[str, tuple[str, int, list[str]]] = {}

    for root in _ROOTS:
        if not root.exists():
            continue
        for skill_file in root.rglob("SKILL.md"):
            # Skip backup/temp directories (relative to root, not root itself)
            rel_parts = skill_file.relative_to(root).parts
            if any("backup" in p.lower() for p in rel_parts):
                continue
            skill_dir = str(skill_file.parent)
            result = validate_context_size(skill_dir)
            results[skill_dir] = (result.status, result.line_count, result.findings)

    return results


def main() -> int:
    fix_list = "--fix-list" in sys.argv
    results = scan_all_skills()

    if not results:
        print("No SKILL.md files found.")
        return 0

    # Sort: fails first, then warns, then passes
    order = {"fail": 0, "warn": 1, "pass": 2}
    sorted_results = sorted(results.items(), key=lambda x: (order[x[1][0]], -x[1][1]))

    pass_count = 0
    warn_count = 0
    fail_count = 0

    for skill_path, (status, line_count, _findings) in sorted_results:
        rel = skill_path.replace("P:/", "").replace("\\", "/")
        if status == "fail":
            print(f"FAIL  {line_count:>4d} lines  {rel}")
            fail_count += 1
        elif status == "warn":
            print(f"WARN  {line_count:>4d} lines  {rel}")
            warn_count += 1
        else:
            pass_count += 1

    print(f"\n{pass_count} pass | {warn_count} warn | {fail_count} fail | {len(results)} total")

    if fix_list and fail_count > 0:
        print("\nFiles exceeding 500 lines (need extraction to references/):")
        for skill_path, (status, line_count, _) in sorted_results:
            if status == "fail":
                print(f"  {skill_path} ({line_count} lines)")

    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
