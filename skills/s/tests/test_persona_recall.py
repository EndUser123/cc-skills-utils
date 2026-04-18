"""Tests for Persona Memory recall functionality in /s skill."""

import sys
from pathlib import Path

# Add skills/s directory to path for imports
skills_path = Path(__file__).parent.parent
sys.path.insert(0, str(skills_path))



def test_recall_previous_sessions_format():
    """Test recall_previous_sessions returns correct format."""
    from persona_recall import recall_previous_sessions

    # Test with a simple query
    result = recall_previous_sessions("test query")

    # Verify result structure
    assert isinstance(result, dict), "Result should be a dictionary"
    assert "sessions" in result, "Result should have 'sessions' key"
    assert "count" in result, "Result should have 'count' key"
    assert "error" in result, "Result should have 'error' key"
    assert isinstance(result["sessions"], list), "Sessions should be a list"
    assert isinstance(result["count"], int), "Count should be an integer"
    assert isinstance(result["filtered_persona"], (str, type(None))), "filtered_persona should be string or None"


def test_recall_persona_filter():
    """Test persona filtering (INNOVATOR, pragmatist, critic, expert)."""
    from persona_recall import recall_previous_sessions

    # Test each persona type
    personas = ["INNOVATOR", "PRAGMATIST", "CRITIC", "EXPERT"]

    for persona in personas:
        result = recall_previous_sessions("test query", persona_filter=persona)

        # Verify persona filter is applied
        assert result["filtered_persona"] == persona, f"Persona filter should be {persona}"
        assert isinstance(result["sessions"], list), f"Sessions should be a list for {persona}"


def test_recall_error_handling():
    """Test error handling when PersonaMemory module unavailable."""
    # This test verifies graceful degradation when PersonaMemory is unavailable
    # Since we have the module available, we'll just verify the error field exists

    from persona_recall import PERSONA_MEMORY_AVAILABLE, recall_previous_sessions

    result = recall_previous_sessions("test query")

    # Verify error handling structure
    assert "error" in result, "Result should always have 'error' field"

    # If PersonaMemory is available, error should be None
    # If PersonaMemory is unavailable, error should contain message
    if PERSONA_MEMORY_AVAILABLE:
        # Module available - error should be None for successful queries
        # (may not be None if DB has issues, but structure should still exist)
        assert isinstance(result["error"], (str, type(None))), "Error should be string or None"
    else:
        # Module unavailable - error should have message
        assert result["error"] is not None, "Error should have message when module unavailable"
        assert "not available" in result["error"].lower(), "Error should mention module unavailable"


def test_recall_empty_results():
    """Test behavior when no previous sessions exist."""
    from persona_recall import recall_previous_sessions

    # Use a very specific query unlikely to have matches
    result = recall_previous_sessions("xyz_very_specific_unlikely_query_12345")

    # Verify empty result handling
    assert isinstance(result["sessions"], list), "Sessions should be a list even when empty"
    assert result["count"] == 0, "Count should be 0 for no results"
    assert len(result["sessions"]) == 0, "Sessions list should be empty"


def test_recall_with_limit():
    """Test recall respects limit parameter."""
    from persona_recall import recall_previous_sessions

    # Test with different limits
    for limit in [1, 5, 10]:
        result = recall_previous_sessions("test query", limit=limit)

        # Verify limit is respected
        assert result["count"] <= limit, f"Count should not exceed limit {limit}"
        assert len(result["sessions"]) <= limit, f"Sessions should not exceed limit {limit}"


def test_recall_with_min_impact():
    """Test recall with minimum impact threshold."""
    from persona_recall import recall_previous_sessions

    # Test with min_impact filter
    result = recall_previous_sessions("test query", min_impact=0.7)

    # Verify structure (actual filtering depends on PersonaMemory implementation)
    assert isinstance(result["sessions"], list), "Sessions should be a list"
    assert isinstance(result["count"], int), "Count should be an integer"


def test_format_recall_results():
    """Test format_recall_results formats output correctly."""
    from persona_recall import format_recall_results

    # Test with error result
    error_result = {
        "sessions": [],
        "count": 0,
        "filtered_persona": None,
        "error": "Test error message"
    }
    formatted = format_recall_results(error_result)

    assert isinstance(formatted, str), "Formatted result should be a string"
    assert "error" in formatted.lower(), "Formatted error should mention error"
    assert "recall error" in formatted.lower(), "Should indicate recall error"

    # Test with empty result
    empty_result = {
        "sessions": [],
        "count": 0,
        "filtered_persona": None,
        "error": None
    }
    formatted = format_recall_results(empty_result)

    assert isinstance(formatted, str), "Formatted result should be a string"
    assert "no relevant" in formatted.lower(), "Empty result should mention no sessions"

    # Test with sessions (simulated)
    sessions_result = {
        "sessions": [
            {
                "title": "Test Session",
                "persona": "INNOVATOR",
                "content": "Test content here",
                "impact": 0.8,
                "timestamp": "2026-03-12",
                "source": "persona_memory"
            }
        ],
        "count": 1,
        "filtered_persona": None,
        "error": None
    }
    formatted = format_recall_results(sessions_result)

    assert isinstance(formatted, str), "Formatted result should be a string"
    assert "1 relevant" in formatted.lower(), "Should show session count"
    assert "test session" in formatted.lower(), "Should include session title"


def test_get_persona_statistics():
    """Test get_persona_statistics returns correct format."""
    from persona_recall import PERSONA_MEMORY_AVAILABLE, get_persona_statistics

    stats = get_persona_statistics()

    # Verify result structure
    assert isinstance(stats, dict), "Stats should be a dictionary"
    assert "total_sessions" in stats, "Stats should have 'total_sessions' key"
    assert "by_persona" in stats, "Stats should have 'by_persona' key"
    assert "error" in stats, "Stats should have 'error' key"

    # Verify types
    assert isinstance(stats["total_sessions"], int), "total_sessions should be an integer"
    assert isinstance(stats["by_persona"], dict), "by_persona should be a dictionary"
    assert isinstance(stats["error"], (str, type(None))), "error should be string or None"

    # If PersonaMemory is available, verify no error
    if PERSONA_MEMORY_AVAILABLE:
        # Stats should be accessible (may be 0 if DB is empty, but should have structure)
        assert stats["total_sessions"] >= 0, "total_sessions should be non-negative"
        assert isinstance(stats["by_persona"], dict), "by_persona should be a dict"


def test_recall_graceful_degradation():
    """Test that recall functions handle PersonaMemory unavailability gracefully."""
    from persona_recall import PERSONA_MEMORY_AVAILABLE

    # If PersonaMemory is available, we can't test the unavailable path
    # But we can verify the module-level flag exists
    assert isinstance(PERSONA_MEMORY_AVAILABLE, bool), "Availability flag should be boolean"

    # Verify functions can be called regardless of availability
    from persona_recall import get_persona_statistics, recall_previous_sessions

    # These should not raise exceptions even if PersonaMemory is unavailable
    result1 = recall_previous_sessions("test")
    assert isinstance(result1, dict), "Should return dict even if unavailable"

    stats = get_persona_statistics()
    assert isinstance(stats, dict), "Should return dict even if unavailable"
