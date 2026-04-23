---
name: cleanup
description: Review and clean up directory structure violations with LLM-guided analysis
category: maintenance
version: 1.0.0
status: stable
triggers:
  - /cleanup
  - "directory cleanup"
aliases:
  - /cleanup

suggest:
  - /comply
  - /bug-hunt
  - /standards
---

# /cleanup - Directory Structure Cleanup

Review and clean up directory structure violations with safe approval workflow.

## Purpose

Review and remediate directory structure violations using an interactive cleanup handler with approval gates.

## Project Context

### Constitution/Constraints
- **PART T: Truthfulness** - Safety over speed, require explicit approval for destructive actions
- **PART E: Evidence-first** - Verify violations before cleanup
- **PART Q: Regression Prevention** - Fix source code creating violations, not symptoms
- **Complete Solutions** - Reference checking before deletion, prevent symptom-only fixes

### Technical Context
- Uses `P:\.claude\hooks\path_validator.py` for violation detection
- Uses `P:\.claude\skills\cleanup\scripts\cleanup.py` for interactive cleanup handler
- Supports modes: Standard (50), Limited (--max 20), Full (--max 100), Preview (--dry-run), Auto-approve (--yes)
- Integrates with `directory_policy.json` as authoritative configuration

### Architecture Alignment
- Works with `/comply`, `/bug-hunt`, `/standards`
- Integrates with path validation hooks
- Results reported in `/main` system health check

## .claude Directory Cleanup (NEW)

**Purpose**: Clean up junk files from `P:\.claude/` directory using patterns from `directory_policy.json`.

**Usage**:
```bash
# Dry-run mode (safe - shows what would be deleted)
python P:\.claude\skills\cleanup\scripts\claude_directory_cleanup.py

# Execute cleanup (actually deletes files)
python P:\.claude\skills\cleanup\scripts\claude_directory_cleanup.py --execute
```

**What it cleans**:
- Backup files (`*.backup*`)
- Session debris (`session-task-console_*.json`, `current_session.json`, etc.)
- Temporary scripts (`consolidate_*.py`, `temp_*.py`, `tmp_*.py`)
- Old documentation (`CONTEXT-FILTERING-QUICKREF.md`, `LLM_*.md`, etc.)
- Cache directories (`.ruff_cache/`, `.mypy_cache/`, `.pytest_cache/`, `.hypothesis/`)
- Backup directories (`backups/`, `agents.backup.*`)

**Patterns are defined in**: `P:\.claude\hooks\config\directory_policy.json` under `claude_directory.blocked_root_patterns`

**Safe by default**: Always runs in dry-run mode first. Review the output before using `--execute`.

---

## Your Workflow

### PHASE 1: Source Code Analysis (NEW - PRINCIPLE-FIRST APPROACH)

**PRINCIPLE**: Fix the source, not the symptom.

Before suggesting file moves, `/cleanup` now analyzes what code is generating violations:

1. **Identify source problems**: Search for code generating violations
   - Coverage files: Search for `--cov-report`, `coverage.report` patterns
   - Test evidence: Identify TDD enforcer, quality monitor sources
   - Data misplacement: Find code creating files in wrong locations

2. **Display source code issues**: Show what needs fixing
   - Source file path
   - Description of the problem
   - Suggested fixes with specific code changes
   - List of violations caused by each source

3. **Recommendation**: Fix source code first, then re-run `/cleanup`

### PHASE 2: Violation Cleanup (Interactive Mode)

After source code analysis, review and clean remaining violations:

1. Review displayed violations with reasons and suggestions
2. Approve cleanup session when prompted
3. For each violation, choose action:
   - **[m]ove** - Move to suggested location
   - **[d]elete** - Delete the file/directory
   - **[s]kip** - Skip this item
   - **[q]uit** - Exit cleanup
4. View cleanup summary and final compliance verification

### Dry-Run Mode

```bash
# Preview violations without executing any actions
python P:\.claude\skills\cleanup\scripts\cleanup.py --dry-run
```

### Auto-Approve Mode (Caution!)

```bash
# Auto-approve all suggested actions
python P:\.claude\skills\cleanup\scripts\cleanup.py --yes
```

## Validation Rules

### Prohibited Actions
- Do NOT cleanup without reviewing violations first
- Do NOT fix violations without addressing source code that created them
- Do NOT delete directories without checking for active references

### Safety Features
- Reference checking before deletion (prevents accidental deletion of actively-used directories)
- Per-file confirmation required
- Summary and verification after cleanup
- Dry-run mode for preview

## Modes

| Mode | Command | Use Case |
|------|---------|----------|
| Interactive | `python scripts/cleanup.py` | Manual review, per-file approval |
| Dry-Run | `python scripts/cleanup.py --dry-run` | Preview without changes |
| Limited | `python scripts/cleanup.py --max 20` | Quick session, fewer files |
| Auto-approve | `python scripts/cleanup.py --yes` | Automated cleanup (caution!) |

## Execution Protocol

### Two-Phase Approach

**PHASE 1: Source Code Analysis**
1. Run `scripts/cleanup.py` to scan for violations
2. **Source analysis runs automatically**:
   - Searches for code generating violations
   - Maps violations to their source files
   - Displays source problems with suggested fixes
3. **If source problems found**: Fix source code first, then re-run `/cleanup`
4. **If source analysis finds nothing but violations remain**: Manually investigate each remaining violation:
   - List contents of the flagged path (`ls`, `Glob`)
   - Determine if it's stale debris (empty/obsolete → delete) or intentional (should be added to policy)
   - **Investigate BEFORE adding to policy**: verify the file serves no purpose before declaring it junk
   - Do NOT skip to Phase 2 without making a determination
5. Re-run `/cleanup` after resolving each violation

**PHASE 2: File Cleanup**
5. **Verify**: Review summary and re-validate

## Integration with /main

The `/main` command now includes filesystem structure validation from `/cleanup`:

```bash
# /main runs cleanup.py --json automatically
/main

# Output example:
[filesystem]: Filesystem structure violations detected
  [WARN] 27 filesystem violations (run /cleanup)
  • UNAUTHORIZED_ROOT_DIRECTORY: 13 violations
  • UNKNOWN_CONFIG_FILE: 9 violations
  • BLOCKED_ROOT_FILE: 3 violations
  • BLOCKED_ROOT_DIRECTORY: 2 violations
```

**Note:** `/main` uses `cleanup.py --json` to get violation counts and types. For detailed violation analysis with source code tracing, run `/cleanup` directly.

## Manual LLM-Guided Cleanup (Optional)

For complex cleanup scenarios requiring LLM analysis:

```bash
# Generate detailed cleanup prompt with analysis commands
python P:\.claude\hooks\path_validator.py --generate-cleanup-prompt --max-files 50
```
