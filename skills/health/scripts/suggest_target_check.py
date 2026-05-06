#!/usr/bin/env python3
"""
Skill suggest: target validation.

Checks that every suggest: target in SKILL.md frontmatter resolves to
a real skill (directory exists or trigger matches).

Community pattern: https://github.com/travisvn/awesome-claude-skills
"""

from __future__ import annotations

import sys
from pathlib import Path

SKILLS_DIR = Path(__file__).parent.parent.parent  # P:/.claude/skills


def get_skill_triggers_and_names() -> tuple[set[str], dict[str, str]]:
    """Build set of all known skill names and trigger->skill mapping."""
    names: set[str] = set()
    triggers: dict[str, str] = {}

    for skill_dir in SKILLS_DIR.iterdir():
        if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
            continue
        sk = skill_dir / "SKILL.md"
        if not sk.exists():
            continue

        names.add(skill_dir.name)

        content = sk.read_text(encoding="utf-8")
        if not content.startswith("---"):
            continue

        parts = content.split("---", 2)
        if len(parts) < 2:
            continue

        try:
            import yaml

            fm = yaml.safe_load(parts[1])
        except Exception:
            continue

        for t in fm.get("triggers", []):
            triggers[t.lstrip("/")] = skill_dir.name
        for a in fm.get("aliases", []):
            triggers[a.lstrip("/")] = skill_dir.name

    return names, triggers


def check_suggest_targets() -> tuple[list[str], list[str]]:
    """Check all suggest: targets across all skills."""
    names, triggers = get_skill_triggers_and_names()

    missing: list[str] = []
    found: list[str] = []

    for skill_dir in SKILLS_DIR.iterdir():
        if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
            continue
        sk = skill_dir / "SKILL.md"
        if not sk.exists():
            continue

        content = sk.read_text(encoding="utf-8")
        if not content.startswith("---"):
            continue

        parts = content.split("---", 2)
        if len(parts) < 2:
            continue

        try:
            import yaml

            fm = yaml.safe_load(parts[1])
        except Exception:
            continue

        for target in fm.get("suggest") or []:
            # Target can be "/skill-name" or "/skill-name (description)"
            target_clean = target.lstrip("/").split()[0]
            if target_clean in triggers or target_clean in names:
                found.append(f"{skill_dir.name} → /{target_clean}")
            else:
                missing.append(f"{skill_dir.name} → /{target_clean}")

    return missing, found


def main() -> None:
    missing, found = check_suggest_targets()

    total = len(missing) + len(found)
    pct = int(len(found) / total * 100) if total > 0 else 100

    print("Suggest Target Validation")
    print("========================")
    print(f"Total suggest links: {total}")
    print(f"Valid targets: {len(found)} ({pct}%)")
    print(f"Missing targets: {len(missing)}")

    if missing:
        print(f"\n⚠️  Missing suggest targets ({len(missing)}):")
        for m in missing[:20]:
            print(f"   • {m}")
        if len(missing) > 20:
            print(f"   ... and {len(missing) - 20} more")
        print("\nStatus: WARNING")
        sys.exit(1)
    else:
        print("\n✅ All suggest targets resolve to existing skills")
        print("Status: HEALTHY")
        sys.exit(0)


if __name__ == "__main__":
    main()
