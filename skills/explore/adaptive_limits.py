#!/usr/bin/env python3
"""Adaptive result limits for token-aware processing.

This module provides adaptive result limits based on query complexity
to optimize token usage for Layer 2 Agent tool filtering.

Adaptive Limits:
- Simple queries (complexity <40): 20 items (faster, less filtering needed)
- Medium queries (complexity 40-60): 30 items (balanced)
- Complex queries (complexity >60): 40 items (more context for semantic filtering)

Token Estimation:
- Estimates token usage before Layer 2 to prevent truncation
- Alerts if approaching token limits (>8k tokens)
"""

from __future__ import annotations

from typing import Any

# Average token counts per result item (empirical estimates)
TOKENS_PER_RESULT = 150  # Average tokens per search result
TOKENS_PER_METADATA = 30  # Average tokens for metadata (source, score, etc.)
LAYER2_SAFE_TOKEN_LIMIT = 8000  # Safe token limit for Layer 2 Agent tool
LAYER2_WARNING_THRESHOLD = 7000  # Warning threshold


def get_adaptive_limit(complexity_score: int) -> int:
    """Get adaptive Layer 1 result limit based on query complexity.

    Args:
        complexity_score: Query complexity score (0-100)

    Returns:
        Recommended result limit for Layer 1 search
        - Simple (<40): 20 items
        - Medium (40-60): 30 items
        - Complex (>60): 40 items
    """
    if complexity_score > 60:
        # Complex queries: more results needed for comprehensive filtering
        return 40
    elif complexity_score >= 40:
        # Medium complexity: balanced result count
        return 30
    else:
        # Simple queries: fewer results sufficient
        return 20


def estimate_tokens(
    result_count: int,
    avg_content_length: int = 300,
    has_metadata: bool = True
) -> int:
    """Estimate token usage for a set of results.

    Args:
        result_count: Number of search results
        avg_content_length: Average character length of result content
        has_metadata: Whether results include metadata (source, score, etc.)

    Returns:
        Estimated token count
    """
    # Base tokens: title + content
    # Approximate 4 characters per token
    content_tokens = (avg_content_length / 4) * result_count

    # Metadata tokens (source, score, URL, etc.)
    metadata_tokens = TOKENS_PER_METADATA * result_count if has_metadata else 0

    # Total estimation
    total_tokens = int(content_tokens + metadata_tokens)

    return total_tokens


def check_token_limit(
    result_count: int,
    avg_content_length: int = 300,
    limit: int = LAYER2_SAFE_TOKEN_LIMIT
) -> dict[str, Any]:
    """Check if estimated token usage is within safe limits.

    Args:
        result_count: Number of search results
        avg_content_length: Average character length of result content
        limit: Token limit to check against

    Returns:
        Dict with:
            - within_limit (bool): True if tokens < limit
            - estimated_tokens (int): Estimated token count
            - warning (str|None): Warning message if approaching limit
    """
    estimated_tokens = estimate_tokens(result_count, avg_content_length)

    within_limit = estimated_tokens < limit
    warning = None

    # Warning if approaching limit (within 1000 tokens)
    if estimated_tokens > limit - 1000:
        warning = f"Approaching token limit: {estimated_tokens} / {limit} tokens"

    # Critical warning if over limit
    if estimated_tokens > limit:
        warning = f"Over token limit: {estimated_tokens} / {limit} tokens - may truncate"

    return {
        "within_limit": within_limit,
        "estimated_tokens": estimated_tokens,
        "warning": warning,
    }


def get_adaptive_config(
    complexity_score: int,
    result_count: int,
    avg_content_length: int = 300
) -> dict[str, Any]:
    """Get complete adaptive configuration for Layer 1 → Layer 2 pipeline.

    Args:
        complexity_score: Query complexity score (0-100)
        result_count: Actual number of results from Layer 1
        avg_content_length: Average character length of result content

    Returns:
        Dict with adaptive configuration:
            - complexity_score (int): Input complexity score
            - complexity_label (str): "Simple", "Medium", or "Complex"
            - adaptive_limit (int): Recommended Layer 1 limit
            - result_count (int): Actual result count
            - estimated_tokens (int): Estimated token usage
            - within_limit (bool): Whether within safe token limits
            - warning (str|None): Warning if approaching/exceeding limits
            - should_reduce (bool): Whether to reduce results before Layer 2
            - reduction_target (int|None): Target count if reduction needed
    """
    from query_complexity import get_complexity_label

    # Get adaptive limit
    adaptive_limit = get_adaptive_limit(complexity_score)

    # Check token limits
    token_check = check_token_limit(result_count, avg_content_length)

    # Determine if reduction is needed
    should_reduce = not token_check["within_limit"]
    reduction_target = None

    if should_reduce:
        # Calculate safe target count
        safe_tokens = LAYER2_WARNING_THRESHOLD
        reduction_target = int(safe_tokens / (TOKENS_PER_RESULT + TOKENS_PER_METADATA))
        reduction_target = max(10, reduction_target)  # Minimum 10 results

    return {
        "complexity_score": complexity_score,
        "complexity_label": get_complexity_label(complexity_score),
        "adaptive_limit": adaptive_limit,
        "result_count": result_count,
        "estimated_tokens": token_check["estimated_tokens"],
        "within_limit": token_check["within_limit"],
        "warning": token_check["warning"],
        "should_reduce": should_reduce,
        "reduction_target": reduction_target,
    }


def recommend_layer2_limit(
    complexity_score: int,
    result_count: int,
    avg_content_length: int = 300
) -> int:
    """Recommend maximum results to pass to Layer 2 Agent tool.

    Args:
        complexity_score: Query complexity score (0-100)
        result_count: Actual number of results from Layer 1
        avg_content_length: Average character length of result content

    Returns:
        Recommended maximum results for Layer 2
    """
    # Get adaptive config
    config = get_adaptive_config(complexity_score, result_count, avg_content_length)

    # If reduction needed, use reduction target
    if config["should_reduce"]:
        return config["reduction_target"]

    # Otherwise, use adaptive limit (capped at actual count)
    return min(config["adaptive_limit"], result_count)
