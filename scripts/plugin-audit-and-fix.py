#!/usr/bin/env python3
"""
Claude Code Plugin Audit & Fix Tool

Audits plugin directories for:
  - Broken symlinks
  - Invalid JSON manifests
  - Malformed hooks.json
  - Hardcoded paths
  - Missing required files
  - Conflicting skill/command names across global and local dirs
Can auto-fix:
  - Invalid JSON
  - Missing hooks.json (creates empty)
  - Broken symlinks (removes or recreates)
  - Stale .claude/.state dirs inside skills/ subdirectories
Can validate:
  - Run 'claude plugin validate' on each plugin
"""
from __future__ import annotations
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import print as rprint
except ImportError:
    Console = None
    Table = None
    Panel = None
    def rprint(*args, **kwargs):
        print(*args, **kwargs)
C_RESET = "[0m"
C_RED = "[91m"
C_YELLOW = "[93m"
C_CYAN = "[96m"
C_GREEN = "[92m"
def _detect_marketplace_root(script_path: str, cli_root: Optional[str] = None) -> Optional[str]:
    """Detect marketplace root from CLI root, env var, or script location."""
    if cli_root:
        packages_root = Path(cli_root)
        # Check for .claude-marketplace subdir (packages root scenario)
        mp_dir = packages_root / ".claude-marketplace"
        if mp_dir.exists():
            return str(mp_dir)
        # Fallback: treat as marketplace root itself
        if packages_root.exists() and (packages_root / "plugins").exists():
            return str(packages_root)
    env_root = os.environ.get("CLAUDE_MARKETPLACE_ROOT") or os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env_root:
        root = Path(env_root)
        for parent in [root, root.parent, root.parent.parent]:
            mp_dir = parent / ".claude-marketplace"
            if mp_dir.exists():
                return str(mp_dir)
        if root.exists() and (root / "plugins").exists():
            return str(root)
    script_dir = Path(script_path).resolve().parent
    if script_dir.name == "scripts":
        mp_dir = script_dir.parent / ".claude-marketplace"
        if mp_dir.exists():
            return str(mp_dir)
        mp_dir = script_dir.parent.parent / ".claude-marketplace"
        if mp_dir.exists():
            return str(mp_dir)
    return None
def _load_json(path: Path) -> tuple[bool, Optional[dict]]:
    """Load JSON safely, return (success, data)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return True, json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return False, None
def _save_json(path: Path, obj: dict) -> bool:
    """Save JSON safely, return success."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)
        return True
    except OSError:
        return False
def audit_plugins(plugins_dir: Path, marketplace_root: str, plugin_filter: Optional[str] = None) -> list[dict]:
    """Audit plugin directories and manifests."""
    results = []
    if not plugins_dir.exists():
        return results
    for plugin in sorted(plugins_dir.iterdir()):
        if plugin.name.startswith(".") or not plugin.is_dir():
            continue
        if plugin_filter and plugin.name != plugin_filter:
            continue
        result = {"plugin": plugin.name, "errors": [], "warnings": [], "fixed": False}

        # Check for orphaned junctions (target doesn't exist)
        is_junction = plugin.is_symlink()
        if is_junction:
            try:
                target = os.readlink(str(plugin))
                if not Path(target).exists():
                    result["errors"].append(f"Orphaned junction (target not found: {target})")
            except OSError:
                pass

        # Check plugin.json
        manifest_path = plugin / ".claude-plugin" / "plugin.json"
        if not manifest_path.exists():
            result["warnings"].append("Missing .claude-plugin/plugin.json")
            marketplace_json = plugin / "marketplace.json"
            if marketplace_json.exists():
                result["warnings"].append("Has marketplace.json but no .claude-plugin/plugin.json")
        else:
            ok, data = _load_json(manifest_path)
            if not ok:
                result["errors"].append("Invalid .claude-plugin/plugin.json")
            elif "name" not in data:
                result["warnings"].append("Missing name in plugin manifest")
        # Check marketplace.json
        mp_json = plugin / "marketplace.json"
        if mp_json.exists():
            ok, data = _load_json(mp_json)
            if not ok:
                result["errors"].append("Invalid marketplace.json")
            else:
                # Warn if .claude-plugin/marketplace.json is missing
                subdir_mp = plugin / ".claude-plugin" / "marketplace.json"
                if not subdir_mp.exists():
                    result["warnings"].append(
                        ".claude-plugin/marketplace.json missing (root marketplace.json exists — auto-fixable)"
                    )
        # Check hooks.json (at hooks/hooks.json)
        hooks_path = plugin / "hooks" / "hooks.json"
        if hooks_path.exists():
            ok, data = _load_json(hooks_path)
            if not ok:
                result["errors"].append("Invalid hooks/hooks.json")
            elif not isinstance(data, dict):
                result["errors"].append("hooks/hooks.json must be a dict")
            elif "hooks" not in data:
                result["errors"].append("hooks/hooks.json missing required 'hooks' key")
            else:
                # Validate hook entry structure: each event entry needs matcher + hooks array
                for event, entries in data.get("hooks", {}).items():
                    if not isinstance(entries, list):
                        result["errors"].append(f"hooks.{event} must be a list")
                        continue
                    for i, entry in enumerate(entries):
                        if not isinstance(entry, dict):
                            result["errors"].append(f"hooks.{event}[{i}] must be a dict")
                            continue
                        if "matcher" not in entry:
                            result["errors"].append(f"hooks.{event}[{i}] missing 'matcher' field")
                        if "hooks" not in entry:
                            result["errors"].append(f"hooks.{event}[{i}] missing 'hooks' array")
                        elif not isinstance(entry["hooks"], list):
                            result["errors"].append(f"hooks.{event}[{i}].hooks must be an array")
                        else:
                            for j, hook in enumerate(entry["hooks"]):
                                if not isinstance(hook, dict):
                                    result["errors"].append(f"hooks.{event}[{i}].hooks[{j}] must be a dict")
                                elif "type" not in hook or "command" not in hook:
                                    result["errors"].append(f"hooks.{event}[{i}].hooks[{j}] missing 'type' or 'command'")
                                elif hook.get("type") == "command":
                                    cmd = hook.get("command", "")
                                    # $CLAUDE_PLUGIN_ROOT/%CLAUDE_PLUGIN_ROOT% is the correct runtime convention.
                                    # Skip path-existence check — it will expand correctly at hook execution time.
                                    has_runtime_env = (
                                        "$CLAUDE_PLUGIN_ROOT" in cmd
                                        or "%CLAUDE_PLUGIN_ROOT%" in cmd.lower()
                                    )
                                    if "$$" in cmd:
                                        result["errors"].append(
                                            f"Hook command contains double-dollar (corrupted variable): {cmd[:80]}"
                                        )
                                    # Extract script path from command (handles "python script.py --args", "node script.js", etc.)
                                    parts = cmd.split()
                                    if parts:
                                        script_path = Path(parts[-1].strip('"').strip("'"))
                                        # Pre-expand runtime env vars BEFORE relative-path prefix
                                        # to prevent double-prefix when path is not absolute
                                        path_str = str(script_path)
                                        env_vars = {"CLAUDE_PLUGIN_ROOT": str(plugin)}
                                        for var, replacement in env_vars.items():
                                            if var in path_str:
                                                path_str = path_str.replace(f"${var}", replacement)
                                        script_path = Path(path_str)
                                        # Resolve relative paths from plugin root (only if still relative after expansion)
                                        if not script_path.is_absolute():
                                            script_path = plugin / script_path
                                        # Only check existence for non-runtime commands (no $CLAUDE_PLUGIN_ROOT/%VAR%)
                                        if not has_runtime_env and not script_path.exists():
                                            result["errors"].append(f"Hook command file not found: {script_path}")
        # Check for .claude/.state inside skill subdirectories (not at plugin root)
        skills_dir = plugin / "skills"
        if skills_dir.is_dir():
            for skill_item in skills_dir.iterdir():
                if skill_item.is_dir():
                    for bad in [".claude", ".state"]:
                        bad_dir = skill_item / bad
                        if bad_dir.exists() and bad_dir.is_dir():
                            result["errors"].append(f"{bad}/ inside skills/{skill_item.name}/ (should be at plugin root)")
        # Check for build artifacts in plugin root
        build_artifacts = ["__pycache__", ".venv", "venv", "node_modules", ".pytest_cache", ".git"]
        gitignore_path = plugin / ".gitignore"
        gitignored = set()
        if gitignore_path.exists():
            with open(gitignore_path, encoding="utf-8") as f:
                gitignored = {line.strip() for line in f if line.strip() and not line.startswith("#")}
        for artifact in build_artifacts:
            artifact_path = plugin / artifact
            if not artifact_path.exists():
                continue
            # .git is always a directory in a repo; check if it's actually gitignored or has a real remote
            if artifact == ".git":
                if ".git" in gitignored:
                    continue
                # Skip warning if plugin is a real git repo with a remote — .git is appropriate there
                try:
                    check = __import__("subprocess").run(
                        ["git", "remote", "get-url", "origin"],
                        cwd=str(plugin),
                        capture_output=True, text=True, timeout=5,
                    )
                    if check.returncode == 0 and check.stdout.strip():
                        continue  # has real remote, .git is legitimate
                except Exception:
                    pass
                # No remote detected — likely a stray clone, warn about it
                result["warnings"].append(f"Build artifact '.git' in plugin root (should be gitignored)")
            else:
                # For other artifacts, only warn if not gitignored
                if artifact in gitignored or artifact + "/" in gitignored:
                    continue
            result["warnings"].append(f"Build artifact '{artifact}' in plugin root (should be gitignored)")
# Check for state/data files in plugin root (state should be in P:\\\\.claude/.artifacts/<terminal_id>/)
        for fpath in plugin.iterdir():
            if fpath.is_file() and any(fpath.suffix == ext for ext in [".data.json", ".meta.json", ".state.json"]):
                result["warnings"].append(f"State file '{fpath.name}' in plugin root (should use P:\\\\.claude/.artifacts/<terminal_id>/)")

        # Check for .claude/ anywhere in the plugin tree (except .claude-plugin/ manifest dir)
        # Workspace-typical entries are legitimate for packages that serve as dev workspaces.
        _workspace_entries = {"hooks", ".artifacts", "settings.local.json", "CLAUDE.md"}
        for bad_claude in plugin.rglob(".claude"):
            # .claude-plugin/ is the legitimate plugin manifest directory — skip it
            if str(bad_claude).endswith(".claude-plugin") or bad_claude.name == ".claude-plugin":
                continue
            if not bad_claude.is_dir():
                continue
            rel = bad_claude.relative_to(plugin)
            entries = [e.name for e in bad_claude.iterdir()]
            non_workspace = [e for e in entries if e not in _workspace_entries]
            if not non_workspace:
                continue
            result["errors"].append(
                f".claude/ at {rel} (should be removed; {len(entries)} entries: {entries[:3]}{'...' if len(entries) > 3 else ''})"
            )
        results.append(result)
    return results
def audit_marketplace(marketplace_root: str) -> list[dict]:
    """Audit marketplace.json."""
    results = []
    mp_path = Path(marketplace_root) / "marketplace.json"
    if not mp_path.exists():
        results.append({"file": "marketplace.json", "error": "marketplace.json not found in marketplace root"})
        return results
    ok, data = _load_json(mp_path)
    if not ok:
        results.append({"file": "marketplace.json", "error": "Invalid JSON"})
        return results
    if "plugins" not in data:
        results.append({"file": "marketplace.json", "warning": "No plugins array"})
        return results

    # Check for unregistered plugins: junctions in plugins/ not in marketplace.json
    registered = {p.get("name", "") for p in data.get("plugins", [])}
    plugins_dir = Path(marketplace_root) / "plugins"
    if plugins_dir.exists():
        for entry in sorted(plugins_dir.iterdir()):
            if entry.name.startswith("."):
                continue
            if entry.name not in registered:
                results.append({
                    "file": "marketplace.json",
                    "warning": f"Unregistered: {entry.name} has junction but is not in marketplace.json",
                    "fix": f"Run: /cc-skills-utils:plugin-installer add {entry.name}",
                })

    return results
def _scan_paths(file_path: Path, plugin_name: str) -> list[str]:
    """Scan a file for hardcoded paths."""
    issues = []
    try: content = file_path.read_text(errors="ignore")
    except OSError:
        return issues
    patterns = [
        r"[A-Za-z]:\\[^'\"]+",  # Windows paths
        r"/home/[^'\"]+",         # Linux home paths
        r"/Users/[^'\"]+",       # macOS paths
        r"/Volumes/[^'\"]+",    # macOS volumes
        r"P:\\\\\\\[^'\"]+",        # Explicit P: drives
    ]
    for pattern in patterns:
        source = re.sub(r"^\./", "", content, flags=re.MULTILINE)
        for match in re.finditer(pattern, source):
            issues.append(f"Hardcoded path: {match.group()}")
    return issues
def scan_source_paths(plugins_dir: Path) -> list[dict]:
    """Recursively scan source files for hardcoded paths."""
    findings = []
    if not plugins_dir.exists():
        return findings
    exts = {".py", ".js", ".ts", ".sh", ".bash", ".md", ".yaml", ".yml", ".json"}
    for plugin in plugins_dir.iterdir():
        if plugin.name.startswith("."):
            continue
        for fpath in plugin.rglob("*"):
            if fpath.is_file() and fpath.suffix in exts:
                issues = _scan_paths(fpath, plugin.name)
                for issue in issues:
                    findings.append({"plugin": plugin.name, "file": str(fpath.relative_to(plugin)), "issue": issue})
    return findings

def audit_orphan_skill_junctions(plugins_dir: Path) -> list[dict]:
    """Detect marketplace entries that are junctions to skills already inside a cluster package.

    A cluster package is any plugin that has .claude-plugin/plugin.json AND a skills/ directory
    with multiple skills. If a marketplace entry is a junction pointing to a subdirectory inside
    another cluster package's skills/ dir, it's redundant — the cluster already provides it.
    """
    findings: list[dict] = []
    if not plugins_dir.exists():
        return findings

    # Build map: cluster_name -> set of skill names it provides
    cluster_skills: dict[str, set[str]] = {}
    for plugin in plugins_dir.iterdir():
        if plugin.name.startswith(".") or not plugin.is_dir():
            continue
        manifest = plugin / ".claude-plugin" / "plugin.json"
        skills_dir = plugin / "skills"
        if manifest.exists() and skills_dir.is_dir():
            skill_names = set()
            for skill in skills_dir.iterdir():
                if skill.is_dir() and (skill / "SKILL.md").exists():
                    skill_names.add(skill.name)
            if len(skill_names) >= 2:  # Clusters have multiple skills
                cluster_skills[plugin.name] = skill_names

    # Check each plugin: is it a junction pointing into a cluster's skills/?
    for plugin in plugins_dir.iterdir():
        if plugin.name.startswith(".") or not plugin.is_dir():
            continue
        # Skip cluster packages themselves
        if plugin.name in cluster_skills:
            continue

        # Resolve junction target
        target = None
        try:
            target = os.readlink(str(plugin))
        except OSError:
            continue

        if not target:
            continue

        # Normalize path separators
        target_norm = target.replace("\\", "/").replace("/p/", "P:" + chr(92))

        # Check if target points into a cluster's skills/ subdirectory
        for cluster_name, skill_names in cluster_skills.items():
            # Pattern: P:\\\\\packages/{cluster}/skills/{skill_name}
            prefix = f"P:\\\\packages/{cluster_name}/skills/"
            if target_norm.startswith(prefix):
                skill_name = target_norm[len(prefix):]
                if skill_name in skill_names:
                    findings.append({
                        "type": "orphan_skill_junction",
                        "marketplace_entry": plugin.name,
                        "target": target_norm,
                        "cluster": cluster_name,
                        "skill": skill_name,
                        "issue": f"'{plugin.name}' is a junction to a skill already provided by cluster '{cluster_name}'",
                    })
                    break

    return findings


def _version_key(v: Path) -> tuple:
    """Sort version directories: latest version first, oldest last.
    Treats version components as integers for proper numeric ordering (2.1.4 > 2.1.3).
    """
    parts = v.name.split(".")
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return (0, 0, 0)


_BIDIR_SKIP_DIRS = {".git", ".claude", "__pycache__", ".pytest_cache", ".mypy_cache", ".venv", "node_modules"}
_BIDIR_SKIP_EXTS = {".pyc", ".pyo"}


def bidir_sync(source: Path, cache: Path) -> dict:
    """Bidirectional sync between source and cache directories.

    For each file that differs, keeps whichever copy has the newer mtime.
    Files only in source are copied to cache. Files only in cache are
    copied to source (preserves work done directly in cache).

    Returns dict with stats: {src_to_cache, cache_to_src, skipped, errors}.
    """
    import shutil
    stats = {"src_to_cache": 0, "cache_to_src": 0, "skipped": 0, "conflicts": [], "errors": []}

    if not source.exists() or not cache.exists():
        stats["errors"].append(f"Missing directory: source={source.exists()}, cache={cache.exists()}")
        return stats

    # Collect relative paths from both sides
    src_files: dict[str, Path] = {}
    cache_files: dict[str, Path] = {}

    def _walk(base: Path, into: dict[str, Path]) -> None:
        for fpath in base.rglob("*"):
            if not fpath.is_file():
                continue
            if any(skip in fpath.parts for skip in _BIDIR_SKIP_DIRS):
                continue
            if fpath.suffix in _BIDIR_SKIP_EXTS:
                continue
            into[str(fpath.relative_to(base))] = fpath

    _walk(source, src_files)
    _walk(cache, cache_files)

    all_keys = set(src_files) | set(cache_files)

    for rel in sorted(all_keys):
        src_file = src_files.get(rel)
        cache_file = cache_files.get(rel)

        if src_file and cache_file:
            # Both exist — compare content
            try:
                if src_file.read_bytes() == cache_file.read_bytes():
                    continue  # identical, skip
            except OSError:
                pass

            # Content differs — skip, report conflict. I (the LLM) will read both
            # and apply the better version inline. No automatic winner based on mtime.
            stats["conflicts"].append(str(rel))
            dest_dir = cache_file.parent
            dest_dir.mkdir(parents=True, exist_ok=True)
            # Preserve both — copy neither direction, just mark conflict
            continue

        elif src_file and not cache_file:
            # Only in source — copy to cache
            dest = cache / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(str(src_file), str(dest))
                stats["src_to_cache"] += 1
            except OSError as e:
                stats["errors"].append(f"copy src→cache {rel}: {e}")

        elif cache_file and not src_file:
            # Only in cache — preserve in cache, don't copy to source
            # (cache-only files are not source changes, they are cache artifacts)
            stats["skipped"] += 1

    return stats


def audit_source_cache_drift(plugins_dir: Path) -> list[dict]:
    """Detect drift between source packages and their cache copies.

    Source is truth. Cache lives at ~/.claude/plugins/cache/local/{name}/{version}/.
    Three drift types detected:
      1. source_modified: files in source changed since cache was installed
      2. cache_only: files in cache that don't exist in source (deleted from source)
      3. stale_version: old version directories in cache that should be purged
    """
    findings: list[dict] = []
    if not plugins_dir.exists():
        return findings

    cache_root = Path(os.path.expanduser("~/.claude/plugins/cache/local"))

    for plugin in plugins_dir.iterdir():
        if plugin.name.startswith(".") or not plugin.is_dir():
            continue

        source_dir = plugins_dir / plugin.name
        if not source_dir.exists():
            continue

        # Get version from manifest
        manifest = source_dir / ".claude-plugin" / "plugin.json"
        src_version = "?"
        if manifest.exists():
            try:
                src_version = json.load(open(manifest)).get("version", "?")
            except Exception:
                pass

        cache_dir = cache_root / plugin.name
        if not cache_dir.exists():
            continue

        # Find versioned directories — sort latest first
        version_dirs = sorted([d for d in cache_dir.iterdir() if d.is_dir()], key=_version_key, reverse=True)
        if not version_dirs:
            continue

        current_version_dir = version_dirs[0]

        # Check for stale version directories (older than current)
        stale_versions = [d for d in version_dirs if d != current_version_dir]
        if stale_versions:
            findings.append({
                "type": "stale_version_dirs",
                "plugin": plugin.name,
                "current_version": current_version_dir.name,
                "stale_versions": [d.name for d in stale_versions],
                "issue": f"'{plugin.name}' has {len(stale_versions)} stale version dir(s): {[d.name for d in stale_versions]}",
            })

        # Check drift against the LATEST (current) version directory only
        drift_files: list[str] = []
        cache_only_files: list[str] = []
        key_patterns = ["**/*.py", "**/*.json", "**/SKILL.md"]
        src_files_set: set[str] = set()
        cache_files_set: set[str] = set()

        for pattern in key_patterns:
            for src_file in source_dir.glob(pattern):
                if ".git" in src_file.parts or "__pycache__" in str(src_file):
                    continue
                rel = src_file.relative_to(source_dir)
                src_files_set.add(str(rel))
                cache_file = current_version_dir / rel
                if cache_file.exists():
                    cache_files_set.add(str(rel))
                    try:
                        if src_file.read_text(encoding="utf-8", errors="ignore") != cache_file.read_text(encoding="utf-8", errors="ignore"):
                            drift_files.append(str(rel))
                    except OSError:
                        pass

        if drift_files:
            findings.append({
                "type": "source_modified",
                "plugin": plugin.name,
                "cache_version": current_version_dir.name,
                "drift_count": len(drift_files),
                "sample_files": drift_files[:5],
                "issue": f"'{plugin.name}' cache ({current_version_dir.name}) has {len(drift_files)} file(s) diverged from source",
            })

        # Detect cache-only files (in cache but not in source — deleted from source)
        cache_only = cache_files_set - src_files_set
        if cache_only:
            findings.append({
                "type": "cache_only",
                "plugin": plugin.name,
                "cache_version": current_version_dir.name,
                "cache_only_count": len(cache_only),
                "cache_only_files": sorted(cache_only)[:5],
                "issue": f"'{plugin.name}' cache has {len(cache_only)} file(s) not in source (deleted from source)",
            })

    return findings


def audit_name_conflicts() -> list[dict]:
    """Check for conflicting skill and command names across global and local skill/command dirs."""
    findings = []
    # Collect skills/commands from: ~/.claude/ and P:\\\\.claude/
    skill_dirs = [
        Path(os.path.expanduser("~/.claude/skills")),
        Path(r"P:\\\\\.claude/skills"),
    ]
    cmd_dirs = [
        Path(os.path.expanduser("~/.claude/commands")),
        Path(r"P:\\\\\.claude/commands"),
    ]
    # Collect skill names (subdirectory with SKILL.md or .md file under skills/)
    skill_names: dict[str, list[str]] = {}
    for sd in skill_dirs:
        if not sd.exists():
            continue
        for item in sd.iterdir():
            if item.is_dir() and (item / "SKILL.md").exists():
                name = item.name
                skill_names.setdefault(name, []).append(str(sd))
            elif item.is_file() and item.suffix == ".md":
                name = item.stem
                skill_names.setdefault(name, []).append(str(sd))

    # Collect command names (filename without .md under commands/)
    cmd_names: dict[str, list[str]] = {}
    for cd in cmd_dirs:
        if not cd.exists():
            continue
        for item in cd.iterdir():
            if item.is_file() and item.suffix == ".md":
                name = item.stem
                cmd_names.setdefault(name, []).append(str(cd))

    # Report conflicts (same name in multiple locations)
    for name, locations in skill_names.items():
        if len(locations) > 1:
            findings.append({
                "type": "skill",
                "name": name,
                "locations": locations,
                "issue": f"Skill '{name}' found in multiple locations: {'; '.join(locations)}"
            })
    for name, locations in cmd_names.items():
        if len(locations) > 1:
            findings.append({
                "type": "command",
                "name": name,
                "locations": locations,
                "issue": f"Command '{name}' found in multiple locations: {'; '.join(locations)}"
            })
    return findings

def auto_fix_plugins(plugins_dir: Path, delete_hooks: bool) -> list[dict]:
    """Auto-fix common issues."""
    results = []
    if not plugins_dir.exists():
        return results
    for plugin in sorted(plugins_dir.iterdir()):
        if plugin.name.startswith(".") or not plugin.is_dir():
            continue
        result = {"plugin": plugin.name, "actions": [], "fixed": False}

        # Fix orphaned junctions (symlink/junction whose target no longer exists)
        if plugin.is_symlink() or plugin.is_dir():
            target = None
            try:
                if plugin.is_symlink():
                    target = os.readlink(str(plugin))
            except OSError:
                pass
            if target and not Path(target).exists():
                try:
                    if plugin.is_symlink():
                        plugin.unlink()
                    else:
                        import shutil
                        shutil.rmtree(str(plugin))
                    result["actions"].append(f"Removed orphaned junction (target not found: {target})")
                    result["fixed"] = True
                except OSError as e:
                    result["actions"].append(f"Failed to remove orphaned junction: {e}")

        if not plugin.exists():
            results.append(result)
            continue

        # Fix broken symlinks
        if plugin.is_symlink() and not plugin.exists():
            if delete_hooks:
                plugin.unlink()
                result["actions"].append("Removed broken symlink")
                result["fixed"] = True
            else:
                result["actions"].append("Broken symlink (needs --auto-fix --delete-hooks)")
        else:
            # Fix invalid plugin.json
            manifest_path = plugin / ".claude-plugin" / "plugin.json"
            if manifest_path.exists():
                ok, data = _load_json(manifest_path)
                if not ok:
                    fixed_data = {"name": plugin.name, "version": "1.0.0", "description": "Auto-fixed manifest"}
                    if _save_json(manifest_path, fixed_data):
                        result["actions"].append("Auto-fixed invalid plugin.json")
                        result["fixed"] = True

            # Fix: copy marketplace.json from root to .claude-plugin/ if missing
            root_mp = plugin / "marketplace.json"
            subdir_mp = plugin / ".claude-plugin" / "marketplace.json"
            if root_mp.exists() and not subdir_mp.exists():
                ok, data = _load_json(root_mp)
                if ok and _save_json(subdir_mp, data):
                    result["actions"].append("Created .claude-plugin/marketplace.json from root marketplace.json")
                    result["fixed"] = True

            # Fix: .venv auto-add to .gitignore
            venv_path = plugin / ".venv"
            if venv_path.exists() and venv_path.is_dir():
                gi = plugin / ".gitignore"
                existing = set()
                if gi.exists():
                    existing = {l.strip() for l in gi.read_text(errors="ignore").splitlines() if l.strip() and not l.startswith("#")}
                if ".venv" not in existing and ".venv/" not in existing:
                    try:
                        with open(gi, "a", encoding="utf-8") as f:
                            if existing:
                                f.write("\n")
                            f.write(".venv/\n")
                        result["actions"].append("Added .venv/ to .gitignore")
                        result["fixed"] = True
                    except OSError:
                        pass

            # Fix: .claude/ at plugin root — remove if empty, flag if suspicious
            claude_root = plugin / ".claude"
            if claude_root.exists() and claude_root.is_dir():
                contents = [e.name for e in claude_root.iterdir()]
                suspicious = [c for c in contents if c in {"skills", "plugins", ".marketplace"}]
                if suspicious:
                    result["errors"].append(
                        f".claude/ at plugin root contains suspicious entries: {suspicious}. Contents: {contents}"
                    )
                elif not contents:
                    try:
                        import shutil
                        shutil.rmtree(str(claude_root))
                        result["actions"].append("Removed empty .claude/ at plugin root")
                        result["fixed"] = True
                    except OSError:
                        pass

            # Fix: .claude/ anywhere in the plugin tree (except .claude-plugin/ manifest dir)
            # Same workspace-entry allowlist as the validator.
            import shutil as _shutil
            _workspace_entries = {"hooks", ".artifacts", "settings.local.json", "CLAUDE.md"}
            for bad_claude in list(plugin.rglob(".claude")):
                # .claude-plugin/ is the legitimate plugin manifest directory — skip it
                if str(bad_claude).endswith(".claude-plugin") or bad_claude.name == ".claude-plugin":
                    continue
                if not bad_claude.is_dir():
                    continue
                rel = bad_claude.relative_to(plugin)
                entries = [e.name for e in bad_claude.iterdir()]
                non_workspace = [e for e in entries if e not in _workspace_entries]
                if not non_workspace:
                    continue
                # Remove only non-workspace entries, keep the directory if
                # workspace entries remain. Previously this nuked the entire
                # directory even when it contained legitimate hooks/artifacts.
                for nw in non_workspace:
                    target = bad_claude / nw
                    try:
                        _shutil.rmtree(str(target)) if target.is_dir() else target.unlink()
                        result["actions"].append(f"Removed {rel}/{nw}")
                        result["fixed"] = True
                    except OSError:
                        pass

            # Fix invalid hooks/hooks.json (only when hooks dir exists)
            hooks_dir = plugin / "hooks"
            if hooks_dir.is_dir():
                hooks_path = hooks_dir / "hooks.json"
                ok, data = _load_json(hooks_path)
                if not hooks_path.exists():
                    if _save_json(hooks_path, {}):
                        result["actions"].append("Created missing hooks/hooks.json")
                        result["fixed"] = True
                elif not ok:
                    if _save_json(hooks_path, {}):
                        result["actions"].append("Auto-fixed invalid hooks/hooks.json")
                        result["fixed"] = True
                elif delete_hooks:
                    hooks_path.unlink()
                    result["actions"].append("Deleted hooks/hooks.json")
                    result["fixed"] = True
        results.append(result)
    return results

def auto_fix_git_artifacts(plugins_dir: Path) -> list[dict]:
    """Add build artifacts to .gitignore files when they exist in plugin root without being gitignored."""
    results = []
    if not plugins_dir.exists():
        return results
    # .git always exists in repos; .pytest_cache is the only other artifact we auto-fix
    auto_fix_artifacts = [".pytest_cache"]
    for plugin in sorted(plugins_dir.iterdir()):
        if plugin.name.startswith("."):
            continue
        result = {"plugin": plugin.name, "actions": [], "fixed": False}
        gitignore_path = plugin / ".gitignore"
        gitignore_entries = set()
        if gitignore_path.exists():
            with open(gitignore_path, encoding="utf-8") as f:
                gitignore_entries = {line.strip() for line in f if line.strip() and not line.startswith("#")}
        for artifact in auto_fix_artifacts:
            artifact_path = plugin / artifact
            if not artifact_path.exists():
                continue
            if artifact in gitignore_entries or artifact + "/" in gitignore_entries:
                continue
            try:
                with open(gitignore_path, "a", encoding="utf-8") as f:
                    f.write(f"\n{artifact}\n")
                result["actions"].append(f"Added {artifact} to .gitignore")
                result["fixed"] = True
            except OSError as e:
                result["actions"].append(f"Failed to update .gitignore: {e}")
        results.append(result)
    return results

def fix_hardcoded_paths(plugins_dir: Path) -> list[dict]:
    """Auto-fix hardcoded P:/ and absolute paths to $CLAUDE_PLUGIN_ROOT-relative paths.

    Rewrites hardcoded paths in .py, .md, .yaml, .yml, .json source files.
    Skips hooks/hooks.json (structural JSON, not path documentation).
    Replacement rules:
      - P:/__csf/... -> $__CSF_ROOT/...
      - P:/packages/<name>/... -> $CLAUDE_PLUGIN_ROOT/...  (for files in the plugin being scanned)
      - P:/.claude/... -> $CLAUDE_ROOT/...
      - P:/__csf.nip/... -> preserved (external project reference)
      - P:/tmp/... -> preserved (temporary paths)
    """
    results = []
    if not plugins_dir.exists():
        return results

    for plugin in sorted(plugins_dir.iterdir()):
        if plugin.name.startswith(".") or not plugin.is_dir():
            continue
        result = {"plugin": plugin.name, "actions": [], "fixed": False}

        plugin_root_pattern = f"P:\\\\packages/{plugin.name}/"
        # no longer needed

        exts = {".py", ".md", ".yaml", ".yml", ".json"}
        for fpath in plugin.rglob("*"):
            if not fpath.is_file():
                continue
            if fpath.suffix.lower() not in exts:
                continue
            # Skip hooks/hooks.json — structural JSON, not path docs
            if str(fpath).endswith("hooks.json") and "hooks" in str(fpath.relative_to(plugin)):
                continue

            try:
                content = fpath.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            original = content

            # Skip files that have no actual hardcoded P:\\packages/ or P:\\.claude/
            # paths remaining. Uses regex to detect the target patterns (1-4
            # backslashes before "packages" or ".claude") while NOT matching
            # already-replaced $CLAUDE_PLUGIN_ROOT or $CLAUDE_ROOT references.
            # Without this guard, the normalizer doubles backslashes on every
            # run, creating infinite drift.
            has_hardcoded = bool(re.search(r'P:\\\{1,4}packages[/\\]|P:\\\{1,4}\.claude[/\\]', content))
            if not has_hardcoded:
                continue

            # Normalize P:\\ to P:\\\ for consistent matching
            content_norm = content.replace("P:" + chr(92), "P:" + chr(92) + chr(92))

            # Rule 1: P:\\\\.claude/... -> $CLAUDE_ROOT/...
            content_norm = re.sub(
                r"P:\\\\\\\\.claude\\",
                "$CLAUDE_ROOT/",
                content_norm,
                flags=re.IGNORECASE,
            )

            # Rule 2: P:\\\\__csf/... -> $__CSF_ROOT/...
            content_norm = re.sub(
                r"P:\\\\\\\__csf\\",
                "$__CSF_ROOT/",
                content_norm,
                flags=re.IGNORECASE,
            )

            # Rule 3: P:\\\\packages/<plugin>/... -> $CLAUDE_PLUGIN_ROOT/...
            content_norm = re.sub(
                re.escape(plugin_root_pattern.replace("/", "\\")),
                "$CLAUDE_PLUGIN_ROOT/",
                content_norm,
                flags=re.IGNORECASE,
            )

            if content_norm != original:
                try:
                    fpath.write_text(content_norm, encoding="utf-8")
                    rel = fpath.relative_to(plugin)
                    result["actions"].append(f"Fixed paths in {rel}")
                    result["fixed"] = True
                except OSError as e:
                    result["actions"].append(f"Failed to write {rel}: {e}")

        results.append(result)
    return results


def bump_version(plugins_dir: Path, marketplace_root: str, plugin_name: str) -> dict:
    """Bump patch version for a plugin in all three version locations."""
    result = {"plugin": plugin_name, "actions": [], "old_version": None, "new_version": None, "errors": []}
    plugin_dir = plugins_dir / plugin_name
    if not plugin_dir.exists():
        result["errors"].append(f"Plugin directory not found: {plugin_dir}")
        return result

    # 1. Read current version from plugin.json
    manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
    if not manifest_path.exists():
        result["errors"].append("Missing .claude-plugin/plugin.json")
        return result
    ok, manifest = _load_json(manifest_path)
    if not ok or "version" not in manifest:
        result["errors"].append("Invalid or version-less plugin.json")
        return result
    old_ver = manifest["version"]
    result["old_version"] = old_ver

    # Bump patch version
    parts = old_ver.split(".")
    if len(parts) != 3:
        result["errors"].append(f"Unexpected version format: {old_ver}")
        return result
    parts[2] = str(int(parts[2]) + 1)
    new_ver = ".".join(parts)
    result["new_version"] = new_ver

    # 2. Update plugin.json
    manifest["version"] = new_ver
    if _save_json(manifest_path, manifest):
        result["actions"].append(f"Updated .claude-plugin/plugin.json: {old_ver} → {new_ver}")
    else:
        result["errors"].append("Failed to save plugin.json")

    # 3. Update both marketplace.json files
    for mp_path in [
        Path(marketplace_root) / "marketplace.json",
        Path(marketplace_root) / ".claude-plugin" / "marketplace.json",
    ]:
        if not mp_path.exists():
            continue
        ok, mp_data = _load_json(mp_path)
        if not ok or "plugins" not in mp_data:
            result["errors"].append(f"Invalid marketplace.json at {mp_path}")
            continue
        found = False
        for entry in mp_data["plugins"]:
            if entry.get("name") == plugin_name:
                entry["version"] = new_ver
                found = True
                break
        if not found:
            result["errors"].append(f"Plugin '{plugin_name}' not found in {mp_path}")
            continue
        if _save_json(mp_path, mp_data):
            result["actions"].append(f"Updated {mp_path.name}: {old_ver} → {new_ver}")
        else:
            result["errors"].append(f"Failed to save {mp_path}")

    return result


def main(argv: list[str]) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Audit and fix Claude Code plugins")
    parser.add_argument("--marketplace-root", default=None, help="Marketplace root directory")
    parser.add_argument("--auto-fix", action="store_true", help="Auto-fix issues")
    parser.add_argument("--delete-hooks", action="store_true", help="Delete hooks.json (use with --auto-fix)")
    parser.add_argument("--scan-paths", action="store_true", help="Scan for hardcoded paths")
    parser.add_argument("--scan-name-conflicts", action="store_true", help="Scan for conflicting skill/command names across global and local dirs")
    parser.add_argument("--plugins", metavar="NAME", help="Filter to a specific plugin name")
    parser.add_argument("--validate", action="store_true", help="Run 'claude plugin validate' on each plugin")
    parser.add_argument("--drift", action="store_true", help="Detect source-vs-cache drift using content hash (no version comparison)")
    parser.add_argument("--bump", metavar="PLUGIN_NAME", help="Bump patch version for a plugin in all version files")
    parser.add_argument("--no-fix-paths", action="store_true", help="Skip hardcoded path auto-fix (default: on)")
    parser.add_argument("--packages-root", default=None, help="Scan source packages directory directly (e.g., P:\\\\packages/)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args(argv[1:])
    script_path = __file__ if "__file__" in dir() else "plugin-audit-and-fix.py"

    # Source packages scan mode: scan P:\\\\packages/ directly
    if args.packages_root:
        packages_dir = Path(args.packages_root)
        if not packages_dir.exists():
            print(f"Error: {packages_dir} does not exist.", file=sys.stderr)
            return 1
        C = C_CYAN
        print(f"{C}=== Source Packages Audit ==={C}\\nRoot: {packages_dir}")

        # Discover plugin dirs (must have .claude-plugin/plugin.json, not excluded)
        plugin_dirs: list[Path] = []
        excluded_dirs: list[str] = []
        for entry in sorted(packages_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith(".") or entry.name.startswith("__"):
                continue
            if not (entry / ".claude-plugin" / "plugin.json").exists():
                continue
            if (entry / ".marketplace-exclude").exists():
                excluded_dirs.append(entry.name)
                continue
            plugin_dirs.append(entry)

        print(f"Found {len(plugin_dirs)} plugin(s)")
        for p in plugin_dirs:
            print(f"  {p.name}")
        if excluded_dirs:
            print(f"Excluded ({len(excluded_dirs)}, have .marketplace-exclude):")
            for e in excluded_dirs:
                print(f"  {e}")

        # Check which are missing from marketplace
        mp_root = _detect_marketplace_root(script_path, args.marketplace_root)
        # Fallback: derive marketplace from packages root directly
        if not mp_root:
            mp_dir = packages_dir / ".claude-marketplace"
            if mp_dir.exists():
                mp_root = str(mp_dir)
        mp_plugins_dir = Path(mp_root) / "plugins" if mp_root else None
        if mp_plugins_dir and mp_plugins_dir.exists():
            mp_names = {p.name for p in mp_plugins_dir.iterdir() if p.is_dir() and not p.name.startswith(".")}
            missing = [p.name for p in plugin_dirs if p.name not in mp_names]
            if missing:
                print(f"\n{C_YELLOW}Missing from marketplace ({len(missing)}):{C_RESET}")
                for m in missing:
                    print(f"  {m} — run /cc-skills-utils:plugin-installer add {m}")
            else:
                print(f"\n{C_GREEN}All source packages have marketplace junctions.{C_RESET}")

        # Audit each source plugin
        print("\nAuditing source packages...")
        all_results = []
        for plugin_dir in plugin_dirs:
            if args.plugins and plugin_dir.name != args.plugins:
                continue
            # Create a temporary plugins_dir-like scan for just this plugin
            results = audit_plugins(packages_dir, mp_root or str(packages_dir), plugin_filter=plugin_dir.name)
            all_results.extend(results)

        error_count = sum(len(r["errors"]) for r in all_results)
        warning_count = sum(len(r["warnings"]) for r in all_results)
        if error_count > 0 or warning_count > 0:
            print(f"{C_RED}Found {error_count} error(s), {warning_count} warning(s){C_RESET}")
            for r in all_results:
                for e in r["errors"]: print(f"  [ERROR] {r['plugin']}: {e}")
                for w in r["warnings"]: print(f"  [WARNING] {r['plugin']}: {w}")
        else:
            print(f"{C_GREEN}All source plugins OK.{C_RESET}")

        # Drift check
        print("\nChecking source vs cache drift...")
        drift_findings = audit_source_cache_drift(packages_dir)
        # Filter to only real plugins
        plugin_names = {p.name for p in plugin_dirs}
        drift_findings = [f for f in drift_findings if f["plugin"] in plugin_names]
        stale_count = sum(1 for f in drift_findings if f["type"] == "stale_version_dirs")
        modified_count = sum(1 for f in drift_findings if f["type"] == "source_modified")
        cache_only_count = sum(1 for f in drift_findings if f["type"] == "cache_only")
        if drift_findings:
            print(f"{C_YELLOW}Found {stale_count} stale, {modified_count} drift, {cache_only_count} cache-only:{C_RESET}")
            for f in drift_findings:
                t = f["type"]
                if t == "stale_version_dirs":
                    print(f"  {f['plugin']}: STALE {f['stale_versions']}")
                elif t == "source_modified":
                    print(f"  {f['plugin']} ({f['cache_version']}): {f['drift_count']} modified")
                elif t == "cache_only":
                    print(f"  {f['plugin']}: {f['cache_only_count']} cache-only")
        else:
            print(f"{C_GREEN}Cache is in sync with source.{C_RESET}")

        if args.auto_fix and mp_root:
            fix_results = auto_fix_plugins(packages_dir, args.delete_hooks)
            fix_count = sum(len(r["actions"]) for r in fix_results if r.get("plugin") in plugin_names)
            if fix_count:
                print(f"{C_GREEN}Fixed {fix_count} issue(s).{C_RESET}")
                for r in fix_results:
                    if r.get("plugin") not in plugin_names:
                        continue
                    for action in r["actions"]:
                        print(f"  [{r['plugin']}] {action}")

            # Auto-fix hardcoded paths (on by default in --packages-root mode)
            if not args.no_fix_paths:
                path_results = fix_hardcoded_paths(packages_dir)
                path_fix_count = sum(len(r["actions"]) for r in path_results if r.get("fixed"))
                if path_fix_count:
                    print(f"{C_GREEN}Fixed hardcoded paths in {path_fix_count} file(s).{C_RESET}")
                    for r in path_results:
                        if not r.get("fixed"):
                            continue
                        for action in r["actions"]:
                            print(f"  [{r['plugin']}] {action}")

            # Auto-fix: stale version dirs + source sync
            # Re-check drift AFTER path fixes — path fixes modify source, so the
            # original drift_findings are stale.
            import shutil
            import subprocess
            path_fixes = path_fix_count if not args.no_fix_paths else 0
            if path_fixes > 0:
                drift_findings = audit_source_cache_drift(packages_dir)
                drift_findings = [f for f in drift_findings if f["plugin"] in plugin_names]
            synced = []
            stale_deleted = []
            for f in drift_findings:
                t = f["type"]
                pkg = f["plugin"]
                cache_root = Path(os.path.expanduser("~/.claude/plugins/cache/local"))
                if t == "stale_version_dirs":
                    for stale_ver in f["stale_versions"]:
                        stale_path = cache_root / pkg / stale_ver
                        if stale_path.exists():
                            shutil.rmtree(str(stale_path))
                            stale_deleted.append(f"{pkg}/{stale_ver}")
                            print(f"  {C_RED}Deleted stale: {pkg}/{stale_ver}{C_RESET}")
                elif t == "source_modified":
                    src = packages_dir / pkg
                    version_dir = cache_root / pkg / f["cache_version"]
                    if src.exists() and version_dir.exists():
                        sync_stats = bidir_sync(src, version_dir)
                        if sync_stats["errors"]:
                            for err in sync_stats["errors"]:
                                print(f"  {C_RED}Sync error {pkg}: {err}{C_RESET}")
                        parts = []
                        if sync_stats["src_to_cache"]:
                            parts.append(f"src→cache: {sync_stats['src_to_cache']}")
                        if sync_stats["cache_to_src"]:
                            parts.append(f"cache→src: {sync_stats['cache_to_src']}")
                        if sync_stats["conflicts"]:
                            parts.append(f"conflicts: {len(sync_stats['conflicts'])} (review manually)")
                        if sync_stats["skipped"]:
                            parts.append(f"cache-only skipped: {sync_stats['skipped']}")
                        if parts:
                            print(f"  {C_GREEN}Synced: {pkg} ({', '.join(parts)}){C_RESET}")
                            synced.append(pkg)
                        else:
                            print(f"  {C_GREEN}Synced: {pkg} (no changes needed){C_RESET}")
                            synced.append(pkg)
                elif t == "cache_only":
                    print(f"  {C_YELLOW}Cache-only files in {pkg}: {f['cache_only_count']} file(s) — restore from git history or delete manually{C_RESET}")

            if stale_deleted:
                print(f"\n{C_GREEN}Deleted {len(stale_deleted)} stale version dir(s): {stale_deleted}{C_RESET}")

        # Only return non-zero for actionable errors (manifest issues), not warnings
        actionable_errors = sum(
            len(r["errors"]) for r in all_results
            if r.get("plugin") in {p.name for p in plugin_dirs}
            and any("plugin.json" in e or "marketplace.json" in e for e in r.get("errors", []))
        )
        return actionable_errors

    resolved_root = args.marketplace_root or os.environ.get("CLAUDE_MARKETPLACE_ROOT")
    mp_root = _detect_marketplace_root(script_path, resolved_root)
    if not mp_root:
        print("Error: Cannot detect marketplace root. Use --marketplace-root or set CLAUDE_MARKETPLACE_ROOT.", file=sys.stderr)
        return 1
    plugins_dir = Path(mp_root) / "plugins"
    C = C_CYAN
    print(f"{C}=== Claude Code Plugin Audit & Fix ==={C}\\nMarketplace: {mp_root}")
    if args.scan_paths:
        print("Scanning for hardcoded paths...")
        findings = scan_source_paths(plugins_dir)
        if findings:
            print(f"{C_RED}Found {len(findings)} hardcoded path(s):{C_RESET}")
            for f in findings:
                print(f"  [{f['plugin']}] {f['file']}: {f['issue']}")
        else:
            print(f"{C_GREEN}No hardcoded paths found.{C_RESET}")
        return 0
    if args.scan_name_conflicts:
        print("Scanning for name conflicts across skill and command directories...")
        conflict_results = audit_name_conflicts()
        if conflict_results:
            print(f"{C_RED}Found {len(conflict_results)} name conflict(s):{C_RESET}")
            for c in conflict_results:
                print(f"  [{c['type']}] {c['name']}: {c['issue']}")
        else:
            print(f"{C_GREEN}No name conflicts found.{C_RESET}")
        return 0
    if args.bump:
        bump_result = bump_version(plugins_dir, mp_root, args.bump)
        if bump_result["errors"]:
            for e in bump_result["errors"]:
                print(f"  {C_RED}ERROR: {e}{C_RESET}")
            return 1
        for a in bump_result["actions"]:
            print(f"  {C_GREEN}{a}{C_RESET}")

        # Post-bump: create new cache dir, remove old version dir
        import shutil
        import subprocess
        cache_root = Path(os.path.expanduser("~/.claude/plugins/cache/local"))
        pkg_name = args.bump
        old_ver = bump_result["old_version"]
        new_ver = bump_result["new_version"]
        cache_dir = cache_root / pkg_name

        if cache_dir.exists():
            # Create new version dir by syncing from source
            src = plugins_dir / pkg_name
            new_cache = cache_dir / new_ver
            if src.exists():
                new_cache.mkdir(parents=True, exist_ok=True)
                sync_stats = bidir_sync(src, new_cache)
                if sync_stats["errors"]:
                    for err in sync_stats["errors"]:
                        print(f"  {C_YELLOW}Cache sync error: {err}{C_RESET}")
                print(f"  {C_GREEN}Created cache: {pkg_name}/{new_ver} (src→cache: {sync_stats['src_to_cache']}, cache→src: {sync_stats['cache_to_src']}){C_RESET}")

            # Remove old version dir
            old_cache = cache_dir / old_ver
            if old_cache.exists() and old_ver != new_ver:
                shutil.rmtree(str(old_cache))
                print(f"  {C_GREEN}Removed stale cache: {pkg_name}/{old_ver}{C_RESET}")

        print(f"\n{C_CYAN}=== Next Steps ==={C_RESET}")
        print(f"  1. /plugin marketplace update local")
        print(f"  2. /reload-plugins")
        return 0
    if args.validate:
        print("Validating plugins...")
        failed = 0
        for plugin in sorted(plugins_dir.iterdir()):
            if plugin.name.startswith("."):
                continue
            if args.plugins and plugin.name != args.plugins:
                continue
            plugin_dir = str(plugin)
            result = __import__("subprocess").run(
                ["claude", "plugin", "validate", plugin_dir],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print(f"  {C_GREEN}✓ {plugin.name}{C_RESET}")
            else:
                print(f"  {C_RED}✗ {plugin.name}{C_RESET}")
                failed += 1
        if failed > 0:
            print(f"{C_RED}{failed} plugin(s) failed validation{C_RESET}")
        else:
            print(f"{C_GREEN}All plugins validated{C_RESET}")
        return failed
    if args.drift:
        findings = audit_source_cache_drift(plugins_dir)
        stale = [f for f in findings if f["type"] == "stale_version_dirs"]
        modified = [f for f in findings if f["type"] == "source_modified"]
        cache_only = [f for f in findings if f["type"] == "cache_only"]
        if stale:
            print(f"{C_YELLOW}Stale version dirs:{C_RESET}")
            for f in stale:
                print(f"  {f['plugin']}: stale {[d for d in f['stale_versions']]}")
        else:
            print("No stale version dirs.")
        if modified:
            print(f"{C_YELLOW}Source drift:{C_RESET}")
            for f in modified:
                sample = ", ".join(f["sample_files"][:3])
                extra = f" (+{f['drift_count'] - len(f['sample_files'])} more)" if f["drift_count"] > len(f["sample_files"]) else ""
                print(f"  {f['plugin']} ({f['cache_version']}): {f['drift_count']} file(s) modified — {sample}{extra}")
        else:
            print("No source drift.")
        if cache_only:
            print(f"{C_YELLOW}Cache-only files:{C_RESET}")
            for f in cache_only:
                print(f"  {f['plugin']}: {[cf for cf in f['cache_only_files']]}")
        else:
            print("No cache-only files.")
        # Output machine-readable summary for downstream parsing
        print(f"\nSummary: {len(stale)} stale, {len(modified)} drift, {len(cache_only)} cache-only")
        return 0
    print("Auditing plugins...")
    plugin_results = audit_plugins(plugins_dir, mp_root, plugin_filter=args.plugins)
    error_count = sum(len(r["errors"]) for r in plugin_results)
    warning_count = sum(len(r["warnings"]) for r in plugin_results)
    if error_count > 0 or warning_count > 0:
        print(f"{C_RED}Found {error_count} error(s), {warning_count} warning(s){C_RESET}")
        for r in plugin_results:
            for e in r["errors"]: print(f"  [ERROR] {r['plugin']}: {e}")
            for w in r["warnings"]: print(f"  [WARNING] {r['plugin']}: {w}")
    else:
        print(f"{C_GREEN}All plugins OK.{C_RESET}")

    # Check for orphan skill junctions (skills duplicated outside their cluster)
    print("\nChecking for orphan skill junctions...")
    orphan_findings = audit_orphan_skill_junctions(plugins_dir)
    if orphan_findings:
        print(f"{C_YELLOW}Found {len(orphan_findings)} orphan skill junction(s):{C_RESET}")
        for f in orphan_findings:
            print(f"  {f['marketplace_entry']} -> {f['cluster']}/skills/{f['skill']}")
    else:
        print(f"{C_GREEN}No orphan skill junctions.{C_RESET}")

    # Check for source/cache drift
    print("\nChecking source vs cache drift...")
    drift_findings = audit_source_cache_drift(plugins_dir)
    stale_count = sum(1 for f in drift_findings if f["type"] == "stale_version_dirs")
    modified_count = sum(1 for f in drift_findings if f["type"] == "source_modified")
    cache_only_count = sum(1 for f in drift_findings if f["type"] == "cache_only")
    if drift_findings:
        print(f"{C_YELLOW}Found {stale_count} stale version dir(s), {modified_count} with source drift, {cache_only_count} with cache-only files:{C_RESET}")
        for f in drift_findings:
            t = f["type"]
            if t == "stale_version_dirs":
                print(f"  {f['plugin']}: STALE versions {[d for d in f['stale_versions']]} (current: {f['current_version']})")
            elif t == "source_modified":
                sample = ", ".join(f["sample_files"][:3])
                extra = f" (+{f['drift_count'] - 3} more)" if f["drift_count"] > 3 else ""
                print(f"  {f['plugin']} ({f['cache_version']}): {f['drift_count']} file(s) modified — {sample}{extra}")
            elif t == "cache_only":
                sample = ", ".join(f["cache_only_files"][:3])
                extra = f" (+{f['cache_only_count'] - 3} more)" if f["cache_only_count"] > 3 else ""
                print(f"  {f['plugin']} ({f['cache_version']}): {f['cache_only_count']} cache-only file(s) — {sample}{extra}")
    else:
        print(f"{C_GREEN}Cache is in sync with source.{C_RESET}")

    if args.auto_fix:
        fix_results = auto_fix_plugins(plugins_dir, args.delete_hooks)
        fix_count = sum(len(r["actions"]) for r in fix_results)
        print(f"{C_GREEN}Fixed {fix_count} issue(s).{C_RESET}")
        for r in fix_results:
            for action in r["actions"]:
                print(f"  [{r['plugin']}] {action}")
        git_results = auto_fix_git_artifacts(plugins_dir)
        git_fix_count = sum(len(r["actions"]) for r in git_results)
        if git_fix_count > 0:
            print(f"{C_GREEN}Added .git to {git_fix_count} .gitignore file(s).{C_RESET}")
            for r in git_results:
                for action in r["actions"]:
                    print(f"  [{r['plugin']}] {action}")

        # Auto-fix: hardcoded paths (on by default, skip with --no-fix-paths)
        path_fix_count = 0
        if not args.no_fix_paths:
            path_results = fix_hardcoded_paths(plugins_dir)
            path_fix_count = sum(len(r["actions"]) for r in path_results if r.get("fixed"))
            if path_fix_count > 0:
                print(f"{C_GREEN}Fixed hardcoded paths in {path_fix_count} file(s).{C_RESET}")
                for r in path_results:
                    for action in r["actions"]:
                        print(f"  [{r['plugin']}] {action}")

        # Auto-fix: remove orphan skill junctions
        if orphan_findings:
            import shutil
            print(f"\n{C_YELLOW}Removing {len(orphan_findings)} orphan skill junction(s)...{C_RESET}")
            for f in orphan_findings:
                junction_path = plugins_dir / f["marketplace_entry"]
                try:
                    if junction_path.is_dir():
                        shutil.rmtree(str(junction_path))
                    print(f"  {C_GREEN}Removed: {f['marketplace_entry']} (now via {f['cluster']}){C_RESET}")
                except OSError as e:
                    print(f"  {C_RED}Failed to remove {f['marketplace_entry']}: {e}{C_RESET}")

        # Auto-fix: stale version dirs + source sync
        # Re-check drift AFTER path fixes — path fixes modify source, so the
        # original drift_findings are stale. Without this, robocopy syncs
        # pre-fix source and path fixes re-introduce drift immediately.
        import shutil
        import subprocess
        if path_fix_count > 0:
            drift_findings = audit_source_cache_drift(plugins_dir)
            drift_findings = [f for f in drift_findings if f["plugin"] in plugin_names]
        synced = []
        stale_deleted = []
        for f in drift_findings:
            t = f["type"]
            pkg = f["plugin"]
            cache_root = Path(os.path.expanduser("~/.claude/plugins/cache/local"))
            if t == "stale_version_dirs":
                # Delete all stale version directories
                for stale_ver in f["stale_versions"]:
                    stale_path = cache_root / pkg / stale_ver
                    if stale_path.exists():
                        shutil.rmtree(str(stale_path))
                        stale_deleted.append(f"{pkg}/{stale_ver}")
                        print(f"  {C_RED}Deleted stale: {pkg}/{stale_ver}{C_RESET}")
            elif t == "source_modified":
                # Bidirectional sync for the current version directory
                src = Path(f"P:\\\\packages/{pkg}")
                version_dir = cache_root / pkg / f["cache_version"]
                if src.exists() and version_dir.exists():
                    sync_stats = bidir_sync(src, version_dir)
                    if sync_stats["errors"]:
                        for err in sync_stats["errors"]:
                            print(f"  {C_RED}Sync error {pkg}: {err}{C_RESET}")
                    parts = []
                    if sync_stats["src_to_cache"]:
                        parts.append(f"src→cache: {sync_stats['src_to_cache']}")
                    if sync_stats["cache_to_src"]:
                        parts.append(f"cache→src: {sync_stats['cache_to_src']}")
                    if sync_stats["conflicts"]:
                        parts.append(f"conflicts: {len(sync_stats['conflicts'])} (review manually)")
                    if sync_stats["skipped"]:
                        parts.append(f"cache-only skipped: {sync_stats['skipped']}")
                    if parts:
                        print(f"  {C_GREEN}Synced: {pkg} ({', '.join(parts)}){C_RESET}")
                        synced.append(pkg)
                    else:
                        print(f"  {C_GREEN}Synced: {pkg} (no changes needed){C_RESET}")
                        synced.append(pkg)
            elif t == "cache_only":
                # Cache-only files are preserved in cache, not copied to source
                print(f"  {C_YELLOW}Cache-only files in {pkg}: {f['cache_only_count']} file(s) — preserved in cache{C_RESET}")

        if stale_deleted:
            print(f"\n{C_GREEN}Deleted {len(stale_deleted)} stale version dir(s): {stale_deleted}{C_RESET}")

        print(f"\n{C_CYAN}=== Next Steps ==={C_RESET}")
        print(f"  1. Run with --scan-paths to detect hardcoded paths")
        print(f"  2. Run with --scan-name-conflicts to detect conflicting skill/command names")
        print(f"  3. Run with --validate to validate all plugins")
        print(f"  4. Update marketplace: {C_CYAN}/plugin marketplace update local{C_RESET}")
    return error_count
if __name__ == "__main__":
    sys.exit(main(sys.argv))
