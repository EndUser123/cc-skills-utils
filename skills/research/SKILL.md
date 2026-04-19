---
name: research
description: Web research with multiple providers and intelligent result synthesis
version: 1.0.0
status: stable
category: research
enforcement: advisory
triggers:
  - /research
  - 'research '
  - 'web search'
  - 'find on web'
aliases:
  - /research
suggest:
  - /search

do_not:
  - claim to search without actually invoking providers
  - fabricate search results without provider responses
  - skip URL fetching when results need source verification
  - return full search results or fetched URL content inline to the caller — write to artifact file and return path + summary instead
  - use --fetch-urls without writing fetched content to an artifact file first

workflow_steps:
  - analyze_query_intent
  - select_search_mode
  - choose_providers
  - execute_search
  - synthesize_results
  - fetch_urls
  - format_output
---

# Research Skill

## Purpose

Conduct comprehensive web research using multiple search providers with intelligent result synthesis, saturation detection, and HyDE-powered query expansion.

## Capabilities

### Providers (working)
- **tavily** - Fast, comprehensive search (recommended default)
- **exa** - High-quality technical/engineering results
- **glm** - Web search via GLM-4.5-Air model
- **serpapi** - Google results via serpapi.com (250/month free)
- **webreader** - URL fetching and content extraction (not a search engine)
- **github** - Code and repository search (requires GITHUB_TOKEN)

### Providers (non-functional)
- **notebooklm** - Document analysis (requires NotebookLM MCP + notebooks)
- **claude** - Claude API documentation (requires ANTHROPIC_API_KEY)

### Modes
- **auto** - Auto-select providers based on query type
- **web** - Web search with multiple providers
- **quick** - Fast results from single provider

### Features
- **HyDE integration** - Query expansion for better results
- **Saturation detection** - Stop when results are semantically saturated
- **URL fetching** - Extract full content from search results
- **Result caching** - Avoid duplicate searches
- **Multi-provider synthesis** - Combine results from multiple sources

## Your Workflow

1. **Analyze query intent** - Detect if technical, general, or code search
2. **Select mode** - Choose auto/web/quick based on query complexity
3. **Choose providers** - Pick appropriate providers for query type
4. **Execute search** - Parallel queries with saturation detection
5. **Synthesize results** - Combine and rank from multiple providers
6. **Fetch URLs** - Extract content when results need verification
7. **Format output** - Present findings with sources and relevance scores

## Provider Selection Guide

| Query Type | Recommended Providers | Alternative |
|------------|----------------------|-------------|
| **General research** | tavily | exa, serpapi |
| **Technical/Code** | exa, github | - |
| **AI/ML topics** | tavily, exa | - |
| **Chinese content** | glm | - |
| **Documentation** | webreader + tavily | - |
| **Fast results** | tavily only | quick mode |

## Usage Examples

### Basic research
```
/research "async best practices in Python"
```

### Technical search with specific provider
```
/research "FastAPI vs Flask performance" --mode exa
```
(Note: Provider names are used as modes, not as separate --providers flag)

### Quick search
```
/research "numpy array operations" --mode quick
```

### Research with URL fetching
```
/research "microservices architecture" --fetch-urls 10
```

### Code-specific search
```
/research "pytest fixtures tutorial" --mode github
```
(Note: Provider names are used as modes)

## GitHub Search Routing

### Intelligent Code vs. Repository Detection

When using `--mode github`, the system intelligently routes between **code search** and **repository search** based on query patterns:

**Routes to CODE SEARCH when**:
- **Code keywords detected**: `function`, `class`, `def`, `import`, `async def`, `await`, `const`, `let`, `var`, `interface`, `component`, `hook`, `lambda`, `decorator`, etc.
- **File extensions present**: `.py`, `.js`, `.ts`, `.java`, `.go`, `.rs`, `.cpp`, `.dockerfile`, `.json`, `.yaml`, etc.
- **Language specifiers used**: `language:python`, `language:javascript`, etc. (GitHub API syntax)

**Routes to REPOSITORY SEARCH when**:
- **No code patterns detected**: General queries like "pytest testing libraries"
- **Repository-focused terms**: "framework", "library", "package", "tool", "tutorial", "guide", "comparison"
- **Ambiguous queries**: Defaults to repository search (safe fallback)

### Known Limitations

**False Positives** (documented in pre-mortem analysis):
- ❌ `"python async framework"` → Routes to code search (user wants repos)
- ❌ `"import tutorial"` → Routes to code search (user wants tutorials)

**These occur because**: Current implementation uses keyword presence without phrase-level context analysis.

**Workaround**: Use web providers for repo discovery when you encounter false positives:
```
/research "python async framework" --mode tavily
```

### Rate Limit Handling

**Automatic fallback**: If code search is rate-limited by GitHub API, the system automatically falls back to repository search with a warning:
```
Warning: "Code search rate limited - showing repositories instead"
```

**Monitoring**: Rate limit errors are logged for monitoring and debugging.

### Examples

**Code search** (finds code files):
```
/research "python function decorator" --mode github
/research "async def await" --mode github
/research "setup.py configuration" --mode github
```

**Repository search** (finds repos):
```
/research "pytest testing libraries" --mode github
/research "python web framework" --mode github
/research "machine learning tools" --mode github
```

**Language specifier** (GitHub API syntax):
```
/research "language:python async" --mode github
/research "language:javascript react" --mode github
```

## Implementation

**Backend**: `P:\packages\search-research\core\cli.py`

**Entry point**: `python -m search_research.cli [query] --mode [auto|web|quick|tavily|serper|exa|...]`

**Available modes**: `auto`, `web`, `quick`, `tavily`, `exa`, `glm`, `serpapi`, `webreader`, `fetch`, `github`, `claude`, `webreader_mcp`, `notebooklm`

**Key capabilities**:
- argparse-based CLI with comprehensive options
- Async provider execution for parallel queries
- SaturationDetector for intelligent stopping
- Multiple output formats (JSON, markdown, terminal)
- Result persistence and caching

## Configuration

**Environment variables** (optional):
```bash
export TAVILY_API_KEY=tvly-xxx
export SERPER_API_KEY=xxx
export EXA_API_KEY=exa_xxx
export PERPLEXITY_API_KEY=pplx-xxx
```

**Config files**: Searches `P:/.env` and `P:/__csf/.env` automatically

## Output

Results include:
- **Title** - Result headline
- **URL** - Source link
- **Snippet** - Content preview
- **Score** - Relevance ranking
- **Provider** - Which provider found it
- **Timing** - Query duration

## Output Routing

Research results can be large — multi-provider synthesis with snippets, and especially URL-fetched content, will overflow the caller's context window if returned inline.

**Default behaviour:**
- Write full results to `.claude/state/research-{query-hash}.md`
- Return to caller: result file path, result count, top 3 titles, and a 2–3 sentence synthesis. Nothing else inline.

**`--fetch-urls` is always high-output:**
- Fetched page content MUST be written to artifact files (`.claude/state/research-urls-{hash}/url-{n}.md`), never returned inline.
- Return to caller: artifact directory path + a one-line summary per URL fetched.
- Treat `--fetch-urls` the same as a large diff or long log — it goes to Tier 1 (Artifact Store), the caller reads from disk selectively.

**When the caller needs specific content from results:**
- Use targeted reads of the result artifact (with `offset`/`limit` or `Grep`) rather than re-running the search or inlining the full result file.

## Integration Points

- **CHS** - Can search chat history for related research
- **CKS** - Can query constitutional knowledge for context
- **/search** - Complementary local search vs web research
- **NotebookLM** - Can send results to NotebookLM for analysis
