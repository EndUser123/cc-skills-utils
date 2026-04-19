---
name: multi-instance-coherence
description: Ensures coherence across multiple AI instances and concurrent tasks.
version: 1.0.0
status: stable
category: quality
triggers:
  - 'multiple instances'
  - 'concurrent'
  - 'coherence'
  - 'parallel'
aliases:
  - '/multi-instance-coherence'

suggest:
  - /nse
  - /orchestrator
  - /workflow
---



## Purpose
Manage state consistency across 5+ concurrent Claude instances.

## Project Context

### Constitution/Constraints
- Fail fast: Report conflicts immediately, don't auto-merge
- Green state axiom: Assume clean state before current modifications

### Technical Context
- Git as primary truth source
- Sapling backups as secondary consistency check
- File timestamps as fallback indicator

### Architecture Alignment
- Integrates with /session-context for continuity
- Supports /nse for coordination recommendations

## Your Workflow

### Session Initialization
1. Verify state consistency (git status, sapling backups, running processes)
2. Validate previous assumptions still valid
3. Check operation log for recent executions
4. Detect uncommitted changes from parallel work

### Before File Modifications
1. Verify no other instance modifying same file
2. Check for uncommitted changes in directory
3. Confirm git status is clean or intentionally modified
4. Use atomic operations (commit immediately after changes)

### Conflict Resolution
1. Stop and report conflict explicitly
2. Never merge/rebase without user confirmation
3. Use explicit locking for long-running operations

## Validation Rules

### Prohibited Actions
- Do NOT auto-merge conflicts without user confirmation
- Do NOT proceed without checking for concurrent modifications
- Do NOT ignore uncommitted changes from other instances

## Session Initialization Protocol
At conversation start, verify:
1. State Consistency: Check git status, sapling backups, running processes
2. Context Validation: Are previous assumptions still valid?
3. Operation Log: What did other instances execute since last sync?
4. Conflict Detection: Are there uncommitted changes from parallel work?

## Multi-Instance Resolution Priority
1. Most recent committed state (git truth)
2. Explicit sapling backups (if git is inconsistent)
3. File timestamps (fallback indicator)
4. User clarification (if ambiguous)

## Concurrent Workflow Protection
When operating with 5+ concurrent Claude instances:

### Before Any File Modification
1. Verify no other instance is currently modifying same file
2. Check for uncommitted changes in the directory
3. Confirm git status is clean or intentionally modified
4. Use atomic operations (commit immediately after changes)

### Conflict Resolution
- If modifications conflict: Stop and report conflict explicitly
- Never merge/rebase without user confirmation
- Use explicit locking (comments in code) for long-running operations
- Report instance identifiers in logs for debugging