#!/usr/bin/env python3
"""
skill_collision_check.py - Detect skill trigger/alias collisions

Run: python P:\\\\\\.claude/skills/_tools/skill_collision_check.py
Returns exit code 0 if healthy, 1 if collisions found

Checks:
1. Duplicate trigger patterns across skills
2. Duplicate aliases across skills
3. Trigger-alias overlaps (trigger in one skill = alias in another)
"""

import sys
from collections import defaultdict
from pathlib import Path

SKILLS_DIR = Path(r"P:\\\\\\.claude/skills")
ARCHIVE_PATTERNS = ["_archive", "backup", ".venv", "node_modules"]


def parse_skill_frontmatter(skill_path: Path) -> dict | None:
    """Parse YAML frontmatter from SKILL.md file."""
    try:
        content = skill_path.read_text(encoding="utf-8", errors="ignore")

        # Extract frontmatter between --- markers
        if not content.startswith("---"):
            return None

        end_marker = content.find("---", 3)
        if end_marker == -1:
            return None

        frontmatter = content[3:end_marker].strip()

        # Simple YAML parsing for triggers and aliases
        result = {
            "name": None,
            "triggers": [],
            "aliases": [],
            "path": str(skill_path.parent.relative_to(SKILLS_DIR)),
        }

        lines = frontmatter.split("\n")
        current_key = None

        for line in lines:
            stripped = line.strip()

            # Key detection
            if stripped.startswith("name:"):
                result["name"] = stripped[5:].strip().strip("\"'")
            elif stripped.startswith("triggers:"):
                current_key = "triggers"
            elif stripped.startswith("aliases:"):
                current_key = "aliases"
            elif stripped.startswith("- ") and current_key in ("triggers", "aliases"):
                value = stripped[2:].strip().strip("\"'")
                if value:
                    result[current_key].append(value)
            elif not stripped.startswith("-") and ":" in stripped:
                current_key = None  # New key, stop collecting

        return result

    except Exception:
        return None


def is_archived(path: Path) -> bool:
    """Check if path is in an archive/backup location."""
    path_str = str(path).lower()
    return any(pattern in path_str for pattern in ARCHIVE_PATTERNS)


def normalize_trigger(trigger: str) -> str:
    """Normalize trigger for comparison."""
    # Remove leading slash, lowercase
    return trigger.lstrip("/").lower().strip()


def find_collisions(skills: list[dict]) -> dict:
    """Find trigger and alias collisions across skills."""
    trigger_map = defaultdict(list)  # trigger -> [skill names]
    alias_map = defaultdict(list)  # alias -> [skill names]

    for skill in skills:
        name = skill["name"] or skill["path"]

        for trigger in skill["triggers"]:
            normalized = normalize_trigger(trigger)
            trigger_map[normalized].append(name)

        for alias in skill["aliases"]:
            normalized = normalize_trigger(alias)
            alias_map[normalized].append(name)

    collisions = {
        "trigger_duplicates": {},
        "alias_duplicates": {},
        "trigger_alias_overlaps": {},
    }

    # Find duplicate triggers
    for trigger, names in trigger_map.items():
        if len(names) > 1:
            collisions["trigger_duplicates"][trigger] = names

    # Find duplicate aliases
    for alias, names in alias_map.items():
        if len(names) > 1:
            collisions["alias_duplicates"][alias] = names

    # Find trigger-alias overlaps (different skills)
    for trigger, trigger_names in trigger_map.items():
        if trigger in alias_map:
            alias_names = alias_map[trigger]
            # Only flag if different skills
            overlap = set(trigger_names) ^ set(alias_names)
            if overlap and trigger_names != alias_names:
                collisions["trigger_alias_overlaps"][trigger] = {
                    "triggers": trigger_names,
                    "aliases": alias_names,
                }

    return collisions


def main():
    issues = []
    warnings = []

    # Find all SKILL.md files
    skill_files = list(SKILLS_DIR.rglob("SKILL.md"))
    active_skills = [f for f in skill_files if not is_archived(f)]

    # Parse all skills
    skills = []
    for skill_file in active_skills:
        parsed = parse_skill_frontmatter(skill_file)
        if parsed and (parsed["triggers"] or parsed["aliases"]):
            skills.append(parsed)

    # Find collisions
    collisions = find_collisions(skills)

    # Report trigger duplicates
    for trigger, names in collisions["trigger_duplicates"].items():
        if len(set(names)) > 1:  # Different skills, not same skill listed twice
            issues.append(f"Duplicate trigger '/{trigger}': {', '.join(set(names))}")

    # Report alias duplicates (less severe)
    for alias, names in collisions["alias_duplicates"].items():
        if len(set(names)) > 1:
            warnings.append(f"Duplicate alias '/{alias}': {', '.join(set(names))}")

    # Report trigger-alias overlaps
    for pattern, info in collisions["trigger_alias_overlaps"].items():
        t_names = set(info["triggers"])
        a_names = set(info["aliases"])
        if t_names != a_names:
            issues.append(
                f"Trigger/alias overlap '/{pattern}': trigger in {t_names}, alias in {a_names}"
            )

    # Output
    if issues or warnings:
        print("⚠️  SKILL COLLISION CHECK")
        print(f"   Skills analyzed: {len(skills)}")

        if issues:
            print("\n❌ COLLISIONS (routing ambiguity):")
            for i in issues[:10]:
                print(f"   • {i}")
            if len(issues) > 10:
                print(f"   ... and {len(issues) - 10} more")

        if warnings:
            print("\n⚡ WARNINGS:")
            for w in warnings[:5]:
                print(f"   • {w}")

        print("\nResolve by renaming triggers or consolidating skills")
        return 1
    else:
        print(f"✅ No skill collisions ({len(skills)} skills analyzed)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
