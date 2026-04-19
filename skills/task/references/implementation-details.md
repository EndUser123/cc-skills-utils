# Implementation Details

## How This Skill Works

When you invoke `/task <command>`, the following occurs:
1. **Skill tool loads this SKILL.md** - The markdown documentation IS the handler
2. **Claude parses your sub-command** - Extracts the operation (list/add/done/start/search/clean/help)
3. **Claude executes the appropriate tool** - Calls TaskList/TaskCreate/TaskUpdate directly
4. **Results are formatted and returned** - You see the output

**There is no separate Python handler file** - This SKILL.md document IS the implementation. When invoked, Claude reads this file and follows the workflow described below.

## Sub-Command Workflows

### List Tasks (Enhanced with Terminal Filtering and Search)

```
1. User: /task list [--status=pending] [--all] [--no-suggest]
2. Claude: Reads this SKILL.md, identifies "list" command
3. Claude: Gets current terminal_id from discovery file or task file name
4. Claude: Calls TaskList() tool
5. Claude: Filters tasks by terminal_id unless --all flag specified
6. Claude: Filters by status if --status specified
7. Claude: Runs search for terminal context (unless --no-suggest specified)
8. Claude: Searches CHS for unresolved items in this terminal
9. Claude: Formats output with tasks + suggestions + unresolved items
```

### Terminal Filtering (Default Behavior)

- By default, `/task list` shows only tasks for current terminal
- Extract terminal_id from task metadata (e.g., `[terminal:env_102392]`)
- Get current terminal_id from task file name: `env_{uuid}_tasks.json`
- Display only matching tasks
- Use `--all` flag to show all terminals

### Daemon Status Check

**IMPORTANT:** Check daemon status via pipe enumeration - avoids `GetConsoleWindow()` window flash:
```python
# GOOD: Enumerate pipes directly (no window flash, no discovery file dependency)
import glob
pipes = glob.glob(r'\\.\pipe\csf_semantic*')
daemon_running = len(pipes) > 0

# BAD: Import terminal_detection (causes window flash on Windows)
from hooks.terminal_detection import detect_terminal_id  # Calls GetConsoleWindow()

# ALSO WORKS: Read discovery file (if it exists)
cat P:/__csf/data/semantic_daemon_discovery.json
```

### Add Task

```
1. User: /task add "Fix authentication bug"
2. Claude: Reads this SKILL.md, identifies "add" command
3. Claude: Validates subject is not empty
4. Claude: Calls TaskCreate(subject="Fix authentication bug", status="pending")
5. Claude: Returns confirmation with task ID
```

### Mark Task Complete

```
1. User: /task done 123
2. Claude: Reads this SKILL.md, identifies "done" command
3. Claude: Calls TaskUpdate(taskId="123", status="completed")
4. Claude: Returns confirmation
```

## Tool Reference

```python
# List tasks
tasks = TaskList()
for task in tasks:
    print(f"#{task['id']} [{task['status']}] {task['subject']}")

# Create task
TaskCreate(
    subject="Fix bug",
    description="Details...",
    status="pending"
)

# Update task
TaskUpdate(
    taskId="123",
    status="completed"
)
```

## Integration Points

- **PostToolUse_task_tracker.py**: Persists task changes to file system
- **TaskList tool**: Returns all tasks across all terminals
- **Session management**: Tasks survive compaction and restore
- **Unified search integration**: Uses /search skill to suggest contextually relevant tasks
