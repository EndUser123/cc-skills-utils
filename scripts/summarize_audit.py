#!/usr/bin/env python3
"""Summarize plugin audit results into prioritized, actionable recommendations.

Consumes structured audit data (JSON) and emits a prioritized action list
with specific fix commands — one-liners the user can copy-paste.

Finds: orphaned junctions, unregistered plugins, frontmatter mismatches,
drift types, broken hooks.json, hardcoded paths.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

FINDING_TYPES = ["ERROR", "WARNING", "ACTIONABLE"]


def _severity_key(f: dict) -> int:
    """ERROR=0, WARNING=1, ACTIONABLE=2 — lower number = higher priority."""
    t = f.get("type", "").upper()
    if t == "ERROR":
        return 0
    if t == "WARNING":
        return 1
    return 2


def _severity_label(f: dict) -> str:
    t = f.get("type", "").upper()
    if t == "ERROR":
        return "ERROR"
    if t == "WARNING":
        return "WARN"
    return "ACTION"


def summarize(json_path: Path) -> list[dict]:
    """Parse audit JSON and return prioritized action list."""
    if not json_path.exists():
        return []

    raw = json.loads(json_path.read_text(encoding="utf-8"))
    # Support both a list of findings and a wrapped dict with a 'findings' key
    if isinstance(raw, list):
        findings = raw
    elif isinstance(raw, dict):
        findings = raw.get("findings", [])
    else:
        findings = []

    actions: list[dict] = []

    for f in findings:
        kind = f.get("kind", f.get("type", ""))

        # Orphaned junction
        if "orphaned" in kind.lower() or "orphan" in kind.lower():
            plugin = f.get("plugin", "?")
            target = f.get("target", "?")
            actions.append({
                "type": "ERROR",
                "plugin": plugin,
                "what": f"Orphaned junction (target not found: {target})",
                "fix": f"Remove junction: Remove-Item 'P:/.claude-marketplace/plugins/{plugin}' -Force",
                "fix_also": f"Re-create junction: cmd /c mklink /J 'P:/.claude-marketplace/plugins/{plugin}' 'P:/packages/{plugin}'",
            })

        # Missing manifest
        elif "missing" in kind.lower() and "plugin.json" in kind:
            plugin = f.get("plugin", "?")
            actions.append({
                "type": "ERROR",
                "plugin": plugin,
                "what": "Missing .claude-plugin/plugin.json",
                "fix": "New-Item -Path 'P:/packages/" + plugin + "/.claude-plugin' -ItemType Directory; "
                       "@{'name'='" + plugin + "';'version'='1.0.0'}| ConvertTo-Json | Set-Content 'P:/packages/" + plugin + "/.claude-plugin/plugin.json'",
            })

        # Invalid JSON
        elif "invalid" in kind.lower() and "json" in kind.lower():
            plugin = f.get("plugin", "?")
            actions.append({
                "type": "ERROR",
                "plugin": plugin,
                "what": f"Invalid JSON in {f.get('file', '?')}",
                "fix": f"Validate and fix: python3 -c \"import json; json.load(open('P:/packages/{plugin}/.claude-plugin/plugin.json'))\"",
            })

        # Frontmatter name mismatch
        elif "name_mismatch" in kind.lower():
            plugin = f.get("plugin", "?")
            skill = f.get("skill", "?")
            frontmatter_name = f.get("frontmatter_name", "?")
            directory_name = f.get("directory_name", "?")
            actions.append({
                "type": "WARNING",
                "plugin": plugin,
                "what": f"SKILL.md has name='{frontmatter_name}' but directory is '{directory_name}/'",
                "fix": ("python3 -c \"import re; p='P:/packages/" + plugin + "/skills/" + skill + "/SKILL.md'; "
                        "c=open(p).read(); c=re.sub(r'name: " + frontmatter_name + "', 'name: " + directory_name + "', c); open(p,'w').write(c)\""),
            })

        # Missing name field
        elif "missing_name_field" in kind.lower():
            plugin = f.get("plugin", "?")
            skill = f.get("skill", "?")
            actions.append({
                "type": "WARNING",
                "plugin": plugin,
                "what": f"skills/{skill}/SKILL.md has no 'name' frontmatter field",
                "fix": ("python3 -c \"import re; p='P:/packages/" + plugin + "/skills/" + skill + "/SKILL.md'; "
                        "c=open(p).read(); c=re.sub(r'^---\\n', '---\\nname: " + skill + "\\n', c); open(p,'w').write(c)\""),
            })

        # Drift: source modified
        elif f.get("type") == "source_modified":
            plugin = f.get("plugin", "?")
            count = f.get("drift_count", 0)
            actions.append({
                "type": "ACTIONABLE",
                "plugin": plugin,
                "what": f"Source diverged from cache ({count} file(s))",
                "fix": f"python3 'P:/packages/cc-skills-utils/scripts/plugin-audit-and-fix.py' --packages-root 'P:/packages' --auto-fix --plugins {plugin}",
            })

        # Drift: stale version dirs
        elif f.get("type") == "stale_version_dirs":
            plugin = f.get("plugin", "?")
            stale = f.get("stale_versions", [])
            actions.append({
                "type": "ACTIONABLE",
                "plugin": plugin,
                "what": f"Stale version dirs: {stale}",
                "fix": f"Remove stale: Get-ChildItem 'C:/Users/brsth/.claude/plugins/cache/local/{plugin}' | Where-Object {{$_.Name -notin @('{f.get('current_version', '')}')}} | Remove-Item -Recurse -Force",
            })

        # Drift: cache-only
        elif f.get("type") == "cache_only":
            plugin = f.get("plugin", "?")
            count = f.get("cache_only_count", 0)
            actions.append({
                "type": "WARNING",
                "plugin": plugin,
                "what": f"Cache has {count} file(s) not in source (deleted from source)",
                "fix": f"Investigate: git -C 'P:/packages/{plugin}' log --diff-filter=D --summary --oneline | Select-String '{plugin}' | Select-Object -First 5",
            })

        # Unregistered plugin (found in marketplace plugins dir but not in marketplace.json)
        elif f.get("type") == "unregistered":
            plugin = f.get("plugin", "?")
            actions.append({
                "type": "ACTIONABLE",
                "plugin": plugin,
                "what": "Plugin in marketplace but not in marketplace.json",
                "fix": f"/cc-skills-utils:plugin-installer add {plugin}",
            })

        # Hardcoded path
        elif "hardcoded" in kind.lower() or "hardcoded" in str(f.get("what", "")).lower():
            plugin = f.get("plugin", "?")
            actions.append({
                "type": "ACTIONABLE",
                "plugin": plugin,
                "what": f"Hardcoded path: {f.get('issue', f.get('what', '?'))}",
                "fix": f"python3 'P:/packages/cc-skills-utils/scripts/plugin-audit-and-fix.py' --packages-root 'P:/packages' --auto-fix --scan-paths --plugins {plugin}",
            })

        # Broken hook command file
        elif "not found" in kind.lower() and "file" in kind.lower():
            plugin = f.get("plugin", "?")
            actions.append({
                "type": "ERROR",
                "plugin": plugin,
                "what": f"Hook command file not found: {f.get('file', '?')}",
                "fix": f"Verify: Get-ChildItem -Recurse 'P:/packages/{plugin}/hooks' -Filter '*.py' | Select-Object FullName",
            })

        # Orphan skill junction (skill in cluster but also separate junction)
        elif f.get("type") == "orphan_skill_junction":
            plugin = f.get("marketplace_entry", "?")
            cluster = f.get("cluster", "?")
            skill = f.get("skill", "?")
            actions.append({
                "type": "ACTIONABLE",
                "plugin": plugin,
                "what": f"'{plugin}' is a junction to a skill already in cluster '{cluster}'",
                "fix": f"Remove redundant junction: Remove-Item 'P:/.claude-marketplace/plugins/{plugin}' -Force; "
                       f"The skill is already available via /{cluster}:{skill}",
            })

        # Generic error/warning
        elif f.get("errors"):
            for e in f.get("errors", []):
                plugin = f.get("plugin", "?")
                actions.append({
                    "type": "ERROR",
                    "plugin": plugin,
                    "what": str(e),
                    "fix": None,
                })
        elif f.get("warnings"):
            for w in f.get("warnings", []):
                plugin = f.get("plugin", "?")
                actions.append({
                    "type": "WARNING",
                    "plugin": plugin,
                    "what": str(w),
                    "fix": None,
                })

    # Sort by severity then plugin name
    actions.sort(key=lambda x: (_severity_key(x), x.get("plugin", "")))
    return actions


def print_summary(actions: list[dict]) -> None:
    """Print prioritized action list in human-readable format."""
    if not actions:
        print("No findings. All plugins OK.")
        return

    # Group by plugin
    by_plugin: dict[str, list[dict]] = {}
    for a in actions:
        by_plugin.setdefault(a["plugin"], []).append(a)

    print("\n=== Plugin Audit — Prioritized Actions ===\n")

    error_count = sum(1 for a in actions if a["type"] == "ERROR")
    warn_count = sum(1 for a in actions if a["type"] == "WARNING")
    action_count = sum(1 for a in actions if a["type"] == "ACTIONABLE")

    if error_count:
        print(f"ERRORS   : {error_count}")
    if warn_count:
        print(f"WARNINGS : {warn_count}")
    if action_count:
        print(f"ACTIONS  : {action_count}")
    print()

    for plugin, plugin_actions in sorted(by_plugin.items()):
        has_errors = any(a["type"] == "ERROR" for a in plugin_actions)
        tag = "ERROR" if has_errors else ("WARN" if any(a["type"] == "WARNING" for a in plugin_actions) else "OK")
        print(f"[{tag}] {plugin}")

        for a in plugin_actions:
            icon = "✗" if a["type"] == "ERROR" else ("!" if a["type"] == "WARNING" else "→")
            print(f"    {icon} {a['what']}")
            if a["fix"]:
                print(f"      Fix: {a['fix']}")
        print()


def machine_summary(actions: list[dict]) -> dict:
    """Return machine-readable summary dict."""
    return {
        "total": len(actions),
        "errors": sum(1 for a in actions if a["type"] == "ERROR"),
        "warnings": sum(1 for a in actions if a["type"] == "WARNING"),
        "actionable": sum(1 for a in actions if a["type"] == "ACTIONABLE"),
        "by_plugin": {p: len(aa) for p, aa in ((p, [a for a in actions if a["plugin"] == p]) for p in set(a["plugin"] for a in actions))},
        "needs_attention": sorted(set(a["plugin"] for a in actions if a["type"] in ("ERROR", "WARNING"))),
        "actionable_plugins": sorted(set(a["plugin"] for a in actions if a["type"] == "ACTIONABLE")),
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        # Run audit inline and summarize
        import subprocess
        result = subprocess.run(
            ["python3", "P:/packages/cc-skills-utils/scripts/plugin-audit-and-fix.py",
             "--packages-root", "P:/packages", "--auto-fix"],
            capture_output=True, text=True
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode

    json_path = Path(argv[1])
    actions = summarize(json_path)
    print_summary(actions)

    # Also emit machine summary as JSON comment
    ms = machine_summary(actions)
    print(f"\n# Machine summary: {json.dumps(ms)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))