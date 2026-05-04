---
name: gitpack
version: "3.1.0"
status: "stable"
category: integration
enforcement: advisory
description: >
  Pack any Python directory into a compact LLM-ready context file. Use this skill whenever the user wants to
  distill, pack, compress, or prepare code for LLM consumption — phrases like "make this repo LLM-ready", "compress
  this codebase for context", "prepare code for AI analysis", "pack this directory", "create a context file from this
  repo". Also use when comparing /gitpack vs /repomix. Pure Python — no external AI tools required.
triggers:
  - /gitpack
aliases:
  - /gitpack
  - /pack
workflow_steps:
  - DISCOVER
  - EXTRACT
  - BUILD
  - APPEND
---

# /gitpack - LLM-Ready Code Packer

Pack a Python directory into a compact context file using only Python's stdlib (AST parsing + direct file reads). No external AI tools, no corruption, deterministic output.

## What This Does

Takes a Python codebase and produces two output files:
- **`<name>_sig.md`** — SIGNATURE TOC + DIRECTORY/FILE INDEX (compact, scannable)
- **`<name>_full.md`** — same + APPENDIX with full source code read directly from disk

Signatures are extracted via Python's `ast` module — exact, deterministic, no LLM involvement.

## Workflow

```
python -c "...inline AST packer..." <target_dir>
```
Or run manually — the packer is a simple inline script (no gitpack.py in this repo).

1. **DISCOVER** — Glob for all `.py` files in `<target_dir>`, applying exclusions
2. **EXTRACT** — Parse each file with `ast`, collect function/class signatures with type annotations
3. **BUILD** — Write two markdown files to `P:/.claude/.artifacts/`:
   - `_sig.md` — signatures + indexes only
   - `_full.md` — signatures + indexes + full source appendix
4. **APPEND** — Top-level `.md` files from `<target_dir>` appended to both outputs

**Default exclusions** — always applied unless user overrides with `--exclude`:
```
__pycache__/,*.pyc,*.pyo,*.so,*.dll,*.exe
.venv/,venv/,env/,site-packages/
.pytest_cache/,.mypy_cache/,.ruff_cache/,.tox/
.git/,.hg/,.svn/
dist/,build/,out/,target/,egg-info/,*.egg-info/
.idea/,.vscode/,.DS_Store,Thumbs.db
.env,.env.*,*.log
```

## Output Files

| File | Contents |
|------|----------|
| `<name>_sig.md` | PACK INFO, HOW TO USE, SIGNATURE TOC, DIRECTORY INDEX, FILE INDEX |
| `<name>_full.md` | All of the above + APPENDIX: FULL IMPLEMENTATIONS (full source from disk) |

**Output location:** `P:/.claude/.artifacts/` — always, never inside the target directory.
This prevents polluting source trees (especially skills/plugin cache) with temp files. |

## Features

- **Pure Python** — uses `ast` for signature extraction, no external dependencies
- **No corruption** — source read directly from disk for appendix, no LLM processing
- **Deterministic** — same input always produces same output
- **Markdown included** — top-level `.md` files appended automatically
- **Type annotations preserved** — return types and arg types shown when present

## Scope and Related Files

**Primary target:** the requested directory. But a complete LLM context often needs related files outside that path.

**Always include when present near the target:**
- Any companion `.py` files referenced by the target (e.g., a service that backs a skill)
- Any `CLAUDE.md`, `AGENTS.md`, or `.mcp.json` in the same tree
- If packing a skill, also pack its backing service, companion scripts, or related config files if they live in `P:/tools/`, `P:/.claude/`, or other well-known locations

**Rule:** If a file is named in code as a dependency or companion, it belongs in the pack. Err on the side of inclusion.

## Skill Name Resolution

When the target is a known skill name (e.g., `/git`, `handoff:id`), resolve it to a filesystem path before packing:

**Resolution order:**
1. `P:/.claude/skills/<name>/` — local skill directory
2. `P:/packages/.claude-marketplace/plugins/<plugin>/skills/<name>/` — marketplace source
3. `C:/Users/brsth/.claude/plugins/cache/local/<plugin>/<version>/skills/<name>/` — installed plugin cache

**Rule:** Skills installed via marketplace are loaded from the **cache on C:**, not from P: source. Always resolve through the cache path when the plugin is installed.

```python
# Skill name resolution helper
SKILL_CACHE_ROOT = Path("C:/Users/brsth/.claude/plugins/cache/local")
MARKETPLACE_ROOT = Path("P:/packages/.claude-marketplace/plugins")

def resolve_skill_path(skill_ref: str) -> Path | None:
    """Resolve a skill reference like '/git' or 'handoff:id' to a filesystem path."""
    # Strip leading slash and split on ':' for namespaced skills
    name = skill_ref.lstrip("/").split(":")[0]
    # Check marketplace plugins for matching skill
    for plugin_dir in MARKETPLACE_ROOT.iterdir():
        if not plugin_dir.is_dir():
            continue
        skill_path = plugin_dir / "skills" / name
        if skill_path.exists() and skill_path.is_dir():
            # Check if installed in cache
            cache_root = SKILL_CACHE_ROOT
            for cache_plugin in cache_root.iterdir() if cache_root.exists() else []:
                for version_dir in cache_plugin.iterdir() if cache_plugin.is_dir() else []:
                    installed = version_dir / "skills" / name
                    if installed.exists():
                        return installed
            return skill_path  # fall back to marketplace source
    return None
```

## Examples

```bash
# Pack a directory — outputs go to P:/.claude/.artifacts/
/gitpack P:\packages\cc-skills-meta

# Pack with exclusions
/gitpack ./my-project --exclude __pycache__,*.pyc
```

**Output:** `P:/.claude/.artifacts/<name>_sig.md` and `_full.md`

## Architecture

No `gitpack.py` in this repo — the packer is a simple inline Python script using `ast`. Run it directly from Bash with `python -c "..."` or copy the pattern into a temp script.

## See Also

- `/gitingest` — Clone + slice + upload to NotebookLM
- `/repomix` — XML/JSON output, skill generation
- `/aid` — Single-file or directory distillation with analysis prompts