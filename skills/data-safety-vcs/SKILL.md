---
name: data-safety-vcs
description: Data safety and version control standard for solo dev environments.
version: "1.0.0"
status: "stable"
category: strategy
triggers:
  - /data-safety-vcs

suggest:
  - /git-safety
  - /checkpoint
  - /backup
---



## Purpose

Prevent data loss and select correct VCS tool for Windows 11 solo development.

## Project Context

### Constitution/Constraints
- Solo-dev environment targeting 75-85% reliability
- No continuous monitoring or always-on tracking
- On-demand execution only
- Enterprise patterns prohibited

### Technical Context
- Windows 11 with PowerShell
- Git for root operations
- Anti-bleed gate for commit safety

### Architecture Alignment
- Part of CSF NIP governance
- Integrates with hooks system (PreToolUse_anti_bleed_gate.py)
- Terminal-scoped workflow to prevent session bleed

## Your Workflow

1. Identify operation risk level (high/medium/low)
2. Select correct VCS tool based on location
3. Use explicit paths (no wildcards) for staging
4. Commit immediately after each discrete unit of work
5. Push after commit (prevent local pileup)

## Validation Rules

- Check current directory before VCS operations
- Never use `git add .` or wildcard staging
- Verify staged files before commit
- Use `git status --porcelain` (fresh command, not cached)

### Prohibited Actions

- `git add .`, `git add *`, `git add -A`, `git add --all`
- Using sl from P:\ root
- Using sl push (use git push instead)
- Leaving WIP uncommitted across session switches
- Batch-committing unrelated work

## Trigger
File modifications, VCS operations, deletion, refactoring.

## Risk-Based Protection Protocol

### High-Risk (Automatic Backup)
- File deletions
- Major refactoring
- Critical system files
- Production code modifications

### Medium-Risk (Conditional Backup)
- Code refactoring
- Configuration modifications
- Documentation restructuring

### Low-Risk (No Backup)
- Minor code edits
- Comment changes
- Documentation updates

## VCS Tool Selection Rules (NON-NEGOTIABLE)

| Location | Operation | Tool | Reason |
|----------|-----------|------|--------|
| P:\ root | ANY | git | Sapling scans Windows system folders |
| P:\ root | status/add/commit | git | Sapling aborts on .BIN |
| Any location | push/pull/fetch | git | Remote operations use git |
| Any location | rebase/merge | git | Complex operations safer with git |

### MANDATORY CHECKLIST
1. Check current directory: pwd
2. If at P:\ root -> use git
4. When unsure -> use git (always works)

### TERMINAL-FOCUSED WORKFLOW (Anti-Bleed)
**Prevent session bleed: unrelated files sweeping into commits.**

**Rule:** Commit immediately after each discrete unit of work.

```
Unit of work → git add <specific-files> → git commit → git push
```

**FORBIDDEN:**
- `git add .` or wildcard staging (sweeps unrelated files)
- `git add *` (same problem)
- Leaving WIP uncommitted across session switches
- Batch-committing unrelated work

**REQUIRED:**
- `git add file1.py file2.md` (explicit paths only)
- `git status` before commit (verify staged files)
- `git diff --staged` (verify changes before commit)
- Push after each commit (prevent local pileup)

**Why:** The working directory is single-use. Each session should start clean.

### FORBIDDEN
- Using sl from P:\ root (permission errors)
- Using sl push (use git push instead)
- Attempting sapling operations without checking directory context

## CONSTITUTIONAL PRIORITY
This section overrides any skill or documentation suggesting sapling usage at P:\ root.

## Automated Rollback Trigger
For high-risk operations:
1. Create backup via sapling/git
2. Execute operation
3. Monitor for error signals
4. IF error detected -> Automatic rollback to backup
5. Report rollback to user with diagnostic logs
## Structural Enforcement

**PreToolUse_anti_bleed_gate.py** - Blocks wildcard git add at the LLM action level:
- Blocks: `git add .`, `git add *`, `git add -A`, `git add --all`, `sl add .`
- Allows: Explicit paths, `git add -u` (tracked only), `git add -p` (interactive)
- Location: `.claude/hooks/PreToolUse_anti_bleed_gate.py`
- Tests: `.claude/hooks/tests/test_PreToolUse_anti_bleed_gate.py` (21 tests)

This prevents the LLM from autonomously using wildcard staging.