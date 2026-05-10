"""Validate all skills for common issues.

Usage: python health_check.py
"""

import json
from datetime import datetime
from pathlib import Path

SKILLS_DIR = Path("P:\\\\\\.claude/skills")
EXCLUDE = {"_tools", "_archive"}
REQUIRED_FIELDS = ["name", "description"]
RECOMMENDED_FIELDS = ["category", "version", "status"]


def check_skill(path: Path) -> dict:
    """Check a single skill for issues."""
    content = path.read_text(encoding="utf-8")
    issues = []
    warnings = []

    lines = len(content.splitlines())
    if lines > 500:
        issues.append(f"Too long: {lines} lines (max 500)")
    elif lines > 400:
        warnings.append(f"Getting long: {lines} lines")

    # Smart TODO/FIXME detection - only flag actual placeholders, not references
    # Real placeholders: "TODO: fix this", "FIXME: broken", "# TODO", "- TODO"
    # Not flagged: "Do NOT generate TODOs", "TODO/FIXME as concept", "antidote"
    import re
    # Pattern matches TODO/FIXME as actual placeholder markers
    placeholder_pattern = re.compile(
        r'(?i)'  # case-insensitive
        r'(^|\n)(?:\s*[-*]?\s*)?'  # start of line or after bullet
        r'(TODO|FIXME)'  # the keyword
        r'[:\s]'  # followed by colon, space, or at end (placeholder)
        r'(?=[^\w]|$)'  # not part of another word
    )
    if placeholder_pattern.search(content):
        warnings.append("Contains TODO/FIXME")

    # Check frontmatter
    if not content.startswith("---"):
        issues.append("Missing frontmatter")
    else:
        for field in REQUIRED_FIELDS:
            if f"{field}:" not in content:
                issues.append(f"Missing required: {field}")
        for field in RECOMMENDED_FIELDS:
            if f"{field}:" not in content:
                warnings.append(f"Missing recommended: {field}")

    return {
        "skill": path.parent.name,
        "lines": lines,
        "issues": issues,
        "warnings": warnings,
        "healthy": len(issues) == 0,
    }


def main():
    results = []

    for skill_dir in SKILLS_DIR.iterdir():
        if not skill_dir.is_dir() or skill_dir.name in EXCLUDE:
            continue
        skill_file = skill_dir / "SKILL.md"
        if skill_file.exists():
            results.append(check_skill(skill_file))

    # Summary
    healthy = sum(1 for r in results if r["healthy"])
    with_warnings = sum(1 for r in results if r["warnings"] and r["healthy"])

    print(f"🏥 Health Check: {healthy}/{len(results)} skills healthy")
    if with_warnings:
        print(f"   ({with_warnings} with warnings)")
    print()

    # Show issues
    for r in results:
        if r["issues"]:
            print(f"❌ {r['skill']}")
            for issue in r["issues"]:
                print(f"   • {issue}")
        elif r["warnings"]:
            print(f"⚠️  {r['skill']}")
            for warn in r["warnings"]:
                print(f"   • {warn}")

    # Export JSON report
    report_path = Path(__file__).parent / "_health_report.json"
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total": len(results),
            "healthy": healthy,
            "with_issues": len(results) - healthy,
        },
        "skills": results,
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n📄 Report: {report_path}")


if __name__ == "__main__":
    main()
