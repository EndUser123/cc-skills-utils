"""
Tests for ConfidenceScheduler class.

RED PHASE: These tests verify the confidence-based scheduling algorithm.
Tests will FAIL until the ConfidenceScheduler class is implemented.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

# Add lib to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.agents.base import Agent
from lib.models import Idea
from lib.scheduler import (
    ConfidenceScheduler,
    SchedulingStrategy,
    TurnOrder,
)


class DummyAgent(Agent):
    """Minimal concrete Agent for testing scheduling."""

    async def generate_ideas(self, context):
        return []

    async def evaluate_idea(self, idea):
        from lib.models import Evaluation

        return Evaluation.from_scores(
            idea_id=idea.id, novelty=50.0, feasibility=50.0, impact=50.0, evaluator="dummy"
        )


class TestConfidenceScheduler:
    """Test suite for ConfidenceScheduler class."""

    @pytest.mark.asyncio
    async def test_scheduler_has_schedule_turns_method(self):
        """Verify ConfidenceScheduler has schedule_turns method."""
        # Create agents with different confidence scores
        agent1 = DummyAgent(name="AgentHigh")
        agent2 = DummyAgent(name="AgentLow")
        agent3 = DummyAgent(name="AgentMedium")

        # Mock confidence computation using the actual method name
        agent1._compute_idea_confidence = AsyncMock(return_value=(0.9, "High"))
        agent2._compute_idea_confidence = AsyncMock(return_value=(0.3, "Low"))
        agent3._compute_idea_confidence = AsyncMock(return_value=(0.6, "Medium"))

        # Create scheduler
        scheduler = ConfidenceScheduler(strategy=SchedulingStrategy.PRIORITY_BASED)

        # Schedule turns for agents
        turn_order = await scheduler.schedule_turns([agent1, agent2, agent3])

        # Should return a turn order
        assert isinstance(turn_order, list)
        assert len(turn_order) == 3
        # All items should be TurnOrder tuples
        for item in turn_order:
            assert isinstance(item, TurnOrder)
            assert hasattr(item, "agent")
            assert hasattr(item, "confidence")
            assert hasattr(item, "position")

    @pytest.mark.asyncio
    async def test_priority_based_scheduling_orders_by_confidence(self):
        """Verify PRIORITY_BASED strategy orders agents by confidence (high to low)."""
        agent_low = DummyAgent(name="Low")
        agent_high = DummyAgent(name="High")
        agent_mid = DummyAgent(name="Mid")

        agent_low._compute_idea_confidence = AsyncMock(return_value=(0.2, "Low"))
        agent_high._compute_idea_confidence = AsyncMock(return_value=(0.95, "High"))
        agent_mid._compute_idea_confidence = AsyncMock(return_value=(0.6, "Mid"))

        scheduler = ConfidenceScheduler(strategy=SchedulingStrategy.PRIORITY_BASED)

        # Create a context for confidence computation
        from lib.models import BrainstormContext

        context = BrainstormContext(topic="Test topic", num_ideas=5)

        turn_order = await scheduler.schedule_turns(
            [agent_low, agent_high, agent_mid], context=context
        )

        # Highest confidence should be first
        assert turn_order[0].agent.name == "High"
        assert turn_order[0].confidence == 0.95
        assert turn_order[0].position == 0

        # Middle confidence should be second
        assert turn_order[1].agent.name == "Mid"
        assert turn_order[1].confidence == 0.6
        assert turn_order[1].position == 1

        # Lowest confidence should be last
        assert turn_order[2].agent.name == "Low"
        assert turn_order[2].confidence == 0.2
        assert turn_order[2].position == 2

    @pytest.mark.asyncio
    async def test_round_robin_scheduling_maintains_order(self):
        """Verify ROUND_ROBIN strategy maintains original agent order."""
        agent1 = DummyAgent(name="First")
        agent2 = DummyAgent(name="Second")
        agent3 = DummyAgent(name="Third")

        agent1._compute_idea_confidence = AsyncMock(return_value=(0.5, "First"))
        agent2._compute_idea_confidence = AsyncMock(return_value=(0.7, "Second"))
        agent3._compute_idea_confidence = AsyncMock(return_value=(0.3, "Third"))

        scheduler = ConfidenceScheduler(strategy=SchedulingStrategy.ROUND_ROBIN)
        turn_order = await scheduler.schedule_turns([agent1, agent2, agent3])

        # Round-robin should maintain original order
        assert turn_order[0].agent.name == "First"
        assert turn_order[1].agent.name == "Second"
        assert turn_order[2].agent.name == "Third"

    @pytest.mark.asyncio
    async def test_weighted_random_uses_confidence_as_weights(self):
        """Verify WEIGHTED_RANDOM strategy uses confidence as probability weights."""
        agent_high = DummyAgent(name="High")
        agent_low = DummyAgent(name="Low")

        agent_high._compute_idea_confidence = AsyncMock(return_value=(0.9, "High"))
        agent_low._compute_idea_confidence = AsyncMock(return_value=(0.1, "Low"))

        scheduler = ConfidenceScheduler(strategy=SchedulingStrategy.WEIGHTED_RANDOM, seed=42)

        # Create a context for confidence computation
        from lib.models import BrainstormContext

        context = BrainstormContext(topic="Test topic", num_ideas=5)

        # Run multiple times to check distribution
        high_count = 0
        iterations = 20

        for _ in range(iterations):
            turn_order = await scheduler.schedule_turns([agent_high, agent_low], context=context)
            # High confidence agent should more often be first
            if turn_order[0].agent.name == "High":
                high_count += 1

        # High confidence should be first more often than low confidence
        # (at least 60% of the time given 0.9 vs 0.1 weights)
        assert high_count >= iterations * 0.6

    @pytest.mark.asyncio
    async def test_scheduler_calls_compute_confidence_on_agents(self):
        """Verify scheduler calls compute_confidence method on each agent."""
        agent1 = DummyAgent(name="Agent1")
        agent2 = DummyAgent(name="Agent2")

        # Mock _compute_idea_confidence method on agents
        agent1._compute_idea_confidence = AsyncMock(return_value=(0.8, "Good"))
        agent2._compute_idea_confidence = AsyncMock(return_value=(0.5, "OK"))

        scheduler = ConfidenceScheduler(strategy=SchedulingStrategy.PRIORITY_BASED)

        # Create a mock context for confidence computation
        mock_context = Mock()
        mock_context.topic = "Test topic"

        turn_order = await scheduler.schedule_turns([agent1, agent2], context=mock_context)

        # Verify all agents got a turn
        assert len(turn_order) == 2

    @pytest.mark.asyncio
    async def test_scheduler_handles_empty_agent_list(self):
        """Verify scheduler handles empty agent list gracefully."""
        scheduler = ConfidenceScheduler(strategy=SchedulingStrategy.PRIORITY_BASED)
        turn_order = await scheduler.schedule_turns([])

        assert turn_order == []

    @pytest.mark.asyncio
    async def test_scheduler_handles_single_agent(self):
        """Verify scheduler handles single agent correctly."""
        agent = DummyAgent(name="Solo")
        agent._compute_idea_confidence = AsyncMock(return_value=(0.75, "Solo"))

        scheduler = ConfidenceScheduler(strategy=SchedulingStrategy.PRIORITY_BASED)

        # Create a context for confidence computation
        from lib.models import BrainstormContext

        context = BrainstormContext(topic="Test topic", num_ideas=5)

        turn_order = await scheduler.schedule_turns([agent], context=context)

        assert len(turn_order) == 1
        assert turn_order[0].agent.name == "Solo"
        assert turn_order[0].confidence == 0.75
        assert turn_order[0].position == 0

    @pytest.mark.asyncio
    async def test_scheduler_handles_tied_confidence_scores(self):
        """Verify scheduler handles tied confidence scores (uses stable sort)."""
        agent1 = DummyAgent(name="First")
        agent2 = DummyAgent(name="Second")
        agent3 = DummyAgent(name="Third")

        # All agents have same confidence
        agent1._compute_idea_confidence = AsyncMock(return_value=(0.5, "First"))
        agent2._compute_idea_confidence = AsyncMock(return_value=(0.5, "Second"))
        agent3._compute_idea_confidence = AsyncMock(return_value=(0.5, "Third"))

        scheduler = ConfidenceScheduler(strategy=SchedulingStrategy.PRIORITY_BASED)
        turn_order = await scheduler.schedule_turns([agent1, agent2, agent3])

        # Should maintain original order for tied scores (stable sort)
        assert turn_order[0].agent.name == "First"
        assert turn_order[1].agent.name == "Second"
        assert turn_order[2].agent.name == "Third"

    @pytest.mark.asyncio
    async def test_scheduler_filters_below_threshold(self):
        """Verify scheduler filters out agents below confidence threshold."""
        agent_high = DummyAgent(name="High")
        agent_mid = DummyAgent(name="Mid")
        agent_low = DummyAgent(name="Low")

        agent_high._compute_idea_confidence = AsyncMock(return_value=(0.8, "High"))
        agent_mid._compute_idea_confidence = AsyncMock(return_value=(0.5, "Mid"))
        agent_low._compute_idea_confidence = AsyncMock(return_value=(0.2, "Low"))

        scheduler = ConfidenceScheduler(
            strategy=SchedulingStrategy.PRIORITY_BASED,
            min_confidence_threshold=0.4,
        )

        # Create a context for confidence computation
        from lib.models import BrainstormContext

        context = BrainstormContext(topic="Test topic", num_ideas=5)

        turn_order = await scheduler.schedule_turns(
            [agent_high, agent_mid, agent_low], context=context
        )

        # Low confidence agent should be filtered out
        assert len(turn_order) == 2
        agent_names = [t.agent.name for t in turn_order]
        assert "Low" not in agent_names
        assert "High" in agent_names
        assert "Mid" in agent_names

    @pytest.mark.asyncio
    async def test_turn_order_dataclass_attributes(self):
        """Verify TurnOrder dataclass has correct attributes."""
        from dataclasses import is_dataclass

        # TurnOrder should be a dataclass
        assert is_dataclass(TurnOrder)

        # Create a TurnOrder instance
        agent = DummyAgent(name="Test")
        turn = TurnOrder(agent=agent, confidence=0.85, position=0)

        # Verify attributes
        assert turn.agent == agent
        assert turn.confidence == 0.85
        assert turn.position == 0

    @pytest.mark.asyncio
    async def test_scheduling_strategy_enum_values(self):
        """Verify SchedulingStrategy enum has expected values."""
        # Check enum has the required strategies
        assert hasattr(SchedulingStrategy, "PRIORITY_BASED")
        assert hasattr(SchedulingStrategy, "ROUND_ROBIN")
        assert hasattr(SchedulingStrategy, "WEIGHTED_RANDOM")

        # Check enum values
        assert SchedulingStrategy.PRIORITY_BASED == "priority_based"
        assert SchedulingStrategy.ROUND_ROBIN == "round_robin"
        assert SchedulingStrategy.WEIGHTED_RANDOM == "weighted_random"

    @pytest.mark.asyncio
    async def test_scheduler_accepts_idea_context_for_confidence(self):
        """Verify scheduler can use Idea context for confidence computation."""
        agent1 = DummyAgent(name="Agent1")
        agent2 = DummyAgent(name="Agent2")

        # Mock confidence computation that would use Idea
        agent1._compute_idea_confidence = AsyncMock(return_value=(0.7, "Good"))
        agent2._compute_idea_confidence = AsyncMock(return_value=(0.4, "Fair"))

        scheduler = ConfidenceScheduler(strategy=SchedulingStrategy.PRIORITY_BASED)

        # Create an Idea for context
        idea = Idea(
            content="Test idea for confidence scheduling",
            persona="TestPractitioner",
            confidence=0.6,
        )

        turn_order = await scheduler.schedule_turns([agent1, agent2], idea_context=idea)

        assert len(turn_order) == 2
        # Higher confidence first
        assert turn_order[0].agent.name == "Agent1"
        assert turn_order[1].agent.name == "Agent2"
