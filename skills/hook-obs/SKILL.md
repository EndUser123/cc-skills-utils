---
name: hook-obs
version: "1.0.0"
status: "stable"
description: Hook observability - performance, traces, health from events database
category: observability
triggers:
  - /hook-obs
aliases:
  - /obs
  - /hook-obs

suggest:
  - /health-monitor
  - /debug
  - /nse
---

# /hook-obs - Hook Observability

View hook performance, traces, and system health from SQLite events database.

## Purpose

Query hook performance, traces, and system health from SQLite events database.

## Project Context

### Constitution/Constraints
- Evidence-first: Report actual data, not assumptions
- Fail fast: Query failures surface immediately

### Technical Context
- SQLite events database as data source
- Implementation at `P:/.claude/hooks/hook_audit_dashboard.py`
- Multiple report types: stats, health, blocks, escalation, replay, and focused diagnostics

### Architecture Alignment
- Integrates with /health-monitor for system checks
- Supports /debug for troubleshooting

## Your Workflow

1. Parse report type from subcommand and optional filters
2. Execute appropriate query against events database
3. Format results for display (tables, histograms, waterfalls)
4. Return actionable insights from data

## Validation Rules

- MUST query actual database, don't simulate
- MUST report query failures immediately
- DO NOT return cached data without timestamp

## Usage

```bash
python P:/.claude/hooks/hook_audit_dashboard.py [subcommand] [--days N] [--terminal] [--all] [--turn TURN_ID]
```

## Reports

| Report | Command | Description |
|--------|---------|-------------|
| Overview | `/hook-obs` | Full dashboard across major diagnostics sections |
| Hook DB Stats | `/hook-obs stats` | Event mix, top hooks, recent events, turn lookup tip |
| Hook Health | `/hook-obs health` | Hook health summary + validator runtime error signals |
| Block Analysis | `/hook-obs blocks` | Blocking events and likely root causes |
| Assumption Audit | `/hook-obs assumptions` | Assumption-audit compliance telemetry |
| Error Attribution | `/hook-obs attribution` | Attribution compliance checks |
| Speculation Gate | `/hook-obs speculation` | Speculation gate metrics |
| Reasoning Profiles | `/hook-obs reasoning` | THINK auto-routing and reasoning profile signals |
| Principle Monitoring | `/hook-obs principles` | Principle events (context reuse, grounded changes, etc.) |
| FrameGuard | `/hook-obs frameguard` | Systemic frame compliance from evidence DB |
| Escalation Guidance | `/hook-obs escalation` | Phase escalation recommendations |
| Replay Metrics | `/hook-obs replay` | Enforcement replay quality |

## Examples

```bash
/hook-obs                                   # Full dashboard
/hook-obs stats                             # DB event summary
/hook-obs stats --turn <turn-id>            # Turn-scoped drill-down
/hook-obs health                            # Hook health + runtime validator errors
/hook-obs blocks                            # Blocking event analysis
/hook-obs assumptions                       # Assumption-audit compliance
/hook-obs attribution                       # Error attribution compliance
/hook-obs speculation                       # Speculation-gate telemetry
/hook-obs reasoning                         # Reasoning profile signals
/hook-obs principles                        # Principle-event overview
/hook-obs escalation                        # Escalation recommendations
/hook-obs replay                            # Replay quality metrics

# Note: /obs is a backward-compatible alias
```

## Quick Reference

| Question | Use |
|----------|-----|
| Which hooks are unhealthy? | `/hook-obs health` |
| What is the current hook event mix? | `/hook-obs stats` |
| Why is this turn blocked? | `/hook-obs stats --turn <turn-id>` |
| Why are hooks blocking overall? | `/hook-obs blocks` |
| Are principle violations increasing? | `/hook-obs principles` |
| Should any guardrails escalate? | `/hook-obs escalation` |
| Is replay quality degrading? | `/hook-obs replay` |
| How is competence trending? | `python P:/.claude/skills/_tools/competence_health_check.py` |

## Future Features

### Competence Trend Visualization

**Status**: Documented in `/main` health check, not yet integrated into `/hook-obs`

**Proposed Implementation**: Add `--competence` flag to show competence check trends over time

**Use Case**: Track competence layer health alongside hook performance metrics

**Integration Point**: Would query competence state from `P:/.claude/session_data/competence_state.json` and display trend similar to `--regression` report

**Example**:
```bash
/hook-obs --competence                   # Show competence check trend
```

**Related**: Competence tracking runs in `/main` health checks (see `competence_health_check.py`)
