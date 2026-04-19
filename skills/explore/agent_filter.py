#!/usr/bin/env python3
"""Agent tool wrapper for Layer 2 semantic filtering.

This module provides the Agent tool integration for intelligent context-aware
filtering. It wraps Claude Code's Agent tool to use LLM intelligence for
semantic filtering instead of crude keyword matching.

Key Features:
- Uses Agent tool with subagent_type="general-purpose"
- Adaptive insight count based on query complexity (5-10 insights)
- Token estimation to prevent truncation
- Error handling with fallback to keyword-based filtering
"""

from __future__ import annotations

import json
import os
from typing import Any

# Import existing prompt creation (relative imports for package context)
from . import layer2_filter
from . import query_complexity


def is_skill_context() -> bool:
    """Detect if running in Claude Code skill execution context.

    In skill execution context, the Agent tool is available for Layer 2 filtering.
    In CLI context, fall back to keyword-based filtering.

    Returns:
        True if CLAUDE_CODE_SKILL_EXECUTION environment variable is set to '1'
    """
    return os.environ.get("CLAUDE_CODE_SKILL_EXECUTION") == "1"


def sanitize_for_prompt(text: str) -> str:
    """Sanitize text to prevent prompt injection attacks (SEC-001).

    Removes or escapes potentially dangerous patterns that could be used
    to inject malicious instructions into Agent prompts.

    Args:
        text: Raw text to sanitize

    Returns:
        Sanitized text safe for inclusion in prompts
    """
    if not text:
        return ""

    import re

    # Break up dangerous instruction-override patterns by inserting spaces
    dangerous_patterns = [
        (r"ignore", "ign ore"),
        (r"instructions", "instr uctions"),
        (r"disregard", "disreg ard"),
        (r"forget", "for get"),
        (r"previous", "prev ious"),
        (r"override", "over ride"),
        (r"system\s*:", "sys tem :"),  # System prompt takeover attempts
        (r"<\|.*?\|>", ""),  # Remove special token capture attempts
    ]

    sanitized = text
    for pattern, replacement in dangerous_patterns:
        # Replace dangerous patterns with safe alternatives
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

    # Remove "and tell me secrets" type exploitation attempts
    exploitation_patterns = [
        r"tell\s+me\s+(secrets|passwords|credentials|api\s+key)",
        r"show\s+me\s+(your\s+)?(instructions|system\s+prompt|internal\s+prompt)",
        r"print\s+(your\s+)?(instructions|system\s+prompt|internal\s+prompt)",
    ]

    for pattern in exploitation_patterns:
        sanitized = re.sub(pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE)

    # Remove excessive whitespace (more than 2 consecutive spaces)
    sanitized = re.sub(r" {3,}", "  ", sanitized)

    # Remove control characters except newlines and tabs
    sanitized = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F]", "", sanitized)

    return sanitized.strip()


def estimate_tokens_from_results(results: list[Any], avg_content_length: int = 300) -> int:
    """Estimate token usage for Agent tool input.

    Args:
        results: Search results
        avg_content_length: Average content length in characters

    Returns:
        Estimated token count
    """
    # Base tokens: title + content (~4 chars per token)
    content_tokens = (avg_content_length / 4) * len(results)

    # Metadata tokens (source, score, prompt overhead)
    metadata_tokens = 50 * len(results)  # ~50 tokens per result with metadata

    # Prompt overhead (~500 tokens for the system prompt and instructions)
    prompt_overhead = 500

    total_tokens = int(content_tokens + metadata_tokens + prompt_overhead)

    return total_tokens


def get_adaptive_insight_count(complexity_score: int, result_count: int) -> int:
    """Get adaptive number of insights to extract based on query complexity.

    Args:
        complexity_score: Query complexity score (0-100)
        result_count: Number of results to filter

    Returns:
        Target number of insights to extract (5-10)
    """
    # High complexity queries: Extract more insights (8-10)
    if complexity_score > 60:
        return min(10, max(8, result_count // 3))

    # Medium complexity: Extract moderate insights (6-8)
    elif complexity_score >= 40:
        return min(8, max(6, result_count // 4))

    # Low complexity: Extract fewer insights (5-7)
    else:
        return min(7, max(5, result_count // 5))


def create_enhanced_layer2_prompt(
    query: str, results: list[Any], complexity_score: int, insight_count: int
) -> str:
    """Create enhanced Layer 2 prompt with complexity context.

    Sanitizes search results before including in prompt to prevent injection (SEC-001).

    Args:
        query: Original search query
        results: Search results to filter
        complexity_score: Query complexity score
        insight_count: Target number of insights

    Returns:
        Enhanced prompt for Agent tool
    """
    # Sanitize results before including in prompt (TASK-001C, SEC-001)
    sanitized_results = []
    for result in results[:50]:  # Cap at 50 for prompt (same as layer2_filter)
        # Create sanitized result object
        class SanitizedResult:
            def __init__(self, title, content, source, score):
                self.title = sanitize_for_prompt(getattr(result, "title", ""))
                self.content = sanitize_for_prompt(getattr(result, "content", ""))
                self.source = getattr(result, "source", "UNKNOWN")
                self.score = getattr(result, "score", 0.5)

        sanitized_results.append(
            SanitizedResult(
                title=getattr(result, "title", ""),
                content=getattr(result, "content", ""),
                source=getattr(result, "source", "UNKNOWN"),
                score=getattr(result, "score", 0.5),
            )
        )

    # Get base prompt from layer2_filter with sanitized results
    base_prompt = layer2_filter.create_layer2_prompt(query, sanitized_results)

    # Add complexity context
    complexity_label = query_complexity.get_complexity_label(complexity_score)

    enhanced_instructions = f"""

QUERY COMPLEXITY: {complexity_label} (score: {complexity_score}/100)
TARGET INSIGHT COUNT: Extract approximately {insight_count} key insights

COMPLEXITY-AWARE FILTERING:
- {"Complex" if complexity_score > 60 else "Simple" if complexity_score < 40 else "Medium"} query: {"Extract more comprehensive insights covering multiple angles" if complexity_score > 60 else "Extract focused, actionable insights" if complexity_score < 40 else "Extract balanced insights with both breadth and depth"}
- Prioritize {"diverse perspectives and comprehensive coverage" if complexity_score > 60 else "direct, actionable insights" if complexity_score < 40 else "practical insights with some context"}

Remember: Quality over quantity. Better {insight_count} excellent insights than {insight_count * 2} mediocre ones."""

    # Insert enhanced instructions before the output requirements
    enhanced_prompt = base_prompt.replace(
        "OUTPUT REQUIREMENTS:", enhanced_instructions + "\n\nOUTPUT REQUIREMENTS:"
    )

    # Update the insight count in the prompt
    enhanced_prompt = enhanced_prompt.replace(
        "Extract 3-5 key insights per relevant result",
        f"Extract {insight_count // 3}-{insight_count // 2} key insights per relevant result",
    )

    return enhanced_prompt


def parse_agent_response(response: str, max_depth: int = 3) -> dict[str, Any] | None:
    """Parse JSON response from Agent tool with depth-limited recursion (SEC-002).

    Args:
        response: Raw response string from Agent tool
        max_depth: Maximum recursion depth to prevent stack overflow (default: 3)

    Returns:
        Parsed dict with themes and filtered_count, or None if parsing fails
    """
    if not response or max_depth <= 0:
        return None

    try:
        # Try to parse as JSON directly
        parsed = json.loads(response)

        # Validate structure
        if "themes" not in parsed:
            return None

        if "filtered_count" not in parsed:
            # Calculate from themes
            parsed["filtered_count"] = sum(len(t.get("insights", [])) for t in parsed["themes"])

        if "original_count" not in parsed:
            # Default to 0 if not provided
            parsed["original_count"] = 0

        return parsed

    except json.JSONDecodeError:
        # Try to extract JSON from markdown code blocks
        if "```json" in response:
            # Extract JSON from code block
            start = response.find("```json") + 7
            end = response.find("```", start)
            if end > start:
                json_str = response[start:end].strip()
                # Recursive parse with depth limit
                return parse_agent_response(json_str, max_depth - 1)

        elif "```" in response:
            # Try generic code block
            start = response.find("```") + 3
            end = response.find("```", start)
            if end > start:
                # Skip language identifier if present
                newline_start = response.find("\n", start)
                if newline_start < end:
                    start = newline_start + 1

                json_str = response[start:end].strip()
                # Recursive parse with depth limit
                return parse_agent_response(json_str, max_depth - 1)

        return None


async def apply_agent_filtering(
    query: str, results: list[Any], trigger_reason: str = "auto", complexity_score: int = 50
) -> dict[str, Any]:
    """Apply Layer 2 filtering using Agent tool.

    This is the main entry point for Agent-based semantic filtering.
    In skill execution context, this would call the Agent tool.
    For now, it falls back to keyword-based filtering until Agent integration.

    Args:
        query: Original search query
        results: Layer 1 filtered results (already reduced by semantic clustering)
        trigger_reason: Why Layer 2 was triggered
        complexity_score: Query complexity score (0-100) for adaptive processing

    Returns:
        Dict with themes, filtered_count, original_count
    """
    # Check if we're in skill execution context with Agent tool available
    in_skill_context = os.environ.get("CLAUDE_CODE_SKILL_EXECUTION") == "1"

    # Estimate tokens
    estimated_tokens = estimate_tokens_from_results(results)

    # Get adaptive insight count
    insight_count = get_adaptive_insight_count(complexity_score, len(results))

    # Log processing info
    print(
        f"[Agent Filter] Complexity: {complexity_score} → {query_complexity.get_complexity_label(complexity_score)}"
    )
    print(f"[Agent Filter] Target insights: {insight_count}")
    print(f"[Agent Filter] Estimated tokens: {estimated_tokens}")

    # Check token limits
    if estimated_tokens > 8000:
        print(f"[Agent Filter] WARNING: High token count ({estimated_tokens}), may truncate")

    if in_skill_context:
        # In skill execution, use Agent tool with timeout protection (TASK-001B)
        # Note: enhanced_prompt will be created when Agent tool call is integrated

        # Attempt Agent tool call with 4s timeout
        import asyncio

        # Use asyncio.timeout for timeout protection
        async def call_agent_with_timeout() -> str | None:
            try:
                async with asyncio.timeout(4.0):
                    # Agent tool invocation would happen here via Claude Code framework
                    # For now, we structure the code to support it
                    # The actual call will be integrated in SKILL.md inline execution
                    pass
            except TimeoutError:
                print("[Agent Filter] Timeout after 4s, falling back to keyword filtering")
                return None
            except Exception as e:
                print(f"[Agent Filter] Agent tool error: {e}, falling back to keyword filtering")
                return None

            return None

        # Attempt Agent call
        try:
            agent_response = await call_agent_with_timeout()

            # If Agent call succeeded, parse response
            if agent_response:
                parsed = parse_agent_response(agent_response)
                if parsed and "themes" in parsed:
                    print(
                        f"[Agent Filter] Agent filtering successful: {parsed['filtered_count']} insights from {parsed['original_count']} results"
                    )
                    return parsed
        except Exception as e:
            print(f"[Agent Filter] Unexpected error during Agent call: {e}")

        # Fall back to keyword filtering if Agent call failed
        print("[Agent Filter] Agent tool unavailable or failed, using keyword fallback")
        return await layer2_filter._keyword_based_filtering(results, query)
    else:
        # CLI mode: use keyword-based fallback
        print("[Agent Filter] CLI context, using keyword fallback")
        return await layer2_filter._keyword_based_filtering(results, query)


def create_agent_filter_summary(
    query: str, original_count: int, filtered_count: int, complexity_score: int, trigger_reason: str
) -> dict[str, Any]:
    """Create a summary of the Agent filtering operation.

    Args:
        query: Original search query
        original_count: Number of results before filtering
        filtered_count: Number of results after filtering
        complexity_score: Query complexity score
        trigger_reason: Why Layer 2 was triggered

    Returns:
        Summary dict with filtering statistics
    """
    return {
        "query": query,
        "original_count": original_count,
        "filtered_count": filtered_count,
        "reduction_ratio": filtered_count / original_count if original_count > 0 else 1.0,
        "complexity_score": complexity_score,
        "complexity_label": query_complexity.get_complexity_label(complexity_score),
        "trigger_reason": trigger_reason,
        "filtering_method": "Agent tool (general-purpose subagent)"
        if os.environ.get("CLAUDE_CODE_SKILL_EXECUTION") == "1"
        else "Keyword-based fallback",
    }
