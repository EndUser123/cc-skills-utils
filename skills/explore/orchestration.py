#!/usr/bin/env python3
"""Orchestration layer for three-layer search filtering - extracted from inline-execution-code.md.

This module provides the execute_unified_search function that orchestrates:
- Layer 1: Adaptive rule-based filtering (fetch with quality floor)
- Layer 2: Context-aware semantic filtering (Agent tool or keyword fallback)
- Layer 3: Template-based presentation formatting

Can be imported by both pytest tests and skill execution markdown.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

# Add paths for imports
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

skills_path = Path(__file__).parent
sys.path.insert(0, str(skills_path))

# Import Layer 1 enhancements (absolute imports for package context)
import skills.explore.adaptive_limits as adaptive_limits
import skills.explore.query_complexity as query_complexity
import skills.explore.semantic_cluster as semantic_cluster

# Import search executor
import skills.explore.search_executor as search_executor

# Import Layer 2 filtering
import skills.explore.agent_filter as agent_filter
import skills.explore.layer2_filter as layer2_filter



def format_themed_results(filtered_data: dict[str, Any], query: str) -> str:
    """Format Layer 2 filtered results with themes."""
    output = [f"=== Universal Search Results: \"{query}\" ==="]
    output.append(f"Layer 2 Applied: Context-aware filtering ({filtered_data.get('original_count', 0)} results → {filtered_data.get('filtered_count', 0)} key insights)\n")

    for theme in filtered_data.get("themes", []):
        theme_name = theme.get("name", "Unknown Theme")
        insights = theme.get("insights", [])

        output.append(f"### Theme: {theme_name} ({len(insights)} insights)")

        for insight in insights:
            title = insight.get("title", "Untitled")
            key_insights = insight.get("key_insights", [])
            source = insight.get("source", "UNKNOWN")
            score = insight.get("score", 0.0)

            output.append(f"\n[{score:.2f}] {source}: {title}")
            output.append("    Key Insights:")
            for ki in key_insights:
                output.append(f"    • {ki}")

    return "\n".join(output)


def format_standard_results(results: list[Any], query: str, limit: int = 30) -> str:
    """Format results without Layer 2 filtering."""
    output = [f"=== Universal Search Results: \"{query}\" ===\n"]

    if not results:
        output.append("No results found.")
        return "\n".join(output)

    for i, result in enumerate(results[:limit], 0):  # User's limit cap
        score = getattr(result, 'score', 0.0)
        title = getattr(result, 'title', 'Untitled')
        source = getattr(result, 'source', 'UNKNOWN')
        url = getattr(result, 'url', '')
        content = getattr(result, 'content', '')[:200]

        output.append(f"[{score:.2f}] {source}: {title}")
        if url:
            output.append(f"    URL: {url}")
        output.append(f"    Preview: {content}...")
        output.append("")

    return "\n".join(output)


async def execute_unified_search(query: str, **kwargs) -> str:
    """
    Execute unified search with three-layer filtering.

    Args:
        query: Search query
        **kwargs: Additional options (mode, limit, context_threshold, etc.)

    Returns:
        Formatted search results
    """
    # Parse options
    mode = kwargs.get("mode", "auto")
    limit = kwargs.get("limit", 30)
    rrf_k = kwargs.get("rrf_k", 60)
    min_score = kwargs.get("min_score", 0.5)
    min_results = kwargs.get("min_results", 3)
    context_threshold = kwargs.get("context_threshold", 20)
    force_context_filter = kwargs.get("force_context_filter", False)
    no_context_filter = kwargs.get("no_context_filter", False)
    enable_jmri = kwargs.get("enable_jmri", True)

    # Layer 1A: Execute search with rule-based filtering
    print(f"[Layer 1A] Searching for '{query}' (mode: {mode}, limit: {limit})")

    # Get adaptive limit based on query complexity
    complexity_score = query_complexity.calculate_complexity_score(query)
    adaptive_config = adaptive_limits.get_adaptive_config(
        complexity_score=complexity_score,
        result_count=limit
    )
    actual_limit = adaptive_config["limit"]

    print(f"[Layer 1C] Query complexity: {complexity_score}/100 ({query_complexity.get_complexity_label(complexity_score)})")
    print(f"[Layer 1D] Adaptive limit: {actual_limit} (base: {limit})")

    # Execute search - execute_search creates its own QualityConfig from min_score
    results = await search_executor.execute_search(
        query=query,
        mode=mode,
        limit=actual_limit,
        rrf_k=rrf_k,
        min_score=min_score,
        min_results=min_results,
        enable_jmri=enable_jmri,
    )

    print(f"[Layer 1A] → {len(results)} results")

    if not results:
        return f"=== No Results Found ===\nQuery: {query}"

    # Layer 1B: Apply semantic clustering
    clustered = semantic_cluster.apply_semantic_clustering(
        results,
        similarity_threshold=0.4,
        max_results=25
    )

    print(f"[Layer 1B] Semantic clustering: {len(results)} → {len(clustered)} results")

    # Layer 2: Check if context-aware filtering should trigger
    should_filter, trigger_reason = layer2_filter.should_apply_context_filter(
        clustered, query, threshold=context_threshold
    )

    # Override checks
    if force_context_filter:
        should_filter = True
        trigger_reason = "force_override"
    elif no_context_filter:
        should_filter = False
        trigger_reason = "user_disabled"

    print(f"[Layer 2] Trigger check: {should_filter} (reason: {trigger_reason})")

    # Apply Layer 2 filtering if triggered
    if should_filter:
        print("[Layer 2] Applying Agent tool semantic filtering...")
        # trigger_reason is str | None from should_apply_context_filter, but when
        # should_filter is True it must be set (force_override/user_disabled or actual reason)
        _trigger_reason: str = trigger_reason if trigger_reason else "auto"
        filtered = await agent_filter.apply_agent_filtering(
            query=query,
            results=clustered,
            trigger_reason=_trigger_reason,
            complexity_score=complexity_score
        )

        # Format themed results
        return format_themed_results(filtered, query)
    else:
        # No Layer 2, use standard format
        print("[Layer 2] Skipped (using Layer 1 output)")
        return format_standard_results(clustered, query, limit=limit)


# Main execution entry point
def main(query: str, **kwargs) -> str:
    """
Main entry point for /explore skill execution.

This function is called by Claude Code when the /explore skill is invoked.
    It executes inline (NOT as subprocess), enabling Agent tool access.
    """
    # Run async search
    result = asyncio.run(execute_unified_search(query, **kwargs))
    return result
