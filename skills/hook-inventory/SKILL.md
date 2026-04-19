---
name: hook-inventory
version: "1.0.0"
status: "stable"
description: Hook file inventory audit - classify all hooks as dead/active/router-dispatched/utility.
category: observability
triggers:
  - /hook-inventory
  - "hook inventory"
  - "dead hooks"
  - "router dispatched"
aliases:
  - /hooks-inv
---

# /hook-inventory - Hook File Inventory Audit

## Purpose

Comprehensively audit all Claude Code hook files to classify them as:
- **Direct-registered**: Hook appears in settings.json
- **Router-dispatched**: Called by a router (imported or subprocess)
- **Utility module**: Imported by other hooks, never standalone
- **Router file**: Consolidates multiple hooks
- **Test file**: In tests/ subdirectory
- **Archive/obsolete**: In archive/, _archive/, or orphaned/
- **Dead/standalone obsolete**: Exists but not referenced anywhere

## Execution Directive

**When invoked, run the hook inventory script:**

```bash
# Full inventory with categorization
python P:/.claude/skills/hook-inventory/hook_inventory.py

# Dead hooks only
python P:/.claude/skills/hook-inventory/hook_inventory.py --dead

# Router dispatch tree
python P:/.claude/skills/hook-inventory/hook_inventory.py --tree

# Export to JSON
python P:/.claude/skills/hook-inventory/hook_inventory.py --json > hooks_inventory.json

# Markdown report
python P:/.claude/skills/hook-inventory/hook_inventory.py --markdown
```

**DO NOT:**
- Manually count files
- Guess at router dispatch patterns
- Skip reading router files

## Output Locations

| File | Purpose |
|------|---------|
| `P:/.claude/hooks/reports/inventory.json` | Full inventory JSON |
| `P:/.claude/hooks/reports/dead_hooks.txt` | List of dead hooks |
| `P:/.claude/hooks/reports/inventory_report.md` | Human-readable report |

## Hook Classification Categories

| Category | Description | Example |
|----------|-------------|----------|
| `DIRECT_REGISTERED` | Hook appears in settings.json hooks array | `UserPromptSubmit_router.py` |
| `ROUTER_DISPATCHED` | Called by router (imported or subprocess) | `unified_prompt_injector.py` |
| `UTILITY_MODULE` | Imported by other hooks, never standalone | `shared_utils.py`, `hook_tracker.py` |
| `ROUTER_FILE` | Router that consolidates multiple hooks | `PreToolUse_write_router.py` |
| `TEST_FILE` | In tests/ subdirectory | `test_hooks_validation.py` |
| `ARCHIVE_OBSOLETE` | In archive/, _archive/, or orphaned/ | `archive/execution_evidence_gate.py` |
| `CONFIRMED_DEAD` | File exists but not referenced anywhere | `goal_anchor_obs.py` |
| `FILE_NOT_FOUND` | Referenced but file doesn't exist | `PostToolUse.py` (glob false positive) |
| `POSSIBLE_UTILITY` | Has references but not clearly an event hook | `analyze_hooks.py` |
| `SUBCOMPONENT` | Part of router/PostToolUse/Stop package | `posttooluse/fix_validator.py` |

## How It Works

1. **Parse settings.json** - Extract all directly registered hooks
2. **Scan all router files** - Extract router-dispatched hooks via:
   - Import statements (`from hook_name import ...`)
   - Subprocess calls (`subprocess.run([python, "hook_name.py"]`)
   - Wrapper function names (`wrap_<hook_name>`)
3. **Scan all hook files** - Build import dependency graph
4. **Cross-reference** - Check logs for actual execution evidence
5. **Classify** - Assign each file to a category
6. **Generate report** - JSON + markdown output

## Subcommands

```bash
/hook-inventory              # Full report
/hook-inventory --dead       # Show only dead hooks
/hook-inventory --tree       # Show router dispatch tree
/hook-inventory --json       # Export JSON
/hook-inventory --markdown    # Export markdown
```

## Quick Reference

```bash
# Find all dead hooks
/hook-inventory --dead

# See how hooks are dispatched
/hook-inventory --tree

# Get count by category
python P:/.claude/hooks/hook_inventory.py --stats
```

## Related Skills

- `/hook-audit` - Behavioral compliance monitoring
- `/clean` - Use inventory results to clean up dead hooks
- `/hooks` - Show active hook configuration
