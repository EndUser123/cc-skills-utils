# cc-skills-utils

Utility skills for Claude Code — discovery, git operations, and general tooling.

## Skills (5)

| Skill | Purpose |
|-------|---------|
| discover | Codebase discovery before implementation |
| gitingest | Prepare repo for NotebookLM ingestion |
| gitready | Universal package creator and portfolio polisher |
| main | Skill health monitoring and management |
| s | Quick shortcut skill |

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
