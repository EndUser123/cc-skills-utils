# cc-skills-utils

Utility skills for Claude Code — git operations, system health, plugin management, and workspace management.

## Skills (6)

| Skill | Purpose | Home |
|-------|---------|------|
| /git | Unified Fleet & Git Management (Sync, Batch, Safety) | `git/` |
| /health | Unified System Health, Observability, and Ops | `health/` |
| /usm | Universal Skill and Plugin Manager | `usm/` |
| /init | Initialize CLAUDE.md at module/feature root | `init/` |
| /plugin-installer | Plugin audit, validate, install, sync, add, remove, refresh, bump, status | `plugin-installer/` |
| /bifrost | Bifrost governance model query with provider taxonomy and cost filtering | `bifrost/` |

## Artifacts Convention

All runtime artifacts write to:

```
.claude/.artifacts/{terminal_id}/{skill_name}/
```

Skills MUST NOT write state to their own directory or to the package root.

## Installation

Skills surfaced via junctions in `P:\\\\\\.claude/skills/`.
