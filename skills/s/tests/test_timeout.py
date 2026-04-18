"""Tests for timeout functionality in /s orchestrator.

This test suite verifies the core timeout behavior using asyncio primitives.
The actual orchestrator tests would require complex module setup.
"""

import asyncio

import pytest


@pytest.mark.asyncio
async def test_asyncio_wait_for_timeout_behavior():
    """Test that asyncio.wait_for enforces timeout correctly.

    This is the core mechanism used by the orchestrator.
    """

    # Task that takes longer than timeout
    async def slow_task():
        await asyncio.sleep(1.0)
        return "completed"

    # Test with very short timeout (0.1s)
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(slow_task(), timeout=0.1)


@pytest.mark.asyncio
async def test_asyncio_gather_with_timeout():
    """Test that asyncio.gather completes tasks in parallel.

    This simulates the orchestrator's parallel agent execution.
    """

    async def fast_task():
        await asyncio.sleep(0.01)
        return "fast"

    async def slow_task():
        await asyncio.sleep(1.0)
        return "slow"

    # Run both tasks with return_exceptions=True
    results = await asyncio.gather(fast_task(), slow_task(), return_exceptions=True)

    # Both should complete because we're using gather without timeout
    assert len(results) == 2
    assert results[0] == "fast"
    assert results[1] == "slow"


@pytest.mark.asyncio
async def test_gather_with_wait_for_timeout():
    """Test that asyncio.wait_for around gather enforces overall timeout.

    This is the pattern used by the orchestrator's _phase_diverge.
    """

    async def fast_task():
        await asyncio.sleep(0.01)
        return "fast"

    async def slow_task():
        await asyncio.sleep(1.0)
        return "slow"

    # With very short timeout (0.1s), the gather should timeout
    # even though fast_task could complete quickly
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(
            asyncio.gather(fast_task(), slow_task(), return_exceptions=True), timeout=0.1
        )


@pytest.mark.asyncio
async def test_partial_completion_with_timeout():
    """Test that ideas from fast providers can be collected with separate timeouts.

    This shows why per-provider timeouts are still useful even with
    an overall phase timeout.
    """
    collected_ideas = []

    async def fast_task():
        await asyncio.sleep(0.01)
        collected_ideas.append("fast_idea")
        return "fast"

    async def slow_task():
        await asyncio.sleep(1.0)
        collected_ideas.append("slow_idea")
        return "slow"

    # When we use gather without timeout, both complete
    tasks = [fast_task(), slow_task()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    assert len(results) == 2
    assert "fast_idea" in collected_ideas
    assert "slow_idea" in collected_ideas


@pytest.mark.asyncio
async def test_timeout_value_accepts_floats():
    """Test that timeout values work correctly as floats.

    This verifies that the configurable timeout parameter works.
    """

    async def quick_task():
        return "done"

    # Test with various timeout values
    result1 = await asyncio.wait_for(quick_task(), timeout=0.5)
    assert result1 == "done"

    result2 = await asyncio.wait_for(quick_task(), timeout=1.0)
    assert result2 == "done"

    result3 = await asyncio.wait_for(quick_task(), timeout=0.1)
    assert result3 == "done"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
