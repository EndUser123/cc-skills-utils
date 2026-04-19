---
name: task-unresolved
description: Detect unresolved items from chat history and propose task candidates, using the task unresolved detector and TaskList hook integration.
version: "1.0.0"
status: stable
category: workflow
triggers:
  - /task-unresolved
aliases:
  - /task-unresolved
suggest:
  - /task
  - /search
execution:
  directive: |
    Run a focused unresolved-task scan for the current terminal.
    Use TaskList to gather current/completed tasks, then invoke the unresolved detector.
    Return unresolved items with confidence and suggested `/task add "..."` actions.
  default_args: ""
  examples:
    - "/task-unresolved"
do_not:
  - block task updates
  - enforce /task list workflow gates
user-invocable: true
---

# /task-unresolved

## Purpose

Find unresolved issues from recent chat history and turn them into concrete task suggestions.

## Workflow

1. Call `TaskList` to get current task state.
2. Use `.claude/skills/task/unresolved_items_detector.py` for unresolved detection.
3. Cross-check with completed tasks and filter likely-resolved items.
4. Output actionable suggestions in this format:
   - `[CHS YYYY-MM-DD] "snippet"`
   - `-> /task add "Suggested task title"`

## Integration Points

- Hook integration: `P:\.claude\hooks\posttooluse\task_unresolved_suggester_hook.py`
- Detector engine: `P:\.claude\skills\task\unresolved_items_detector.py`
- Registry wiring: `P:\.claude\hooks\posttooluse\__init__.py`
