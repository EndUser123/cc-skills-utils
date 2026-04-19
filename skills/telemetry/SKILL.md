---
name: telemetry
description: Records system events, execution outcomes, and constitutional violations to a persistent database
version: "1.0.0"
status: stable
category: utility
triggers:
  - /telemetry
aliases:
  - /telemetry

suggest:
  - /health-monitor
  - /debug
  - /nse
---

# Telemetry Service

Records system events, execution outcomes, and constitutional violations to a persistent database.

## Purpose

Record system events, execution outcomes, and constitutional violations to persistent database.

## Project Context

### Constitution/Constraints
- On-demand telemetry only (no continuous monitoring)
- Solo dev authority: no multi-user telemetry needed
- Data safety: local storage only

### Technical Context
- Spec at P:/__csf/src/features/commands/co/telemetry_spec.py
- Documentation at ./telemetry_inst.md
- Persistent SQLite database for event storage

### Architecture Alignment
- Part of CSF NIP telemetry system
- Integrates with health-monitor
- Works with debug skill for analysis

## Your Workflow

When invoked:
1. Identify event type (system, execution, violation, performance)
2. Record event with timestamp and metadata
3. Store to persistent database
4. Return confirmation

## Validation Rules

- On-demand only, no background collection
- Local storage only
- Minimal overhead for recording

---

## Integration

- Spec: P:/__csf/src/features/commands/co/telemetry_spec.py
- Docs: ./telemetry_inst.md
