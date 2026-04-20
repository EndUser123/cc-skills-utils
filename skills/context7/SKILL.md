---
name: context7
description: "Docs-as-Code: Fetch fresh, version-specific documentation via Context7 API."
version: "1.1.0"
status: "stable"
enforcement: advisory
category: research
triggers:
  - /context7
  - "use context7"
  - "docs for"
execution:
  directive: |
    Use the Context7 API to fetch fresh documentation for specific libraries.

    1. **Check Session History**:
       - STOP if you have already fetched docs for this library/topic and they are visible in your context history.
       - Reuse the existing tool output from your memory.
       - Only proceed if this is a new query or the previous docs have scrolled out of context.

    2. **Identify the Library**: Extract the library name from the user's prompt (e.g., "Next.js", "Supabase", "Tailwind").

    3. **Identify the Intent**: What is the user trying to do? (e.g., "authentication", "middleware", "setup").

    4. **Expand the Query**: Transform the user's brief query into a detailed natural-language question.
       - Bad: "nextjs middleware" -> Context7 returns generic results
       - Good: "How to implement middleware in Next.js App Router with code examples"
       - Bad: "pandas join" -> May miss relevant snippets
       - Good: "How to merge two DataFrames in pandas with an outer join example"
       - Why: Context7 uses query for relevance ranking -- detailed questions score better matches

    5. **Decide Mode**: Choose `code_only` or `full` based on query type.
       - `code_only` (default): When asking for syntax, API signatures, or implementing familiar patterns
       - `full`: When asking "how does X work", debugging, or first contact with an unfamiliar library
       - Why: `code_only` saves ~80% tokens; `full` provides necessary context for learning

    6. **Check for Version Pinning**: If the user mentions a specific version, append it to the libraryId.
       - Format: /org/library/v1.2.3 (e.g., /vercel/next.js/v15.1.8)
       - If no version mentioned, use the base libraryId (latest)
       - Why: Pinning ensures consistent results across sessions and CI environments

    7. **Search & Resolve ID**:
       - Call `mcp__plugin_context7_context7__resolve-library-id` with `libraryName` and `query`
       - Example: `libraryName: "Supabase"`, `query: "how to authenticate users"`
       - Returns the exact Context7-compatible library ID (e.g., `/supabase/supabase-js`)

    8. **Fetch Context**:
       - Call `mcp__plugin_context7_context7__query-docs` with `libraryId` and `expanded_query`
       - Use the resolved library ID from step 7 (append version if pinning in step 6)
       - Pass `mode: "code_only"` or `mode: "full"` based on step 5 decision
       - Example: `libraryId: "/supabase/supabase-js"`, `query: "authentication methods with examples"`

    9. **Handle Errors**:
       | Code | Meaning                          | Action                                        |
       |------|----------------------------------|-----------------------------------------------|
       | 202  | Library not finalized            | Wait briefly, retry                           |
       | 301  | Library redirected               | Follow `redirectUrl` in response              |
       | 401  | Invalid API key                  | Key must start with `ctx7sk` -- check config  |
       | 404  | Library not found                | Verify library name spelling                   |
       | 429  | Rate limited                     | Exponential backoff, use cached data if avail  |
       | 500/503 | Server error                | Retry with backoff                            |

   10. **Present**: Show the documentation and use it to answer the request.

  default_args: ""
  examples:
    - "/context7 how to auth with supabase"
    - "/context7 nextjs middleware"
    - "/context7 django 4.2 migrations"

do_not:
  - guess library versions (always check context)
  - use outdated knowledge if Context7 provides newer data
  - fetch context for generic programming concepts (only for specific libraries)
  - use brief keywords as queries -- always expand to natural language

output_template: |
  ## Context7 Verification: [Library Name]

  **Library ID:** `[resolved_id]`
  **Query:** `[expanded_query]`
  **Version:** `[pinned version or "latest"]`
  **Mode:** `[code_only or full]`

  ### Documentation Summary
  [Summarize the key points retrieved from Context7]

  ### Code Example (Verified)
  ```[lang]
  [Code snippet based on fresh docs]
  ```

---

# Context7 - Fresh Documentation

**Objective:** Eliminate hallucinations by injecting real-time, version-specific documentation into the context.

## How to Use

1. **Trigger**: `/context7 [query]` or `use context7`
2. **Process**:
   - The agent searches for the library.
   - The agent fetches relevant docs for your query.
   - The agent generates code/answers based on *that* documentation.

## Requirements

- **MCP Server**: Context7 MCP server must be configured in your Claude Code settings
- **API Key**: Configure via MCP server settings (set in Claude Code MCP configuration)
- No environment variables needed - MCP handles authentication

## Workflow Example

**User:** "How do I do auth in Supabase? use context7"

**Agent:**
1.  Call `resolve-library-id` with `libraryName: "Supabase"`, `query: "authentication"` -> Returns `/supabase/supabase-js`
2.  Call `query-docs` with `libraryId: "/supabase/supabase-js"`, `query: "how to authenticate users with examples"`
3.  **Result:** Returns official Supabase Auth documentation with code examples.
4.  **Answer:** Generates code using the verified `supabase.auth.signInWithPassword()` method.

## Best Practices

1. **Be Specific**: Use natural language questions, not keywords
   - Good: "How to implement middleware in Next.js App Router"
   - Bad: "nextjs middleware"

2. **Pin Versions**: When discussing a specific version, include it
   - Format: `/org/library/v1.2.3`
   - Example: `/vercel/next.js/v15.1.8`

3. **Check Cache**: Don't re-fetch if recent docs are in context
   - Context7 docs update infrequently
   - Caching for hours/days is appropriate

4. **Mode Selection**: Choose based on what you need
   | Situation | Mode | Example Query |
   |----------|------|---------------|
   | Need explanation / learning | `full` | "how does Next.js middleware work" |
   | Debugging subtle behavior | `full` | "why is my middleware not being called" |
   | Unfamiliar library first contact | `full` | "how to use LangChain prompts" |
   | Need syntax / API signature | `code_only` | "Next.js middleware function signature" |
   | Implementing familiar pattern | `code_only` | "add JWT validation to Express middleware" |
   | Quick reference check | `code_only` | "React useCallback dependency array" |

   **Default to `code_only`** unless: the query asks "how does X work", involves debugging, or targets a library not yet seen in the session.

   Note: The MCP tool output is markdown with code blocks. Post-filter by keeping only ` ``` ` blocks for token-efficient code-only mode.
