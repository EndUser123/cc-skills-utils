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
- Implementation at `P:/__csf/src/features/commands/observability.py`
- Multiple report types: health, blocks, latency, waterfall, regression

### Architecture Alignment
- Integrates with /health-monitor for system checks
- Supports /debug for troubleshooting

## Your Workflow

1. Parse report type from command flags
2. Execute appropriate query against events database
3. Format results for display (tables, histograms, waterfalls)
4. Return actionable insights from data

## Validation Rules

- MUST query actual database, don't simulate
- MUST report query failures immediately
- DO NOT return cached data without timestamp

## Usage

```bash
python P:/__csf/src/features/commands/observability.py [OPTIONS]
```

## Reports

| Report | Option | Description |
|--------|--------|-------------|
| Overview | (none) | Total events, traces, sessions, time range |
| Hook Health Matrix | `--health` | Success/block/error rates, P95 latency, trends |
| Block Analysis | `--blocks [hook]` | Root cause of blocks, trigger patterns |
| Latency Distribution | `--dist [hook]` | Visual histogram with percentiles |
| Trace Waterfall | `--waterfall <id>` | Nested execution flow visualization |
| Regression Detection | `--regression` | Performance degradation detection |
| Article Compliance Heatmap | `--heatmap` | Compliance rate by article with trends |
| Session Failure Analysis | `--failures` | Failed sessions with reasons |
| Hook Performance | `-p, --performance` | P50/P95/P99 latencies |
| Slow Hooks | `--slow MS` | Hooks slower than MS milliseconds |
| Recent Traces | `-t, --traces` | Recent traces list |
| Trace Detail | `-t <trace_id>` | Detailed trace waterfall |
| Compliance Stats | `-c, --compliance` | Block statistics by hook |

## Examples

```bash
/hook-obs                                    # Overview
/hook-obs --health                           # Hook health matrix
/hook-obs --blocks                           # Block analysis for all hooks
/hook-obs --blocks truth_validator            # Block analysis for specific hook
/hook-obs --dist                             # Latency distribution
/hook-obs --dist pre_tool_use                # Latency for specific hook
/hook-obs --waterfall 1a2b3c4d               # Trace waterfall
/hook-obs --regression                       # Regression detection
/hook-obs --heatmap                          # Article compliance heatmap
/hook-obs --failures                         # Session failures
/hook-obs -p --sort p95                      # Hook performance sorted by P95
/hook-obs --slow 200                         # Slow hooks over 200ms

# Note: /obs is a backward-compatible alias
```

## Quick Reference

| Question | Use |
|----------|-----|
| Which hooks are unhealthy? | `/hook-obs --health` |
| Why is this hook blocking? | `/hook-obs --blocks <hook>` |
| Is latency consistent? | `/hook-obs --dist <hook>` |
| What's the execution flow? | `/hook-obs -t <trace_id>` |
| Did performance degrade? | `/hook-obs --regression` |
| Which articles are problematic? | `/hook-obs --heatmap` |
| Which sessions failed? | `/hook-obs --failures` |
| Which hooks are slowest? | `/hook-obs -p --sort p95` |
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
