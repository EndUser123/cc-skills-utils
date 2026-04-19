# Explore (`/explore`)

**True universal search across your local data AND the web.**

## What It Does

The `/explore` command searches **EVERYTHING** in one query:
- ✅ Your chat history (CHS)
- ✅ Your knowledge base (CKS)
- ✅ Your source code
- ✅ Your documentation
- ✅ Your skills
- ✅ The web (Tavily, Serper, Exa)

Results are **merged and ranked by relevance** so you get the best information from all sources.

## Why Use `/explore`?

### Problem: Two separate searches
```bash
/search "async patterns"      # Your local notes
/research "async patterns"    # Web tutorials
# Now you have to mentally combine them 😅
```

### Solution: One unified search
```bash
/explore "async patterns"
# → Shows your notes + web tutorials, ranked together
```

## Usage

### Basic (auto mode)
```bash
/explore "python async patterns"
# Fast local results first, web search if needed
```

### Comprehensive (unified mode)
```bash
/explore "authentication best practices" --mode unified
# Always searches both local AND web
```

### Local-only (fast, private)
```bash
/explore "what did we discuss" --mode local-only
# Same as /search, no web API calls
```

## Modes

| Mode | What It Does | Speed | Use Case |
|------|--------------|-------|----------|
| `auto` (default) | Local first, web if needed | 1-10s | Default choice |
| `unified` | Always search both | 5-11s | Maximum coverage |
| `local-only` | Local only | <1s | Fast, private |
| `web-fallback` | Local, web if quality low | 1-10s | Verify knowledge |

## Output Format

Results show **source indicators** so you know where each result came from:

```
[0.95] 📚 LOCAL: CKS Pattern: "Use async/await properly"
    From: Knowledge base

[0.92] 🌐 WEB: Real Python: "Async IO in Python"
    URL: https://realpython.com/async-io-python/

[0.88] 💬 LOCAL: CHS Discussion: "We chose asyncio"
    From: Chat session (2 days ago)
```

**Indicators:**
- 📚 LOCAL - Your docs, code, knowledge
- 💬 LOCAL - Your chat history
- 🌐 WEB - Web search results

## Implementation

**Status:** ✅ Complete

The `/explore` skill uses the `UnifiedAsyncRouter` implementation:
- **Core:** `P:/packages/search-research/core/unified_router.py`
- **Quality checks:** `P:/packages/search-research/core/quality_checker.py`
- **RRF fusion:** `P:/packages/search-research/core/hybrid_ensemble.py`

**Script:** `P:/packages/search-research/skills/explore/explore.py`

## Migration from `/search` + `/research`

| Old Way | New Way |
|---------|---------|
| `/search "X"` then `/research "X"` | `/explore "X"` |
| Mental merge required | Automatic merge |
| Two commands | One command |

**When to still use `/search` or `/research`:**
- `/search` - Only want local results (faster, private)
- `/research` - Only want web results (no local clutter)
- `/explore` - Want everything (recommended for most cases)

## Examples

```bash
# Find everything about async patterns
/explore "python async patterns"

# Comprehensive search with more results
/explore "authentication" --mode unified --limit 20

# Fast local-only search
/explore "what did we discuss about hooks" --mode local-only

# Verify your local knowledge is current
/explore "vector database best practices" --mode web-fallback
```

## Quick Start

1. **Basic universal search:**
   ```bash
   /explore "your query here"
   ```

2. **Force comprehensive search:**
   ```bash
   /explore "query" --mode unified
   ```

3. **Local-only (like /search):**
   ```bash
   /explore "query" --mode local-only
   ```

That's it! No need to run `/search` and `/research` separately anymore.
