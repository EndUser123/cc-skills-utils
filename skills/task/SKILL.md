---
name: task
description: Task orchestration - manage Claude Code task list
version: "1.0.0"
status: stable
category: workflow
enforcement: advisory
triggers:
  - /task
aliases:
  - /task
  - /tasks
  - /todo

suggest:
  - /nse
  - /breakdown
  - /session

hooks:
  PostToolUse:
    - matcher: "TaskList"
      hooks:
        - type: prompt
          prompt: |
            Verify /task list workflow was executed completely.

            ENFORCEMENT LEVEL: advisory (warn, don't block)

            Required workflow steps:
            1. TaskList() was called (built-in tool)
            2. Results were filtered by terminal_id (unless --all flag)
            3. /search was called for terminal context (unless --no-suggest flag)
            4. CHS search for unresolved items (unless --no-suggest flag)
            5. Output includes "Suggested" or "Unresolved" sections (unless --no-suggest)

            This validation applies only to /task list flows.
            Do not enforce these requirements for TaskCreate/TaskUpdate/TaskGet operations.
            If this is not a list-style flow, return {"ok": true}.

            Check the user's message and tool usage.
            - If all steps complete: return {"ok": true}
            - If steps missing BUT enforcement is advisory: return {"ok": true, "warning": "ADVISORY: [which step missing] - use /task list for enhanced output"}
            - Do NOT return {"ok": false} - this skill is advisory enforcement
          model: haiku
          timeout: 30
user-invocable: true
---

# /task - Task Orchestration

## Purpose

Orchestrator for Claude Code task list operations. Routes sub-commands to built-in TaskCreate/TaskUpdate/TaskList/TaskGet tools.

## Context

- **Solo-dev**: Task management for individual workflow, not team coordination
- **Tool-first**: Wraps built-in tools, not a replacement system
- **Evidence-based**: Task status reflects actual work, not aspirations
- **Persistence**: `.claude/state/task_tracker/{terminal_id}_tasks.json` via PostToolUse_task_tracker hook
- **Multi-terminal safe**: Tasks persist across compaction and sessions
- **No Python handler**: This SKILL.md IS the implementation

## Workflow

1. **Parse sub-command** - Extract first argument as operation
2. **Route to handler** - Delegate to appropriate implementation
3. **Execute tool** - Call built-in tool (TaskCreate/TaskUpdate/etc)
4. **Return result** - Display formatted output

## Sub-Commands

| Command | Purpose | Tool |
|---------|---------|------|
| `list` | Show tasks (filtered by terminal) | TaskList |
| `add <subject>` | Create new task | TaskCreate |
| `done <id>` | Mark task complete | TaskUpdate |
| `start <id>` | Start working on task | TaskUpdate |
| `search <query>` | Find tasks by keyword | TaskList |
| `clean` | Remove completed tasks | TaskUpdate |
| `help` | Show usage | None |

## Validation Rules

- **Before routing**: Validate sub-command exists
- **Before task creation**: Check subject is not empty, no duplicates
- **Before task update**: Verify task ID exists
- **After operations**: Show confirmation with task details
- **Prohibited**: Marking non-existent tasks, bulk ops without confirmation, creating separate task system

## Usage

```bash
/task list                     # Tasks for current terminal (default)
/task list --all               # All terminals
/task list --status pending    # Filter by status
/task list --no-suggest        # Skip search suggestions

/task add "Fix auth bug"                  # Create task
/task add "Dark mode" --priority high     # With priority
/task start 123                           # Begin work
/task done 123                            # Complete
/task search "authentication"             # Search
/task clean                               # Remove completed
```

## Output Quick Reference

**Task format:** `#<id> [<status>] <subject> [owner=<owner>] [blockedBy=<ids>]`

**Status indicators:** `[pending]` / `[in_progress]` / `[completed]`

**List output includes:**
- Pending tasks for current terminal
- Suggested items (CKS/CHS search results) -- unless `--no-suggest`
- Unresolved chat history items with quick-add prompts -- unless `--no-suggest`

## References

| File | Contents |
|------|----------|
| [implementation-details.md](references/implementation-details.md) | Sub-command workflows, daemon status check, tool API reference |
| [output-format.md](references/output-format.md) | Full output templates, status indicators, suggestion formats |
| [search-integration.md](references/search-integration.md) | Terminal context building, CHS unresolved detection, search execution flow |

## Integration

- **PostToolUse_task_tracker.py**: Persists task changes to file system
- **Session management**: Tasks survive compaction and restore
- **Unified search**: Uses /search skill for contextual suggestions (see references/search-integration.md)

## Why This Matters

Prevents task list chaos:
- Tasks accumulate without cleanup -> `/task clean`
- Lost track of pending -> `/task list --status pending`
- No quick way to create -> `/task add "subject"`
