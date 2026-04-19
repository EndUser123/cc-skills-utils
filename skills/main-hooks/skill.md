---
name: main-hooks
description: Main Cognitive Steering Framework with enforcement - system health checks and workspace validation
version: 1.0.0
status: stable
category: governance
triggers:
  - /main-hooks
aliases:
  - /main-hooks

suggest:
  - /nse
  - /search
  - /standards

hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "python \"$CLAUDE_PROJECT_DIR/.claude/skills/main-hooks/hooks/PreToolUse_main_gate.py\""
          timeout: 10
---

# Main Cognitive Steering Framework (Hooks Mode)

## ⚡ EXECUTION DIRECTIVE

**When /main-hooks is invoked, IMMEDIATELY execute:**

```bash
cd P:/__csf && python src/modules/observability/system_health.py
```

Parse output, highlight warnings and critical issues, provide actionable next steps.

**Enforcement active:** PreToolUse gate validates that Bash commands call `system_health.py`.

**DO NOT:**
- Display this documentation without executing
- Suggest commands that don't call `system_health.py`
- Skip CLI execution for documentation display

---

## Purpose

System health checks and workspace validation for CSF NIP ecosystem.
With enforcement hooks to prevent incorrect CLI usage.

---

## Quick Start (Actual CLI Commands)

```bash
# Direct CLI execution (enforced - gate validates these)
cd P:/__csf && python src/modules/observability/system_health.py           # All checks
cd P:/__csf && python src/modules/observability/system_health.py --quick     # Fast check
cd P:/__csf && python src/modules/observability/system_health.py --all       # Explicit all
cd P:/__csf && python src/modules/observability/system_health.py --health --json  # JSON output
```

---

## Health Checks (13 total)

**Core Infrastructure:**
- Directory structure (.evidence, .claude/logs, .claude)
- Recent activity (last hour events)
- Error rate analysis
- Test infrastructure

**High-Impact Systems:**
- Git hooks (constitutional enforcement)
- API key configuration (LLM providers)

**Feature Integrations:**
- CHS RAG (chat history search)
- Archon integration (content retrieval)
- AI Distiller (code analysis)
- Semantic integration
- Semantic change detection

**External Systems:**
- Search backends (CHS, RLM, HNSW, code analysis, grep, LSP, skills, CDS, fuzzy, hybrid)
- Research providers (Tavily, Serper, WebReader)

---

## Available Commands

| Flag | Description |
|------|-------------|
| `--health` | System health status (default) |
| `--quick` | Quick health check (skips slow checks) |
| `--all` | Run all checks (explicit) |
| `--activity` | Last hour system activity |
| `--blocked` | Blocked actions and reasons |
| `--tests` | Test coverage statistics |
| `--evidence` | Evidence summary |
| `--packages` | Check for outdated packages |
| `--llm` | LLM provider health check |
| `--quota` | API quota status |
| `--hooks` | Hook smoke test |
| `--json` | Output in JSON format |
| `--root <path>` | Custom project root |

---

## Output Interpretation

**Overall Status:**
- `HEALTHY` (score ≥80%) — All systems operational
- `DEGRADED` (score 50-79%) — Some warnings, investigate
- `UNHEALTHY` (score <50%) — Critical issues require attention

**Common Actions:**
- Check system activity and hooks (if no activity in last hour)
- Investigate high error rate (if errors >30%)
- Set up test infrastructure (if no test files found)
- Verify quota configuration (if quota check fails)

---

## Workspace Structure

```
P:/
├── .claude/                    # Claude Code runtime
├── __csf/                      # CSF NIP system
│   └── src/modules/observability/system_health.py
└── projects/                   # Applications
```
