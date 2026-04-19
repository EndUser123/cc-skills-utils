---
name: session
description: Manage logical work sessions across terminals and compaction
version: "1.0.0"
status: stable
category: task
triggers:
  - /session
aliases:
  - /session

# /session - Session Management CLI

**Purpose:** Manage logical work sessions across terminals and compaction.

## Commands

### `/session`
List all sessions with activity info.

### `/session <name>`
Create new session and switch to it.

### `/session rename <new-name>`
Rename current session.

### `/session switch <session-id>`
Switch to different session.

### `/session claim <task-id>`
Claim a task for current session (moves from its current session).

### `/session info`
Show current session details.

## Session Architecture

**Session ID** = Logical work unit (persists across terminals and /clear)
- Used as primary grouping key for tasks
- Shared across multiple terminals
- Survives context compaction

**Terminal ID** = Physical instance (for collision safety only)
- Prevents concurrent edit conflicts
- Used for re-entrancy guards

## Implementation

Uses `SessionManager` class from `.claude/hooks/__lib/session_manager.py`.

**State location:** `.claude/state/session_manager/`
**Current session:** `.claude/hooks/current_session.json`

## Examples

```bash
# Create new session for feature work
/session feature-auth

# Switch back to previous session
/session switch default_1769727000

# Rename current session
/session rename auth-refactor

# Claim orphaned task
/session claim 123
```

## Multi-Terminal Usage

Multiple terminals can work on same session:
- Terminal A: `/session api-work`
- Terminal B: `/session switch api-work_123456`

Both terminals see same tasks and state.

## Environment Variables

- `SESSION_STATE_DIR`: Override state directory location
