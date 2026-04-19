---
name: scratchpad
description: Persistent scratchpad worktree management with sl (lock-free)
version: "1.0.0"
status: stable
category: strategy
activation_triggers: ['/scratchpad', '/sp']
triggers:
  - '/scratchpad'
aliases:
  - '/scratchpad'

suggest:
  - /sp
  - /sap
  - /git-worktrees
---


# /scratchpad - Scratchpad Worktrees

Manage isolated git worktrees for experimental work using sl (Sapling) for lock-free operations.

## Purpose

Manage isolated git worktrees for experimental work without lock conflicts.

## Project Context

### Constitution/Constraints
- Solo dev authority: no multi-user coordination needed
- Lock-free operations required for parallel terminal usage
- Files must not be written to P:/__csf root (hook enforcement)

### Technical Context
- Uses sl (Sapling SCM) instead of git for lock-free operations
- Worktrees stored at P:/worktrees/<name>/
- Python handler at src/modules/scratchpad/commands.py

### Architecture Alignment
- Part of CSF NIP scratchpad module
- Integrates with sap (Sapling) workflow
- Avoids git index.lock conflicts

## Your Workflow

1. Create worktree using `sl new` at P:/worktrees/<name>/
2. List worktrees using `sl worktree list`
3. Commit changes using `git commit` (sl has separate index)
4. Push using `sl push` (lock-free, no daemon needed)

## Validation Rules

### Prohibited Actions
- Using `git` for worktree operations (use `sl` instead)
- Writing scratchpad files to P:/__csf root
- Creating worktrees outside P:/worktrees/

## Implementation

```python
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, 'P:/__csf/src')

# Import handler
from src.modules.scratchpad.commands import ScratchpadCommandHandler

handler = ScratchpadCommandHandler()
```

## Commands

### create <name>

```python
result = handler.handle_create(name)
# Returns: {"success": bool, "message": str, "path": Path}
```

Creates a new worktree at `P:/worktrees/<name>/` using `sl new`.

### list

```python
result = handler.handle_list()
# Returns: {"success": bool, "worktrees": [...]}
```

Lists all scratchpad worktrees using `sl worktree list`.

### commit <branch> <message>

```python
result = handler.handle_commit(branch, cwd, message)
# Returns: {"success": bool, "message": str}
```

Commits changes using `git commit`. sl has separate index and doesn't see git-tracked files.

### push <branch>

```python
result = handler.handle_push(branch)
# Returns: {"success": bool, "message": str}
```

Pushes directly using `sl push`. No daemon needed - sl is lock-free.

## Why sl (Sapling)?

Git's `index.lock` mechanism causes conflicts when multiple terminals access the same repo. sl (Sapling SCM) was designed for monorepo-scale parallel operations and uses a different locking mechanism that doesn't conflict.

**Benefits:**
- No push serialization needed
- No daemon process to manage
- Direct push works from multiple terminals

## Correct Import Paths

```
✓ from src.modules.scratchpad.commands import ScratchpadCommandHandler

✗ from features.modules.scratchpad.commands import ScratchpadCommandHandler  # WRONG
```

## Module Locations

- Handler: `src/modules/scratchpad/commands.py`
- Tests: `tests/modules/test_scratchpad.py`

## Aliases

- `/scratchpad` - Full command
- `/sp` - Short alias
