"""Persona Memory recall module for /s Strategy skill.

This module provides functionality to recall previous multi-persona brainstorm
sessions from Persona Memory storage.

Integration with /s skill:
- Recall previous brainstorm sessions on the same or similar topics
- Filter by persona type (INNOVATOR, pragmatist, critic, expert)
- Display historical insights alongside new analysis
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Try to import PersonaMemory (graceful degradation if unavailable)
try:
    from features.cognitive.persona_memory import PersonaMemory
    PERSONA_MEMORY_AVAILABLE = True
except ImportError:
    logger.warning("PersonaMemory module not available - recall functionality disabled")
    PERSONA_MEMORY_AVAILABLE = False
    PersonaMemory = None  # type: ignore


def recall_previous_sessions(
    query: str,
    persona_filter: str | None = None,
    limit: int = 5,
    min_impact: float | None = None,
) -> dict[str, Any]:
    """Recall previous brainstorm sessions from Persona Memory.

    Args:
        query: Search query for finding relevant sessions
        persona_filter: Optional persona type to filter by
            (INNOVATOR, pragmatist, critic, expert)
        limit: Maximum number of sessions to return (default: 5)
        min_impact: Optional minimum impact score threshold (0.0-1.0)

    Returns:
        Dictionary with:
            - sessions: List of brainstorm sessions from Persona Memory
            - count: Number of sessions found
            - filtered_persona: Persona type used for filtering (if any)
            - error: Error message if recall failed (None if successful)

    Example:
        >>> result = recall_previous_sessions("database design")
        >>> print(f"Found {result['count']} previous sessions")
        >>> for session in result['sessions']:
        ...     print(f"- {session['title']} (persona: {session['persona']})")
    """
    # Check if PersonaMemory is available
    if not PERSONA_MEMORY_AVAILABLE:
        return {
            "sessions": [],
            "count": 0,
            "filtered_persona": None,
            "error": "PersonaMemory module not available"
        }

    try:
        # Initialize PersonaMemory
        pm = PersonaMemory()

        # Build search parameters
        search_params = {
            "query": query,
            "limit": limit,
        }

        # Add persona filter if specified
        if persona_filter:
            search_params["persona"] = persona_filter.upper()

        # Add minimum impact filter if specified
        if min_impact is not None:
            search_params["min_impact"] = min_impact

        # Execute search
        results = pm.search(**search_params)

        # Format results
        sessions = []
        for result in results:
            sessions.append({
                "title": result.get("title", "Untitled Session"),
                "persona": result.get("persona", "UNKNOWN"),
                "content": result.get("content", ""),
                "impact": result.get("impact", 0.5),
                "timestamp": result.get("timestamp", ""),
                "source": "persona_memory"
            })

        return {
            "sessions": sessions,
            "count": len(sessions),
            "filtered_persona": persona_filter,
            "error": None
        }

    except Exception as e:
        logger.error(f"Persona Memory recall failed: {e}")
        return {
            "sessions": [],
            "count": 0,
            "filtered_persona": persona_filter,
            "error": str(e)
        }


def get_persona_statistics() -> dict[str, Any]:
    """Get statistics about stored brainstorm sessions.

    Returns:
        Dictionary with:
            - total_sessions: Total number of sessions stored
            - by_persona: Breakdown by persona type
            - error: Error message if stats retrieval failed (None if successful)

    Example:
        >>> stats = get_persona_statistics()
        >>> print(f"Total sessions: {stats['total_sessions']}")
        >>> for persona, count in stats['by_persona'].items():
        ...     print(f"  {persona}: {count}")
    """
    # Check if PersonaMemory is available
    if not PERSONA_MEMORY_AVAILABLE:
        return {
            "total_sessions": 0,
            "by_persona": {},
            "error": "PersonaMemory module not available"
        }

    try:
        # Initialize PersonaMemory
        pm = PersonaMemory()

        # Get statistics
        stats = pm.get_stats()

        return {
            "total_sessions": stats.get("total", 0),
            "by_persona": stats.get("by_persona", {}),
            "error": None
        }

    except Exception as e:
        logger.error(f"Persona Memory statistics failed: {e}")
        return {
            "total_sessions": 0,
            "by_persona": {},
            "error": str(e)
        }


def format_recall_results(results: dict[str, Any]) -> str:
    """Format Persona Memory recall results for display.

    Args:
        results: Results dictionary from recall_previous_sessions()

    Returns:
        Formatted string for display in /s skill output

    Example:
        >>> results = recall_previous_sessions("database design")
        >>> formatted = format_recall_results(results)
        >>> print(formatted)
    """
    if results["error"]:
        return f"\n⚠️  Previous Sessions: Recall error - {results['error']}"

    if results["count"] == 0:
        return "\n📚 Previous Sessions: No relevant brainstorm sessions found"

    output = [f"\n📚 Previous Sessions: {results['count']} relevant brainstorm sessions found"]

    if results["filtered_persona"]:
        output.append(f"   (Filtered by: {results['filtered_persona']})")

    for i, session in enumerate(results["sessions"], 1):
        output.append(f"\n{i}. **{session['title']}**")
        output.append(f"   Persona: {session['persona']} | Impact: {session['impact']:.2f}")
        if session.get("timestamp"):
            output.append(f"   Date: {session['timestamp']}")
        output.append(f"   Content: {session['content'][:150]}...")

    return "\n".join(output)
