# cc-skills-utils

Utility skills for Claude Code — git operations, system health, plugin management, and workspace management.

## Skills (5)

| Skill | Purpose | Home |
|-------|---------|------|
| /git | Unified Fleet & Git Management (Sync, Batch, Safety) | `git/` |
| /main | Real-time infrastructure health probe (alias: /health) | `main/` |
| /init | Initialize CLAUDE.md at module/feature root | `init/` |
| /plugin-installer | Plugin audit, validate, install, sync, add, remove, refresh, bump, status | `plugin-installer/` |
| /bifrost | RETIRED — Bifrost not in use; skill pending removal (see Tier 2 of bifrost excision) | `bifrost/` |

## Artifacts Convention

All runtime artifacts write to:

```
.claude/.artifacts/{terminal_id}/{skill_name}/
```

Skills MUST NOT write state to their own directory or to the package root.

## Installation

Plugins live directly in `P:/packages/.claude-marketplace/plugins/<name>/`.
