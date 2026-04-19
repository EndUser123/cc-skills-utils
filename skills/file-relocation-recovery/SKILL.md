---
name: file-relocation-recovery
version: "1.0.0"
status: "stable"
description: Auto-relocation system for CSF root files and how to recover "missing" files.
category: operations
triggers:
  - 'file disappeared'
  - 'where did my file go'
  - 'file not found'
  - 'file moved'
  - 'file relocation'
aliases:
  - '/file-relocation'
suggest:
  - /research
---

## Purpose


## How It Works

1. **PreToolUse** detects CSF root write, warns but ALLOWS
2. File gets written to the "wrong" location
3. **PostToolUse** relocator moves it to correct location
4. You see: `📁 FILE RELOCATED: P:/__csf/test.py → P:/__csf/tests/test.py`

## Auto-Routing Rules

| File Pattern | Relocated To |
|--------------|--------------|
| `.claude/plans/*` | `P:/__csf/.speckit/plans/active/` |
| `test_*.py`, `*_test.py` | `P:/__csf/tests/` |
| `fix_*.py`, `clean_*.py` | `P:/__csf/scripts/` |
| `*_report*.json` | `P:/__csf/reports/` |
| Other CSF root files | `P:/__csf/.staging/` |

## File Relocation Recovery

When a file you wrote "disappears" or isn't where expected:

1. **Check relocation log first** (fastest path):

   ```bash
   tail -5 "P:/.claude/session_data/file_relocations.jsonl"
   ```

2. **Hook that does relocation:** `P:/.claude/hooks/PostToolUse_file_relocator.py`

3. **Don't search randomly** - the log tells you exactly where files went.

## What This Means For You

- **Don't fight path blocks** - the system handles it
- **Check relocations** - if you see a relocation message, note the new path
- **Use proper paths upfront** - avoid relocation overhead by targeting correct directories

## Still Blocked

These paths are still blocked (not auto-relocated):

- External paths (outside `P:/`) without user consent
- System-critical paths
- Protected `.claude` configuration files

## Trigger

Activate when:
- A file you wrote "disappears" or isn't where expected
- You see a relocation message and want to understand it
- Blocked from writing to certain paths
