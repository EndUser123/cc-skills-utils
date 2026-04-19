---
name: team
description: Multi-agent task coordination for parallel Claude Code sessions.
version: "1.0.0"
status: stable
category: orchestration
triggers:
  - "/team"
  - "pull a task"
  - "claim a task"
  - "team coordination"
aliases:
  - /team
---

# /team - Multi-Agent Task Coordination

## When to Use

- Running multiple Claude Code sessions in parallel
- Coordinating work across multiple agents/terminals
- Implementing reviewer workflow (worker -> review -> approve -> close)

## Instructions

**Just tell me what you want in plain English. I'll figure it out.**

Examples:
- "do the yt-fts refactoring tasks. use /refactor"
- "review all completed work"
- "claim the next available task"

---

## Quick Start

### Start Work on a Feature/Bug

1. "Analyze [scope] and create tasks" -> creates 3-8 tasks via TaskCreate
2. "Show me the task list" -> TaskList to verify
3. Work through tasks in order: read files, plan, code, commit

### Discover Issues During Work

"Create task: [issue description]" with:
- **file:line** - Exact location
- **error type** - What's wrong
- **reproduction steps** - How to trigger

### Decompose Complex Tasks

"Break this into subtasks" when a task has 3+ pieces. Set dependencies with `addBlockedBy`.

See `references/workflow-modes.md` for full code examples of all modes.

---

## Modes

### Worker Mode (default)

`/team` or `/team --work`

1. List open tasks -> filter unassigned, unblocked -> claim highest priority
2. Claim: `update(task_id, status="in_progress", assignee=SESSION_ID)`
3. Work the task, then mark for review: `update(task_id, labels=["workflow:review"])`

### Batch Mode

`/team --filter <pattern> --use <skill> [--all]`

Process all matching tasks sequentially, invoking the specified skill for each.

Natural language: "do the yt-fts refactoring tasks. use /refactor"

### Review Mode

`/team --review`

1. Find tasks with `workflow:review` label
2. Check implementation, verify tests, check code quality
3. Approve: `update(task_id, labels=["workflow:approved"])` or reject back to `in_progress`

### Complete Work

`/team --complete <task-id>` -> marks for review, closes after approval.

---

## Workflow State Machine

```
                    +---------+
                    |  open   |
                    +----+----+
                         | /team (worker)
                         v
                    +------------+
                    |in_progress |
                    |(assignee)  |
                    +----+-------+
                         | /team --complete
                         v
                    +------------+
                    | workflow:  |
                    |  review    |
                    +----+-------+
                         | /team --review
                         v
                    +------------+       +----------+
                    | workflow:  |<------| rejected |
                    |  approved  |       +----------+
                    +----+-------+
                         | close
                         v
                    +------------+
                    |  closed    |
                    +------------+
```

## Parameters

| Parameter | Description | Required |
|-----------|-------------|----------|
| `--work` | Worker mode: claim and work on tasks | No (default) |
| `--review` | Review mode: review completed tasks | No |
| `--complete <id>` | Complete current task and mark for review | No |
| `--filter <pattern>` | Filter tasks by title/description pattern | No |
| `--use <skill>` | Skill to invoke for each task | No |
| `--all` | Process all matching tasks until none remain | No |

## Race Condition Handling

Multiple sessions may claim the same task. After claiming, verify `assignee == SESSION_ID`. If mismatch, find next available task.

See `references/workflow-modes.md` for full race condition code.

---

## TDD Enforcement (MANDATORY for Code Changes)

All code modification tasks must follow TDD workflow (RED -> GREEN -> REGRESSION).

Auto-detect: refactor/bug_fix/feature/improvement types require TDD. Docs/config are exempt.

Flow: write failing test -> execute task -> tests pass -> run regression suite.

See `references/tdd-enforcement.md` for:
- `detect_task_type()` - task type detection logic
- `execute_task_with_tdd()` - full TDD workflow with phase verification
- `ensure_test_exists()`, `run_pytest()`, `run_regression_tests()` - helpers
- Enhanced batch mode with TDD enforcement

---

## Claude Code Tasks Integration

Set `CLAUDE_CODE_TASK_LIST_ID=project-name` to share tasks across terminals.

Built-in tools: `TaskCreate`, `TaskGet`, `TaskUpdate`, `TaskList`

See `references/claude-code-tasks.md` for:
- Task discovery and creation patterns
- Cycle detection (auto-create review phase when all primary tasks done)
- Environment setup for multi-terminal coordination
- Full usage examples

---

## Reference Files

| File | Contents |
|------|----------|
| `references/workflow-modes.md` | Worker, batch, review mode code + task discovery + decomposition |
| `references/tdd-enforcement.md` | TDD detection, workflow, helpers, enhanced batch mode |
| `references/claude-code-tasks.md` | Task tools, cycle detection, environment setup, examples |

## Solo Developer Constraints

- User-initiated batch processing only (explicit `--all` flag required)
- No continuous monitoring or background daemons
- Failed claims/tasks halt execution (requires manual intervention)
- Clear stopping condition (all matching tasks processed)

## Constitution Compliance

Extends:
- **PART T (Truthfulness)**: Report claim failures honestly
- **PART P (Evidence)**: Verify task state before claiming
- **Instance Isolation**: Session IDs prevent cross-contamination
