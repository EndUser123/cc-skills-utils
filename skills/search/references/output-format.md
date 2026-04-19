# Search Output Format

Results are grouped by source with relevance scores and match explanations:

```
=== CKS (3 results) ===
[0.92] Memory: "Discussed authentication approach..."
  Why matched: "authentication", "JWT", "API" keywords
  From: Session on 2026-01-15 (2 days ago)

[0.87] Pattern: "Always use JWT for API auth..."
  Why matched: "JWT", "authentication", "API"
  From: Knowledge base

=== CHS (2 results) ===
[0.85] [2026-01-15] Session: "User asked about OAuth..."
  Why matched: "OAuth", "authentication", "discussion"

[0.72] [2026-01-10] Session: "Configured JWT tokens..."
  Why matched: "JWT", "tokens", "configuration"

=== JSONL (fallback) ===
[2026-02-08] 9f00140b.jsonl: "auto-read hook discussion..."
  Why matched: "hook", "discussion"
```

Options:
- `--expand` - Show full content instead of snippets
- `--json` - Machine-readable JSON output
- `--limit N` - Limit results per backend

## Result Explanations

Each search result includes a "Why matched" explanation that shows which terms or concepts caused the match. This helps you:

1. **Understand relevance** - See exactly what triggered the match
2. **Refine queries** - Adjust terms based on what actually matched
3. **Debug searches** - Identify why unexpected results appeared

Explanation types:
- **Keyword matches** - Literal terms found in the content
- **Semantic matches** - Conceptually related content (via embeddings)
- **Combined** - Both keyword and semantic factors

For semantic matches, the explanation may include related concepts that aren't exact keyword matches but are semantically connected to your query.
