# Claude Code Tasks Integration Reference

## When to Use Claude Code Tasks

- **Multi-session collaboration**: Set `CLAUDE_CODE_TASK_LIST_ID=project-name` to share tasks across terminals
- **Auto-sync**: Tasks appear in all sessions immediately when created/updated
- **Built-in tools**: `TaskCreate`, `TaskGet`, `TaskUpdate`, `TaskList`

## Task Discovery Instructions

When working on tasks and you discover new issues:

```
"Create a task for: [issue description]"
```

Include:
- **subject**: Actionable title (e.g., "Fix SQL injection in transcription_worker.py:216")
- **description**: Technical details (file:line, error type, context)
- **activeForm**: What to show while working (e.g., "Fixing SQL injection...")

**Example:**
```
User: "I found a bug in the code"
Claude: Creating task with:
  subject: "Fix SQL injection in transcription_worker.py"
  description: "Line 216 uses string concatenation for LIMIT clause. Use parameterized query."
  activeForm: "Fixing SQL injection vulnerability"
```

## Cycle Detection Instructions

When completing the last primary task:

1. Check if all primary (non-review) tasks are completed
2. If yes, create review phase tasks:

```
"All primary tasks complete. Creating review phase tasks:
- 'Review implementation against requirements'
- 'Verify tests pass'
- 'Check code quality and security'"
```

**Example workflow:**
```
[Worker completes last primary task]
-> TaskUpdate(task_id, status="completed")
-> Check: Are all primary tasks completed?
-> Yes: Create "Review Phase" task
-> Other terminals see the review task, can claim it
```

## Using Claude Code Tasks with /team

```python
# Use Claude Code Tasks
TaskCreate(
    subject="Fix bug in auth module",
    description="File: src/auth.py:45 - Null pointer when token expires",
    activeForm="Fixing auth token expiration bug"
)

# For cycle detection
tasks = TaskList()
primary_done = all(t.get("status") == "completed" for t in tasks if not is_review(t))
if primary_done:
    TaskCreate(
        subject="Review Phase",
        description="All primary work complete. Review implementation.",
        addBlockedBy=[completed_task_ids]
    )
```

## Environment Setup

For multi-terminal coordination:
```bash
# Terminal 1
export CLAUDE_CODE_TASK_LIST_ID=yt-fts
claude

# Terminal 2 (same task list)
export CLAUDE_CODE_TASK_LIST_ID=yt-fts
claude
```

Both terminals see the same tasks in real-time.

## Race Condition Handling

Multiple sessions may try to claim the same task. Check `assignee` after update to verify:

```python
# Try to claim
original = show(task_id)
if not original.get('assignee'):
    update(task_id, status="in_progress", assignee=SESSION_ID)
    updated = show(task_id)

    # Verify we actually claimed it
    if updated.get('assignee') != SESSION_ID:
        print("Task was claimed by another session")
        # Find next available task
```

If claiming fails, find the next available task.

## Examples

### Worker claiming a task
```
User: /team

Claude: Claimed: Implement feature X (P1)
Task claimed. Starting work on: Implement feature X
```

### Reviewer picking up work
```
User: /team --review

Claude: Found 1 task awaiting review:
Reviewing implementation...
[Review passes]
Approved. Marking for closing.
```

### Completing work for review
```
User: /team --complete T-123

Claude: Marked T-123 for review. Awaiting reviewer approval.
```
