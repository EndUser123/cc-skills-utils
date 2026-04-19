# Search Auto-Detection Rules

## Chat History Detection (`--source chat` auto-enabled)

Query patterns trigger chat search:
- **Conversational**: "we discussed", "what did we say", "you mentioned", "I said"
- **Temporal**: "recent", "yesterday", "last week", "earlier today", "our conversation"
- **Pronouns**: "we decided", "you told me", "they agreed" (first/second/third person)
- **Meta-discussion**: "about the hook", "the skill we", "that function from before"

Examples:
```
"what did we discuss about authentication"  -> chat only
"recent changes to the search skill"        -> chat only
"you mentioned something about FAISS"      -> chat only
```

## Web Search Detection (routes to `/research`)

Query patterns that suggest web research needs:
- **Technical**: "async patterns", "JWT auth", "FAISS index" (code/docs)
- **Procedural**: "how to", "tutorial", "best practices"
- **Reference**: "the README", "documentation", "the skill for X"
- **External**: "python package", "library", "API"

**For web search, use `/research` instead of `/search`.**

Examples:
```
/research "how does FAISS work"                    -> web search
/research "the search skill documentation"       -> web search
/research "python async patterns"                  -> web search
```

## Combined Search (`--source all` auto-enabled)

Query patterns trigger both local and chat:
- **Cross-reference**: "what did docs say about X vs what we discussed"
- **Evolution**: "how our approach to Y changed over time"
- **Validation**: "does the code match our earlier discussion"
- **Complex**: multi-part queries needing context from multiple sources

## Chat Method Auto-Detection

When chat search is triggered, method is auto-selected:

| Query Pattern | Method | Why |
|---------------|--------|-----|
| "5 min ago", "just now", "today" | `grep` | Very recent, not in FAISS yet |
| "we discussed", "meaning", "concept" | `vector` | Semantic meaning matters |
| "error message", "exception", "traceback" | `grep` | Exact text matching |
| "authentication design", "architecture" | `vector` | Deep semantic search |

## Depth Auto-Detection

Detail level auto-selected based on query:
- **Exploratory** ("find", "search", "look for") -> `summary`
- **Specific** ("ID chs_123", "full details") -> `full`
- **Result count** < 10 -> auto-upgrade to `full`

## Query Detection Rules

1. **Code-first indicators**: Function names, file extensions, technical symbols, `git` commands
2. **Knowledge-first indicators**: "pattern", "lesson", "approach", "strategy", convention terms
3. **Conversation-first indicators**: "discussed", "said", "decided", "agreed", "mentioned", pronouns like "we"
4. **URL patterns**: http/https URLs trigger webreader_mcp
5. **GitHub patterns**: `org/repo` format triggers zread/github tools
6. **Error indicators**: Stack traces, error codes, exception types

## Backend Weighting

When multiple backends are queried, results are weighted by:
- **Relevance score** (from backend)
- **Source multiplier** (based on query type match)
- **Recency bonus** (for CHS/JSONL - recent conversations rank higher)
