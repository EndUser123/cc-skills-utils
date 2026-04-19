#!/usr/bin/env python3
"""Functional tests for real searches through three-layer filtering.

These tests execute actual searches (not mocks) to validate:
- Layer 1: Rule-based filtering works correctly
- Layer 2: Trigger detection and semantic filtering
- Layer 3: Presentation formatting (both standard and themed)
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from skills.explore.search_executor import execute_search, format_results_human
from skills.explore import agent_filter, layer2_filter, query_complexity


class TestFunctionalLayer1Only:
    """Test Layer 1 filtering with real searches."""

    @pytest.mark.asyncio
    async def test_simple_query_returns_results(self):
        """Test simple query returns results via Layer 1 only."""
        query = "python async"

        # Execute search (Layer 1 filtering happens inside)
        results = await execute_search(query, mode="auto", limit=10)

        # Verify Layer 1 returned results
        assert len(results) > 0, "Layer 1 should return results for 'python async'"

        # Verify quality floor applied
        for result in results:
            assert hasattr(result, 'score'), "Result should have score"
            assert result.score >= 0.5, f"Result score {result.score} should meet quality floor of 0.5"

        # Format for display (Layer 3)
        output = format_results_human(query, results, "auto", layer2_applied=False)

        # Verify Layer 3 standard format
        assert "Universal Search Results" in output
        assert query in output
        assert f"Results: {len(results)}" in output

    @pytest.mark.asyncio
    async def test_layer1_enforces_hard_cap(self):
        """Test Layer 1 enforces maximum of 50 results."""
        # Query that might return many results
        query = "python"

        # Execute search with high limit
        results = await execute_search(query, mode="auto", limit=100)

        # Verify hard cap enforced
        assert len(results) <= 50, f"Layer 1 should enforce hard cap of 50, got {len(results)}"


class TestFunctionalLayer2Triggering:
    """Test Layer 2 trigger detection with real searches."""

    @pytest.mark.asyncio
    async def test_high_result_count_triggers_layer2(self):
        """Test Layer 2 triggers when result count is high."""
        # Use a broad query to get many results
        query = "python programming"

        # Execute search
        results = await execute_search(query, mode="auto", limit=50)

        # Check if Layer 2 should trigger
        should_apply, reason = layer2_filter.should_apply_context_filter(
            results,
            query
        )

        # With many results, Layer 2 should trigger
        if len(results) >= 20:
            assert should_apply is True, "Layer 2 should trigger with 20+ results"
            assert reason is not None
            print(f"Layer 2 triggered: {reason}")
        else:
            pytest.skip(f"Need 20+ results to test Layer 2 trigger, got {len(results)}")

    @pytest.mark.asyncio
    async def test_context_hints_trigger_layer2(self):
        """Test Layer 2 triggers on context hints in query."""
        # Query with context hints
        query = "what did we discuss about async"

        # Execute search
        results = await execute_search(query, mode="auto", limit=10)

        # Check if Layer 2 should trigger
        should_apply, reason = layer2_filter.should_apply_context_filter(
            results,
            query
        )

        # Should trigger due to context hints
        assert should_apply is True, "Layer 2 should trigger on context hints"
        assert reason == "context_hints"

    @pytest.mark.asyncio
    async def test_simple_query_skips_layer2(self):
        """Test Layer 2 skips for simple queries with few results."""
        # Simple, specific query
        query = "hello world"

        # Execute search
        results = await execute_search(query, mode="auto", limit=10)

        # Check if Layer 2 should trigger
        should_apply, reason = layer2_filter.should_apply_context_filter(
            results,
            query
        )

        # Should NOT trigger for simple query with few results
        assert should_apply is False, "Layer 2 should not trigger for simple query"
        assert reason is None


class TestFunctionalLayer2Filtering:
    """Test Layer 2 filtering with real searches (CLI context)."""

    @pytest.mark.asyncio
    async def test_layer2_keyword_fallback_in_cli_context(self, monkeypatch):
        """Test Layer 2 uses keyword fallback in CLI context."""

        # Ensure CLI context (no skill execution env var)
        monkeypatch.delenv('CLAUDE_CODE_SKILL_EXECUTION', raising=False)

        # Execute search that would trigger Layer 2
        query = "python async programming tutorial"
        results = await execute_search(query, mode="auto", limit=30)

        # Apply Layer 2 filtering (should use keyword fallback in CLI)
        complexity_score = query_complexity.calculate_complexity_score(query)

        filtered = await agent_filter.apply_agent_filtering(
            query,
            results,
            complexity_score=complexity_score
        )

        # Verify keyword fallback worked
        assert "themes" in filtered
        assert "filtered_count" in filtered
        assert "original_count" in filtered

        # Verify filtered count is reasonable
        assert filtered["filtered_count"] <= filtered["original_count"]

        print(f"Layer 2 filtering: {filtered['original_count']} → {filtered['filtered_count']} insights")


class TestFunctionalEndToEnd:
    """Test complete end-to-end flow with real searches."""

    @pytest.mark.asyncio
    async def test_complete_flow_standard_output(self):
        """Test complete flow with standard Layer 3 output."""
        query = "python async await"

        # Layer 1: Execute search
        results = await execute_search(query, mode="auto", limit=10)

        # Layer 2: Check if triggered (but don't apply for this test)
        should_apply, reason = layer2_filter.should_apply_context_filter(results, query)

        # Layer 3: Format for display (standard)
        output = format_results_human(
            query,
            results,
            "auto",
            layer2_applied=False
        )

        # Verify complete flow output
        assert len(output) > 0, "Output should not be empty"
        assert "Universal Search Results" in output
        assert query in output
        assert f"Results: {len(results)}" in output

        # Print sample output for manual verification
        print("\n=== Sample Output (first 500 chars) ===")
        print(output[:500])
        print("=== End Sample ===\n")

    @pytest.mark.asyncio
    async def test_complete_flow_with_layer2_simulation(self):
        """Test complete flow with simulated Layer 2 themed output."""
        query = "python async programming patterns"

        # Layer 1: Execute search
        results = await execute_search(query, mode="auto", limit=20)

        # Simulate Layer 2 filtered results
        mock_filtered_results = {
            "themes": [
                {
                    "name": "Async Patterns",
                    "insights": [
                        {
                            "title": f"Result {i}",
                            "source": results[i].source if i < len(results) else "WEB",
                            "key_insights": [f"Insight {i}"]
                        }
                        for i in range(min(3, len(results)))
                    ]
                }
            ],
            "original_count": len(results),
            "filtered_count": min(3, len(results))
        }

        # Layer 3: Format for display (themed)
        output = format_results_human(
            query,
            results,
            "auto",
            layer2_applied=True,
            filtered_results=mock_filtered_results
        )

        # Verify themed output
        assert "Theme: Async Patterns" in output
        assert "Layer 2 Applied" in output
        assert f"{len(results)} results → {min(3, len(results))} key insights" in output

        print("\n=== Sample Themed Output (first 500 chars) ===")
        print(output[:500])
        print("=== End Sample ===\n")


class TestFunctionalErrorHandling:
    """Test error handling with real searches."""

    @pytest.mark.asyncio
    async def test_empty_query_returns_empty_results(self):
        """Test empty query returns empty results gracefully."""
        query = ""

        # Execute search
        results = await execute_search(query, mode="auto", limit=10)

        # Should return empty list, not raise
        assert isinstance(results, list)

        # Format output
        output = format_results_human(query, results, "auto", layer2_applied=False)

        # Should handle empty results
        assert "No results found" in output

    @pytest.mark.asyncio
    async def test_special_characters_in_query(self):
        """Test query with special characters doesn't break."""
        # Query with special characters (but not injection patterns)
        query = "python async/await (event loop)"

        # Execute search - should not raise
        results = await execute_search(query, mode="auto", limit=10)

        # Should return results or empty list
        assert isinstance(results, list)

        # If we got results, format them
        if results:
            output = format_results_human(query, results, "auto", layer2_applied=False)
            assert len(output) > 0
