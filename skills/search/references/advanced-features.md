# Advanced Search Features

## Intelligent Defaults

Search features automatically enable based on context, query complexity, and result characteristics.

### Auto-Enable Triggers

| Feature | Auto-Enabled When | Disabled When |
|---------|------------------|---------------|
| **--explain** | Query >100 chars, contains OR, >2s execution, >2 backends, or 0 results | Simple fast queries |
| **--session** | Running in terminal (WT_SESSION detected) | Script/programmatic usage |
| **--cluster** | 10+ results from 2+ sources | Few results or single source |

### Feature Behaviors

**--explain (Auto)**
- Shows for complex/slow/failed queries
- Helps debug "why no results?" scenarios
- Silent for simple quick searches

**--session (Auto)**
- Enables in terminal mode automatically
- Maintains context for follow-up queries
- Disabled for scripts to avoid state bloat

**--cluster (Auto)**
- Groups results by topic when diverse
- Only triggers with sufficient data
- Avoids clustering small/homogeneous sets

### Override with Explicit Flags

```bash
# Force explain on simple query
/search "simple" --explain

# Disable session in terminal
/search "query" --no-session

# Force clustering on small results
/search "query" --cluster topic
```

### Configuration

Customize thresholds via `IntelligentDefaults` class:

```python
from knowledge.systems.chs.v2.intelligent_defaults import IntelligentDefaults

config = IntelligentDefaults(
    explain_threshold_ms=5000,    # Default: 2000
    explain_query_length=50,       # Default: 100
    cluster_min_results=20,        # Default: 10
    cluster_min_sources=3,         # Default: 2
)
```

---

## Execution Plan Explanation (--explain)

The `--explain` flag provides detailed insight into how the search system processes your query.

```bash
/search "python async patterns" --explain
```

Output:
```json
{
  "query": "python async patterns",
  "intent": "code-first",
  "intent_reasoning": "Contains code pattern: 'async'",
  "backends_selected": ["Code/Grep", "CKS", "CHS"],
  "backend_reasoning": "Code-first query prioritizes source code search",
  "hyde_generated": false,
  "hyde_phrases": [],
  "cache_hits": {"chs": 1, "cks": 0, "code": 0},
  "timings_ms": {"intent": 0.5, "backend_selection": 0.2, "hyde": 0, "cache_check": 0.1, "total": 0.8},
  "optimization_suggestion": "Use --hyde flag for improved semantic matching on complex queries"
}
```

### Explain Fields

| Field | Description |
|-------|-------------|
| `query` | Original search query |
| `intent` | Classified intent (code-first, knowledge-first, conversation-first, general, etc.) |
| `intent_reasoning` | Explanation of why the intent was classified |
| `backends_selected` | List of backends that will be queried |
| `backend_reasoning` | Explanation of backend selection logic |
| `hyde_generated` | Whether HyDE enhancement is active |
| `hyde_phrases` | Key phrases extracted via HyDE (if enabled) |
| `cache_hits` | Cache hit counts per backend |
| `timings_ms` | Timing breakdown per phase |
| `optimization_suggestion` | Suggested improvement for the query |

---

## Enhanced Search with HyDE

For better results on technical queries, use HyDE enhancement:

```bash
# Enhanced semantic search (recommended)
/hyde "python async patterns"

# Standard search with HyDE option
/search --hyde "query"
```

HyDE uses hypothetical document generation to improve semantic search relevance.

---

## Refinement Mode

Interactive refinement mode for narrowing search results:

```bash
# Start refinement mode
/search "python async" --refine

# Example session:
> Found 47 results. Enter term to filter, 'view N' to see result, or 'done':
> patterns
> Filtered to 12 results containing "patterns"
> view 3
> [Shows result 3 in detail]
> await
> Filtered to 5 results containing "await"
> done
> [Shows final 5 results]
```

**Refinement commands:**
- `<term>` - Filter results by keyword
- `view N` - Show full content of result N
- `undo` - Remove last filter
- `done` - Exit refinement and show results

---

## Multi-hop Search

Discover related queries and follow knowledge chains:

```bash
# Enable multi-hop suggestions
/search "scalar quantization" --suggest

# Output includes:
=== Results ===
[Standard search results]

=== Suggested Follow-ups ===
1. "vector database compression" - Related to quantization techniques
2. "product quantization" - Alternative compression method
3. "FAISS index parameters" - Implementation details
```

**Multi-hop options:**
- `--suggest N` - Show up to N suggestions (default: 3)
- `--auto-hop` - Automatically run suggested queries
- `--chain-depth N` - Max hops in a chain (default: 2)

Use multi-hop when exploring unfamiliar topics or when initial results are sparse.

---

## Result Clustering

Group search results into thematic clusters for better organization:

```bash
# Cluster by semantic topic (uses embeddings)
/search "python async" --cluster topic

# Cluster by source backend
/search "authentication" --cluster backend

# Cluster by time (recent/older/archived)
/search "authentication" --cluster temporal

# Filter to specific cluster
/search "python async" --cluster topic --filter c1

# Interactive cluster exploration
/search "python async" --cluster topic --interactive
```

### Clustering Modes

| Mode | Description | Speed | When Useful |
|------|-------------|-------|-------------|
| **topic** | Semantic clustering using embeddings | ~50ms | Exploring themes in results |
| **backend** | Group by source (CHS, CKS, etc.) | ~5ms | Understanding result sources |
| **temporal** | Group by time (recent/older/archived) | ~5ms | Finding recent vs historical info |

### Clustering Output

When clustering is enabled, results include cluster metadata:

```
=== Clustering Summary ===
Mode: topic
Total results: 47
Clusters: 3

  [c1] Async/Await Patterns (5 results, 0.89 confidence)
  [c2] Event Loop Architecture (3 results, 0.82 confidence)
  [c3] Coroutine Best Practices (2 results, 0.76 confidence)

Unclustered: 37
```

Each cluster includes:
- **id**: Cluster identifier (c1, c2, etc.)
- **label**: Auto-generated topic label
- **count**: Number of results in cluster
- **confidence**: Average semantic similarity (0-1)
- **summary**: Brief description of cluster content

### Cluster Filtering

After seeing clusters, filter to specific topics:

```bash
# Show only cluster c1 results
/search "python async" --cluster topic --filter c1

# Combine with other flags
/search "async" --cluster topic --filter c1 --limit 20 --backend chs
```

### Implementation Notes

- Clustering only activates for 10+ results (not useful for small sets)
- Topic clustering uses existing embeddings (no recomputation)
- Backend/temporal modes use simple grouping (no ML needed)
- Labels are auto-generated from result content keywords

---

## Conversational Search Continuum (--session)

Enable conversational search with context tracking across queries:

```bash
# Start session mode
/search "python async patterns" --session

# Results show with reference IDs: [1] [2] [3] ...

# Follow-up on specific result
/search "tell me more about result 3" --session

# View session summary
/search --session --summary

# Export session to CKS
/search --session --export
```

### Session Features

| Feature | Description |
|---------|-------------|
| **Query History** | Tracks last 5 queries with timestamps |
| **Result Reference** | Number results [1], [2], [3] for easy reference |
| **Follow-up Queries** | "tell me more about result #3" shows full details |
| **Session Summary** | Shows search path and topics covered |
| **CKS Export** | Persist session knowledge to Constitutional Knowledge System |

### Session Output

Session mode includes reference numbers in results:

```
=== CHS Session Results ===
Query: "python async patterns"
Session ID: sess-abc123 (Query 1/5)

[1] [0.92] "Use asyncio with async/await syntax..."
    From: 2025-01-15 discussion

[2] [0.87] "Async functions return coroutines..."
    From: 2025-01-10 discussion

[3] [0.75] "Event loop manages async tasks..."
    From: 2024-12-20 discussion
```

### Session Implementation

- **Storage**: Temporary (cleaned up after export)
- **Session ID**: Auto-generated or uses WT_SESSION env var
- **History Limit**: Last 5 queries, 10 results each
- **Export Target**: CKS database for persistence
- **Non-breaking**: Works without --session (normal search unaffected)
