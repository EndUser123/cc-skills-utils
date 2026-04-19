#!/usr/bin/env python3
"""Search executor module - Extracted search logic for inline skill execution.

This module provides reusable functions for executing universal search
with three-layer filtering. Can be imported in skill context for inline execution.

Functions:
    execute_search: Execute search with Layer 1 filtering
    apply_layer1_rule_based_filtering: Apply Python rule-based filtering
    format_results_human: Format results for human display
    format_results_json: Format results as JSON
"""

from __future__ import annotations

import json

# Import search backend
import sys
from pathlib import Path
from typing import Any

# Add search-research package to path (use absolute path to avoid conflicts)
search_research_path = Path("P:/packages/search-research").resolve()
if str(search_research_path) not in sys.path:
    sys.path.insert(0, str(search_research_path))

from core.quality_checker import QualityConfig
from search_research import UnifiedAsyncRouter


async def execute_search(
    query: str,
    mode: str = "auto",
    limit: int = 10,
    rrf_k: int = 60,
    min_score: float = 0.5,
    min_results: int = 3,
    enable_jmri: bool = True,
) -> list:
    """Execute universal search with Layer 1 filtering.

    Args:
        query: Search query
        mode: Search mode (auto, unified, local-only, web-fallback)
        limit: Maximum results from Layer 1
        rrf_k: RRF constant for result fusion
        min_score: Minimum relevance score for quality floor
        min_results: Minimum result count for quality check
        enable_jmri: Enable jMRI token-efficient retrieval

    Returns:
        List of search results (Layer 1 filtered)
    """
    # Configure quality thresholds
    # Map parameters to QualityConfig schema
    quality_config = QualityConfig(
        confidence_threshold=min_score,
    )

    # Initialize unified router
    router = UnifiedAsyncRouter(
        mode=mode, enable_jmri=enable_jmri, rrf_k=rrf_k, quality_config=quality_config
    )

    # Execute search - Layer 1 filtering happens inside UnifiedAsyncRouter
    # Error handling: wrap in try/except with fallback logic (TASK-002)
    try:
        results = await router.search_async(query, limit=limit)
    except ConnectionError as e:
        # Web search backend failed - log and return empty list
        print(f"[Search Executor] ConnectionError: {e}")
        results = []
    except TimeoutError as e:
        # Backend timeout - log and return empty list
        print(f"[Search Executor] TimeoutError: {e}")
        results = []
    except Exception as e:
        # Unexpected error - log full traceback and return empty list
        print(f"[Search Executor] Unexpected error: {type(e).__name__}: {e}")
        results = []

    # Enforce hard cap of 50 results (Layer 1A)
    # NOTE: Limit enforcement is done at Layer 3 (formatter), not here.
    # Layer 1 fetches an adaptive amount (via actual_limit) to feed Layer 2 effectively.
    if len(results) > 50:
        results = results[:50]

    return results


def apply_layer1_rule_based_filtering(results: list) -> list:
    """Apply Layer 1 Python rule-based filtering.

    NOTE: This function is provided for API completeness.
    In practice, Layer 1 filtering (deduplication, quality floor, hard cap)
    is already applied inside UnifiedAsyncRouter.search_async().

    This function can be used for validation or additional filtering.

    Layer 1 includes:
    - Deduplication: Remove exact and near-duplicate results
    - Quality floor: Filter results with score < min_score
    - Hard cap: Enforce maximum of 50 results

    Args:
        results: List of search results

    Returns:
        Filtered list (same as input if already filtered by UnifiedAsyncRouter)
    """
    # Layer 1 filtering is already applied by UnifiedAsyncRouter
    # This function exists for API completeness and potential extensions
    return results


def format_results_human(
    query: str, results: list, mode: str, layer2_applied: bool = False, filtered_results: Any = None
) -> str:
    """Format results in human-readable format with three-layer output.

    Args:
        query: Original search query
        results: Search results from UnifiedAsyncRouter
        mode: Search mode used
        layer2_applied: Whether Layer 2 filtering was applied
        filtered_results: Filtered results from Layer 2 (if applied)

    Returns:
        Formatted string for display
    """
    output = []

    if layer2_applied and filtered_results and "themes" in filtered_results:
        # Themed format (Layer 2 applied)
        output.append(f'=== Universal Search Results: "{query}" ===')
        output.append(f"Mode: {mode}")
        output.append(
            f"Layer 2 Applied: Context-aware filtering ({filtered_results['original_count']} results → {filtered_results['filtered_count']} key insights)\n"
        )

        for theme in filtered_results["themes"]:
            output.append(f"### Theme: {theme['name']} ({len(theme['insights'])} insights)\n")

            for insight in theme["insights"][:3]:  # Show max 3 per theme
                source = insight.get("source", "WEB")
                indicator = (
                    "📚"
                    if source in ["CKS", "Code", "DOCS", "CDS", "GREP", "SKILLS"]
                    else "💬"
                    if source == "CHS"
                    else "🌐"
                )

                output.append(f"{indicator} {insight['title']}")

                if "key_insights" in insight:
                    output.append("    Key Insights:")
                    for insight_text in insight["key_insights"]:
                        output.append(f"    • {insight_text}")

                output.append("")
    else:
        # Standard format (Layer 1 only or Layer 2 skipped)
        output.append(f'=== Universal Search Results: "{query}" ===')
        output.append(f"Mode: {mode}")
        output.append(f"Results: {len(results)}")
        output.append("")

        if not results:
            output.append("No results found.")
            return "\n".join(output)

        for i, result in enumerate(results, 1):
            # Determine source indicator
            source = result.source if hasattr(result, "source") else "unknown"
            if source in ["CHS", "CKS", "Code", "DOCS", "SKILLS", "CDS", "GREP"]:
                indicator = "📚" if source != "CHS" else "💬"
            else:
                indicator = "🌐"

            # Relevance score
            score = result.score if hasattr(result, "score") else 0.0

            # Title and content
            title = result.title if hasattr(result, "title") else "Untitled"
            content = result.content if hasattr(result, "content") else ""

            output.append(f"[{score:.2f}] {indicator}: {title}")

            # Add content preview
            if content:
                preview = content[:200] + "..." if len(content) > 200 else content
                output.append(f"    Content: {preview}")

            output.append("")

    return "\n".join(output)


def format_results_json(query: str, results: list, mode: str) -> str:
    """Format results as JSON.

    Args:
        query: Original search query
        results: Search results
        mode: Search mode used

    Returns:
        JSON string
    """
    results_dict = {"query": query, "mode": mode, "count": len(results), "results": []}

    for result in results:
        result_dict = {
            "title": result.title if hasattr(result, "title") else "Untitled",
            "content": result.content if hasattr(result, "content") else "",
            "score": result.score if hasattr(result, "score") else 0.0,
            "source": result.source if hasattr(result, "source") else "unknown",
        }

        if hasattr(result, "url") and result.url:
            result_dict["url"] = result.url

        if hasattr(result, "metadata") and result.metadata:
            result_dict["metadata"] = result.metadata

        results_dict["results"].append(result_dict)

    return json.dumps(results_dict, indent=2)
