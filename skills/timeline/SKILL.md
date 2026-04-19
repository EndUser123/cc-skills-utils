---
name: timeline
description: View timeline of tool usage with session summaries
version: "1.0.0"
status: stable
category: strategy
triggers:
  - /timeline
aliases:
  - /timeline

suggest:
  - /checkpoint
  - /health-monitor
  - /nse
---

# Timeline


## Purpose

View timeline of tool usage with session summaries and activity tracking.

## Project Context

### Constitution / Constraints

- **Evidence-first**: Timeline provides actual execution history, not speculation
- **Solo-dev constraint**: Lightweight tracking, no continuous monitoring
- **Data safety**: Timeline data stored locally in SQLite

### Technical Context

- CheckpointTimeline with SQLite at: `~/.claude/timeline.db`
- Events captured by PostToolUse_checkpoint_timeline.py hook
- Supports session grouping, filtering, and search

### Architecture Alignment

- **Observability pattern**: Passive data collection for retrospective analysis
- **Hook integration**: Works with PostToolUse hooks for event capture

## Your Workflow

1. **Parse command arguments** - Extract limit, type, search, session options
2. **Query timeline database** - Retrieve events from SQLite
3. **Group into sessions** (if --sessions flag) - Aggregate related activity
4. **Format output** - Show files worked on, activity breakdown, errors
5. **Display summary** - Present actionable timeline view

## Validation Rules

### Prohibited Actions

- **Do not speculate** - Use actual timeline data only
- **Do not create continuous monitoring** - This is passive collection only

### Data Privacy

- Timeline data is local to user's machine
- No external transmission of activity data


View your tool usage timeline grouped into sessions. Shows what files you worked on and what you accomplished.

## Usage

```
/timeline [--sessions] [--limit N] [--type TYPE] [--search QUERY]
```

## Options

| Option | Description |
|--------|-------------|
| `--sessions`, `-s` | Group events into sessions (recommended) |
| `--limit N` | Limit to N results (default: 20) |
| `--type TYPE` | Filter by event type (e.g., tool_Edit, tool_Bash) |
| `--search QUERY` | Search for events containing query |
| `--around TIMESTAMP` | Show events around a checkpoint |

## Examples

```bash
/timeline --sessions
/timeline --limit 50
/timeline --type tool_Edit
/timeline --search main.py
```

## Session View Output

Shows:
- Files worked on
- Activity breakdown (edits/commands/reads)
- Test results
- Errors

## Implementation

Uses CheckpointTimeline with SQLite at: `~/.claude/timeline.db`

Events captured by PostToolUse_checkpoint_timeline.py hook.
