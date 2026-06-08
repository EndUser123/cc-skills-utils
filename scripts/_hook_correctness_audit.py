"""
Hook correctness audit for plugin-audit-and-fix.py.

Checks all plugin hook files for:
  1. Python syntax errors (ast.parse)
  2. Python 3.14+ import alias patterns (import X as _X)
  3. Dangling _P / _s / _l alias references
  4. normalize_stdout defined inside bootstrap block
  5. Stop hook schema compliance (allow vs approve)
  6. State file path drift (.artifacts/ vs hooks/state/)
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
from pathlib import Path
from typing import Optional


# Only flag bare underscore aliases: `import x as _`  (Python 3.14 SyntaxError).
# `import x as _s` / `import x as _os` are valid — do NOT flag them.
_IMPORT_ALIAS_PATTERNS = [
    re.compile(r"^import\s+\w+\s+as\s+_(?!\w)", re.MULTILINE),
    re.compile(r"^from\s+\w+\s+import\s+.*\s+as\s+_(?!\w)", re.MULTILINE),
]
_STALE_ALIAS_REFS = re.compile(r"\b_P\b|_s\.path\b|_l\b")
# Detects whether the bootstrap block defines the old aliases — if so, post-bootstrap
# references to _P / _s / _l are not dangling; the aliases are still in scope.
_BOOTSTRAP_DEFINES_ALIAS = re.compile(
    r"import\s+sys\s+as\s+_\w+|from\s+pathlib\s+import\s+Path\s+as\s+_\w+"
)


def audit_hook_correctness(plugins_dir: Path, plugin_filter: Optional[str] = None) -> list[dict]:
    """Audit all plugin hook files for correctness issues."""
    findings = []

    def _check_file(fpath: Path, plugin_name: str) -> list[dict]:
        results = []
        try:
            txt = fpath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return results

        # 1. Syntax check
        try:
            ast.parse(txt)
        except SyntaxError as e:
            results.append({
                "plugin": plugin_name,
                "file": str(fpath.relative_to(plugins_dir.parent.parent)),
                "type": "syntax_error",
                "message": f"SyntaxError at line {e.lineno}: {e.msg}",
                "line": e.lineno,
                "fix_available": False,
            })
            return results

        # 2. Import alias patterns
        for pattern in _IMPORT_ALIAS_PATTERNS:
            for m in pattern.finditer(txt):
                line_no = txt[:m.start()].count("\n") + 1
                line = txt.splitlines()[line_no - 1].strip()
                results.append({
                    "plugin": plugin_name,
                    "file": str(fpath.relative_to(plugins_dir.parent.parent)),
                    "type": "import_alias",
                    "message": f"Python 3.14+ SyntaxError: import alias: {line}",
                    "line": line_no,
                    "fix_available": True,
                })

        # 3. Dangling alias refs after bootstrap.
        # Only flag when the bootstrap uses the *new* canonical form (plain
        # `import sys`) and NOT the old alias style.  If the bootstrap block
        # itself defines `import sys as _s` / `from pathlib import Path as _P`
        # the aliases are still in scope — post-bootstrap uses are valid.
        bootstrap_end_pos = txt.find("# --- end bootstrap ---")
        bootstrap_start_pos = txt.find("# --- plugin bootstrap ---")
        if bootstrap_end_pos >= 0 and bootstrap_start_pos >= 0:
            bootstrap_block = txt[bootstrap_start_pos:bootstrap_end_pos]
            if not _BOOTSTRAP_DEFINES_ALIAS.search(bootstrap_block):
                after_bootstrap = txt[bootstrap_end_pos:]
                for m in _STALE_ALIAS_REFS.finditer(after_bootstrap):
                    abs_pos = bootstrap_end_pos + m.start()
                    ref_line_no = txt[:abs_pos].count("\n") + 1
                    ref_line = txt.splitlines()[ref_line_no - 1].strip()
                    results.append({
                        "plugin": plugin_name,
                        "file": str(fpath.relative_to(plugins_dir.parent.parent)),
                        "type": "dangling_alias",
                        "message": f"Unresolved alias reference: {ref_line}",
                        "line": ref_line_no,
                        "fix_available": True,
                    })

        # 4. normalize_stdout inside bootstrap block
        bootstrap_start = txt.find("# --- plugin bootstrap ---")
        bootstrap_end = txt.find("# --- end bootstrap ---")
        norm_pos = txt.find("def _normalize_stdout", bootstrap_start) if bootstrap_start >= 0 else -1
        if bootstrap_start >= 0 and bootstrap_end >= 0 and 0 <= norm_pos < bootstrap_end:
            line_no = txt[:norm_pos].count("\n") + 1
            results.append({
                "plugin": plugin_name,
                "file": str(fpath.relative_to(plugins_dir.parent.parent)),
                "type": "normalize_in_bootstrap",
                "message": "_normalize_stdout defined inside bootstrap block — broken structure",
                "line": line_no,
                "fix_available": True,
            })

        # 5. Stop hook schema: "allow" instead of "approve"
        is_stop = "/stop" in str(fpath) or "# --- Stop" in txt[:200]
        if is_stop:
            try:
                r = subprocess.run(
                    ["python", str(fpath)],
                    input="{}",
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                out = (r.stdout or "").strip()
                if out:
                    try:
                        obj = json.loads(out)
                        if obj.get("decision") == "allow":
                            results.append({
                                "plugin": plugin_name,
                                "file": str(fpath.relative_to(plugins_dir.parent.parent)),
                                "type": "schema_allow",
                                "message": "Stop hook outputs 'allow' instead of 'approve' — schema violation",
                                "line": None,
                                "fix_available": False,  # fixed at hook_runner level
                            })
                    except json.JSONDecodeError:
                        pass
            except Exception:
                pass

        # 6. dirname-derived global-resource path (plugin-migration trap).
        # A hook that has the bootstrap `_hooks_dir` but builds a path to a
        # GLOBAL resource dir (config/rules/templates) from a *different*
        # dirname(__file__)-derived var resolves to its own hooks/<phase>/
        # subdir after migration — so the resource is silently never found
        # (e.g. directory_policy loaded an empty allowlist and blocked every
        # external write). Use `_hooks_dir` instead.
        if "_hooks_dir" in txt:
            for am in re.finditer(
                r"(\w+)\s*=\s*(?:os\.path\.dirname\(os\.path\.abspath\(__file__\)\)"
                r"|(?:Path|PathLib)\(__file__\)\.resolve\(\)\.parent)",
                txt,
            ):
                var = am.group(1)
                if var == "_hooks_dir":
                    continue
                join_re = re.compile(
                    rf'\b{re.escape(var)}\b\s*\)?\s*/\s*"(?:config|rules|templates)"'
                    rf'|os\.path\.join\(\s*{re.escape(var)}\s*,\s*"(?:config|rules|templates)"'
                )
                jm = join_re.search(txt)
                if jm:
                    results.append({
                        "plugin": plugin_name,
                        "file": str(fpath.relative_to(plugins_dir.parent.parent)),
                        "type": "dirname_global_resource_path",
                        "message": (
                            f"Global resource path built from '{var}' (= dirname(__file__)) "
                            f"instead of bootstrap '_hooks_dir'. After plugin migration this "
                            f"resolves to the hook's own subdir and the resource is silently "
                            f"not found. Use _hooks_dir."
                        ),
                        "line": txt[:jm.start()].count("\n") + 1,
                        "fix_available": False,
                    })
                    break

        return results

    # Walk all plugin hooks directories
    for plugin in sorted(plugins_dir.iterdir()):
        if plugin.name.startswith(".") or not plugin.is_dir():
            continue
        if plugin_filter and plugin.name != plugin_filter:
            continue

        for hook_dir in ["hooks", "hooks/stop", "hooks/pretool",
                          "hooks/posttool", "hooks/userpromptsubmit"]:
            hooks_path = plugin / hook_dir
            if not hooks_path.exists():
                continue
            for fpath in sorted(hooks_path.glob("*.py")):
                if fpath.name.startswith("_"):
                    continue
                for finding in _check_file(fpath, plugin.name):
                    findings.append(finding)

        # Router block-reason check: a dispatch router that blocks via exit(2)
        # MUST write the reason to stderr — the harness shows ONLY stderr for
        # exit-2 blocks, so reason-on-stdout yields a bare "Blocked by hook"
        # (see blocking_stderr_standard). Guards against regenerated routers
        # losing the _emit_block stderr path.
        for router in plugin.rglob("__lib/router.py"):
            try:
                rtxt = router.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "sys.exit(2)" in rtxt and "sys.stderr" not in rtxt:
                findings.append({
                    "plugin": plugin.name,
                    "file": str(router.relative_to(plugins_dir.parent.parent)),
                    "type": "block_reason_not_on_stderr",
                    "message": "Router blocks via exit(2) but never writes stderr — "
                               "block reason will be lost (bare 'Blocked by hook'). "
                               "Route the block through an _emit_block() helper.",
                    "line": None,
                    "fix_available": False,
                })

    return findings


def fix_hook_correctness(plugins_dir: Path, plugin_filter: Optional[str] = None) -> list[dict]:
    """Auto-fix hook correctness issues found by audit_hook_correctness."""
    results = []
    audit_results = audit_hook_correctness(plugins_dir, plugin_filter)

    by_file: dict[str, list[dict]] = {}
    for f in audit_results:
        if not f.get("fix_available"):
            continue
        by_file.setdefault(f["file"], []).append(f)

    for fpath_str, issues in by_file.items():
        fpath = plugins_dir.parent.parent / fpath_str
        if not fpath.exists():
            continue

        txt = fpath.read_text(encoding="utf-8")
        original = txt
        fixed_any = False

        for issue in issues:
            if issue["type"] == "import_alias":
                # Replace: "import sys as _s; from pathlib import Path as _P"
                # With: "import sys\nfrom pathlib import Path"
                old_import = re.compile(
                    r"import\s+(\w+)\s+as\s+_\w+\s*;?\s*from\s+pathlib\s+import\s+Path\s+as\s+_\w+"
                )
                txt = old_import.sub("import \\1\nfrom pathlib import Path", txt)
                # Also handle single-alias lines
                single_alias = re.compile(r"import\s+(\w+)\s+as\s+_\w+")
                # Only replace if the same module is also imported the standard way
                existing_imports = set(re.findall(r"^import\s+(\w+)", txt, re.MULTILINE))
                for m in single_alias.finditer(txt):
                    mod = m.group(1)
                    if mod not in existing_imports:
                        txt = txt[:m.start()] + f"import {mod}" + txt[m.end():]
                fixed_any = True

            elif issue["type"] == "dangling_alias":
                txt = txt.replace("Path(", "Path(")
                txt = txt.replace("sys.path", "sys.path")
                txt = txt.replace("_l = Path(", "_lib = Path(")
                txt = txt.replace("str(_l)", "str(_lib)")
                fixed_any = True

            elif issue["type"] == "normalize_in_bootstrap":
                # Move _normalize_stdout out of bootstrap block to after end marker
                bs = txt.find("# --- plugin bootstrap ---")
                be = txt.find("# --- end bootstrap ---")
                ns = txt.find("def _normalize_stdout", bs) if bs >= 0 else -1
                if bs >= 0 and be >= 0 and ns >= 0 and ns < be:
                    # Find end: next "\ndef " after function start
                    after_func = txt[ns + 20:]
                    ne_search = re.search(r"\ndef\s", after_func)
                    ne = ns + 20 + (ne_search.start() if ne_search else len(txt))
                    func_body = txt[ns:ne].strip()
                    # Remove from bootstrap block
                    txt = txt[:ns] + txt[ne:]
                    # Insert after end marker
                    em = txt.find("# --- end bootstrap ---")
                    if em >= 0:
                        insert_pos = em + 22
                        txt = txt[:insert_pos] + "\n\n" + func_body + "\n" + txt[insert_pos:]
                fixed_any = True

        if fixed_any and txt != original:
            try:
                ast.parse(txt)
                fpath.write_text(txt, encoding="utf-8")
                results.append({
                    "plugin": issues[0]["plugin"],
                    "file": fpath_str,
                    "type": "hook_correctness_fix",
                    "actions": [f"Applied {len(issues)} fix(es): {', '.join(sorted(set(i['type'] for i in issues)))}"],
                    "fixed": True,
                })
            except SyntaxError as e:
                results.append({
                    "plugin": issues[0]["plugin"],
                    "file": fpath_str,
                    "type": "hook_correctness_fix",
                    "errors": [f"Auto-fix produced invalid Python: {e}"],
                    "fixed": False,
                })

    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Hook correctness audit")
    parser.add_argument("--plugins-root", required=True, help="Plugin root directory")
    parser.add_argument("--fix", action="store_true", help="Auto-fix issues")
    parser.add_argument("--plugin", help="Filter to specific plugin")
    args = parser.parse_args()

    plugins_dir = Path(args.plugins_root)
    if args.fix:
        results = fix_hook_correctness(plugins_dir, args.plugin)
    else:
        results = audit_hook_correctness(plugins_dir, args.plugin)

    print(f"Findings: {len(results)}")
    for r in results:
        msg = r.get("message")
        if not msg and r.get("errors"):
            msg = r["errors"][0]
        elif not msg and r.get("actions"):
            msg = r["actions"][0]
        elif not msg:
            msg = "no details"
        print(f"  [{r.get('type', '?')}] {r.get('file', '?')}: {str(msg)[:80]}")
