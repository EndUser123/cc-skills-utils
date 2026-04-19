---
name: gitbatch
version: 0.6.0
status: "stable"
description: "Execute batch skill application across P:/packages using subagents with result envelopes. Agents save files directly, pass filenames back — reducing orchestrator token costs."
category: orchestration
triggers:
  - /gitbatch
suggest:
  - /p
  - /verify
  - /critique
execution_hint: "Agent tool: Spawn gitbatch-worker agents to run skills in parallel, collect result envelopes"
enforcement: advisory
---

# /gitbatch — Batch Skill Execution (Agent-Based)

## Purpose

Execute skills across multiple packages using **subagents with result envelopes**. Agents save results to files and pass filenames back to the orchestrator, avoiding full content streaming through the orchestrator context.

## Usage

```bash
# Execute /p on all packages (agent-based with result envelopes)
/gitbatch /p
/gitbatch /p P:/packages/debugRCA           # Target specific package
/gitbatch /p debugRCA handover              # Target by package name

# Dry-run (show execution plan without running)
/gitbatch --dry-run /p

# Force legacy mode (Skill() calls instead of agents)
/gitbatch --legacy /p
```

**What happens:** Orchestrator spawns agents that invoke skills, save results to evidence files, and return result envelopes. Only the small envelope (not full skill output) flows back through orchestrator.

## Key Difference from v0.5

| Aspect | v0.5 (Legacy) | v0.6 (Agent-Based) |
|--------|---------------|---------------------|
| Execution | Orchestrator executes `Skill()` calls | Subagents invoke skills, save files |
| Token flow | Full skill output streams through orchestrator | Only result envelope (JSON) through orchestrator |
| Result storage | Evidence files | Evidence files (same) |
| Scalability | Limited by orchestrator context | Scales with subagent count |

## Arguments

| Position | Description | Default |
|----------|-------------|---------|
| `$1` | Skill name (e.g., `/p`, `/verify`) | `/gitready --check-only` |
| `$2..$N` | Target packages or folders | All packages |

**Flexible Detection:**
- Arguments starting with `/` → skill name
- Arguments with `P:/`, `~/`, `C:/`, or containing `/` → folder path
- Plain words matching package names → package

## Flags

| Flag | Description |
|------|-------------|
| `--execute` | Agent-based execution with result envelopes (default) |
| `--dry-run` | Preview execution plan without running |
| `--legacy` | Use old `Skill()` call flow (orchestrator executes) |
| `--halt-on-failure` | Stop batch on first failure (default: continue) |
| `--parallel` | Execute agents in parallel (future) |
| `--evidence-dir` | Create evidence directory for result persistence |
| `--help` | Show usage |

## Execution Flow (Agent-Based)

### Step 1: Parse Arguments

Same as v0.5 — flexible detection parses arguments.

### Step 2: Expand Targets

Same as v0.5 — resolve package names to paths.

### Step 3: Spawn Subagents with Result Envelopes

**Dry-run mode:** Shows execution plan without running.

**Agent-based execution (default):** For each package, spawn a subagent that invokes the skill, saves results to an evidence file, and returns a result envelope (small JSON) instead of full output. See [Result Envelope Schema](references/subagent-result-envelope.md) for the full schema and implementation details.

### Step 4: Collect Envelopes and Generate Summary

Orchestrator:
1. Receives result envelopes from all subagents (not full skill output)
2. Reads evidence files to generate skill-adaptive summary
3. Reports batch summary

**Token savings:** Instead of full skill output (~500-2000 tokens per package), orchestrator receives only the envelope (~100 tokens).

## Result Envelope Pattern

See [references/subagent-result-envelope.md](references/subagent-result-envelope.md) for schema, implementation, and token savings comparison.

## Evidence Contract

See [references/evidence-contract.md](references/evidence-contract.md) for file format, naming, and skill-specific evidence fields.

## Summary Templates

See [references/summary-templates.md](references/summary-templates.md) for skill-adaptive report formats (`/p`, `/gitready`, `/critique`, generic).

## Legacy Mode (`--legacy`)

Use `--legacy` to revert to v0.5 flow where the orchestrator executes `Skill()` calls directly and receives full output.

## Package Discovery

Packages are discovered dynamically from `P:/packages/`. When no explicit targets are given, the script enumerates all subdirectories and excludes:

- `__pycache__/` — Python cache artifacts
- `.archive/` — Archived/stale packages
- `arch/` — Infrastructure package
- `gitbatch/` — The orchestrating skill itself

All remaining directories containing a `SKILL.md` or `skills/` subdirectory are considered valid package targets. New packages added to `P:/packages/` are automatically included on the next run.

## Design

- **Agent-based execution**: Orchestrator spawns subagents that invoke skills and save results to files
- **Result envelopes**: Subagents return small JSON envelopes instead of streaming full output
- **Legacy mode**: `--legacy` flag reverts to v0.5 `Skill()` call flow for backwards compatibility
- **Evidence-dir for persistence**: Use `--evidence-dir` to write per-package JSON results for compaction immunity
- **Idempotent**: Safe to re-run
- **Multi-terminal safe**: Sequential agent execution prevents race conditions
- **Token efficient**: ~90% reduction in orchestrator token costs via result envelopes
