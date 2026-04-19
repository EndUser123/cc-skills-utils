#!/usr/bin/env python3
"""
Hook Inventory Audit - Comprehensive hook file classification.

Categorizes all hooks as:
- DIRECT_REGISTERED: In settings.json
- ROUTER_DISPATCHED: Called by router
- UTILITY_MODULE: Imported by other hooks
- ROUTER_FILE: Consolidates multiple hooks
- TEST_FILE: In tests/ subdirectory
- ARCHIVE_OBSOLETE: In archive/, _archive/, orphaned/
- STANDALONE_OBSOLETE: Not referenced anywhere

Usage:
    python hook_inventory.py              # Full report
    python hook_inventory.py --dead         # Dead hooks only
    python hook_inventory.py --tree         # Router dispatch tree
    python hook_inventory.py --json         # Export JSON
    python hook_inventory.py --markdown      # Export markdown
    python hook_inventory.py --stats        # Statistics only
"""

from __future__ import annotations

import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

# =============================================================================
# CONFIGURATION
# =============================================================================
SCRIPT_DIR = Path(__file__).parent
HOOKS_DIR = Path(r"P:\.claude\hooks")
SETTINGS_PATH = Path(r"P:\.claude\settings.json")
REPORTS_DIR = SCRIPT_DIR / "reports"

# Router files to scan for dispatched hooks
ROUTER_PATTERNS = [
    "*router*.py",
    "UserPromptSubmit_*.py",
    "PreToolUse_*.py",
    "PostToolUse_*.py",
    "Stop*.py",
    "SessionStart*.py",
    "SessionEnd*.py",
    "PreCompact*.py",
]

# Subdirectories that contain non-hook files
UTILITY_DIRS = {
    "__lib__",
    "__csf__",
    "__csf",
    "tests",
    "scanners",
    "validators",
    "repositories",
    "disler_utils",
    "posttooluse",  # Consolidated package (SUBCOMPONENT)
    "pretooluse",  # Consolidated package (SUBCOMPONENT)
    "stop",  # Consolidated package (SUBCOMPONENT)
    "archive",
    "_archive",
    "orphaned_*",
}

# Subdirectories containing consolidated hook packages (subcomponents)
SUBCOMPONENT_DIRS = {
    "posttooluse",
    "pretooluse",
    "stop",
    "stophook",
}

# =============================================================================
# DATA STRUCTURES
# =============================================================================
class HookInfo:
    """Information about a hook file."""

    def __init__(self, path: Path):
        self.path = path
        self.name = path.stem
        self.category = "UNKNOWN"
        self.references = []  # Files that reference this hook
        self.imports = []  # Files this hook imports
        self.found_in_settings = False
        self.dispatched_by_router = None
        self.is_test_file = False
        self.is_archive = False
        self.is_utility = False

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "name": self.name,
            "category": self.category,
            "references": self.references,
            "imports": self.imports,
            "found_in_settings": self.found_in_settings,
            "dispatched_by_router": self.dispatched_by_router,
            "is_test_file": self.is_test_file,
            "is_archive": self.is_archive,
            "is_utility": self.is_utility,
        }

# =============================================================================
# PARSERS
# =============================================================================
def parse_settings_for_hooks(settings_path: Path) -> Set[str]:
    """Extract hook names registered in settings.json."""
    hooks = set()

    if not settings_path.exists():
        return hooks

    try:
        with open(settings_path, encoding="utf-8") as f:
            settings = json.load(f)
    except (json.JSONDecodeError, IOError):
        return hooks

    hooks_config = settings.get("hooks", {})

    for phase, matchers in hooks_config.items():
        for matcher in matchers:
            for hook in matcher.get("hooks", []):
                cmd = hook.get("command", "")
                # Extract Python script path from command
                if cmd.startswith("python ") or ".py " in cmd:
                    # Handle various command formats:
                    # python P:/.claude/hooks/hook_name.py
                    # python P:/.claude/hooks/__lib/hook_runner.py P:/.claude/hooks/hook_name.py
                    parts = cmd.split()
                    for part in parts:
                        if part.endswith(".py"):
                            hook_path = Path(part.replace("P:/.claude/hooks/", ""))
                            hooks.add(hook_path.stem)
                elif ".ps1" in cmd:
                    # PowerShell hooks
                    hook_path = Path(cmd.split()[-1])
                    hooks.add(hook_path.stem)

    return hooks


def extract_imports_from_file(file_path: Path) -> Set[str]:
    """Extract import statements from a Python file."""
    imports = set()

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except (IOError, OSError):
        return imports

    # Parse with AST for accurate import extraction
    try:
        tree = ast.parse(content, filename=str(file_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    # Get the base module name
                    imports.add(node.module.split(".")[0])
    except (SyntaxError, ValueError):
        # Fallback to regex if AST parsing fails
        import_patterns = [
            r"^from\s+(\w+)",
            r"^import\s+(\w+)",
            r"from\s+\.claude\.hooks\.(\w+)",
        ]
        for line in content.split("\n"):
            for pattern in import_patterns:
                match = re.search(pattern, line.strip())
                if match:
                    imports.add(match.group(1))

    return imports


def extract_subprocess_calls(file_path: Path) -> Set[str]:
    """Extract hook names called via subprocess."""
    hooks = set()

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except (IOError, OSError):
        return hooks

    # Match patterns like:
    # subprocess.run([sys.executable, "hook_name.py"])
    # subprocess.run([python, "P:/.claude/hooks/hook_name.py"])
    # subprocess.run([python, "stop/hook_name.py"])  # subdirectory dispatch
    # HookPath / f"{hook_name}.py"
    patterns = [
        r'subprocess\.\w+\([^)]*"(\w+)/(\w+)\.py"',      # "subdir/hook.py"
        r'subprocess\.\w+\([^)]*"?(\w+)\.py"?',         # "hook.py" (no subdir)
        r'from\s+(\w+)/(\w+)\s+import',                  # from subdir.module import
        r'import\s+(\w+)',                               # import module
    ]

    for line in content.split("\n"):
        # Skip comments
        line = re.sub(r'#.*$', '', line)
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                # If pattern captured subdirectory and filename separately
                if '/' in match.group(0):
                    # Extract just the filename part (after last /)
                    full_match = re.search(r'["\']?(\w+)/(\w+)\.py["\']?', line)
                    if full_match:
                        hooks.add(full_match.group(2))  # filename part
                else:
                    hooks.add(match.group(1))

    # Also look for HOOK_SEQUENCE patterns like:
    # ("stop/contract_validator.py", "CONTRACT_VALIDATOR_ENABLED", "true", "subprocess"),
    hook_sequence_pattern = r'\(["\'](\w+)/(\w+)\.py["\']'
    for match in re.finditer(hook_sequence_pattern, content):
        hooks.add(match.group(2))  # filename part

    return hooks


def extract_router_dispatches(router_file: Path) -> Tuple[Set[str], Set[str]]:
    """Extract hooks dispatched by a router.

    Returns:
        (dispatched_hooks, imported_modules)
    """
    dispatched = set()
    imported = set()

    try:
        content = router_file.read_text(encoding="utf-8", errors="ignore")
    except (IOError, OSError):
        return dispatched, imported

    # Extract imports
    imported = extract_imports_from_file(router_file)

    # Extract wrap_ functions (router wrapper pattern)
    # NOTE: Many functions named wrap_* are NOT actual dispatched hooks
    # They may be utility functions within routers. Only mark as dispatched
    # if they clearly match hook naming patterns.
    wrap_funcs_raw = set(re.findall(r'def\s+wrap_(\w+)\s*\(', content))

    # Filter out common utility patterns that aren't actual hook names
    non_hook_patterns = [
        'run_hooks', 'main', 'log', 'get_', 'set_', 'build_', 'create_',
        'format_', 'parse_', 'load_', 'save_', 'write_', 'read_',
        'check_', 'verify_', 'validate_', 'resolve_', 'extract_',
        'emit_', 'record_', 'track_', 'handle_', 'process_',
    ]

    wrap_funcs = set()
    for func in wrap_funcs_raw:
        # Only count as dispatched hook if it doesn't match utility patterns
        if not any(pattern in func.lower() for pattern in non_hook_patterns):
            wrap_funcs.add(func)

    # Extract subprocess calls
    subprocess_hooks = extract_subprocess_calls(router_file)

    dispatched.update(wrap_funcs)
    dispatched.update(subprocess_hooks)

    return dispatched, imported


def is_router_file(file_path: Path, content: str) -> bool:
    """Check if file is a router."""
    indicators = [
        "router" in file_path.stem.lower(),
        "consolidates" in content.lower(),
        "HOOK_SEQUENCE" in content,
        "def wrap_" in content,
        "def run_hooks" in content,
        "dispatched" in content.lower(),
    ]
    return any(indicators)


# =============================================================================
# MAIN AUDIT
# =============================================================================
def audit_hooks() -> Dict[str, HookInfo]:
    """Perform comprehensive hook audit."""
    all_files = {}
    all_hooks = {}  # name -> HookInfo

    # Collect all Python files in hooks directory
    for py_file in HOOKS_DIR.rglob("*.py"):
        # Skip subdirectories that are known utilities
        rel_path = py_file.relative_to(HOOKS_DIR)
        parts = rel_path.parts

        # Check if in utility/test/designive/subcomponent directory
        is_test = "tests" in parts
        is_archive = any(p in ["archive", "_archive"] or p.startswith("orphaned_") for p in parts)
        is_utility = any(p in UTILITY_DIRS for p in parts)
        is_subcomponent = any(p in SUBCOMPONENT_DIRS for p in parts)

        info = HookInfo(py_file)
        info.is_test_file = is_test
        info.is_archive = is_archive
        info.is_utility = is_utility

        # Classify files by directory location
        if is_test:
            info.category = "TEST_FILE"
        elif is_archive:
            info.category = "ARCHIVE_OBSOLETE"
        elif is_subcomponent:
            info.category = "SUBCOMPONENT"
        elif is_utility:
            info.category = "UTILITY_MODULE"

        all_hooks[info.name] = info
        all_files[str(rel_path)] = info

    # Parse settings.json for direct-registered hooks
    settings_hooks = parse_settings_for_hooks(SETTINGS_PATH)
    for name in settings_hooks:
        if name in all_hooks:
            all_hooks[name].found_in_settings = True
            if all_hooks[name].category == "UNKNOWN":
                all_hooks[name].category = "DIRECT_REGISTERED"

    # Analyze router files
    router_files = []
    for pattern in ROUTER_PATTERNS:
        router_files.extend(HOOKS_DIR.glob(pattern))

    router_dispatch_map = {}  # router_name -> set of dispatched hooks

    for router_file in router_files:
        if not router_file.is_file() or router_file.name == "__init__.py":
            continue

        dispatched, imported = extract_router_dispatches(router_file)

        if dispatched or imported:
            router_name = router_file.stem
            router_dispatch_map[router_name] = dispatched

            # Mark router as ROUTER_FILE
            if router_name in all_hooks:
                all_hooks[router_name].category = "ROUTER_FILE"

            # Mark dispatched hooks
            for hook_name in dispatched:
                if hook_name in all_hooks:
                    all_hooks[hook_name].dispatched_by_router = router_name
                    if all_hooks[hook_name].category == "UNKNOWN":
                        all_hooks[hook_name].category = "ROUTER_DISPATCHED"

            # Track imports for utility detection
            for module in imported:
                if module in all_hooks and not all_hooks[module].imports:
                    all_hooks[module].references.append(router_name)

    # Build import dependency graph
    for name, info in all_hooks.items():
        if info.category in ["TEST_FILE", "ARCHIVE_OBSOLETE"]:
            continue

        imports = extract_imports_from_file(info.path)
        for imported_module in imports:
            if imported_module in all_hooks:
                all_hooks[imported_module].references.append(name)
                info.imports.append(imported_module)

    # Verify files actually exist before marking as dead
    # This catches false positives from glob pattern matching
    for name, info in all_hooks.items():
        if info.category == "STANDALONE_OBSOLETE":
            if not info.path.exists():
                # File truly doesn't exist - confirm dead
                info.category = "FILE_NOT_FOUND"
            elif info.path.exists():
                # File exists but not referenced - verify not router-dispatched
                if not info.dispatched_by_router and not info.found_in_settings:
                    info.category = "CONFIRMED_DEAD"
                else:
                    # Has some reference, may be utility or indirect dispatch
                    info.category = "POSSIBLE_UTILITY"

    # Identify utility modules (imported but not standalone hooks)
    for name, info in all_hooks.items():
        if info.category == "UNKNOWN" and info.references and not info.dispatched_by_router:
            # If imported by others and not dispatched by router, likely utility
            if not any(x in name.lower() for x in ["test", "hook", "check", "analyze"]):
                # Check if looks like a utility (not an event hook)
                event_prefixes = [
                    "UserPromptSubmit", "PreToolUse", "PostToolUse",
                    "Stop", "SessionStart", "SessionEnd", "PreCompact",
                    "Notification",
                ]
                is_event_hook = any(name.startswith(p) for p in event_prefixes)
                if not is_event_hook and info.references:
                    info.category = "UTILITY_MODULE"

    # Mark remaining UNKNOWN as STANDALONE_OBSOLETE
    for name, info in all_hooks.items():
        if info.category == "UNKNOWN":
            info.category = "STANDALONE_OBSOLETE"

    return all_hooks, router_dispatch_map


# =============================================================================
# REPORTING
# =============================================================================
def generate_report(hooks: Dict[str, HookInfo], router_map: Dict[str, Set[str]], args) -> None:
    """Generate and output reports based on arguments."""

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Count by category
    by_category = defaultdict(list)
    for info in hooks.values():
        by_category[info.category].append(info)

    # Statistics
    if "--stats" in args:
        print("\n" + "=" * 60)
        print("HOOK INVENTORY STATISTICS")
        print("=" * 60)
        total = len(hooks)
        for cat in [
            "DIRECT_REGISTERED",
            "ROUTER_DISPATCHED",
            "ROUTER_FILE",
            "UTILITY_MODULE",
            "TEST_FILE",
            "ARCHIVE_OBSOLETE",
            "SUBCOMPONENT",  # Part of router/PostToolUse/Stop package
            "STANDALONE_OBSOLETE",
            "POSSIBLE_UTILITY",  # Previously "UNKNOWN" but has references
            "CONFIRMED_DEAD",  # File doesn't exist
            "FILE_NOT_FOUND",  # Exists but not referenced
        ]:
            count = len(by_category.get(cat, []))
            pct = (count / total * 100) if total else 0
            print(f"{cat:25} {count:4} ({pct:5.1f}%)")
        print("-" * 60)
        print(f"{'TOTAL':25} {total:4}")
        return

    # Dead hooks only (now includes CONFIRMED_DEAD and FILE_NOT_FOUND)
    # Note: SUBCOMPONENT files are NOT included - they're part of packages
    if "--dead" in args:
        dead = by_category.get("STANDALONE_OBSOLETE", [])
        dead.extend(by_category.get("CONFIRMED_DEAD", []))
        dead.extend(by_category.get("FILE_NOT_FOUND", []))
        dead.extend(by_category.get("ARCHIVE_OBSOLETE", []))
        # Don't include SUBCOMPONENT files in dead list - they're organized in packages

        print("\n" + "=" * 60)
        print(f"DEAD/OBSOLETE HOOKS: {len(dead)}")
        print("=" * 60)

        for info in sorted(dead, key=lambda x: x.name):
            conf = " [CONFIRMED]" if info.category == "CONFIRMED_DEAD" else ""
            missing = " [MISSING]" if info.category == "FILE_NOT_FOUND" else ""
            print(f"  {info.name}{conf}{missing}")

        # Write to file
        dead_file = REPORTS_DIR / "dead_hooks.txt"
        with open(dead_file, "w", encoding="utf-8") as f:
            for info in sorted(dead, key=lambda x: x.name):
                f.write(f"{info.name}\n")
        print(f"\nWritten to: {dead_file}")
        return

    # Router dispatch tree
    if "--tree" in args:
        print("\n" + "=" * 60)
        print("ROUTER DISPATCH TREE")
        print("=" * 60)

        for router_name, dispatched in sorted(router_map.items()):
            print(f"\n{router_name}/")
            for hook in sorted(dispatched):
                print(f"  ├── {hook}")
        return

    # Full JSON export
    if "--json" in args:
        output = {
            "total_hooks": len(hooks),
            "by_category": {
                cat: len(items) for cat, items in by_category.items()
            },
            "hooks": {name: info.to_dict() for name, info in hooks.items()},
            "router_dispatch_map": {
                router: list(hooks) for router, hooks in router_map.items()
            },
        }

        json_file = REPORTS_DIR / "inventory.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, default=str)
        print(f"JSON report written to: {json_file}")
        return

    # Markdown export
    if "--markdown" in args:
        lines = [
            "# Hook Inventory Report\n",
            f"**Generated**: {len(hooks)} hooks analyzed\n",
            "## Summary by Category\n\n",
            "| Category | Count | Percentage |",
            "|----------|-------|------------|",
        ]
        total = len(hooks)
        for cat in [
            "DIRECT_REGISTERED",
            "ROUTER_DISPATCHED",
            "ROUTER_FILE",
            "UTILITY_MODULE",
            "TEST_FILE",
            "ARCHIVE_OBSOLETE",
            "SUBCOMPONENT",  # Part of router/PostToolUse/Stop package
            "STANDALONE_OBSOLETE",
        ]:
            count = len(by_category.get(cat, []))
            pct = (count / total * 100) if total else 0
            lines.append(f"| {cat} | {count} | {pct:.1f}% |")

        lines.append("\n## Dead/Obsolate Hooks\n")
        dead = by_category.get("STANDALONE_OBSOLETE", [])
        if dead:
            for info in sorted(dead, key=lambda x: x.name):
                lines.append(f"- `{info.name}`")
        else:
            lines.append("*No dead hooks found.*")

        md_content = "\n".join(lines)
        md_file = REPORTS_DIR / "inventory_report.md"
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"Markdown report written to: {md_file}")
        return

    # Default: print summary
    print("\n" + "=" * 60)
    print("HOOK INVENTORY SUMMARY")
    print("=" * 60)

    print(f"\nTotal hooks found: {len(hooks)}")
    print(f"  Direct-registered: {len(by_category.get('DIRECT_REGISTERED', []))}")
    print(f"  Router-dispatched: {len(by_category.get('ROUTER_DISPATCHED', []))}")
    print(f"  Router files: {len(by_category.get('ROUTER_FILE', []))}")
    print(f"  Utility modules: {len(by_category.get('UTILITY_MODULE', []))}")
    print(f"  Subcomponent files: {len(by_category.get('SUBCOMPONENT', []))}")
    print(f"  Test files: {len(by_category.get('TEST_FILE', []))}")
    print(f"  Archive/obsolete: {len(by_category.get('ARCHIVE_OBSOLETE', []))}")
    print(f"  Standalone obsolete: {len(by_category.get('STANDALONE_OBSOLETE', []))}")

    print("\n" + "-" * 60)
    print("STANDALONE OBSOLETE (potential cleanup)")
    print("-" * 60)
    dead = by_category.get("STANDALONE_OBSOLETE", [])
    for info in sorted(dead, key=lambda x: x.name)[:20]:
        print(f"  {info.name}")
    if len(dead) > 20:
        print(f"  ... and {len(dead) - 20} more")

    print("\nUse --dead, --tree, --json, --markdown, or --stats for detailed output.")


# =============================================================================
# MAIN
# =============================================================================
def main():
    """Main entry point."""
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print(__doc__)
        return 0

    print("Scanning hooks...")
    hooks, router_map = audit_hooks()
    generate_report(hooks, router_map, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
