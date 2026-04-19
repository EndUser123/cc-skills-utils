---
name: restore
description: Restore CKS checkpoint after compaction
version: 1.0.0
status: stable
category: recovery
triggers:
  - /restore
aliases:
  - /restore

suggest:
  - /checkpoint
  - /checkpoint-restore
  - /chs
---

# Restore CKS Checkpoint

Restore task context from CKS hyper-graph database after compaction events.

## Purpose

Restore task context from CKS hyper-graph database after compaction events, enabling session continuity.

## Project Context

### Constitution/Constraints
- On-demand restoration only (no automatic tracking)
- CKS-based persistence
- Session continuity support

### Technical Context
- CKS database: `P:/.cks/storage/cks.db`
- Entity type: SessionCheckpoint
- Displays: task name, progress percentage, blockers, modified files, next steps

### Architecture Alignment
- Integrates with `/checkpoint` for checkpoint management
- Works alongside `/checkpoint-restore` for full workflow
- Suggests `/chs` for chat history search

## Your Workflow

1. **Query CKS**: Retrieve latest SessionCheckpoint
2. **Display Context**: Show task name, progress, blockers, files, next steps
3. **Restore**: Present context to user for session continuation

### Execution
Uses CKSHyperGraphClient to query hyper-graph for SessionCheckpoint entities.

## Validation Rules

### Prohibited Actions
- Do NOT create checkpoints without user action
- Do NOT claim checkpoint exists without database query
- Do NOT modify checkpoint data without explicit user request

## What This Does

When you run `/restore`, it will:
1. Query CKS for the latest SessionCheckpoint
2. Display task context including:
   - Task name
   - Progress percentage
   - Current blockers (if any)
   - Recently modified files
   - Next steps

## Usage

Run this command after a compaction event to restore your task context:

```bash
/restore
```

## Execution

```bash
python -c "
import sys
sys.path.insert(0, 'P:/__csf/src')
from src.cks.integration.adapters.project_context.cks_client import CKSHyperGraphClient

cks = CKSHyperGraphClient('P:/.cks/storage/cks.db')
checkpoints = cks.hyper_graph_query(entity_type='SessionCheckpoint', limit=1)

if not checkpoints:
    print('No checkpoints found in CKS database.')
else:
    cp = checkpoints[0]
    attrs = cp.get('attributes', {})
    print(f'## Restored CKS Checkpoint')
    print(f'**Checkpoint ID**: {cp.get(\"entity_id\", \"unknown\")}')
    print(f'**Task**: {attrs.get(\"task\", \"unknown\")}')
    print(f'**Progress**: {attrs.get(\"progress_pct\", 0)}%')
    # ... additional output
"
```
