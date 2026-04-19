# CHS Configuration

## Config File

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

## Workspace Aliases

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
