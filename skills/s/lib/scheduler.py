"""
Confidence-based scheduler for multi-agent turn-taking.

This module implements scheduling algorithms that use agent confidence scores
to determine turn order in multi-agent brainstorming sessions.

Key components:
- SchedulingStrategy: Enum of available scheduling strategies
- TurnOrder: Dataclass representing a single turn assignment
- ConfidenceScheduler: Main scheduler class with multiple strategies
"""

from __future__ import annotations

import dataclasses
import random
from enum import Enum

from .agents.base import Agent
from .models import BrainstormContext, Idea


class SchedulingStrategy(str, Enum):
    """
    Scheduling strategies for confidence-based turn-taking.

    Strategies:
        PRIORITY_BASED: Agents with higher confidence speak first
        ROUND_ROBIN: All agents take turns in original order
        WEIGHTED_RANDOM: Random order weighted by confidence scores

    Example:
        ```python
        scheduler = ConfidenceScheduler(strategy=SchedulingStrategy.PRIORITY_BASED)
        turn_order = await scheduler.schedule_turns(agents)
        ```
    """

    PRIORITY_BASED = "priority_based"
    ROUND_ROBIN = "round_robin"
    WEIGHTED_RANDOM = "weighted_random"


@dataclasses.dataclass(frozen=True)
class TurnOrder:
    """
    Represents a single turn assignment in the scheduling order.

    Attributes:
        agent: The Agent assigned to this turn
        confidence: The agent's computed confidence score (0-1)
        position: The position in the turn sequence (0-indexed)

    Example:
        ```python
        turn = TurnOrder(agent=agent1, confidence=0.85, position=0)
        print(f"{turn.agent.name} speaks first with {turn.confidence} confidence")
        ```
    """

    agent: Agent
    confidence: float
    position: int


class ConfidenceScheduler:
    """
    Confidence-based scheduler for multi-agent turn-taking.

    This scheduler computes confidence scores for each agent and orders them
    according to the selected scheduling strategy.

    Attributes:
        strategy: The scheduling strategy to use (default: PRIORITY_BASED)
        min_confidence_threshold: Minimum confidence for an agent to participate
        seed: Random seed for WEIGHTED_RANDOM strategy (for reproducibility)

    Example:
        ```python
        # Priority-based scheduling (high confidence first)
        scheduler = ConfidenceScheduler(strategy=SchedulingStrategy.PRIORITY_BASED)
        turn_order = await scheduler.schedule_turns(agents)

        # Round-robin scheduling (original order maintained)
        scheduler = ConfidenceScheduler(strategy=SchedulingStrategy.ROUND_ROBIN)
        turn_order = await scheduler.schedule_turns(agents)

        # Weighted random scheduling (probabilistic based on confidence)
        scheduler = ConfidenceScheduler(
            strategy=SchedulingStrategy.WEIGHTED_RANDOM,
            seed=42  # For reproducibility in tests
        )
        turn_order = await scheduler.schedule_turns(agents)
        ```
    """

    # Scheduling constants
    _DEFAULT_MIN_CONFIDENCE: float = 0.0
    _DEFAULT_RANDOM_SEED: int | None = None

    def __init__(
        self,
        strategy: SchedulingStrategy = SchedulingStrategy.PRIORITY_BASED,
        min_confidence_threshold: float = _DEFAULT_MIN_CONFIDENCE,
        seed: int | None = _DEFAULT_RANDOM_SEED,
    ):
        """
        Initialize the confidence scheduler.

        Args:
            strategy: The scheduling strategy to use
            min_confidence_threshold: Minimum confidence for participation (0-1)
            seed: Random seed for WEIGHTED_RANDOM strategy

        Raises:
            ValueError: If min_confidence_threshold is not in [0, 1]
        """
        if not 0.0 <= min_confidence_threshold <= 1.0:
            raise ValueError(
                f"min_confidence_threshold must be in [0, 1], got {min_confidence_threshold}"
            )

        self.strategy = strategy
        self.min_confidence_threshold = min_confidence_threshold
        self._seed = seed

        # Initialize random number generator with seed if provided
        self._rng = random.Random(seed) if seed is not None else random

    async def schedule_turns(
        self,
        agents: list[Agent],
        context: BrainstormContext | None = None,
        idea_context: Idea | None = None,
    ) -> list[TurnOrder]:
        """
        Schedule turn order for agents based on their confidence scores.

        Args:
            agents: List of agents to schedule
            context: Optional BrainstormContext for confidence computation
            idea_context: Optional Idea for confidence computation

        Returns:
            List of TurnOrder objects sorted by the selected strategy.
            Agents below min_confidence_threshold are filtered out.

        Raises:
            ValueError: If strategy is not a valid SchedulingStrategy

        Example:
            ```python
            scheduler = ConfidenceScheduler(strategy=SchedulingStrategy.PRIORITY_BASED)
            turn_order = await scheduler.schedule_turns(
                agents=[agent1, agent2, agent3],
                context=brainstorm_context
            )
            for turn in turn_order:
                print(f"{turn.position}: {turn.agent.name} (confidence: {turn.confidence})")
            ```
        """
        if not agents:
            return []

        # Compute confidence scores for all agents
        agent_confidences: list[tuple[Agent, float]] = []
        for agent in agents:
            confidence = await self._compute_agent_confidence(agent, context, idea_context)
            agent_confidences.append((agent, confidence))

        # Filter agents below threshold
        filtered_agents = [
            (agent, conf)
            for agent, conf in agent_confidences
            if conf >= self.min_confidence_threshold
        ]

        if not filtered_agents:
            return []

        # Schedule based on strategy
        if self.strategy == SchedulingStrategy.PRIORITY_BASED:
            return self._schedule_priority_based(filtered_agents)
        elif self.strategy == SchedulingStrategy.ROUND_ROBIN:
            return self._schedule_round_robin(filtered_agents)
        elif self.strategy == SchedulingStrategy.WEIGHTED_RANDOM:
            return self._schedule_weighted_random(filtered_agents)
        else:
            raise ValueError(f"Unknown scheduling strategy: {self.strategy}")

    async def _compute_agent_confidence(
        self,
        agent: Agent,
        context: BrainstormContext | None = None,
        idea_context: Idea | None = None,
    ) -> float:
        """
        Compute confidence score for an agent.

        Uses the agent's _compute_idea_confidence method if available,
        otherwise returns a default confidence.

        Args:
            agent: The agent to compute confidence for
            context: Optional BrainstormContext
            idea_context: Optional Idea for confidence computation

        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Check if agent has the confidence computation method
        if hasattr(agent, "_compute_idea_confidence"):
            try:
                if idea_context:
                    confidence, _ = await agent._compute_idea_confidence(idea_context)
                elif context:
                    # Create a dummy idea for confidence computation
                    dummy_idea = Idea(
                        content=context.topic,
                        persona=agent.name,
                    )
                    confidence, _ = await agent._compute_idea_confidence(dummy_idea)
                else:
                    # No context available, use default confidence
                    confidence = 0.5
                return confidence
            except Exception:
                # On error, return default confidence
                return 0.5
        else:
            # Agent doesn't have confidence computation, return default
            return 0.5

    def _schedule_priority_based(
        self, agent_confidences: list[tuple[Agent, float]]
    ) -> list[TurnOrder]:
        """
        Schedule agents by confidence (highest first).

        Uses stable sort to maintain original order for tied scores.

        Args:
            agent_confidences: List of (agent, confidence) tuples

        Returns:
            List of TurnOrder sorted by confidence (descending)
        """
        # Sort by confidence descending, then by original index (stable sort)
        indexed = list(enumerate(agent_confidences))
        indexed.sort(key=lambda x: (-x[1][1], x[0]))

        # Create TurnOrder objects
        turn_orders = []
        for position, (_, (agent, confidence)) in enumerate(indexed):
            turn_orders.append(TurnOrder(agent=agent, confidence=confidence, position=position))

        return turn_orders

    def _schedule_round_robin(
        self, agent_confidences: list[tuple[Agent, float]]
    ) -> list[TurnOrder]:
        """
        Schedule agents in their original order.

        Args:
            agent_confidences: List of (agent, confidence) tuples

        Returns:
            List of TurnOrder in original order
        """
        turn_orders = []
        for position, (agent, confidence) in enumerate(agent_confidences):
            turn_orders.append(TurnOrder(agent=agent, confidence=confidence, position=position))

        return turn_orders

    def _schedule_weighted_random(
        self, agent_confidences: list[tuple[Agent, float]]
    ) -> list[TurnOrder]:
        """
        Schedule agents using weighted random selection based on confidence.

        Higher confidence agents are more likely to be scheduled earlier.

        Args:
            agent_confidences: List of (agent, confidence) tuples

        Returns:
            List of TurnOrder in weighted random order
        """
        # Create a copy and shuffle using weighted random
        remaining = list(agent_confidences)
        turn_orders = []
        position = 0

        while remaining:
            # Calculate total confidence remaining
            total_confidence = sum(conf for _, conf in remaining)

            if total_confidence == 0:
                # All confidences are 0, use uniform random
                idx = self._rng.randint(0, len(remaining) - 1)
            else:
                # Weighted random selection
                r = self._rng.uniform(0, total_confidence)
                cumulative = 0.0
                idx = 0

                for i, (_, conf) in enumerate(remaining):
                    cumulative += conf
                    if cumulative >= r:
                        idx = i
                        break

            # Move selected agent to turn order
            agent, confidence = remaining.pop(idx)
            turn_orders.append(TurnOrder(agent=agent, confidence=confidence, position=position))
            position += 1

        return turn_orders


__all__ = [
    "SchedulingStrategy",
    "TurnOrder",
    "ConfidenceScheduler",
]
