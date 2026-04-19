---
name: search
description: Unified intelligent search - searches only local data stores (CKS, CHS, CDS, code, docs, skills)
version: "1.2.0"
status: stable
category: unified
enforcement: strict
triggers:
  - /search
  - 'search '
  - 'find '
  - 'look for'
workflow_steps:
  - execute_search_workflow
aliases:
  - /search
  - /chs
  - /recent
  - /search-more
  - /progressive-search

suggest:
  - /research
  - /cks
  - /daemon

do_not:
  - summarize this skill instead of executing it
  - fabricate search results without querying backends
  - skip the semantic daemon when it is available
  - present results without relevance scores
---

# Unified Search

## Purpose

Single entry point to search across all CSF NIP data stores in parallel - **local sources only**. For web research, use `/research`.

**Scope**: CKS, CHS, CDS, Code/Grep, DOCS, SKILLS. No external dependencies.

## Project Context

- **Solo-dev constraints apply** (CLAUDE.md)
- **No external dependencies**: All search is local, privacy-preserving
- **Efficiency over complexity**: Parallel execution, fast responses
- **Evidence-based**: Search results provide citation context
- **Canonical CLI**: `P:/packages/search-research/core/cli.py`
- **Backends**: CKS, CHS (claude-history/Rust+FTS5), CDS, Code/Grep, DOCS, SKILLS
- **Search methods**: FTS5 (~10ms), Hybrid (~50ms), Semantic (~200ms)
- **Output formats**: Human-readable (default), JSON for scripting
- **CHS bootstrap**: If `chat_history.db` exists but FTS5 tables are missing, build it with `python -m core.chs.scripts.reindex_from_jsonl --db-path "P:/__csf/data/chat_history.db" --history-path "~/.claude/history.jsonl"`

See `references/architecture.md` for backend architecture details and NotebookLM integration.

## Your Workflow

1. **Auto-detect intent** - Analyze query for chat/web/combined source needs
2. **Select backends** - Automatically choose based on query patterns
3. **Choose chat method** - Auto-detect vector (semantic) vs grep (recent)
4. **Expand boundary search** - Prefer producers, consumers, schemas, validators, replay, and invalidation logic when query implies contracts or handoffs
5. **Execute search** - Parallel query across selected backends
6. **Check CHS results** - If empty/unavailable, trigger JSONL fallback
7. **Collect results** - Gather with relevance scores
8. **Format output** - Group by source, show relevance, citations, match explanations
9. **Present findings** - Human-readable or JSON format

## Auto-Detection Rules

The system **automatically** detects search intent. No flags needed.

| Query Pattern | Source | Example |
|---------------|--------|---------|
| "we discussed", "you mentioned", pronouns | `chat` | "what did we discuss about auth" |
| "recent", "yesterday", "earlier today" | `chat` | "recent changes to the search skill" |
| "how does X work", "tutorial", code terms | `docs` | "how does FAISS work" |
| "compare X vs Y", "evolved over time" | `chat` + `docs` | "how our auth approach evolved" |
| URLs (http/https) | Suggest `/research` | direct fetch |

Chat method is also auto-selected: `grep` for recent/exact matches, `vector` for semantic/conceptual queries.

See `references/auto-detection.md` for full detection rules, query indicators, and backend weighting.

## Validation Rules

- **Before claiming search works**: Verify actual query execution, not assumption
- **Before citing results**: Ensure result actually contains claimed content
- **Empty results**: Report clearly, don't fabricate findings
- **Relevance scores**: Report actual scores from search engine
- **Do not invent module paths**: Never call `knowledge.systems.chs.cli` (does not exist)
- **CHS readiness**: A non-empty `chat_history.db` file is not enough; verify schema/FTS tables or reindex first

When the query is about architecture, handoffs, resume, stale data, fields, payloads, schemas, or consumers, `/search` should preferentially surface:

- existing producers
- existing consumers
- schemas/validators
- replay/invalidation logic
- transcript/resume artifacts

## Routing Behavior

`/search` is a discovery skill. It may suggest downstream skills once relevant evidence is surfaced:

- `/arch` when search shows unresolved contract/state boundaries
- `/planning` when execution shape is unclear after discovery
- `/verify` when the main question becomes "does this actually work?"

`/search` should not absorb architecture, planning, or verification responsibilities.

## Execution Directive

Run local-only search for `/search` requests:

```bash
cd "P:/packages/search-research" && python -c "
from core.unified_router import UnifiedAsyncRouter
import asyncio

async def search():
    router = UnifiedAsyncRouter(mode='local-only')
    results = await router.search_async('$query', limit=10)
    for r in results:
        print(f'[{r.score:.2f}] {r.title}')
        print(f'  {r.content[:200]}...')
        print()

asyncio.run(search())
"
```

**Session-chain queries** (last 7 days):

```bash
cd "P:/packages/search-research" && python -c "
from pathlib import Path
from datetime import datetime, timedelta

project = Path.home() / '.claude/projects/P--'
handoff_dir = Path('P:/.claude/state/handoff')
cutoff = datetime.now() - timedelta(days=7)

transcripts = [p for p in project.glob('*.jsonl') if datetime.fromtimestamp(p.stat().st_mtime) > cutoff]
transcripts.sort(key=lambda p: p.stat().st_mtime, reverse=True)
print(f'=== Session Transcripts ({len(transcripts)} last 7 days) ===')
for t in transcripts:
    mtime = datetime.fromtimestamp(t.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
    print(f'  [{mtime}] {t.name}')

handoffs = [p for p in handoff_dir.glob('console_*_handoff.json') if datetime.fromtimestamp(p.stat().st_mtime) > cutoff]
handoffs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
print(f'\n=== Handoff Files ({len(handoffs)} last 7 days) ===')
for h in handoffs:
    mtime = datetime.fromtimestamp(h.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
    print(f'  [{mtime}] {h.name}')
"
```

For chat history only:

```bash
cd "P:/packages/search-research" && python -c "
from core.unified_router import UnifiedAsyncRouter
import asyncio

async def search():
    router = UnifiedAsyncRouter(mode='local-only')
    results = await router.search_async('$query', limit=20)
    for r in results:
        if 'chat' in r.source.lower() or 'chs' in r.source.lower():
            print(f'[{r.score:.2f}] {r.title}')
            print(f'  {r.content[:200]}...')
            print()

asyncio.run(search())
"
```

## Quick Usage

```bash
# Chat history - auto-detected
/search "what did we discuss about authentication"
/search "recent changes to the search skill"

# Web sources - auto-detected
/search "how does FAISS work"
/search "python async patterns"

# Session chain - list transcript and handoff files
/search "session chain files"
/search "filepaths for session-chain"
/search "transcript files"

# Hint overrides (when detection gets it wrong)
/search "authentication [from chat]"
/search "authentication [from docs]"
/search "authentication [recent]"
```

Manual flags are available for precise control:

```bash
/search "query" --source chat|web|all
/search "query" --chat-method vector|grep|auto
/search "query" --depth summary|full|auto
/search "query" --explain --cluster topic --session
```

## Backends

| Backend | Description | Content |
|---------|-------------|---------|
| **CHS** | Chat History (claude-history/FTS5; bootstrap with reindex_from_jsonl.py) | Sessions and messages |
| **CKS** | Knowledge (FAISS) | Patterns, lessons, docs |
| **CDS** | Discovery Findings | Code analysis findings |
| **Code/Grep** | Source Code | File content search |
| **DOCS** | Documentation | Markdown files in docs/ |
| **SKILLS** | Skills & Commands | Progressive disclosure search |
| **JSONL** | Conversations (Fallback) | Raw conversation files when CHS empty |

## Source Priority

| Query Pattern | Priority Backends | Rationale |
|---------------|-------------------|-----------|
| "git commit", "function xyz" | Code/Grep -> CKS -> CHS | Code first |
| "pattern xyz", "lesson" | CKS -> DOCS -> CHS | Knowledge first |
| "we discussed", "said" | CHS -> CKS | Conversation first |
| "how does X work" | NotebookLM -> CKS -> DOCS | Long-form synthesis first |
| URLs | webreader_mcp -> DOCS | Direct fetch |
| "org/repo" | zread -> github | GitHub tools |
| "how to", "tutorial" | DOCS -> CKS -> Code | Documentation first |
| errors, stack traces | Code -> CKS -> CHS | Source context first |
| "we decided", "agreed" | CHS -> CKS | Decision history first |

The `--backend` flag always overrides automatic priority.

## Search Methods

| Method | Speed | Coverage | When Used |
|--------|-------|----------|-----------|
| **FTS5** | ~10ms | Full DB | Keyword matching (CHS) |
| **Hybrid** | ~50ms | Full DB | FTS5 pre-filter + semantic re-rank |
| **Semantic** | ~200ms | Indexed | Conceptual/meaning search |

## Subagent Delegation

For complex multi-step searches, delegate to subagents to preserve context memory.

Use subagents when: query spans multiple independent sources, analysis requires deep exploration, or synthesis is needed across multiple result sets.

See `references/subagent-delegation.md` for delegation patterns, parallel execution, and example workflows.

## Advanced Features

The following features auto-enable based on context and result characteristics:

| Feature | Auto-Enabled When | Reference |
|---------|------------------|-----------|
| `--explain` | Query >100 chars, >2s execution, or 0 results | `references/advanced-features.md` |
| `--session` | Running in terminal (WT_SESSION detected) | `references/advanced-features.md` |
| `--cluster` | 10+ results from 2+ sources | `references/advanced-features.md` |
| `--hyde` | Manual flag for semantic enhancement | `references/advanced-features.md` |
| `--refine` | Interactive result narrowing | `references/advanced-features.md` |
| `--suggest` | Multi-hop knowledge chains | `references/advanced-features.md` |

See `references/advanced-features.md` for: intelligent defaults configuration, execution plan explanation, HyDE enhancement, refinement mode, multi-hop search, result clustering, and conversational session mode.

## Consolidated Features

This skill absorbs `/chs`, `/recent`, `/search-more`, and `/progressive-search`.

| Old Command | New Behavior |
|-------------|--------------|
| `/chs "query"` | `/search "query"` (auto-detects chat) |
| `/recent "query"` | `/search "query"` (auto-detects recent + grep) |
| `/search-more "id"` | `/search "id" --depth full` |
| `/progressive-search` | `/search "query"` (auto depth) |

See `references/consolidated-features.md` for: source control (`--source`), chat search method (`--chat-method`), detail level (`--depth`), progressive disclosure workflow, and recent message search.

See `references/output-format.md` for: result grouping format, match explanations, and output options.

## Operational Parameters

The following environment variables control search behavior:

| Env Var | Default | Purpose |
|---------|---------|---------|
| `SEARCH_ENABLE_KG_BOOSTING` | — | Enable KG entity affinity boosting |
| `SEARCH_KG_BOOST_ALPHA` | — | Jaccard similarity weight (0.0-1.0) |
| `SEARCH_KG_BOOST_ENTITY_TYPES` | — | Filter by entity types (comma-separated) |
| `FAST_BACKEND_TIMEOUT` | 2s | Fast backend timeout |
| `COMPREHENSIVE_BACKEND_TIMEOUT` | 8s | Comprehensive backend timeout |
| `SEARCH_CACHE_TTL` | 3600s | LRU cache TTL |

**Extended backends** (KG Boosting, CPG, HDMA, CallGraph, AST, Persona, RLM) are documented in `references/architecture.md`.

## Reference Files

| File | Contents |
|------|----------|
| `references/architecture.md` | Backend architecture, chat history system, NotebookLM integration |
| `references/auto-detection.md` | Full detection rules, query indicators, backend weighting |
| `references/advanced-features.md` | Intelligent defaults, explain, HyDE, refine, multi-hop, clustering, session |
| `references/consolidated-features.md` | Source control, chat method, depth, progressive disclosure, migration |
| `references/output-format.md` | Result format, match explanations, output options |
| `references/subagent-delegation.md` | Delegation patterns, parallel execution, workflow examples |
