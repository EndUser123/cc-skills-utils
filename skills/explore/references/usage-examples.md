# Usage Examples

## Basic universal search (auto-filtering)
```bash
/explore "python async patterns"
# → Layer 1A: Python filters duplicates, quality floor
# → Layer 1B: Semantic clustering removes near-duplicates
# → Layer 1C: Complexity score calculated
# → Layer 1D: Adaptive limit applied
# → Layer 2: Auto-enables if >20 results → Agent tool extracts key insights
# → Layer 3: Formatted themed output
```

## Context-aware filtering example
```bash
/explore "what did we decide about authentication"
# → Layer 1: Returns 35 results
# → Layer 2: Auto-enables (context hint: "what did we decide")
#   → Agent tool filters to 8 themed results
#   → Groups: "JWT vs OAuth", "Token Storage", "Refresh Strategy"
```

## Force comprehensive search
```bash
/explore "authentication best practices" --mode unified
# → Always searches local + web
# → Layer 2: Auto-enables if >20 results
```

## Local-only (like /search)
```bash
/explore "what did we discuss" --mode local-only
# → Fast, no web APIs
# → Layer 2: Still applies if triggered
```

## Programmatic use (no Layer 2)
```bash
/explore "query" --no-context-filter
# → Layer 1 only (faster, predictable)
```

## Force distillation (always Layer 2)
```bash
/explore "microservices patterns" --force-context-filter
# → Layer 2: ALWAYS applies
# → Extracts key insights, groups by theme
```

## Advanced Options

```bash
# Adjust Layer 2 trigger threshold
/explore "query" --context-threshold 50

# Custom quality thresholds
/explore "query" --min-score 0.7 --min-results 5

# RRF tuning
/explore "query" --rrf-k 80  # More diversity

# Result limits
/explore "query" --limit 20
```

