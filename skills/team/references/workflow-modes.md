# Workflow Modes Reference

## Session Identification

First, identify the current session uniquely:

```python
from pathlib import Path
import sys
sys.path.insert(0, str(Path("P:/__csf/.staging")))

# Generate session ID from worktree path
SESSION_ID = Path.cwd().name  # e.g., "w1t1", "w2t3"
```

## Worker Mode (Claim Tasks)

**Usage:** `/team` or `/team --work`

1. **List available tasks:**
   ```python
   tasks = list_issues(status="open")
   ```

2. **Filter for available work:**
   - No blockers (`blocked_by` is empty)
   - Not already assigned (assignee is empty)
   - Priority order: P0 -> P1 -> P2 -> P3 -> P4

   ```python
   available = [t for t in tasks if not t.get('assignee') and not t.get('blocked_by')]
   ```

3. **Claim the highest priority available task:**
   ```python
   task = available[0]
   update(task['id'], status="in_progress", assignee=SESSION_ID)
   ```

4. **Report task details:**
   ```python
   task = show(task['id'])
   print(f"Task: {task['title']}")
   print(f"Priority: P{task.get('priority', 3)}")
   ```

## Batch Mode (Work Through Multiple Tasks)

**Formal Usage:** `/team --filter <pattern> --use <skill> [--all]`

**Natural Language Examples:**
- "do the yt-fts refactoring tasks. use /refactor to perform the work"
- "work on all test tasks. use /tdd"
- "handle the database issues with /fix"

Process multiple matching tasks sequentially until done:

```python
import re
pattern = re.compile("yt-fts", re.IGNORECASE)

tasks = list_issues(status="open")
matching = [t for t in tasks if pattern.search(t.get('title', ''))]

for task in matching:
    # Claim task
    update(task['id'], status="in_progress", assignee=SESSION_ID)

    # Work on task (invoke skill here)
    # ...

    # Mark for review
    update(task['id'], labels=["workflow:review"])
```

**Example:**
```
User: /team --filter "yt-fts" --use /refactor --all

Claude: Found 3 yt-fts tasks:

Working through tasks sequentially...

[1/3] Running /refactor...
[1/3] Marking for review...
[1/3] Complete.

[2/3] Running /refactor...
[2/3] Marking for review...
[2/3] Complete.

[3/3] Running /refactor...
[3/3] Marking for review...
[3/3] Complete.

All yt-fts tasks complete. 3 tasks processed.
```

## Review Mode (Review Completed Work)

**Usage:** `/team --review`

```python
# Find tasks awaiting review
tasks = list_issues()
review_tasks = [t for t in tasks if "workflow:review" in t.get('labels', [])]

if review_tasks:
    task = review_tasks[0]
    update(task['id'], assignee=SESSION_ID)

    # Review the work
    # - Check implementation against requirements
    # - Verify tests pass
    # - Check code quality

    # Approved: mark for closing
    update(task['id'], labels=["workflow:approved"])

    # OR rejected: send back to work
    update(task['id'], status="in_progress", labels=[])
```

## Complete Work

**Usage:** `/team --complete <task-id>`

```python
# Mark for review
update(task_id, labels=["workflow:review"])

# After approval, close the task
close(task_id)
```

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

## Task Discovery

When finding bugs/issues during work:

```
"Create task: [issue description]"
```

Always include:
- **file:line** - Exact location
- **error type** - What's wrong (SQL injection, race condition, etc.)
- **reproduction steps** - How to trigger (if applicable)

**Example:**
```
TaskCreate(
    subject="Fix SQL injection in transcription_worker.py:216",
    description="Line 216 uses string concatenation for LIMIT clause with "
                "user input. Attack can inject arbitrary SQL. "
                "Fix: Use parameterized query with ? placeholder.",
    activeForm="Fixing SQL injection vulnerability"
)
```

## Complex Task Decomposition

When a task has 3+ distinct pieces:

```
"Break this into subtasks"
```

- Create separate TaskCreate for each subtask
- Set dependencies with `addBlockedBy` if order matters
- Each subtask should be independently verifiable

**Example:**
```
Original: "Implement caching layer"

Decomposed:
  - Task: "Add cache key generation" (no dependencies)
  - Task: "Implement cache get/set" (no dependencies)
  - Task: "Add cache invalidation" (blocked by: get/set)
  - Task: "Update callers to use cache" (blocked by: all above)
```
