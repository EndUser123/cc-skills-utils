---
name: explore
description: "ALWAYS use this skill for explore queries - unified search across your local data (chat history, knowledge base, code, docs) AND the web with intelligent source selection."
version: "1.0.0"
status: stable
enforcement: advisory
category: unified
triggers:
  - /explore
  - 'search for'
  - 'what do we know about'
  - 'find information'
  - 'look for information'
aliases:
  - /explore
  - /explore
  - /universal
  - /search-all

do_not:
  - fabricate web search results without calling web APIs
---

# Explore (`/explore`)

## Purpose

Single entry point to search **EVERYTHING** - your local data (chat history, knowledge base, code, docs) AND the web (current documentation, best practices, Stack Overflow). Results are merged and ranked by relevance, then intelligently filtered via three-layer architecture.

## When to Use

| Command | Searches | Speed | When To Use |
|---------|----------|-------|-------------|
| `/search` | Local data only | <1s | "What did we discuss?" |
| `/research` | Web only | 5-10s | "What's the current best practice?" |
| **`/explore`** | **Both + merged results** | 1-10s | "I want to see everything" |

## Three-Layer Filtering Architecture

| Layer | Responsibility | When Applied |
|-------|---------------|--------------|
| **Layer 1A** | Volume control, deduplication, quality floor | Always |
| **Layer 1B** | Semantic clustering (Jaccard similarity) | Always |
| **Layer 1C** | Query complexity scoring | Always |
| **Layer 1D** | Adaptive result limits (token-aware) | Always |
| **Layer 2** | Semantic relevance via Agent tool (LLM-based) | Conditional (auto-triggers) |
| **Layer 3** | Presentation formatting | Always |

**Layer 2 Auto-triggers when:**
- Result count > 20 (configurable: `--context-threshold N`)
- Query contains context hints (`"we discussed"`, `"for the X feature"`)
- Query complexity score high (>60) + sufficient results (>15)

**User overrides:**
- `--no-context-filter`: Skip Layer 2
- `--force-context-filter`: Force Layer 2 even for small result sets
- `--context-threshold N`: Adjust trigger threshold (default: 20)

## Execution Model

This skill executes inline Python code (no subprocess). The Agent tool is ONLY available in skill execution context.

> **Full inline execution code:** See `references/inline-execution-code.md` for the complete Python source that handles three-layer filtering orchestration.

## Quick Usage

```bash
/explore "python async patterns"                          # Auto-filtering (default)
/explore "what did we decide about auth"                   # Context-aware (auto-triggers Layer 2)
/explore "best practices" --mode unified                   # Force local + web
/explore "what did we discuss" --mode local-only          # Fast, no web APIs
/explore "query" --no-context-filter                      # Layer 1 only
/explore "microservices patterns" --force-context-filter  # Always apply Layer 2
```

> **More examples and advanced options:** See `references/usage-examples.md`

## Output Format

Results display as `[score] SOURCE: title` with preview text. When Layer 2 activates, results are grouped by theme with key insights extracted per group.

> **Full output format examples:** See `references/output-format.md`

## Validation Rules

- Verify actual web API calls were made before citing results
- Ensure URL and content are real before citing web sources
- Always indicate local vs web source attribution
- Report empty results clearly for both sources
- Web search failures fall back to local results with warning

## Performance

| Mode | Local | Web | Total | Use Case |
|------|-------|-----|-------|----------|
| `auto` | <1s | 0-10s | 0-11s | Default, adaptive |
| `unified` | <1s | 5-10s | 5-11s | Comprehensive |
| `local-only` | <1s | 0s | <1s | Fast, private |
| `web-fallback` | <1s | 0-10s | 0-11s | Quality-focused |

Layer 1 total: <1 second. Layer 2: <5 seconds when triggered.

## Reference Files

| File | Contents |
|------|----------|
| `references/inline-execution-code.md` | Full Python execution source code |
| `references/implementation-details.md` | Layer behavior, trigger conditions, error handling |
| `references/usage-examples.md` | Usage examples and advanced CLI options |
| `references/output-format.md` | Output format examples (Layer 1 vs Layer 2) |
| `references/migration-notes.md` | Migration from `/search` + `/research` workflow |
| `references/troubleshooting.md` | Common issues and solutions |
| `references/performance-tuning.md` | Speed vs coverage tuning guide |

