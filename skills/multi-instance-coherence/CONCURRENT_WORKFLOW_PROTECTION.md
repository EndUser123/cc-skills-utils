Concurrent Workflow Protection

## Before Any File Modification (5+ Instances)

1. Verify no other instance is currently modifying same file
2. Check for uncommitted changes in the directory
3. Confirm git status is clean or intentionally modified
4. Use atomic operations (commit immediately after changes)

## Conflict Resolution

- If modifications conflict: Stop and report conflict explicitly
- Never merge/rebase without user confirmation
- Use explicit locking (comments in code) for long-running operations
- Report instance identifiers in logs for debugging