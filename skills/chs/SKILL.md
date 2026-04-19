---
name: chs
description: Dedicated chat history search with summarization, workspace aliases, tool filtering, context preview, session stats, and branch filtering
category: chat-history
triggers:
  - /chs
aliases:
  - /chs
  - /chat-history
  - /history-search

suggest:
  - /search
  - /all
  - /cks

do_not:
  - duplicate /search functionality - use this for chat-specific workflows
  - load full conversations into context unnecessarily
  - skip the two-stage search architecture
  - probe CLI help for export when the export mapping is already documented
---

# Chat History Search (/chs)

## Purpose

Dedicated search for Claude Code chat history with advanced features: summarization modes, workspace aliases, tool filtering, context preview, session statistics, and branch filtering.

**Why /chs instead of /search?**
- `/search` = Unified search across all sources (chat + knowledge + code + docs)
- `/chs` = Chat-specific workflows with dedicated features for conversation analysis

## Project Context

### Technical Architecture
- **Primary CLI**: `P:/packages/search-research/skills/chs/scripts/chs_cli.py`
- **CHS Backend**: Reuses existing CHS infrastructure from `/search`
- **Two-Stage Search**: Lightweight index → Deep content scan (on-demand)
- **Storage**: SQLite metrics database at `P:/packages/search-research/data/chs_metrics.db`
- **FTS5 bootstrap**: `python -m core.chs.scripts.reindex_from_jsonl --db-path "P:/__csf/data/chat_history.db" --history-path "~/.claude/history.jsonl"`
- **Bootstrap rule**: If `chat_history.db` exists but schema/FTS tables are missing, reindex from `history.jsonl` before trusting search results

### Consolidation History
- Previously part of `/search` (consolidated old `/chs`, `/recent`, `/search-more`)
- Now re-extracted as dedicated chat history skill with advanced features
- `/search` handles unified queries; `/chs` handles chat-specific workflows

## Your Workflow

1. **Parse query** - Extract filters (workspace, tool, branch, date, mode)
2. **Stage 1 search** - Lightweight index-only search (firstPrompt, summary fields)
3. **Check results** - If insufficient, trigger Stage 2
4. **Stage 2 search** - Deep JSONL content scan (only when needed)
5. **Apply filters** - Tool, branch, workspace, date filters
6. **Generate output** - Summary, context preview, or full details
7. **Optional summarization** - Apply selected summarization mode

## Quick Start: Searching Previous Sessions

When you have a session_id from handoff context or need to find content from a previous conversation:

### With session_id (from handoff)

```bash
# View the session with surrounding context
/chs show {session_id} --context 20

# Search within a specific session for unique phrases
/chs "CRITICAL: You MUST call Skill" --session {session_id}

# Use two-stage search for deep exploration
/chs "Option A Option B Option C" --session {session_id} --stage auto
```

### Without session_id (search across all sessions)

```bash
# Search for unique phrases from the conversation
/chs "unique phrase from discussion"

# Filter by workspace or time
/chs "authentication" --workspace tiny-vacation --since "7 days ago"

# Use context preview to see surrounding messages
/chs show {found_session_id} --context 10
```

### Why /chs instead of generic search tools

| Feature | /chs | Generic (grep/Read) |
|---------|-----|---------------------|
| **Speed** | ~10ms index, ~500ms deep | Full file scan every time |
| **Context** | Session-aware, filters | Raw content only |
| **Precision** | Two-stage search | Manual pattern refinement |
| **Output** | Structured with context | Raw grep results |

### Search Tips from Failure Analysis

**DO:**
- Use unique phrases from the conversation ("CRITICAL: You MUST call Skill")
- Combine multiple unique terms for better matching
- Search the handoff session file first
- Use `--context` flag to see surrounding messages

**DON'T:**
- Use generic terms ("Option A") that match unrelated content
- Search current session when handoff points to previous session
- Use grep/python when /chs exists and has the session
- Load full conversations unnecessarily (use two-stage search)

## Seven Key Features

### 1. Summarization Modes

Transform raw chat history into structured documentation.

| Mode | Description | Use Case |
|------|-------------|----------|
| `documentation` | Full technical doc: problem, changes, patterns, lessons | Deep dive into complex sessions |
| `short-memory` | MEMORY.md-ready bullets (500-2000 chars) | Quick knowledge capture |
| `changelog` | Added/Changed/Fixed/Removed with file paths | Track what changed over time |
| `debug-postmortem` | Symptoms, investigation, dead ends, root cause, fix | Learn from debugging sessions |
| `onboarding` | "How this works" for new devs | Team knowledge transfer |

```bash
/chs "authentication" --mode documentation
/chs "session-abc123" --mode short-memory
/chs "migration" --mode changelog
/chs "error handling" --mode debug-postmortem
/chs "project-architecture" --mode onboarding
```

### 2. Two-Stage Search Architecture

**Stage 1 (Fast):** FTS5 / index-only search
- Searches: `firstPrompt`, `summary`, `terminalId`, `branch`, `timestamp`
- Speed: ~10ms
- Use for: Initial exploration, finding relevant sessions
- If the SQLite schema is missing or stale, bootstrap via `reindex_from_jsonl.py` before relying on Stage 1

**Stage 2 (Deep):** Full JSONL content scan
- Searches: All message content, tool results, thinking blocks
- Speed: ~500ms (depends on corpus size)
- Use for: When Stage 1 finds nothing or needs more detail

```bash
/chs "authentication" --stage 1  # Fast index search
/chs "authentication" --stage 2  # Deep content scan
/chs "authentication" --stage auto  # Auto-select (default)
```

**Key principle:** Never load full conversations into context unnecessarily.

### 3. Workspace Aliases

Group related workspaces for unified search.

```bash
# Define aliases in config file
# ~/.claude/chs_config.json
{
  "workspace_aliases": {
    "frontend": ["tiny-vacation", "vacation-api", "vacation-ui"],
    "backend": ["api-gateway", "auth-service", "user-service"],
    "ml": ["ml-pipeline", "model-training", "inference"]
  }
}

# Search across aliased workspaces
/chs "deployment" --workspace-alias frontend
/chs "auth" --workspace-alias backend
```

### 4. Tool-Based Filtering

Find conversations by tool usage.

```bash
# Find all Edit tool usage on a file
/chs --tool Edit --file "config/api.php"

# Find Task tool usage in last 7 days
/chs --tool Task --since "7 days ago"

# Find Bash tool usage with keyword
/chs "npm" --tool Bash --limit 50
```

Supported tools: Edit, Write, Bash, Read, Grep, Glob, Task, Agent, LSP, etc.

### 5. Context Window Preview

Show surrounding messages for context without loading full conversation.

```bash
/chs show <session-id> --context 10  # Show 10 messages before/after
/chs show <session-id> --context 5 --center  # Center on match
```

**Output format:**
```
=== Session: abc123 ===
[5 messages before match]
...
[MATCH] User: "how does authentication work?"
[1 message after match]
...
Use --depth full to see complete conversation.
```

### 6. Session Statistics Dashboard

Metrics and insights about chat history.

```bash
/chs stats
/chs stats --workspace tiny-vacation
/chs stats --since "30 days ago"
```

**Statistics include:**
- Total sessions per workspace
- Average session length (messages, duration)
- Most-used tools (by count)
- Terminal ID ↔ session mapping
- Branch distribution
- Time-based patterns (hourly, daily activity)

### 7. Session Chain Export

When the user asks for `export`, interpret it as a full session-chain export, not a search-result export.

**Exact CLI mapping:**

```bash
python P:/packages/search-research/skills/chs/scripts/chs_cli.py --export --session-id <session-id> --output <path>
```

**Behavior:**
- `--export` writes the full linked session chain to a markdown file
- `--session-id` is optional; if omitted, the current session is used
- `--output` is optional; if omitted, the CLI writes to `~/.claude/exports/chain_<timestamp>.md`
- `--exclude-thinking` removes thinking blocks from the export
- `--include-tool-results` keeps raw tool results in the export

**Examples:**

```bash
# Export the current session chain
python P:/packages/search-research/skills/chs/scripts/chs_cli.py --export

# Export a specific session chain
python P:/packages/search-research/skills/chs/scripts/chs_cli.py --export --session-id abc123

# Export to a specific file
python P:/packages/search-research/skills/chs/scripts/chs_cli.py --export --session-id abc123 --output P:/tmp/chs-export.md
```

### 8. Branch-Based Filtering

Search conversations by git branch.

```bash
/chs "deploy" --branch "main"
/chs "feature" --branch "feature/story-6.5"
/chs "bugfix" --branch "fix/auth-error"
```

**Use case:** "What did we discuss on the feature/story-6.5 branch?"

## Command Reference

### Basic Search

```bash
/chs "query"                          # Basic search
/chs "authentication" --limit 20      # Limit results
/chs "migration" --since "7 days ago" # Date filter
/chs "migration" --until "2025-01-01" # Until date
/chs "error" --exact                  # Exact match
```

### Filter Options

```bash
# Workspace filters
/chs "deploy" --workspace tiny-vacation
/chs "api" --workspace-alias frontend

# Tool filters
/chs --tool Edit --file "*.py"
/chs --tool Bash --since "today"

# Branch filters
/chs "feature" --branch "main"
/chs "bugfix" --branch "fix/*"

# Content filters
/chs --exclude-thinking               # Exclude thinking blocks
/chs --include-tool-results           # Include tool execution results
```

### Output Options

```bash
# Detail levels
/chs "query" --depth summary          # Lightweight index only
/chs "query" --depth full             # Complete content
/chs "query" --depth auto             # Auto-detect (default)

# Context preview
/chs show <session-id> --context 10

# Summarization modes
/chs "query" --mode documentation
/chs "query" --mode short-memory
/chs "query" --mode changelog
/chs "query" --mode debug-postmortem
/chs "query" --mode onboarding

# Output formats
/chs "query" --format json            # Machine-readable
/chs "query" --format markdown        # Formatted markdown
```

### Session Management

```bash
# Show specific session
/chs show <session-id>
/chs show <session-id> --max-messages 100
/chs show <session-id> --json          # JSON output

# List recent sessions
/chs list --limit 20
/chs list --workspace tiny-vacation
/chs list --since "yesterday"

# Statistics
/chs stats
/chs stats --workspace tiny-vacation
```

### Advanced Options

```bash
# Search stages
/chs "query" --stage 1                # Index-only (fast)
/chs "query" --stage 2                # Deep scan
/chs "query" --stage auto             # Auto-select

# Rebuild index
/chs --reindex                        # Rebuild search index

# Query export
/chs "query" --output results.json    # Save to file
/chs "query" --clipboard              # Copy to clipboard

# Session chain export
/chs export                           # Export full session chain
/chs export --session-id abc123       # Export specific session chain
/chs export --output P:/tmp/out.md    # Write export to a specific file
```

## Configuration

Create `~/.claude/chs_config.json`:

```json
{
  "workspace_aliases": {
    "frontend": ["tiny-vacation", "vacation-api"],
    "backend": ["api-gateway", "auth-service"]
  },
  "defaults": {
    "limit": 20,
    "depth": "summary",
    "stage": "auto"
  },
  "paths": {
    "metrics_db": "P:/packages/search-research/data/chs_metrics.db"
  }
}
```

## Integration with /search

```bash
# /search for unified search across all sources
/search "authentication"

# /chs for chat-specific workflows with advanced features
/chs "authentication" --mode documentation --context 10
```

**When to use which:**
- Use `/search` for: General queries, multi-source research, quick lookups
- Use `/chs` for: Chat-specific analysis, summarization, filtering, statistics

## Examples

### Find and summarize debugging session
```bash
/chs "CSRF error" --mode debug-postmortem
```

### Track changes over time
```bash
/chs "authentication" --mode changelog --since "30 days ago"
```

### Find all Edit usage on a file
```bash
/chs --tool Edit --file "config/api.php" --since "7 days ago"
```

### Search across related workspaces
```bash
/chs "deployment" --workspace-alias frontend
```

### Generate onboarding docs
```bash
/chs "project architecture" --mode onboarding --output docs/onboarding.md
```

### View context around match
```bash
/chs show abc123 --context 10
```

### Session statistics
```bash
/chs stats --workspace tiny-vacation --since "30 days ago"
```

## Implementation Notes

- **Reuses existing CHS backend** from `/search` for consistency
- **Metrics database** tracks usage patterns and sync status
- **Two-stage architecture** ensures fast initial results
- **Summarization modes** use LLM templates for structured output
- **Workspace aliases** defined in config file for flexibility
- **Tool filtering** parses JSONL content for tool usage patterns
- **Branch detection** extracts from session metadata
