Conflict Resolution Rules

## Primary Rule

If modifications conflict: Stop and report conflict explicitly

## Forbidden

- Never merge/rebase without user confirmation
- Never auto-resolve conflicts
- Never assume one state is correct without asking

## Required

- Report conflict explicitly to user
- Wait for user direction on resolution
- Use explicit locking (comments in code) for long-running operations
- Report instance identifiers in logs for debugging