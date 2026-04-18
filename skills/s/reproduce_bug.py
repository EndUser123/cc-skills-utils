import asyncio
import sys
from pathlib import Path


# Mock the Agent class since we can't easily instantiate the real one with all its LLM dependencies
class MockAgent:
    def __init__(self, name):
        self.name = name


# Add lib to path
sys.path.insert(0, str(Path.cwd()))


async def reproduce_position_bug():
    from lib.scheduler import ConfidenceScheduler, SchedulingStrategy

    # Create a scheduler with weighted random strategy and a seed for reproducibility
    scheduler = ConfidenceScheduler(strategy=SchedulingStrategy.WEIGHTED_RANDOM, seed=42)

    # Create some mock agents
    agents = [MockAgent(f"Agent-{i}") for i in range(5)]

    # Mock _compute_agent_confidence to return different confidences
    # In weighted random, position 0 should be the first agent selected,
    # position 1 the second, etc.

    async def mock_compute(agent, context=None, idea_context=None):
        # Assign confidences such that selection order is likely to be varied
        conf_map = {"Agent-0": 0.1, "Agent-1": 0.9, "Agent-2": 0.5, "Agent-3": 0.2, "Agent-4": 0.8}
        return conf_map.get(agent.name, 0.5)

    # Patch the scheduler's private method
    scheduler._compute_agent_confidence = mock_compute

    print("Scheduling turns with WEIGHTED_RANDOM...")
    turns = await scheduler.schedule_turns(agents)

    print("\nResults:")
    for turn in turns:
        print(f"Position {turn.position}: {turn.agent.name} (Confidence: {turn.confidence})")

    # Verify that positions are sequential 0, 1, 2, 3, 4
    positions = [t.position for t in turns]
    print(f"\nPositions assigned: {positions}")

    # The actual order of agents in the list 'turns' IS the order they were selected.
    # My theory was that they might be out of order if some sorting happened,
    # but _schedule_weighted_random appends them to turn_orders in the order they are picked.
    # Let's re-examine _schedule_weighted_random:
    #
    # while remaining:
    #     ... selection logic ...
    #     agent, confidence = remaining.pop(idx)
    #     turn_orders.append(TurnOrder(agent=agent, confidence=confidence, position=position))
    #     position += 1

    # Wait, if they are appended in order and position is incremented, they should be correct.
    # Let's check _schedule_priority_based:
    #
    # indexed = list(enumerate(agent_confidences))
    # indexed.sort(key=lambda x: (-x[1][1], x[0]))
    # turn_orders = []
    # for position, (_, (agent, confidence)) in enumerate(indexed):
    #     turn_orders.append(TurnOrder(agent=agent, confidence=confidence, position=position))

    # This also seems to assign positions based on the final sorted order.

    # Wait, the "bug" I suspected was that position might refer to the ORIGINAL index.
    # But TurnOrder.position is defined as "The position in the turn sequence (0-indexed)".
    # So if it's the sequence order, then 0, 1, 2... is correct for the output list.

    # Let's look at the "weighted_random" implementation again.
    # It picks one, appends it with position 0, then picks next, appends with position 1.
    # This matches the definition of "position in the turn sequence".

    # Is there a bug in how it's used? If the caller expects 'position' to be the original
    # index, then it's a mismatch. But the docstring says "position in the turn sequence".


if __name__ == "__main__":
    asyncio.run(reproduce_position_bug())
