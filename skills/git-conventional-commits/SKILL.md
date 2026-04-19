---
triggers:
  - /git-conventional-commits
aliases:
  - /git-conventional-commits

suggest:
  - /commit
  - /push



name: git-conventional-commits
version: "1.0.0"
status: "stable"
description: Generate and validate commit messages following Conventional Commits specification.
category: execution
---

# Conventional Commits for CSF NIP

Generate structured commit messages that integrate with CSF NIP workflow.

## Purpose

Generate and validate commit messages following Conventional Commits specification.

## Project Context

### Constitution/Constraints
- Per CLAUDE.md: Follow git-safety protocols before committing
- Per git-conventional-commits: Subject line < 50 characters, imperative mood

### Technical Context
- Format: `type(scope): subject`
- Types: feat, fix, refactor, perf, test, docs, style, chore, revert
- Integrates with Sapling (`sl commit`)

### Architecture Alignment
- Works with git-safety skill for validation
- Works with git-sapling skill for Sapling-specific commands
- Enforced by hooks in `P:/.claude/hooks/`

## Your Workflow

When generating commit messages:
1. Identify primary change type (feat/fix/refactor/etc.)
2. Determine affected scope (hooks/cks/orchestrator/etc.)
3. Write concise subject (<50 chars, imperative mood)
4. Add body if needed (explains why, not how)

## Validation Rules

### Validation Checklist
- Type is one of: feat, fix, refactor, perf, test, docs, style, chore, revert
- Subject line < 50 characters
- Subject uses imperative mood ("add" not "adds")
- No period at end of subject
- Scope is relevant to change
- Body explains why (not how) if needed

## Format

```
type(scope): subject under 50 chars

Optional body explaining the why and what, not how.

Refs: TSK-ID
```

## Types

| Type | When to Use | Example |
|------|-------------|---------|
| `feat` | New feature | `feat(orchestrator): add parallel task execution` |
| `fix` | Bug fix | `fix(hooks): resolve TDD state race condition` |
| `refactor` | Code restructuring | `refactor(cks): simplify storage interface` |
| `perf` | Performance improvement | `perf(vector): optimize similarity search` |
| `test` | Test additions | `test(hooks): add PostToolUse coverage` |
| `docs` | Documentation | `docs(commands): update CWO12 reference` |
| `style` | Formatting | `style(python): apply black formatter` |
| `chore` | Maintenance | `chore(deps): update pytest to 9.0` |
| `revert` | Revert previous | `revert(feat): rollback multi-agent dispatch` |

## CSF NIP Scopes

Common scopes in this codebase:
- `orchestrator` - Multi-agent coordination
- `hooks` - Claude Code hooks (PreToolUse, PostToolUse)
- `cks` - Cognitive Knowledge System
- `nip` - NIP command infrastructure
- `quality` - Code quality and validation
- `skills` - Workspace and project skills
- `constitution` - CSF NIP constitution

## Integration with Sapling

When using `sl commit`, format as:
```
sl commit -m "feat(scope): subject"
```

Sapling will convert to git format automatically.

## Examples

### Good
```
feat(hooks): add two-phase debug warning system

Phase 1 (PostToolUse) detects errors and writes to state.
Phase 2 (PreToolUse) reads state and shows warning before next tool.

This implements the "shift-left" pattern from System 2 thinking.

Refs: TSK-251228-1443
```

### Poor
```
fixed git stuff

Changed the hooks to work better.
```

## Activation Triggers

This skill activates when:
- User asks about committing changes
- User asks for commit message format
- User mentions "commit message", "conventional commits"
- User runs commands like `/sl commit`, `git commit`
- Previous tool output contains "commit" and context suggests formatting needed
- Subagent spawned with git-related task

## Validation Checklist

Before accepting a commit message:
- [ ] Type is one of: feat, fix, refactor, perf, test, docs, style, chore, revert
- [ ] Subject line < 50 characters
- [ ] Subject uses imperative mood ("add" not "adds")
- [ ] No period at end of subject
- [ ] Scope is relevant to change
- [ ] Body explains why (not how) if needed

## Generating Commit Messages

When user asks for a commit message, analyze the changes and generate:

1. **Identify the primary change type** (feat/fix/refactor/etc.)
2. **Determine the affected scope** (hooks/cks/orchestrator/etc.)
3. **Write a concise subject** (<50 chars, imperative mood)
4. **Add body if needed** (explains why, not how)

### Example Generation

Input: "Added two-phase debug warning to hooks"

Output:
```
feat(hooks): add two-phase debug warning system

Phase 1 (PostToolUse) detects errors and writes to session state.
Phase 2 (PreToolUse) reads state and shows warning before next tool.
```

## Integration Notes

This skill works with:
- **git-safety** - Validates safety before committing
- **git-sapling** - Provides sapling-specific commit commands
- Hooks in `P:/.claude/hooks/` - Enforce conventional commit format

## Metadata

**Version:** 1.0.0
**Created:** 2025-12-29
**Purpose:** Consistent commit message format
