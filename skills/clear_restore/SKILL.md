---
name: clear_restore
description: Remove RESTORE_CONTEXT.md file created by CKS restoration
category: management
version: 1.0.0
status: stable
triggers:
  - /clear_restore
aliases:
  - /clear_restore

suggest:
  - /restore
  - /checkpoint
  - /nse
---

# /clear_restore - Remove Context Restoration File

Removes the `RESTORE_CONTEXT.md` file created after compaction events.

## Purpose

Remove the RESTORE_CONTEXT.md file created by CKS restoration after compaction.

## Project Context

### Constitution/Constraints
- Solo-dev appropriate - manual cleanup after context review
- Evidence-first - verify file exists before attempting removal

### Technical Context
- File location: `P:/.claude/RESTORE_CONTEXT.md`
- Created by CKS restoration after context compaction
- Contains session context for continuity

### Architecture Alignment
- Works with `/restore`, `/checkpoint`, `/nse`
- Provides cleanup after CKS restoration workflow

## Your Workflow

1. Verify `P:/.claude/RESTORE_CONTEXT.md` exists
2. Remove file using `rm -f`
3. Report completion (or indicate file not found)

## Validation Rules

### Prohibited Actions
- Do NOT assume file exists without checking
- Do NOT remove other files in `.claude/` directory

## Usage

```bash
/clear_restore
```

## What It Does

Deletes `P:/.claude/RESTORE_CONTEXT.md` if it exists.

## When to Use

- After reviewing restored context
- After resuming work, no longer need reminder
- Before starting new task

## Implementation

```bash
rm -f "P:/.claude/RESTORE_CONTEXT.md"
```
