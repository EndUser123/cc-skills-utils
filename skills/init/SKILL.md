---
name: init
id: init
version: "1.0.0"
status: "stable"
enforcement: advisory
category: initialization
description: Initialize CLAUDE.md at module/feature root
triggers:
  - '/init'
aliases:
  - '/init'

suggest:
  - /gitready
  - /standards
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
- Works with `/standards` for compliance
- Integrates with `/nse` for Next Step Engine

## Your Workflow

**EXECUTIVE DIRECTIVE:**

**When invoked:**

1. **Determine target location** from argument or current directory
2. **Check if CLAUDE.md already exists** at target
3. **Create CLAUDE.md** with appropriate template
4. **Report location created**

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
