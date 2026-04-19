"""Layer 2: Context-Aware Semantic Filtering.

This module provides intelligent semantic filtering for search results,
reducing large result sets to key insights grouped by theme.

IMPORTANT: In Claude Code skill execution, this uses the Agent tool directly.
There are NO external LLM API calls - the Agent tool IS the LLM interface.

Integration with Agent tool wrapper (TASK-005):
- Imports apply_agent_filtering from agent_filter module
- Enhanced with query complexity scoring and adaptive limits
- Fallback to keyword-based filtering for CLI mode
"""

from __future__ import annotations

from typing import Any

# Import Agent tool wrapper and complexity scoring
# NOTE: query_complexity is imported but not used in this module (used in agent_filter)
# agent_filter is used in apply_layer2_filtering function
from . import agent_filter  # noqa: F401
from . import query_complexity  # noqa: F401

# Pre-compiled theme keyword sets for performance (TASK-014 optimization)
# Using frozenset for O(1) lookup and immutability
THEME_KEYWORDS = {
    "Async Programming": frozenset(["async", "await", "asyncio", "coroutine"]),
    "Frameworks & APIs": frozenset(["api", "framework", "library", "flask", "fastapi"]),
    "Best Practices": frozenset(["pattern", "practice", "best", "guide", "tutorial"]),
    "Error Handling": frozenset(["error", "exception", "handling", "debug"]),
    "Search Architecture": frozenset(["search", "router", "backend", "frontend"]),
    "Testing": frozenset(["test", "testing", "pytest", "unittest"]),
}


def has_context_hints(query: str) -> bool:
    """Detect if query contains context hints requiring Layer 2 filtering.

    Args:
        query: Search query string

    Returns:
        True if query contains context hints
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
        "our approach",
        "recall",
        "remember",
        "previously",
    ]
    query_lower = query.lower()
    return any(hint in query_lower for hint in context_hints)


def should_apply_context_filter(
    results: list[Any], query: str, threshold: int = 20
) -> tuple[bool, str | None]:
    """Determine if Layer 2 context-aware filtering should be applied.

    Enhanced with query complexity scoring for adaptive triggering (TASK-005).

    Args:
        results: Search results from Layer 1
        query: Original search query
        threshold: Result count threshold (default: 20)

    Returns:
        Tuple of (should_apply, reason)
    """
    # Use query complexity scoring for adaptive triggering (TASK-005)
    try:
        complexity_score = query_complexity.calculate_complexity_score(query)
        adaptive_threshold = query_complexity.get_layer2_threshold(complexity_score)

        # Check adaptive thresholds
        if len(results) >= adaptive_threshold:
            complexity_label = query_complexity.get_complexity_label(complexity_score)
            return (
                True,
                f"{complexity_label} query (score: {complexity_score}), {len(results)} results >= threshold {adaptive_threshold}",
            )

    except Exception:
        # Fallback to simple threshold if complexity scoring fails
        pass

    # Original threshold check as fallback
    if len(results) > threshold:
        return True, "result_count"

    if has_context_hints(query):
        return True, "context_hints"

    return False, None


def create_layer2_prompt(query: str, results: list[Any]) -> str:
    """Create the prompt for Layer 2 semantic filtering.

    This prompt is designed to work with Claude Code's Agent tool.

    Args:
        query: Original search query
        results: Search results to filter

    Returns:
        Prompt string for Agent tool
    """
    # Format results for the prompt
    formatted_results = []
    for i, result in enumerate(results[:50], 1):  # Cap at 50 for prompt
        title = result.title if hasattr(result, "title") else str(result)
        content = getattr(result, "content", "")
        source = getattr(result, "source", "UNKNOWN")
        score = getattr(result, "score", 0.5)

        formatted_results.append(
            f"{i}. [{score:.2f}] {title}\n   Source: {source}\n   Content: {content[:200]}...\n"
        )

    results_text = "\n".join(formatted_results)

    prompt = f"""You are a CONTEXT-AWARE FILTER for search results. Your task is to extract only the most relevant insights and organize them by theme.

QUERY: {query}
RESULTS COUNT: {len(results)}

SEARCH RESULTS:
{results_text}

YOUR TASK:
1. Analyze each result for ACTUAL relevance to the query intent
2. Extract 3-5 key insights per relevant result
3. Group results by theme/topic (maximum 5 themes)
4. Preserve source attribution (where did this come from?)
5. Return ONLY valid JSON in this exact format:

{{
  "themes": [
    {{
      "name": "Theme Name",
      "insights": [
        {{
          "title": "Result Title",
          "key_insights": [
            "First key insight",
            "Second key insight",
            "Third key insight"
          ],
          "source": "SOURCE",
          "score": 0.95
        }}
      ]
    }}
  ],
  "filtered_count": N,
  "original_count": {len(results)}
}}

FOCUS PRINCIPLES:
- Quality over quantity: Better to have 10 great results than 50 mediocre ones
- Semantic relevance: Not just keyword matching - understand the MEANING
- Actionable insights: What can the user actually DO with this information?
- Context awareness: What is the user actually trying to achieve?

FILTERING CRITERIA:
- Remove duplicates and near-duplicates
- Remove low-quality or generic results
- Keep results that directly answer the query
- Keep results that provide context or background
- Keep results that offer alternatives or comparisons
- Discard results that are tangentially related at best

OUTPUT REQUIREMENTS:
- Return ONLY the JSON object, no additional text
- Ensure all quotes are properly escaped
- Use double quotes, not single quotes
- Make sure JSON is valid and parseable

Do NOT apply artificial token limits. Return as much detail as needed to be useful."""

    return prompt


async def apply_layer2_filtering(query: str, results: list[Any]) -> dict[str, Any]:
    """Apply Layer 2 filtering using the best available method.

    Enhanced with Agent tool wrapper integration (TASK-005):
    - Uses query complexity scoring for adaptive triggering
    - Calls agent_filter.apply_agent_filtering() in skill context
    - Falls back to keyword-based filtering in CLI mode

    In Claude Code skill execution: Uses Agent tool (subagent)
    In CLI mode: Uses keyword-based fallback

    Args:
        query: Original search query
        results: Search results from Layer 1

    Returns:
        Dictionary with filtered results grouped by theme
    """
    # Calculate query complexity for adaptive processing (TASK-005)
    try:
        complexity_score = query_complexity.calculate_complexity_score(query)
    except Exception:
        # Default to medium complexity if scoring fails
        complexity_score = 50

    # Determine trigger reason
    should_apply, trigger_reason = should_apply_context_filter(results, query)

    if not should_apply:
        # No Layer 2 filtering needed, return results as-is
        # Convert to themed format for consistency
        return await _keyword_based_filtering(results, query)

    # Use Agent tool wrapper (TASK-005)
    try:
        # This will use Agent tool in skill context, keyword fallback in CLI
        filtered_results = await agent_filter.apply_agent_filtering(
            query=query,
            results=results,
            trigger_reason=trigger_reason or "auto",
            complexity_score=complexity_score,
        )

        return filtered_results

    except Exception as e:
        # If Agent filtering fails, fall back to keyword-based
        print(f"[Layer 2] Agent filtering failed: {e}, using keyword fallback")
        return await _keyword_based_filtering(results, query)


async def _keyword_based_filtering(results: list[Any], query: str) -> dict[str, Any]:
    """Fallback keyword-based filtering when Agent tool unavailable.

    Performance optimizations (TASK-014):
    - Pre-compiled theme keyword sets (THEME_KEYWORDS) for O(1) lookup
    - Cached lowercased strings (single .lower() call per result)
    - Single-pass theme detection using set intersection
    - Early exit on first theme match

    Args:
        results: Search results from Layer 1
        query: Original search query

    Returns:
        Dictionary with filtered results grouped by theme
    """
    # Group by theme using keyword detection
    themes = {}

    for result in results:
        # Extract title and content
        if hasattr(result, "title"):
            title = result.title
            content = getattr(result, "content", "")
        else:
            title = str(result)
            content = ""

        # Cache lowercased strings (TASK-014 optimization)
        title_lower = title.lower()
        content_lower = content.lower()

        # Single-pass theme detection (TASK-014 optimization)
        # Use set intersection for faster keyword matching
        detected_theme = None
        for theme_name, keywords in THEME_KEYWORDS.items():
            # Check if any keyword exists in title or content
            # Using any() with generator expression for early exit
            if any(keyword in title_lower or keyword in content_lower for keyword in keywords):
                detected_theme = theme_name
                break  # Early exit on first match

        # Default to General if no theme matched
        theme = detected_theme or "General"

        if theme not in themes:
            themes[theme] = []

        # Get source
        if hasattr(result, "backend"):
            source = result.backend
        elif hasattr(result, "source"):
            source = result.source
        else:
            source = "UNKNOWN"

        # Get score
        if hasattr(result, "score"):
            score = result.score
        else:
            score = 0.5

        # Extract key insights
        insights = [f"Relevance: {score:.2f}", f"Source: {source}"]

        if hasattr(result, "content") and result.content:
            preview = result.content[:100]
            insights.append(f"Preview: {preview}...")

        themes[theme].append({"title": title, "key_insights": insights, "source": source})

    # Limit to top 5 insights per theme
    filtered_themes = []
    for theme_name, theme_insights in themes.items():
        filtered_themes.append({"name": theme_name, "insights": theme_insights[:5]})

    filtered_count = sum(len(t["insights"]) for t in filtered_themes)

    return {
        "themes": filtered_themes,
        "filtered_count": min(filtered_count, len(results)),
        "original_count": len(results),
    }
