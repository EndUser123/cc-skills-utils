# Output Format Reference

## Enhanced Task List Format

**Enhanced task list format with terminal filtering and search integration:**
```
Terminal: {path} (terminal_id: {id})

Pending Tasks ({count}):
  #{id} [{status}] {subject} [blockedBy=<ids>]
    {description}

Suggested for this terminal ({count}):
  [CKS 0.85] Pattern: "Always test hooks before deployment"
  [CHS 0.72] Session: "User discussed semantic daemon IPC optimization"

Unresolved from Chat History ({count}):
  [CHS 2026-01-15] "Daemon crashes when concurrent requests exceed 4"
    -> /task add "Fix daemon crash on concurrent requests"
  [CHS 2026-01-14] "Hook timeout not configurable, stuck at 5s"
    -> /task add "Make hook timeout configurable"
```

## Task Format

```
#<id> [<status>] <subject> [owner=<owner>] [blockedBy=<ids>]
```

## Status Indicators

- `[pending]` - Task not started
- `[in_progress]` - Task actively being worked on
- `[completed]` - Task finished

## Search Suggestion Format

- `[CKS 0.XX] Pattern: "..."` - Knowledge pattern from CKS
- `[CHS 0.XX] Session: "..."` - Chat history snippet
- `[Code 0.XX] File: "...:line"` - Code reference
- `[Doc 0.XX] Title: "..."` - Documentation reference

## Unresolved CHS Items Format

- `[CHS date] "Content snippet"` -> Quick-add prompt with suggested task title
