# Agent Tool Usage Best Practices

This document contains detailed guidance on using the Agent/Task tool correctly when spawning subagents from skills.

## CRITICAL: subagent_type vs model Parameter

When using the `Task` tool to spawn subagents from skills, understand the difference:

**❌ WRONG:**
```markdown
Launch subagents (haiku model):
```
This gets misinterpreted as `subagent_type="haiku"` → **ERROR** (haiku is not an agent type)

**✅ CORRECT:**
```markdown
Launch subagents with model="haiku":
```
This correctly passes `model: "haiku"` → Works as expected

## Parameter Reference

| Parameter | Purpose | Valid Values | Required |
|-----------|---------|--------------|----------|
| `subagent_type` | Specifies which specialized agent to use | `general-purpose`, `Explore`, `Plan`, `feature-dev:code-architect`, etc. | **Yes** |
| `model` | Override the default model for this subagent | `sonnet`, `opus`, `haiku` | No (defaults to inherited) |
| `prompt` | What the subagent should do | Free text instructions | **Yes** |
| `description` | Short summary for task tracking | 3-5 word summary | **Yes** |

## When to Specify model Parameter

Only specify `model` when you need:
- **Speed optimization**: Use `model="haiku"` for simple tasks (bash commands, file checks, basic reporting)
- **Quality override**: Use `model="opus"` for complex reasoning when default would be sonnet
- **Cost optimization**: Use `model="haiku"` for high-volume, low-complexity operations

## Example from /p skill (detection phase)

```markdown
Launch 2 parallel Task subagents with model="haiku":

Subagent 1 — Test Detection:
Run these commands and report all output:
  pytest --collect-only -q 2>&1 | head -5
  python -c "import subprocess; ..."

Subagent 2 — File & Marker Detection:
Run these commands and report all output:
  ls README.md LICENSE 2>&1
  ls .github/workflows/*.yml 2>&1
```

This correctly uses `model="haiku"` for fast, simple command execution.

## Common Mistakes

1. **Using model name as subagent_type**: `subagent_type: "haiku"` → ERROR
2. **Omitting required parameters**: Missing `description` → Silent no-op
3. **Confusing model selection with agent type**: Model is about capability/cost, agent type is about specialization

## Task Tool All Parameters

The Task tool requires these parameters:

- **subagent_type** (required): Which specialized agent to use
- **prompt** (required): What the agent should do
- **description** (required): Short summary for task tracking

Optional parameters:
- **model**: Override default model (sonnet/opus/haiku)
- **name**: Custom name for the agent (for team coordination)
- **team_name**: Spawn agent into specific team
- **mode**: Permission mode (acceptEdits, bypassPermissions, etc.)

## Subagent Type Quick Reference

Common subagent types:
- `general-purpose`: General tasks, research, multi-step work
- `Explore`: Fast codebase exploration and pattern discovery
- `Plan`: Implementation planning and design
- `feature-dev:code-architect`: Feature architecture design
- `feature-dev:code-explorer`: Deep codebase feature analysis
- `tdd-test-writer`: Write failing tests for TDD
- `tdd-implementer`: Implement minimal code to pass tests
- `tdd-refactorer`: Refactor code after tests pass

See agent definitions in system-reminder for complete list.

## Best Practices

1. **Always provide all 3 required parameters**: subagent_type, prompt, description
2. **Use model parameter thoughtfully**: Default is usually best, override only for specific optimization needs
3. **Choose specialized agents**: Use domain-specific agents (Explore, Plan) over general-purpose when appropriate
4. **Clear descriptions**: Make descriptions actionable and specific for task tracking
5. **Parallel execution**: Launch multiple agents in parallel for independent work
