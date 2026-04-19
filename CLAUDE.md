# cc-skills-utils

Utility skills for Claude Code — discovery, git operations, hooks, session management, and general tooling.

## Skills (26)

| Skill | Purpose |
|-------|---------|
| ask | Universal CLI router |
| cleanup | Cleanup workflow |
| clear_restore | Clear restore state |
| discover | Codebase discovery before implementation |
| git | Multi-repo sync and worktree management |
| gitbatch | Batch git operations |
| git-conventional-commits | Conventional commit enforcement |
| gitingest | Prepare repo for NotebookLM ingestion |
| github-ready | GitHub publication preparation |
| gitready | Universal package creator and portfolio polisher |
| handoff | Session handoff |
| hook-audit | Hook auditing |
| hook-inventory | Hook inventory scanning |
| hook-obs | Hook observability |
| hooks-edit | Hook editing |
| init | Project initialization |
| main | Skill health monitoring and management |
| main-hooks | Core hook management |
| push | Git push wrapper |
| restore | Session restore |
| s | Quick shortcut skill |
| skill-ship-workspace | Skill distribution workspace |
| task | Task management |
| task-unresolved | Unresolved task checking |
| track | Item tracking |

## Artifacts Convention

All runtime artifacts write to:

```
P:/.claude/.artifacts/{terminal_id}/<skill-name>/
```

`terminal_id` from `CLAUDE_TERMINAL_ID` env var (falls back to `"default"`).

Skills MUST NOT write state to their own directory or to the package root. The `.gitignore` covers `.evidence/`, `.state/`, `.benchmarks/`, `__pycache__/`.

## Installation

Skills surfaced via junctions in `.claude/skills/`:

```powershell
New-Item -ItemType Junction -Path "P:/.claude/skills/<name>" -Target "P:/packages/cc-skills-utils/skills/<name>"
```

Command frontends live in `.claude/commands/<name>.md`.
