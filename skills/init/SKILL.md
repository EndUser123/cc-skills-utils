---
name: init
id: init
version: "1.0.0"
status: "stable"
enforcement: advisory
category: initialization
workflow_steps: [locate, check, create, report, rule-shape-check]
description: Initialize CLAUDE.md at module/feature root
triggers:
  - '/init'
aliases:
  - '/init'

suggest:
  - /gitready
---


# /init — Initialize CLAUDE.md

Creates `CLAUDE.md` at the appropriate root level for a module or feature.

## Purpose

Initialize CLAUDE.md at module/feature root for guidance.

## Project Context

### Constitution/Constraints
- Per CLAUDE.md: Module-level CLAUDE.md provides context-specific guidance
- Should not override root CLAUDE.md constitutional rules

### Technical Context
- Creates `CLAUDE.md` at appropriate root level
- Includes template with module purpose, development commands, key files
- Respects existing CLAUDE.md (error if already exists)

### Architecture Alignment
- Integrates with `/build` for feature development
- Integrates with `/nse` for Next Step Engine

## Your Workflow

**EXECUTIVE DIRECTIVE:**

**When invoked:**

1. **Determine target location** from argument or current directory
2. **Check if CLAUDE.md already exists** at target
3. **Create CLAUDE.md** with appropriate template
4. **Report location created**
5. **Rule-shape check** — review each entry against the Rule Placement table below; if any rule is path-scoped or activity-bound, tell the user the better mechanism (`.claude/rules/` or a skill) instead of leaving it stranded in CLAUDE.md

---

## Usage

```bash
/init                          # Initialize at current directory root
/init <path>                   # Initialize at specific path
/init src/features/constraints # Initialize specific module
```

---

## Location Detection

**Target is determined as:**

| Input Pattern | Resolved Location |
|---------------|-------------------|
| No argument | Current working directory |
| `src/features/<name>` | `src/features/<name>/CLAUDE.md` |
| `src/csf/<name>` | `src/csf/<name>/CLAUDE.md` |
| `tools/<name>` | `tools/<name>/CLAUDE.md` |
| Relative path | Resolved from current directory |

---

## Template

Created `CLAUDE.md` includes:

```markdown
# CLAUDE.md

This file provides guidance to Claude Code when working with code in this module.

## Module Purpose

[Describe what this module does]

## Development Commands

```bash
# Testing
pytest tests/ -v

# Linting (ruff)
ruff check .
ruff format .
ruff check --fix .

# Type checking
mypy src/
```

## Key Files

| File | Purpose |
|------|---------|
| `main.py` | Entry point |
| `config.py` | Configuration |

## Dependencies

- Internal: [list internal deps]
- External: [list external deps]

## Notes

[Any important notes for Claude Code]

## Rule Placement

Claude Code loads this file on every session in this subtree. Not every rule belongs here — pick the mechanism that matches the rule's trigger:

| Rule triggers on... | Put it in... | Why |
|---|---|---|
| A specific file path or extension (e.g. `*.py`, `src/api/**`) | `.claude/rules/<name>.md` with `paths:` frontmatter | Loaded only when those files are touched — no cost otherwise |
| An activity or procedure (e.g. "when releasing", "on PR") | a Skill | Invoked on demand, not always loaded |
| Everything in this subtree, always | this `CLAUDE.md` | Always-loaded context — keep it <200 lines |
```

---

## Validation Rules

### Prohibited Actions
- Do NOT overwrite existing CLAUDE.md without confirmation
- Do NOT create at non-module roots without explicit path
- Do NOT use templates that override constitutional rules

### Required Checks
- Always check if CLAUDE.md exists at target location
- Always verify target path is valid directory
- Always use appropriate template for module type

## Error Handling

```
❌ CLAUDE.md already exists
→ Location: <path>
→ Action: Delete existing file first, or use /doc to update

❌ Invalid path
→ Path: <path>
→ Action: Verify path exists
```
