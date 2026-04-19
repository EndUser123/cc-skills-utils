# Consolidated Search Features

Includes functionality from `search-more`, `progressive-search`, `chs`, and `recent`.

## Source Control (`--source`)

| Value | Description | Equivalent To |
|-------|-------------|----------------|
| `local` | Local sources: CKS, CHS, CDS, Code, DOCS, SKILLS | Default `/search` behavior |
| `chat` | Chat history only | `/chs`, `/recent` |
| `all` | Search all local sources | Combines local + chat |

```bash
# Search chat history with FAISS
/search "authentication" --source chat --chat-method vector

# Search only local sources
/search "database" --source local

# Search all local
/search "async patterns" --source all
```

**Note:** For web search, use `/research` instead.

## Chat Search Method (`--chat-method`)

When `--source chat` is specified, choose the search algorithm:

| Value | Description | Performance | When To Use |
|-------|-------------|-------------|-------------|
| `vector` | FAISS semantic search | <1s (indexed), 87s (first) | Deep history, semantic meaning |
| `grep` | Reverse grep scan | Instant | Recent messages (minutes/hours) |
| `auto` | Auto-detect best method | Varies | Let system decide |

```bash
# Deep semantic search
/search "we discussed authentication" --source chat --chat-method vector

# Fast recent message search
/search "what happened 5 min ago" --source chat --chat-method grep

# Auto-detect (system chooses based on query)
/search "git commit message" --source chat --chat-method auto
```

**Auto-detection logic:**
- Time-based queries ("5 minutes ago", "recent", "today") -> `grep`
- Semantic queries ("we discussed", "meaning of", "concept") -> `vector`
- Default -> `vector`

## Detail Level (`--depth`)

| Value | Description | Token Cost | When To Use |
|-------|-------------|------------|-------------|
| `summary` | Lightweight index with IDs | ~10x savings | Initial exploration, finding relevant results |
| `full` | Complete content for all results | High | Final research, need all details |
| `auto` | Auto-detect based on query | Varies | Let system decide |

```bash
# Get lightweight index (token-efficient)
/search "authentication" --depth summary

# Get full details immediately
/search "authentication" --depth full

# Auto-detect based on result count
/search "authentication" --depth auto
```

**Auto-detection logic:**
- Query contains "ID", "specific", "details" -> `full`
- Query returns <10 results -> `summary`
- Default -> `summary`

## Progressive Disclosure Workflow

For token-efficient research:

1. **Start with summary:**
   ```bash
   /search "authentication" --depth summary
   # Returns: [1] CHS: User auth flow (ID: chs_abc123)
   #          [2] CKS: Auth module (ID: cks_def456)
   ```

2. **Review interesting results:**
   ```bash
   /search "authentication" --source local --depth summary
   # Identify which IDs are relevant
   ```

3. **Drill down to specific IDs:**
   ```bash
   /search "chs_abc123,cks_def456" --source local --depth full
   # Fetches full content only for specified IDs
   ```

**Token savings:** ~90% for typical workflows

## Recent Message Search (Fast Reverse Grep)

For very recent messages (minutes/hours old), the system automatically uses reverse grep instead of FAISS:

```bash
# Messages newer than FAISS index
/search "litellm error" --source chat --chat-method grep

# Time-windowed recent search
/search "faiss" --source chat --chat-method grep --minutes 60
```

This bypasses the 11-minute FAISS rebuild and provides instant results for recent conversations.

## Combined Examples

```bash
# Deep chat history search (weeks/months)
/search "database design" --source chat --chat-method vector --depth summary

# Recent messages only (today)
/search "faiss" --source chat --chat-method grep

# Local sources with summary
/search "async patterns" --source local --depth summary

# Everything with full details
/search "architecture" --source all --depth full

# Auto-detect everything
/search "git hooks" --depth auto --chat-method auto
```

---

## Migration Reference

| Old Command | New Behavior | Notes |
|-------------|--------------|-------|
| `/chs "query"` | `/search "query"` | Auto-detects chat intent |
| `/recent "query"` | `/search "query"` | Auto-detects recent + grep |
| `/search-more "id"` | `/search "id" --depth full` | Drill-down by ID |
| `/progressive-search` | `/search "query"` | Auto depth selection |

**Auto-detection means you rarely need flags.** Just search naturally:

```bash
# These all work - no flags needed
/search "what did we discuss about authentication"  # -> chat search
/research "how does FAISS work"                    # -> web search
/search "authentication [recent]"              # -> recent chat
```

**The /chs skill directory has been deleted.** All functionality is now in /search with smarter defaults.
