---
name: hooks-edit
version: "1.0.0"
status: "stable"
description: "Edit Claude Code hook files"
category: control
triggers:
  - '/hooks-edit'
aliases:
  - '/hooks-edit'

suggest:
  - /git-safety
  - /comply
  - /standards
---

# hooks-edit Skill

Temporary hook suspension for editing constitutional hooks.

## Purpose

Edit Claude Code hook files by temporarily suspending constitutional hooks.

## Project Context

### Constitution/Constraints
- Per CLAUDE.md: Hooks enforce constitutional rules structurally
- Editing hooks requires bypass to prevent hook self-blocking

### Technical Context
- Sets `CONSTITUTIONAL_HOOKS_BYPASS=1` in execution context
- Prevents recursive hook calls during hook editing
- Must be explicitly disabled after editing

### Architecture Alignment
- Integrates with git-safety for safe hook file editing
- Works with /comply and /standards for validation

## Your Workflow

When `/hooks-edit` is invoked:
1. Check if hooks are currently bypassed
2. If not, set bypass state and notify user
3. Remind to run `/hooks-edit --off` when done

## Validation Rules

### Prohibited Actions
- Do not leave hooks in bypassed state after editing
- Do not edit hooks without explicitly invoking `/hooks-edit`

## Activation

When user runs `/hooks-edit` or `/hooks-edit [hook_names...]`

## Behavior

1. Check if hooks are currently bypassed
2. If not, set bypass state and notify user
3. Remind to run `/hooks-edit --off` when done

## Environment

Sets `CONSTITUTIONAL_HOOKS_BYPASS=1` in the execution context.

## Exit

User runs `/hooks-edit --off` to remove bypass state.
