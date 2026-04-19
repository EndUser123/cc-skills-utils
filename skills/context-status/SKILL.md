---
name: context_status
description: Context usage statistics via compaction timing analysis
version: "1.0.0"
status: "stable"
category: utilities
triggers:
  - /context-status
aliases:
  - /context-status
suggest:
  - /llm-health
  - /llm-performance
  - /quota
---

# Context Status

Display context usage statistics by analyzing compaction timing patterns.

## Purpose

Display context usage statistics by analyzing Claude Code's compaction timing patterns, providing insight into token consumption and context management.

## Project Context

### Constitution/Constraints
- **Evidence-First** - Show actual statistics from logs
- **Investigation Before Claims** - Analyze real data, not estimates

### Technical Context
- Analyzes Claude Code context compaction logs
- Uses PowerShell for log parsing and timing analysis
- Tracks token usage, compaction frequency, context size trends

### Architecture Alignment
- Works with `/llm-health`, `/llm-performance`, `/quota`
- Supports context optimization decisions

## Your Workflow

1. Access Claude Code session logs
2. Parse compaction events and timestamps
3. Calculate statistics:
   - Total context tokens used
   - Compaction frequency
   - Average context size
   - Token usage trends
4. If `--detailed`: show breakdown by category
5. Display formatted results

## Validation Rules

### Prohibited Actions

- Do NOT estimate usage without reading actual logs
- Do NOT fabricate statistics
- Do NOT assume log location without verification

## Usage

```bash
/context-status [--detailed]
```

## Options

| Option | Description |
|--------|-------------|
| `--detailed` | Show detailed breakdown by category |

## Examples

### Basic status
```bash
/context-status
```

### Detailed breakdown
```bash
/context-status --detailed
```

## Output

Shows statistics about:
- Total context tokens used
- Compaction frequency
- Average context size
- Token usage trends

## Implementation

Uses PowerShell to analyze Claude Code's context compaction logs and timing data.
