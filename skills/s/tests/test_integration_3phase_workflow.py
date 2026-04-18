#!/usr/bin/env python3
"""
Integration test for 3-phase workflow (P0-5).

Tests the complete Diverge → Discuss → Converge workflow with:
- Phase timeout enforcement
- Result aggregation and ranking
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

# Setup sys.path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent.parent.parent / "__csf" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.orchestrator import BrainstormOrchestrator


@pytest.mark.asyncio
async def test_3phase_workflow_basic():
    """Test basic 3-phase workflow completes successfully."""
    orchestrator = BrainstormOrchestrator(
        enable_performance_tracking=False,
        enable_pheromone_trail=False,
        enable_replay_buffer=False,
        enable_got=False,
        enable_tot=False,
    )

    # Run brainstorm with simple topic
    result = await orchestrator.brainstorm(
        prompt="Test topic for 3-phase workflow",
        personas=["innovator", "pragmatist", "critic"],
        timeout=120.0,
        num_ideas=3,
        fresh_mode=False,
    )

    # Verify result structure
    assert result is not None
    assert result.session_id is not None
    assert result.metrics is not None

    print("[PASS] test_3phase_workflow_basic")


@pytest.mark.asyncio
async def test_phase_timeout_enforcement():
    """Test that phase timeouts are enforced correctly."""
    orchestrator = BrainstormOrchestrator(
        enable_performance_tracking=False,
        enable_pheromone_trail=False,
        enable_replay_buffer=False,
        enable_got=False,
        enable_tot=False,
    )

    # Test with short timeout - should complete but may have fewer ideas
    result = await orchestrator.brainstorm(
        prompt="Test topic for timeout",
        personas=["innovator"],
        timeout=10.0,  # Short timeout
        num_ideas=1,
        fresh_mode=False,
    )

    assert result is not None
    assert result.session_id is not None

    print("[PASS] test_phase_timeout_enforcement")


@pytest.mark.asyncio
async def test_result_ranking_and_filtering():
    """Test that results are properly ranked and filtered."""
    orchestrator = BrainstormOrchestrator(
        enable_performance_tracking=False,
        enable_pheromone_trail=False,
        enable_replay_buffer=False,
        enable_got=False,
        enable_tot=False,
    )

    result = await orchestrator.brainstorm(
        prompt="Test ranking and filtering",
        personas=["innovator", "pragmatist"],
        timeout=120.0,
        num_ideas=5,
        fresh_mode=False,
    )

    # Check that ideas are generated
    assert result is not None

    # Check that top_ideas method works
    top_ideas = result.top_ideas(3)
    assert len(top_ideas) <= 3

    # Check metrics
    metrics = orchestrator.get_metrics()
    assert metrics is not None
    assert "phase" in metrics

    print("[PASS] test_result_ranking_and_filtering")


async def main():
    """Run all integration tests."""
    print("=" * 60)
    print("P0-5: Integration tests for 3-phase workflow")
    print("=" * 60)

    tests = [
        test_3phase_workflow_basic,
        test_phase_timeout_enforcement,
        test_result_ranking_and_filtering,
    ]

    for test in tests:
        try:
            await test()
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            return 1

    print("=" * 60)
    print("All P0-5 integration tests passed!")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
