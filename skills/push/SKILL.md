---
name: push
description: Fast push with retry logic for concurrent operations
version: 1.0.0
status: stable
category: git
triggers:
  - /push
aliases:
  - /push

suggest:
  - /commit
  - /git-safety
---

# /push - Fast Push

## Purpose

Fast push with retry logic for concurrent operations. Pushes the current branch with automatic retry for `index.lock` conflicts from concurrent git operations across multiple terminals.

## Project Context

### Constitution / Constraints
- **Solo-dev constraints apply** (CLAUDE.md)
- **Git-primary repo**: Uses git with retry instead of sl (sapling) for reliability
- **Concurrent operations**: Handle `index.lock` conflicts from multi-terminal workflow
- **Scratchpad worktrees**: Commits must be done first (`/commit` or `/sp commit`)

### Technical Context
- **Script**: `P:/__csf/.staging/git_push_with_retry.py`
- **Retry logic**: 5 attempts with exponential backoff (1s, 2s, 4s, 8s, 16s)
- **Lock handling**: Attempts to remove stale lock files before retry
- **Why not sl**: Sapling requires tracking entire repo state separately from git, causing sync issues
- **Current directory**: Pushes branch in current working directory

### Architecture Alignment
- Integrates with /commit (commit before push), /git-safety (pre-push checks)
- Links to /sp (scratchpad worktree management)
- Part of git workflow ecosystem

## Your Workflow

1. **VERIFY COMMIT** — Ensure changes are committed (`git status`, `git log -1`)
2. **EXECUTE PUSH** — Run git_push_with_retry.py with automatic retry
3. **HANDLE LOCKS** — Clear stale `index.lock` files if conflicts detected
4. **RETRY WITH BACKOFF** — 5 attempts with delays (1s, 2s, 4s, 8s, 16s)
5. **REPORT RESULT** — Success or failure with attempt count
6. **SUGGEST NEXT** — Offer to continue working or verify remote

## Validation Rules

- **Before pushing**: Verify commit exists (`git log -1`)
- **After lock conflict**: Clear stale locks, retry with backoff
- **After success**: Verify remote received commits
- **For scratchpad**: Use `/sp commit` before `/push`

### Prohibited Actions

- Pushing without committing first
- Using sl (sapling) in git-primary repo
- Skipping lock cleanup on retry
- Pushing from wrong directory

## Usage

```bash
/push
```

Executes: `python __csf/.staging/git_push_with_retry.py`

## Concurrency Support

- Automatic retry (5 attempts) with exponential backoff
- Handles `index.lock` conflicts from concurrent operations
- 1s, 2s, 4s, 8s, 16s delays between retries
- Attempts to remove stale lock files before retry

## Why not sl?

sl (Sapling) requires tracking the entire repo state separately from git, which
causes sync issues. For a git-primary repo, using git with retry is more reliable.

## Notes

- Pushes the current branch in the current directory
- For scratchpad worktrees, commits must be done first (`/commit` or `/sp commit`)
- Use `/sp` for worktree create/list operations

## See Also

- `/commit` - Commit changes
- `/sp` - Scratchpad worktree management
