"""
Three-layer filtering implementation for /explore skill.

This module implements the context-aware filtering logic for the /explore skill,
including trigger detection and subagent orchestration.
"""

from typing import Any


def has_context_hints(query: str) -> bool:
    """
    Detect if query contains context hints that require Layer 2 filtering.

    Context hints indicate the user is asking about:
    - Previous discussions ("we discussed", "we decided")
    - Specific features/contexts ("for the X feature")
    - Conversation history ("mentioned earlier", "related to our")

    Args:
        query: The search query string

    Returns:
        True if context hints detected, False otherwise
    """
    context_hints = [
        "we discussed",
        "we decided",
        "we agreed",
        "mentioned earlier",
        "for the",
        "in the context of",
        "related to our",
        "what did we",
        "you said",
        "they said",
        "our approach",
        "our implementation"
    ]

    query_lower = query.lower()
    return any(hint in query_lower for hint in context_hints)


def should_apply_context_filter(
    results: list[Any],
    query: str,
    threshold: int = 20
) -> tuple[bool, str]:
    """
    Determine if Layer 2 context-aware filtering should be applied.

    Triggers for Layer 2:
    1. Result count exceeds threshold (default: 20)
    2. Query contains context hints (conversation awareness needed)

    Args:
        results: List of search results from Layer 1
        query: The original search query
        threshold: Result count threshold (default: 20)

    Returns:
        Tuple of (should_enable: bool, reason: str)
        - should_enable: True if Layer 2 should be applied
        - reason: "result_count", "context_hints", or None
    """
    # Check result count threshold
    if len(results) > threshold:
        return True, "result_count"

    # Check context hints
    if has_context_hints(query):
        return True, "context_hints"

    return False, None


async def apply_context_filter(results: list[Any], query: str) -> dict[str, Any]:
    """
    Apply Layer 2 context-aware filtering via subagent.

    This function orchestrates the subagent that performs semantic filtering:
    - Analyzes results for query relevance
    - Extracts key insights (3-5 per result)
    - Groups results by theme
    - Preserves source attribution

    Args:
        results: List of search results from Layer 1
        query: The original search query

    Returns:
        Dictionary with filtered results:
        {
            "themes": [...],           # Themed result groups
            "filtered_count": N,        # Number of results after filtering
            "original_count": M         # Number of results before filtering
        }
    """
    # Import here to avoid circular dependency
    # In actual skill execution, this would use Claude Code's Agent tool
    try:
        from anthropic import Anthropic

        # Format results for subagent
        results_text = _format_results_for_subagent(results)

        # Construct prompt for subagent
        prompt = f"""You are a CONTEXT-AWARE FILTER for search results.

QUERY: {query}
RESULTS COUNT: {len(results)}
RESULTS: {results_text}

YOUR TASK:
1. Analyze each result for actual relevance to the query
2. Extract 3-5 key insights per relevant result
3. Group results by theme/topic (max 5 themes)
4. Preserve source attribution (where did this come from?)
5. Return JSON structure:
   {{
     "themes": [
       {{"name": "Theme Name", "insights": [...]}}
     ],
     "filtered_count": N,
     "original_count": {len(results)}
   }}

FOCUS:
- Quality over quantity (better to have 10 great results than 50 mediocre ones)
- Semantic relevance (not just keyword matching)
- Actionable insights (what can the user actually DO with this?)
- Context awareness (what is the user actually trying to achieve?)

Do NOT apply artificial token limits. Return as much detail as needed to be useful."""

        # Call LLM for context-aware filtering
        # Note: In actual skill execution, this would use Agent() tool
        client = Anthropic()
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        # Parse response (in real execution, would be structured JSON)
        import json
        filtered = json.loads(response.content[0].text)

        return filtered

    except Exception as e:
        # Fallback: return original results with note
        return {
            "themes": [
                {
                    "name": "All Results",
                    "insights": results  # Fallback to original
                }
            ],
            "filtered_count": len(results),
            "original_count": len(results),
            "filtering_error": str(e)
        }


def _format_results_for_subagent(results: list[Any]) -> str:
    """
    Format results for subagent processing.

    Args:
        results: List of search results

    Returns:
        Formatted string representation
    """
    formatted = []

    for i, result in enumerate(results):
        # Handle both SearchResult objects and dicts
        if hasattr(result, 'title'):
            title = result.title
            content = result.content
            url = getattr(result, 'url', '')
            source = result.source
            score = result.score
        else:
            title = result.get('title', '')
            content = result.get('content', '')
            url = result.get('url', '')
            source = result.get('source', 'WEB')
            score = result.get('score', 0.0)

        formatted.append(f"""
{i+1}. {title}
   Content: {content[:200]}...
   URL: {url}
   Source: {source}
   Score: {score}
""")

    return "\n".join(formatted)


def format_standard_results(results: list[Any], query: str) -> str:
    """
    Format results without Layer 2 filtering (standard format).

    Args:
        results: List of search results
        query: The original search query

    Returns:
        Formatted string for display
    """
    output = []

    output.append(f"=== Universal Search Results: \"{query}\" ===")
    output.append(f"Results: {len(results)}")
    output.append("")

    if not results:
        output.append("No results found.")
        return "\n".join(output)

    for i, result in enumerate(results, 1):
        # Handle both SearchResult objects and dicts
        if hasattr(result, 'title'):
            title = result.title
            content = result.content
            url = getattr(result, 'url', None)
            source = result.source
            score = result.score
        else:
            title = result.get('title', 'Untitled')
            content = result.get('content', '')
            url = result.get('url', None)
            source = result.get('source', 'WEB')
            score = result.get('score', 0.0)

        # Determine source indicator
        if source in ["CHS", "CKS", "Code", "DOCS", "SKILLS"]:
            indicator = "📚 LOCAL" if source != "CHS" else "💬 LOCAL"
        else:
            indicator = "🌐 WEB"

        # Format output
        output.append(f"[{score:.2f}] {indicator}: {title}")

        if url:
            output.append(f"    URL: {url}")

        # Add content preview
        preview = content[:200] + "..." if len(content) > 200 else content
        output.append(f"    Content: {preview}")

        output.append("")

    return "\n".join(output)


def format_themed_results(filtered_results: dict[str, Any], query: str) -> str:
    """
    Format themed results from Layer 2 filtering.

    Args:
        filtered_results: Dictionary with themes and insights from Layer 2
        query: The original search query

    Returns:
        Formatted string for display
    """
    output = []

    original_count = filtered_results.get("original_count", 0)
    filtered_count = filtered_results.get("filtered_count", 0)

    output.append(f"=== Universal Search Results: \"{query}\" ===")
    output.append(f"Layer 2 Applied: Context-aware filtering ({original_count} results → {filtered_count} key insights)")
    output.append("")

    themes = filtered_results.get("themes", [])

    if not themes:
        output.append("No themed results available.")
        return "\n".join(output)

    for theme in themes:
        theme_name = theme.get("name", "Unnamed Theme")
        insights = theme.get("insights", [])

        output.append(f"### Theme: {theme_name} ({len(insights)} insights)")

        for insight in insights:
            if isinstance(insight, dict):
                title = insight.get("title", "Untitled")
                key_insights = insight.get("key_insights", [])
                source = insight.get("source", "WEB")
            else:
                title = str(insight)
                key_insights = []
                source = "WEB"

            # Determine source indicator
            if source in ["CHS", "CKS", "Code", "DOCS"]:
                indicator = "📚" if source != "CHS" else "💬"
            else:
                indicator = "🌐"

            output.append(f"{indicator} {title}")

            if key_insights:
                output.append("    Key Insights:")
                for insight_text in key_insights:
                    output.append(f"    • {insight_text}")

            output.append("")

    return "\n".join(output)


def _serialize_results(results: Any) -> Any:
    """
    Convert SearchResult objects to JSON-serializable dicts.

    Args:
        results: Search results (list of SearchResult or dict from Layer 2)

    Returns:
        JSON-serializable version of results
    """
    from dataclasses import asdict

    if isinstance(results, list):
        # Convert list of SearchResult objects to dicts
        return [asdict(r) if hasattr(r, '__dataclass_fields__') else r for r in results]
    elif isinstance(results, dict):
        # Layer 2 output - keep as-is (already structured)
        return results
    else:
        return results


def format_output(
    results: Any,
    query: str,
    layer2_applied: bool,
    format_type: str = "human"
) -> str:
    """
    Layer 3: Format output based on whether Layer 2 was applied.

    Args:
        results: Search results (either list from Layer 1 or dict from Layer 2)
        query: The original search query
        layer2_applied: Whether Layer 2 filtering was applied
        format_type: Output format ("human" or "json")

    Returns:
        Formatted string for display
    """
    if format_type == "json":
        # Return JSON format (programmatic use)
        import json
        return json.dumps({
            "query": query,
            "results": _serialize_results(results),
            "layer2_applied": layer2_applied
        }, indent=2)

    # Human-readable format
    if layer2_applied and isinstance(results, dict) and "themes" in results:
        # Use themed format
        return format_themed_results(results, query)
    else:
        # Use standard format
        return format_standard_results(results, query)
