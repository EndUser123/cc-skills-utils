# Implementation Details

## Layer 1 Enhancements

### Layer 1A: Rule-Based Filtering (Always)
- Duplicate removal (URL + title similarity)
- Quality floor (score >= min_score)
- Per-backend limits (max 10 per source)
- Hard cap (max 50 results)

### Layer 1B: Semantic Clustering (Always)
- Jaccard similarity clustering (threshold: 0.4)
- Keeps top-N from each cluster (preserves diversity)
- Reduces 30-40 items → 20-25 items
- Processing time: <500ms

### Layer 1C: Query Complexity Scoring (Always)
- Term specificity (technical vs generic)
- Intent ambiguity (clear vs multiple interpretations)
- Expected diversity (based on term variance)
- Score: 0-100 (Simple <40, Medium 40-60, Complex >60)

### Layer 1D: Adaptive Limits (Always)
- Simple queries: 20 items (faster)
- Medium queries: 30 items (balanced)
- Complex queries: 40 items (more context)
- Token estimation before Layer 2

## Layer 2: Agent Tool Integration

### Trigger Conditions
- High complexity (>60) + >15 results → trigger
- Medium complexity (40-60) + >20 results → trigger
- Low complexity (<40) + >30 results → trigger
- Context hints present → trigger
- User override with `--force-context-filter`

### Adaptive Behavior
- High complexity queries: Extract 8-10 insights (comprehensive)
- Low complexity queries: Extract 5-7 insights (focused)
- Token estimation: Alert if >8k tokens (prevent truncation)

### Error Handling
- Agent tool failure → Keyword-based fallback
- Invalid JSON → Graceful degradation
- CLI mode (no Agent tool) → Keyword-based filtering

## Performance Characteristics

| Mode | Local Speed | Web Speed | Total | Use Case |
|------|------------|-----------|-------|----------|
| `auto` | <1s | 0-10s | 0-11s | Default, adaptive |
| `unified` | <1s | 5-10s | 5-11s | Comprehensive |
| `local-only` | <1s | 0s | <1s | Fast, private |
| `web-fallback` | <1s | 0-10s | 0-11s | Quality-focused |

**Layer 1 Performance:**
- Layer 1A (search): <200ms overhead
- Layer 1B (clustering): <500ms overhead
- Layer 1C (complexity): <100ms overhead
- Layer 1D (limits): <50ms overhead
- **Total Layer 1: <1 second**

**Layer 2 Performance:**
- Agent tool filtering: <5 seconds overhead
- Token usage: <8k tokens (Layer 1 pre-filtering keeps this manageable)

## Error Handling Scenarios

### Web search failures
```bash
/explore "query" --mode auto
# → Local search succeeds
# → Web search fails (network, API error)
# → Result: Shows local results with warning
```

### Quality fallback
```bash
/explore "very specific term" --mode auto
# → Local search returns 1 low-quality result (score: 0.3)
# → Quality check fails
# → Triggers web search automatically
# → Result: Enhanced with web results
```

### Agent tool failures
```bash
/explore "query" (triggers Layer 2)
# → Agent tool fails or times out
# → Falls back to keyword-based filtering
# → Result: Still shows Layer 1 output
```

