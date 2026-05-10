#!/usr/bin/env python3
"""
settings_health_check.py - Detect when P:\\\\\\.claude/settings.json needs optimization

Run: python P:\\\\\\.claude/hooks/settings_health_check.py
Returns exit code 0 if healthy, 1 if issues found

Checks:
1. File size/line count thresholds
2. Dead env vars (defined but unreferenced)
3. Duplicate entries
4. Disabled-but-present hooks
5. Embedded documentation blocks
6. Misplaced lifecycle hooks
"""

import glob
import json
import sys
from pathlib import Path

# Thresholds
MAX_LINES = 900
MAX_SIZE_KB = 35
MAX_ENV_VARS = 70
MAX_HOOK_ENTRIES = 60

# Subdirectories to skip (reduces scan scope)
SKIP_DIRS = {"skills", "hooks", "agents", "state", "history", "sessions", "__pycache__"}

# Known system/Claude-provided vars (don't flag as dead)
SYSTEM_VARS = {
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "ELEVENLABS_API_KEY",
    "CLAUDE_SESSION_ID",
    "CLAUDE_CONVERSATION_ID",
    "CLAUDE_TOOL_NAME",
    "CLAUDE_CWD",
    "CLAUDE_PROJECT_DIR",
    "CLAUDE_ENVIRONMENT",
    "HF_HOME",
    "SENTENCE_TRANSFORMERS_HOME",
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS",  # Claude Code platform var, not a Python hook
    "MULTI_AGENT_ENABLED",  # Claude Code agent teams config
    "OBLIGATION_TTL_SECONDS",  # Claude Code internal timeout
    "STRAWBERRY_VALIDATOR_ENABLED",  # Strawberry validation flag
    "STRAWBERRY_VALIDATOR_VERBOSE",  # Strawberry validation verbosity
}

# Cache file for known env vars (avoid re-scanning)
CACHE_FILE = Path("P:\\\\\\.claude/state/settings_vars_cache.json")


def load_settings():
    with open(r"P:\\\\\\.claude/settings.json") as f:
        return json.load(f)


def get_file_stats():
    path = Path(r"P:\\\\\\.claude/settings.json")
    content = path.read_text(encoding="utf-8")
    return {
        "lines": len(content.splitlines()),
        "size_kb": path.stat().st_size / 1024,
    }


def find_referenced_vars():
    """Scan active .py files for env var references."""
    referenced = set()
    for f in glob.glob(r"P:\\\\\\.claude/**/*.py", recursive=True):
        if "_archive" in f or "backup" in f:
            continue
        try:
            content = open(f, encoding="utf-8", errors="ignore").read()
            # Quick scan for quoted uppercase identifiers
            import re

            matches = re.findall(r'["\']([A-Z][A-Z0-9_]{2,})["\']', content)
            referenced.update(matches)
        except:
            pass
    return referenced


def check_dead_env_vars(settings, referenced):
    """Find env vars defined but not referenced."""
    defined = set(settings.get("env", {}).keys())
    dead = defined - referenced - SYSTEM_VARS
    return list(dead)


def check_duplicates(settings):
    """Check for duplicate entries."""
    issues = []

    # Check skillPaths
    skill_paths = settings.get("skills", {}).get("skillPaths", [])
    if len(skill_paths) != len(set(skill_paths)):
        issues.append("Duplicate skillPaths entries")

    return issues


def check_disabled_hooks(settings):
    """Find hooks controlled by ENABLED=false vars."""
    env = settings.get("env", {})
    disabled_vars = [
        k for k, v in env.items() if k.endswith("_ENABLED") and str(v).lower() in ("false", "0")
    ]
    return disabled_vars


def check_embedded_docs(settings):
    """Check for large documentation blocks that should be extracted."""
    issues = []

    # Known doc-like keys
    doc_keys = ["hook_architecture", "design_philosophy", "migration_history"]

    def check_obj(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                curr_path = f"{path}.{k}" if path else k
                for doc_key in doc_keys:
                    if doc_key in k.lower():
                        issues.append(f"Embedded docs: {curr_path}")
                check_obj(v, curr_path)

    check_obj(settings)
    return issues


def check_misplaced_hooks(settings):
    """Find hooks in wrong lifecycle."""
    issues = []
    hooks = settings.get("hooks", {})

    # PreToolUse hooks should not be in SessionEnd
    session_end = hooks.get("SessionEnd", [])
    for entry in session_end:
        for hook in entry.get("hooks", []):
            cmd = hook.get("command", "")
            if "PreToolUse" in cmd or "UserPromptSubmit" in cmd:
                issues.append(f"Misplaced hook in SessionEnd: {cmd}")

    return issues


def count_hook_entries(settings):
    """Count total hook entries."""
    count = 0
    for lifecycle, entries in settings.get("hooks", {}).items():
        for entry in entries:
            count += len(entry.get("hooks", []))
    return count


def main():
    issues = []
    warnings = []

    settings = load_settings()
    stats = get_file_stats()

    # 1. Size checks
    if stats["lines"] > MAX_LINES:
        issues.append(f"Line count {stats['lines']} exceeds {MAX_LINES}")
    if stats["size_kb"] > MAX_SIZE_KB:
        issues.append(f"File size {stats['size_kb']:.1f}KB exceeds {MAX_SIZE_KB}KB")

    # 2. Env var count
    env_count = len(settings.get("env", {}))
    if env_count > MAX_ENV_VARS:
        issues.append(f"Env vars {env_count} exceeds {MAX_ENV_VARS}")

    # 3. Dead env vars (always run - archive-only or unreferenced vars)
    referenced = find_referenced_vars()
    dead = check_dead_env_vars(settings, referenced)
    if dead:
        for var in sorted(dead):
            warnings.append(f"Orphaned env var (no active hook reads it): {var}")

    # 4. Duplicates
    dups = check_duplicates(settings)
    issues.extend(dups)

    # 5. Disabled hooks
    disabled = check_disabled_hooks(settings)
    if len(disabled) > 3:
        warnings.append(f"Found {len(disabled)} disabled-but-defined hooks")

    # 6. Embedded docs
    docs = check_embedded_docs(settings)
    issues.extend(docs)

    # 7. Misplaced hooks
    misplaced = check_misplaced_hooks(settings)
    issues.extend(misplaced)

    # 8. Hook count
    hook_count = count_hook_entries(settings)
    if hook_count > MAX_HOOK_ENTRIES:
        warnings.append(f"Hook entries {hook_count} exceeds {MAX_HOOK_ENTRIES}")

    # Output
    if issues or warnings:
        print("⚠️  SETTINGS HEALTH CHECK")
        print(
            f"   Lines: {stats['lines']} | Size: {stats['size_kb']:.1f}KB | Env: {env_count} | Hooks: {hook_count}"
        )
        if issues:
            print("\n❌ ISSUES:")
            for i in issues:
                print(f"   • {i}")
        if warnings:
            print("\n⚡ WARNINGS:")
            for w in warnings:
                print(f"   • {w}")
        print("\nRun: claude 'optimize P:\\\\\\.claude/settings.json'")
        return 1
    else:
        print(
            f"✅ settings.json healthy ({stats['lines']} lines, {stats['size_kb']:.1f}KB, {env_count} env, {hook_count} hooks)"
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
