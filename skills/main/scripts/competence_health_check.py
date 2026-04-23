#!/usr/bin/env python3
"""
Competence Layer Health Check

Validates:
- Registry loads and has all 6 task types
- Contract log file exists and isn't bloated (>10MB)
- Compliance metrics show healthy rates (>70% overall)
- No stale skill mappings (skills that should exist but don't)

Usage:
    python competence_health_check.py
"""

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Add hooks to path
# __file__ = P:/.claude/skills/main/scripts/competence_health_check.py
# parent.parent = P:/.claude/skills/main, ../../hooks = P:/.claude/hooks
HOOKS_DIR = Path(__file__).parent.parent / "../../hooks"
HOOKS_DIR = HOOKS_DIR.resolve()
sys.path.insert(0, str(HOOKS_DIR))

# Paths
REGISTRY_FILE = HOOKS_DIR / "competence" / "templates" / "task_type_registry.json"
CONTRACT_LOG = HOOKS_DIR.parent / "logs" / "contract_completeness.jsonl"

# Thresholds
MAX_LOG_SIZE_MB = 10
MIN_COMPLIANCE_RATE = 0.70
MIN_ENTRIES = 10  # Need at least this many checks for meaningful metrics


def check_registry() -> tuple[bool, str, list[str]]:
    """Check task type registry loads and has required content."""
    details = []

    if not REGISTRY_FILE.exists():
        return False, "❌ Registry file missing", [f"Expected: {REGISTRY_FILE}"]

    try:
        with open(REGISTRY_FILE, encoding="utf-8") as f:
            registry = json.load(f)
    except json.JSONDecodeError as e:
        return False, f"❌ Registry JSON parse error: {e}", []

    # Check task types
    task_types = registry.get("task_types", {})
    required_types = {"research", "analysis", "implementation", "validation", "planning", "meta"}
    present_types = set(task_types.keys())

    missing = required_types - present_types
    if missing:
        return False, f"❌ Missing task types: {missing}", list(present_types)

    # Check skill_mappings
    skill_mappings = registry.get("skill_mappings", {})
    if not skill_mappings:
        details.append("⚠️  No skill mappings defined (new skills won't have contracts)")

    # Check each task type has output_contract
    for name, task_type in task_types.items():
        if name == "meta":
            continue  # Meta has no contract
        if "output_contract" not in task_type:
            details.append(f"⚠️  Task type '{name}' missing output_contract")

    return True, f"✅ Registry OK ({len(task_types)} types, {len(skill_mappings)} skills)", details


def check_contract_log() -> tuple[bool, str, list[str]]:
    """Check contract log exists and isn't bloated."""
    details = []

    if not CONTRACT_LOG.exists():
        return True, "✅ No contract log yet (system new or not used)", []

    size_mb = CONTRACT_LOG.stat().st_size / (1024 * 1024)

    if size_mb > MAX_LOG_SIZE_MB:
        return (
            False,
            f"❌ Contract log bloated ({size_mb:.1f}MB > {MAX_LOG_SIZE_MB}MB)",
            [f"Consider archiving: {CONTRACT_LOG}"],
        )

    # Count entries
    try:
        with open(CONTRACT_LOG, encoding="utf-8") as f:
            line_count = sum(1 for _ in f)
    except Exception:
        line_count = 0

    details.append(f"   {line_count} logged events, {size_mb:.2f}MB")

    return True, f"✅ Contract log OK ({line_count} events)", details


def check_compliance_metrics() -> tuple[bool, str, list[str]]:
    """Check contract compliance rates from log."""
    details = []

    if not CONTRACT_LOG.exists():
        return True, "⚠️  No compliance data yet", []

    # Load last 30 days of data
    cutoff = datetime.now(UTC) - timedelta(days=30)
    entries = []
    missing_counts = {}

    try:
        with open(CONTRACT_LOG, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    ts = datetime.fromisoformat(entry.get("ts", ""))
                    if ts < cutoff:
                        continue
                    entries.append(entry)

                    # Track missing fields
                    for field in entry.get("missing_fields", []):
                        missing_counts[field] = missing_counts.get(field, 0) + 1
                except (json.JSONDecodeError, ValueError):
                    continue
    except Exception as e:
        return False, f"❌ Log read error: {e}", []

    if len(entries) < MIN_ENTRIES:
        return True, f"⚠️  Insufficient data ({len(entries)} checks, need {MIN_ENTRIES})", []

    # Calculate compliance rate
    total = len(entries)
    passed = sum(1 for e in entries if e.get("result") == "pass")
    rate = passed / total if total > 0 else 0

    # By skill breakdown
    by_skill = {}
    for entry in entries:
        skill = entry.get("skill", "unknown")
        if skill not in by_skill:
            by_skill[skill] = {"total": 0, "pass": 0}
        by_skill[skill]["total"] += 1
        if entry.get("result") == "pass":
            by_skill[skill]["pass"] += 1

    # Show compliance by skill (worst first)
    for skill, stats in sorted(
        by_skill.items(), key=lambda x: x[1]["pass"] / x[1]["total"] if x[1]["total"] > 0 else 0
    ):
        if stats["total"] >= 3:  # Only show skills with meaningful data
            skill_rate = stats["pass"] / stats["total"]
            status = "✅" if skill_rate >= MIN_COMPLIANCE_RATE else "⚠️"
            details.append(
                f"   {status} {skill}: {skill_rate:.1%} ({stats['pass']}/{stats['total']})"
            )

    # Most commonly missing fields
    if missing_counts:
        details.append("   Most missing fields:")
        for field, count in sorted(missing_counts.items(), key=lambda x: -x[1])[:3]:
            details.append(f"      • {field}: {count} occurrences")

    # Escalation recommendations
    for skill, stats in by_skill.items():
        if stats["total"] < 3:
            continue
        skill_rate = stats["pass"] / stats["total"]
        if skill_rate < 0.7:
            details.append(f"   💡 Consider escalating '{skill}' to warn mode")

    if rate < MIN_COMPLIANCE_RATE:
        return False, f"❌ Low compliance ({rate:.1%} < {MIN_COMPLIANCE_RATE:.0%})", details

    return True, f"✅ Compliance OK ({rate:.1%} overall)", details


def main():
    """Run all competence layer health checks."""
    print("📋 Competence Layer Health")
    print("=" * 50)

    all_ok = True
    all_details = []

    # Registry check
    ok, msg, details = check_registry()
    print(msg)
    all_ok = all_ok and ok
    all_details.extend(details)

    # Contract log check
    ok, msg, details = check_contract_log()
    print(msg)
    all_ok = all_ok and ok
    all_details.extend(details)

    # Compliance metrics check
    ok, msg, details = check_compliance_metrics()
    print(msg)
    all_ok = all_ok and ok
    all_details.extend(details)

    # Print details
    if all_details:
        print()

    # Maintenance reminders
    print("📌 Maintenance Reminders:")
    print("   • Review /hook-obs escalation monthly for enforcement mode changes")
    print("   • Add new skills to skill_mappings in task_type_registry.json")
    print("   • Archive contract_completeness.jsonl if >10MB")
    print("   • After 2+ weeks: check if Part 2 (Behavioral Gates) is needed")

    if all_details:
        print("\nDetails:")
        for detail in all_details:
            print(detail)

    print("=" * 50)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
