---
name: health
description: Unified System Health, Observability, and Maintenance
version: 1.0.0
status: stable
category: governance
triggers:
  - /health
  - /obs
  - /hook-obs
  - /hooks-edit
  - /context-status
  - /cks-usage
  - /cleanup
  - /recover
  - /optimize-claude-md

suggest:
  - /explore
  - /git

hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "python \"$CLAUDE_PROJECT_DIR/.claude/skills/health/hooks/PreToolUse_main_gate.py\""
          timeout: 10
---

# /health - System Health & Observability

Unified command for system health checks, hook observability, and workspace maintenance.

## ⚡ EXECUTION DIRECTIVE

**When /health is invoked (with no args or --health), IMMEDIATELY execute:**

```bash
python P:\\\\\\packages/.claude-marketplace/plugins/cc-skills-utils/skills/health/scripts/main_health.py
```

## Subcommands & Modes

| Command | Purpose | Implementation |
|---------|---------|----------------|
| `/health` | Full system health check | `system_health.py` |
| `/health obs` | Hook observability & traces | `hook_audit_dashboard.py` |
| `/health edit` | Temporary hook suspension | Sets `CONSTITUTIONAL_HOOKS_BYPASS=1` |
| `/health context`| Context & token usage stats | PowerShell log parser |
| `/health cks` | CKS usage & stats | `cks_usage_enforcer.py` |
| `/health cleanup`| Workspace violation cleanup | `cleanup_violations.py` |
| `/health recover`| System recovery & restoration | `recovery_engine.py` |
| `/health optimize`| CLAUDE.md optimization | `optimize_claude_md.py` |

---

## 1. System Health (`/health`)

Checks core infrastructure, high-impact systems, and feature integrations.

**Flags:**
- `--quick`: Fast check (skips slow checks)
- `--all`: Run all checks
- `--activity`: Last hour activity
- `--llm`: Provider health
- `--quota`: API quota status

---

## 2. Hook Observability (`/health obs`)

View hook performance, traces, and blocking events.
Alias: `/hook-obs`, `/obs`.

**Reports:**
- `stats`: Event mix & top hooks
- `health`: Hook health summary
- `blocks`: Blocking event analysis
- `reasoning`: Reasoning profile signals

---

## 3. Hook Editing (`/health edit`)

Temporarily suspends constitutional hooks for editing.
Alias: `/hooks-edit`.

**Usage:**
- `/health edit`: Enable bypass
- `/health edit --off`: Disable bypass

---

## 4. Context & Tokens (`/health context`)

Display token usage and compaction timing patterns.
Alias: `/context-status`.

---

## 5. Maintenance & Recovery

| Mode | Usage |
|------|-------|
| **Cleanup** | `/health cleanup` — Removes directory structure violations |
| **Recover** | `/health recover` — System restoration after failures |
| **Optimize** | `/health optimize` — Optimizes CLAUDE.md for token efficiency |

---

## Validation Rules

- **Evidence-First**: Always query the actual database or logs.
- **Fail Fast**: Report failures immediately.
- **Bypass Safety**: Never leave `/health edit` active after use.
