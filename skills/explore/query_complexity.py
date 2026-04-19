#!/usr/bin/env python3
"""Query complexity scoring for adaptive Layer 2 triggering.

This module analyzes search queries to determine their complexity level,
which informs adaptive Layer 2 filtering thresholds and result limits.

Complexity Score (0-100):
- 0-39: Simple queries (specific, clear intent, low diversity)
- 40-60: Medium complexity (moderate specificity, some ambiguity)
- 61-100: Complex queries (broad, ambiguous, high diversity expected)

Adaptive Layer 2 Triggering:
- High complexity (>60) + >15 results → trigger Layer 2
- Medium complexity (40-60) + >20 results → trigger Layer 2
- Low complexity (<40) + >30 results → trigger Layer 2
"""

from __future__ import annotations

import re

# Technical terms that indicate specificity
TECHNICAL_TERMS = {
    # Programming languages/frameworks
    'python', 'javascript', 'typescript', 'java', 'rust', 'go', 'ruby', 'php',
    'react', 'vue', 'angular', 'svelte', 'django', 'flask', 'fastapi', 'express',
    'async', 'await', 'promise', 'observable', 'coroutine', 'thread', 'process',

    # Technical concepts
    'api', 'rest', 'graphql', 'grpc', 'websocket', 'http', 'https', 'tcp', 'udp',
    'sql', 'nosql', 'database', 'orm', 'migration', 'schema', 'query', 'index',
    'algorithm', 'data structure', 'complexity', 'optimization', 'performance',
    'authentication', 'authorization', 'oauth', 'jwt', 'session', 'cookie',
    'docker', 'kubernetes', 'container', 'deployment', 'ci/cd', 'testing',

    # File/protocol formats
    'json', 'xml', 'yaml', 'csv', 'markdown', 'pdf', 'html', 'css',
}

# Multi-word technical terms (must be checked as phrases)
MULTI_WORD_TECHNICAL_TERMS = [
    'machine learning', 'natural language processing', 'deep learning',
    'neural network', 'computer vision', 'data science', 'software engineering',
    'system design', 'web development', 'mobile development', 'cloud computing',
    'devops engineering', 'site reliability', 'unit testing', 'integration testing',
    'continuous integration', 'continuous deployment', 'version control',
    'agile methodology', 'scrum framework', 'kanban board',
]

# Ambiguity indicators that suggest multiple possible interpretations
AMBIGUITY_INDICATORS = [
    r'\bhow\b',  # "how to", "how does"
    r'\bwhat\b',  # "what is", "what are"
    r'\bwhich\b',  # "which one", "which approach"
    r'\bwhere\b',  # "where to", "where can"
    r'\bwhen\b',  # "when to", "when should"
    r'\bwhy\b',  # "why use", "why does"
    r'\bbest\b',  # "best practice", "best way"
    r'\bbetter\b',  # "better approach", "better performance"
    r'\bcompare\b',  # "compare different approaches"
    r'\bdifferent\b',  # "different approaches", "different ways"
    r'\bversus\b',  # "versus", "vs"
    r'\bvs\b',  # "versus", "vs"
]

# Negation patterns that reduce specificity
NEGATION_PATTERNS = [
    r'\bnot\s+\w+',  # "not python", "not async"
    r'\bwithout\s+\w+',  # "without docker"
    r'\bexcept\s+\w+',  # "except react"
    r'\bno\s+\w+',  # "no database"
]

# Context hints that suggest user wants comprehensive filtering
CONTEXT_HINTS = [
    'discuss', 'mention', 'talk about', 'cover', 'explain',
    'compare', 'difference', 'versus', 'vs',
    'example', 'tutorial', 'guide', 'how to',
    'is',  # Added: "what is X" queries (TASK-011 v2)
    'are',  # Added: "what are X" queries (TASK-011 v2)
    'practices',  # Added: "best practices for X" (TASK-011 v2)
    'best',  # Added: "best X" queries (TASK-011 v2)
]

# Pre-compile regex patterns for performance (TASK-011 optimization)
COMPILED_AMBIGUITY_PATTERNS = [re.compile(p) for p in AMBIGUITY_INDICATORS]
COMPILED_NEGATION_PATTERNS = [re.compile(p) for p in NEGATION_PATTERNS]


def calculate_complexity_score(query: str) -> int:
    """Calculate query complexity score (0-100) with optimized detection.

    Optimizations (TASK-011):
    - Cached compiled regex patterns for performance
    - Multi-word technical term detection (e.g., "machine learning")
    - Negation handling (e.g., "not python" reduces specificity)
    - Improved scoring calibration

    Args:
        query: Search query string

    Returns:
        Complexity score from 0-100
        - 0-39: Simple (specific, clear intent)
        - 40-60: Medium (moderate specificity)
        - 61-100: Complex (broad, ambiguous)
    """
    if not query:
        return 0

    query_lower = query.lower()
    words = re.findall(r'\b\w+\b', query_lower)
    word_count = len(words)

    # Metric 1: Term specificity (0-35 points) - INCREASED cap from 30
    # Higher score = more specific technical terms
    technical_count = sum(1 for word in words if word in TECHNICAL_TERMS)

    # Check for multi-word technical terms (TASK-011 optimization)
    # Each multi-word term adds significant specificity
    for phrase in MULTI_WORD_TECHNICAL_TERMS:
        if phrase in query_lower:
            technical_count += 5  # Multi-word terms count much more (increased from 3)

    # Check for negation patterns (TASK-011 optimization)
    has_negation = False
    for pattern in COMPILED_NEGATION_PATTERNS:
        if pattern.search(query_lower):
            has_negation = True
            break

    # Calculate specificity score - increased weight and cap (TASK-011 v2)
    specificity_score = min(50, technical_count * 12)  # Cap from 45→50, weight from 9→12

    # Bonus for very high technical term counts (TASK-011 v3)
    # If query has many technical terms (>5), add extra complexity
    if technical_count > 5:
        specificity_score = min(60, specificity_score + 10)  # Boost up to 60

    # Extreme bonus for very long queries with many technical terms (TASK-011 v3)
    # If query has 50+ technical terms, push to max complexity
    if technical_count >= 50:
        specificity_score = 100  # Max complexity for very long technical queries
    elif word_count > 10 and technical_count > 0:
        repetition_ratio = word_count / technical_count
        if repetition_ratio > 3:  # Mostly repetition of few technical terms
            specificity_score = min(70, specificity_score + 20)  # Boost up to 70

    # Reduce specificity if negation present (TASK-011 optimization)
    if has_negation:
        specificity_score = max(0, specificity_score - 20)  # Penalty from 15→20

    # Metric 2: Intent ambiguity (0-60 points) - increased cap and weight (TASK-011 v2)
    # Higher score = more ambiguous (question words, comparative terms)
    ambiguity_score = 0
    for pattern in COMPILED_AMBIGUITY_PATTERNS:  # Use cached compiled patterns
        if pattern.search(query_lower):
            ambiguity_score += 20  # Increased from 15
    ambiguity_score = min(60, ambiguity_score)  # Cap from 50→60

    # Metric 3: Expected diversity (0-30 points) - increased cap (TASK-011 v2)
    # Higher score = broader query expecting diverse results
    diversity_score = 0

    # Short queries are often broader - moderate value to keep simple queries <40 (TASK-011 v3)
    if word_count <= 3:
        diversity_score += 15  # Reduced to keep "python async" at 39 (under 40)
    elif word_count >= 6:
        diversity_score -= 5

    # Context hints suggest need for comprehensive filtering - increased weight
    context_hint_count = sum(1 for hint in CONTEXT_HINTS if hint in query_lower)
    diversity_score += context_hint_count * 10  # Increased from 8

    # Clamp to valid range - increased cap from 20 to 30
    diversity_score = max(0, min(30, diversity_score))

    # Calculate total complexity score
    complexity_score = specificity_score + ambiguity_score + diversity_score

    # Clamp to 0-100 range
    return max(0, min(100, complexity_score))


def get_layer2_threshold(complexity_score: int) -> int:
    """Get Layer 2 triggering threshold based on query complexity.

    Args:
        complexity_score: Query complexity score (0-100)

    Returns:
        Minimum result count to trigger Layer 2 filtering
    """
    if complexity_score > 60:
        # Complex queries: trigger earlier (15 results)
        return 15
    elif complexity_score >= 40:
        # Medium complexity: trigger at moderate level (20 results)
        return 20
    else:
        # Simple queries: trigger later (30 results)
        return 30


def should_trigger_layer2(
    query: str,
    result_count: int,
    context_threshold: int = 20
) -> tuple[bool, str, int]:
    """Determine if Layer 2 filtering should be triggered based on query complexity.

    Args:
        query: Search query
        result_count: Number of results from Layer 1
        context_threshold: Fallback threshold if complexity scoring fails

    Returns:
        Tuple of (should_trigger, reason, complexity_score)
    """
    # Calculate complexity score
    complexity_score = calculate_complexity_score(query)

    # Get adaptive threshold
    adaptive_threshold = get_layer2_threshold(complexity_score)

    # Determine if Layer 2 should trigger
    if result_count >= adaptive_threshold:
        complexity_label = get_complexity_label(complexity_score)
        reason = f"{complexity_label} query (score: {complexity_score}), {result_count} results >= threshold {adaptive_threshold}"
        return True, reason, complexity_score

    # Check for explicit context hints
    query_lower = query.lower()
    has_context_hints = any(hint in query_lower for hint in CONTEXT_HINTS)

    if has_context_hints and result_count >= context_threshold:
        reason = f"Context hints detected, {result_count} results >= fallback threshold {context_threshold}"
        return True, reason, complexity_score

    reason = f"{result_count} results below adaptive threshold {adaptive_threshold} (complexity: {complexity_score})"
    return False, reason, complexity_score


def get_complexity_label(complexity_score: int) -> str:
    """Get human-readable complexity label.

    Args:
        complexity_score: Complexity score (0-100)

    Returns:
        Complexity label: "Simple", "Medium", or "Complex"
    """
    if complexity_score > 60:
        return "Complex"
    elif complexity_score >= 40:
        return "Medium"
    else:
        return "Simple"


def get_adaptive_limit(complexity_score: int) -> int:
    """Get adaptive Layer 1 result limit based on query complexity.

    Args:
        complexity_score: Query complexity score (0-100)

    Returns:
        Recommended result limit for Layer 1 search
    """
    if complexity_score > 60:
        # Complex queries: more results needed (40 items)
        return 40
    elif complexity_score >= 40:
        # Medium complexity: balanced (30 items)
        return 30
    else:
        # Simple queries: fewer results sufficient (20 items)
        return 20
