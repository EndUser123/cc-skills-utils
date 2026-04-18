#!/usr/bin/env python3
"""
Integration test for Advanced Features (Pheromone Trails & Replay Buffer).

Verifies that:
1. Guidance is fetched from pheromone trails.
2. Candidates are fetched from replay buffer.
3. This information is available to agents for idea generation.
"""

import asyncio
import shutil
import sys
from pathlib import Path

import pytest

# Setup sys.path for imports
# Assuming we are in .claude/skills/s/tests/
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.orchestrator import BrainstormOrchestrator
from lib.pheromone.models import PathSignature
from lib.pheromone.trail import get_global_trail
from lib.replay.buffer import get_global_buffer
from lib.replay.models import ReplayRecord


async def setup_test_data(tmp_dir: Path):
    """Setup mock pheromone and replay data."""
    pheromone_db = tmp_dir / "test_pheromones.db"
    replay_db = tmp_dir / "test_replay.db"

    # Setup Pheromones
    trail = get_global_trail(str(pheromone_db))
    # Deposit success for a specific persona and direction
    signature = PathSignature.from_idea(
        topic="sustainable energy",
        persona="Innovator",
        reasoning_path=["Solar power", "Orbital mirrors"],
        domains=["space", "energy"],
    )
    # Deposit enough to exceed threshold (50.0 in orchestrator)
    trail.deposit(signature, score=90.0, weight=2.0)
    trail.close()

    # Setup Replay Buffer
    buffer = get_global_buffer(str(replay_db))
    record = ReplayRecord.from_idea(
        idea_id="test-idea-123",
        content="Orbital solar mirrors for 24/7 sustainable energy collection",
        persona="Innovator",
        reasoning_path=["Solar power", "Orbital mirrors"],
        score=95.0,
        tags=["space", "energy", "sustainable energy"],
    )
    buffer.add_record(record)
    buffer.close()

    return str(pheromone_db), str(replay_db)


@pytest.mark.asyncio
async def test_advanced_features_integration():
    """Test that advanced features are integrated into the workflow."""
    tmp_dir = Path("test_tmp")
    tmp_dir.mkdir(exist_ok=True)

    try:
        pheromone_path, replay_path = await setup_test_data(tmp_dir)

        orchestrator = BrainstormOrchestrator(
            use_mock_agents=True,  # Use mock agents for testing
            enable_pheromone_trail=True,
            pheromone_db_path=pheromone_path,
            enable_replay_buffer=True,
            replay_db_path=replay_path,
        )

        # Run brainstorm on a similar topic
        result = await orchestrator.brainstorm(
            prompt="sustainable energy solutions", personas=["Innovator"], num_ideas=1, timeout=30.0
        )

        # 1. Check if guidance was fetched
        assert "pheromone_guidance" in result.metadata
        guidance = result.metadata["pheromone_guidance"]
        print(f"Guidance fetched: {guidance}")
        assert len(guidance["suggested_personas"]) > 0

        # 2. Check if replay candidates were fetched
        assert "replay_candidates" in result.metadata
        candidates = result.metadata["replay_candidates"]
        print(f"Candidates fetched: {len(candidates)}")
        assert len(candidates) > 0

        # 3. Check if agents received this data (THE CRITICAL GAP CHECK)
        # In mock mode, the _MockAgent currently just generates generic text.
        # We want to see if the context.metadata passed to agents contains the data.

        # Since we use real orchestrator but mock agents, we can check orchestrator's context
        # This is expected to FAIL currently as the orchestrator DOES NOT inject it into context
        print("Checking if guidance/candidates are in context.metadata...")
        assert (
            "pheromone_guidance" in orchestrator.context.metadata
        ), "Guidance NOT injected into context!"
        assert (
            "replay_candidates" in orchestrator.context.metadata
        ), "Candidates NOT injected into context!"

        print("\n[PASS] Advanced features fetched and injected into context!")

    finally:
        # Cleanup
        if tmp_dir.exists():
            try:
                shutil.rmtree(tmp_dir)
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(test_advanced_features_integration())
