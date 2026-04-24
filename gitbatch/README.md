# gitbatch — Batch Package Polish

Preview and document batch skill application across packages in `P:/packages`.

**Current Status**: Preview/documentation tool. Actual batch execution requires
manual skill invocation (slash commands cannot be chained from bash scripts).

## Quick Start

```bash
# Preview what /gitready would do on all packages
/gitbatch --dry-run /gitready

# Preview on specific packages
/gitbatch --dry-run /gitready debugRCA/ handover/

# Preview /verify on all packages
/gitbatch --dry-run /verify
```

## How It Works

1. **Preview**: `/gitbatch --dry-run` shows what WOULD be executed
2. **Execute**: You manually run each skill command shown

```
/gitbatch --dry-run /gitready
=== Shows ===
Would execute: Skill(skill="/gitready", args="--target P:/packages/claude-history"))

Then you run:
Skill(skill="gitready", args="--target P:/packages/claude-history")
```

## Skill Setup (Windows Junction)

After creating the package, link it into your skills directory:

```powershell
New-Item -ItemType Junction -Path "P:\.claude\skills\gitbatch" -Target "P:\packages\gitbatch\skills\gitbatch"
```

## Architecture

```
gitbatch/
├── skills/
│   └── gitbatch/
│       └── SKILL.md          # Skill definition + /gitbatch slash command
├── scripts/
│   ├── batch_polish.sh      # Bash preview script (sequential, idempotent)
│   └── batch_polish.py      # Python reference (not used directly)
└── README.md
```

## Design Principles

| Principle | Implementation |
|-----------|----------------|
| Sequential | No parallelism — avoids terminal contention |
| Idempotent | Safe to re-run; partial runs leave packages valid |
| Multi-terminal safe | Each package is isolated; no shared state |
| Exclusions | `__pycache__/`, `.archive/`, `arch/` excluded |

## Why Preview-Only?

Slash command skills (like `/gitready`) can only be invoked through Claude Code's
Skill() tool. Bash scripts cannot invoke slash commands directly.

Workaround: Preview what would run, then execute Skill() calls manually or via
Claude Code's inline execution.

## Packages Covered

`claude-history`, `debugRCA`, `gitready`, `handoff`, `loop-core`, `minimax-mcp`, `prompting-toolkit`, `reasoning`, `refactor`, `reflect-system`, `search-research`, `skill-guard`

## Excluded

- `arch/` — Infrastructure, not a package
- `__pycache__/` — Python bytecode cache
- `.archive/` — Archived packages
