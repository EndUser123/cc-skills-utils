---
name: exec
version: "1.0.0"
status: "stable"
description: CWO15 execution entry point - context-aware execution that analyzes conversation for next action.
category: execution
triggers:
  - /exec
aliases:
  - /exec

suggest:
  - /nse
  - /workflow
  - /build
---

# /exec — CWO15 Execution Entry (Context-Aware)

Context-aware execution entry point that analyzes conversation to determine next action. **Prefix ALL output with `[EXEC]` tag.**

## Purpose

Context-aware execution entry point that analyzes conversation to determine next action based on session context.

## Project Context

### Constitution/Constraints
- Follows CLAUDE.md constitutional principles
- Solo-dev appropriate (Director + AI workforce model)
- Evidence-first context analysis
- TDD compliance required (RED -> GREEN -> REFACTOR)

### Technical Context
- Analyzes: recent conversation, git status, errors, active TSK, file changes
- ML System Health Check (silent validation)
- Regression testing (automatic after implementation)
- TaskMaster resolution for active TSK directories

### Architecture Alignment
- CWO15 execution entry point
- Integrates with /specify, /cwo, /breakdown
- Part of CSF NIP workflow orchestration

## Your Workflow

### With Active TSK:
1. TaskMaster resolution (use existing TSK directory)
2. ML System Health Check (silent validation)
3. Validate Steps 1-7 (execute missing if needed)
4. Execute Step 8 (implementation with TDD)
5. Automatic regression testing
6. Report completion with next-step suggestions

### Without Active TSK:
1. Context analysis (conversation, git status, errors)
2. Identify next action based on context
3. Propose execution
4. Execute or confirm based on clarity

## Validation Rules

- All output prefixed with [EXEC] tag
- TDD compliance enforced
- Regression testing automatic after implementation
- Fresh git commands (never cached)

## Usage

```bash
# Context-aware (DEFAULT) — analyzes conversation, proposes execution
/exec

# With explicit task
/exec "implement user authentication system"

# Continue through to Step 14
/exec "implement feature" --continue

# Force (bypass validation)
/exec "deploy hotfix" --force

# Validate only
/exec --validate-only
```

## Context-Aware Behavior

**`/exec` ALWAYS analyzes context automatically:**

| Context Source | What It Provides |
|----------------|------------------|
| Recent conversation | What was just discussed, planned, or attempted |
| Git status | Uncommitted changes, recent commits, branch state |
| Recent errors | Failures, exceptions, issues that need fixing |
| Active TSK (if exists) | Formal task definition, requirements, planned steps |
| File changes | What code was just modified or created |

**Then proposes execution based on:**
- What work is in progress
- What errors need fixing
- What was just planned but not executed
- What git state suggests (uncommitted changes, etc.)

## What Happens

### With Active TSK:
1. **TaskMaster resolution** — Use existing TSK directory
2. **ML System Health Check** — Silent validation (report issues only)
3. **Validate Steps 1-7** — Execute missing if needed
4. **Execute Step 8** — Implementation with TDD
5. **REGRESSION (AUTOMATIC)** — Run related tests to catch breaks
6. **Report completion** — With next-step suggestions

### Without Active TSK (Context-Aware Mode):
1. **Context Analysis** — Recent conversation, git status, errors
2. **Identify Next Action** — What should happen next based on context
3. **Propose Execution** — Show what `/exec` found and suggests
4. **Execute or Confirm** — Proceed if clear, ask if ambiguous

## See Also

- `/specify` — Create TSK and Step 1 specification
- `/cwo` — Full workflow orchestration
- `/breakdown` — Planning phase with artifact generation
