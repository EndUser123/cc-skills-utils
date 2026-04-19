---
name: hook-audit
version: "1.0.0"
status: "stable"
description: Hook behavioral compliance monitoring - tracks LLM compliance with hook injections, blocking rates, and escalation decisions.
category: observability
triggers:
  - /hook-audit
  - "hook compliance"
  - "hook health"
  - "behavioral audit"
aliases:
  - /hook-audit

suggest:
  - /analytics
  - /debug
---

# /hook-audit - Hook Behavioral Compliance Monitoring

## Purpose

Monitor and analyze LLM behavioral compliance with hook system interventions. Tracks whether injected instructions are followed, measures blocking effectiveness, and recommends Phase 1 → Phase 2 escalations.

## ⚡ EXECUTION DIRECTIVE

**When invoked, run the hook audit dashboard:**

```bash
# Default: Full dashboard
python P:/.claude/hooks/hook_audit_dashboard.py

# With subcommand
python P:/.claude/hooks/hook_audit_dashboard.py blocks
python P:/.claude/hooks/hook_audit_dashboard.py assumptions
python P:/.claude/hooks/hook_audit_dashboard.py attribution
python P:/.claude/hooks/hook_audit_dashboard.py health
python P:/.claude/hooks/hook_audit_dashboard.py escalation
python P:/.claude/hooks/hook_audit_dashboard.py replay
python P:/.claude/hooks/hook_audit_dashboard.py stats
python P:/.claude/hooks/hook_audit_dashboard.py reasoning

# Custom time period
python P:/.claude/hooks/hook_audit_dashboard.py --days 14
python P:/.claude/hooks/hook_audit_dashboard.py attribution --days 30
python P:/.claude/hooks/hook_audit_dashboard.py stats --turn <turn-id>

# Terminal filtering (v2.1)
python P:/.claude/hooks/hook_audit_dashboard.py --terminal        # Current terminal only
python P:/.claude/hooks/hook_audit_dashboard.py --all             # Per-terminal breakdown
python P:/.claude/hooks/hook_audit_dashboard.py assumptions --terminal --days 7
```

**DO NOT:**
- Summarize without running the dashboard
- Invent compliance rates
- Skip the actual analysis

## Domain Scope

This skill covers **LLM behavioral compliance**, NOT:
- System performance metrics → use `/analytics`
- Code quality analysis → use `/analyze`
- Application error logs → use `/analysis-logs`

## Subcommands

See `references/subcommand-details.md` for full output descriptions.

| Command | Summary |
|---------|---------|
| (default) | Decision pattern monitoring - type distribution, extraction rates |
| `blocks` | Hook blocking events - totals, reasons, Catch-22 detection |
| `assumptions` | Assumption audit compliance - tool use vs [UNVERIFIED] rates |
| `attribution` | Error attribution - source types, escalation recommendations |
| `speculation` | Speculation gate - violations, block events, pattern types |
| `friction` | Style friction - permission_seeking, too_terse, repeat_request |
| `reasoning` | THINK profile routing - auto vs explicit, distribution, cooldown |
| `health` | Hook system health - timeouts, failures, enforcement metrics |
| `escalation` | Phase 1 to Phase 2 escalation recommendations |
| `replay` | Enforcement replay quality - block rates, autofix, latency |
| `stats` | Diagnostics DB stats - turn-scoped hook invocation lookup |

## Log File Locations

| Log | Path |
|-----|------|
| Decision Patterns | `P:/.claude/state/logs/decision_patterns.jsonl` |
| Error Attribution | `P:/.claude/logs/error_attribution.jsonl` |
| Assumption Audit | `P:/.claude/hooks/logs/test_assumption_audit.jsonl` |
| Skill Enforcement | `P:/.claude/logs/skill_enforcement.jsonl` |
| Hook Blocks | `P:/.claude/logs/hook_blocks.jsonl` |
| Hook Decisions | `P:/.claude/hooks/session_data/hook_decisions_YYYY-MM-DD.jsonl` |
| Enforcement State | `P:/.claude/hooks/session_data/enforcement_state.json` |
| Enforcement Events | `P:/.claude/hooks/session_data/enforcement_events.jsonl` |
| Reasoning Profiles | `P:/.claude/hooks/logs/reasoning_profiles.jsonl` |

## Escalation & Runtime

See `references/escalation-and-runtime.md` for:
- Phase 1/2 escalation framework and current phase status
- Runtime error metrics (HOOK_RUNTIME_ERROR, HOOK_NON_JSON_OUTPUT)
- Manual query examples
- Analysis script index

## Quick Reference

```bash
/hook-audit                  # Full dashboard
/hook-audit blocks           # Blocking events
/hook-audit escalation       # Escalation recommendations
/hook-audit replay           # Replay quality metrics
/hook-audit --days 30        # Last 30 days
/hook-audit --terminal       # Current terminal only (v2.1)
/hook-audit --all            # Per-terminal breakdown (v2.1)
/hook-audit stats --turn <turn-id>  # Turn-scoped diagnostics lookup
```

## Terminal Isolation (v2.1)

| Flag | Effect |
|------|--------|
| `--terminal` | Current terminal only |
| `--all` | Per-terminal breakdown |
| (none) | Aggregate all terminals |

See `P:/.claude/hooks/docs/TERMINAL_ISOLATION.md` for details.
