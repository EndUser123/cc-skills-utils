"""
Voting Mechanisms for Multi-Agent Consensus

This module implements various voting strategies for building consensus
among multiple agents after debates, including majority, weighted, unanimous,
and Borda count voting.
"""
from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .models import (
    DebatedIdea,
    RoundContribution,
)

logger = logging.getLogger(__name__)


class VotingStrategy(str, Enum):
    """
    Enumeration of available voting strategies.

    Strategies:
    - MAJORITY: Simple majority vote (50% + 1)
    - WEIGHTED: Weighted voting based on agent credibility
    - UNANIMOUS: All agents must agree
    - BORDA: Borda count ranking system
    """

    MAJORITY = "majority"
    WEIGHTED = "weighted"
    UNANIMOUS = "unanimous"
    BORDA = "borda"


class ConsensusResult(BaseModel):
    """
    Result of a consensus-building voting process.

    Attributes:
        idea_id: ID of the idea that was voted on
        strategy: Which voting strategy was used
        consensus_score: Final consensus score (0-100)
        agreement_level: How much agents agreed (0-100)
        votes_for: Number of votes in favor
        votes_against: Number of votes against
        votes_abstain: Number of abstentions
        total_votes: Total number of votes cast
        individual_votes: Individual agent votes and weights
        passed: Whether the vote passed
        timestamp: When the vote was conducted

    """

    idea_id: str = Field(
        ...,
        description="ID of the idea that was voted on"
    )
    strategy: VotingStrategy = Field(
        ...,
        description="Which voting strategy was used"
    )
    consensus_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Final consensus score (0-100)"
    )
    agreement_level: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="How much agents agreed (0-100)"
    )
    votes_for: int = Field(
        ...,
        ge=0,
        description="Number of votes in favor"
    )
    votes_against: int = Field(
        ...,
        ge=0,
        description="Number of votes against"
    )
    votes_abstain: int = Field(
        default=0,
        ge=0,
        description="Number of abstentions"
    )
    total_votes: int = Field(
        ...,
        ge=0,
        description="Total number of votes cast"
    )
    individual_votes: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Individual agent votes and weights"
    )
    passed: bool = Field(
        ...,
        description="Whether the vote passed"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the vote was conducted"
    )


class VotingMechanism:
    """
    Implements various voting strategies for multi-agent consensus.

    The VotingMechanism coordinates voting after debates to determine
    the level of agent agreement and produce consensus scores.

    Attributes:
        strategy: The voting strategy to use
        agent_weights: Optional weights for each agent (for weighted voting)

    Example:
        ```python
        voting = VotingMechanism(strategy=VotingStrategy.WEIGHTED)
        result = await voting.vote_on_idea(
            idea=debated_idea,
            agents=[expert, critic, innovator]
        )
        print(f"Consensus Score: {result.consensus_score}")
        print(f"Passed: {result.passed}")
        ```

    """

    def __init__(
        self,
        strategy: VotingStrategy = VotingStrategy.WEIGHTED,
        agent_weights: dict[str, float] | None = None
    ):
        """
        Initialize the voting mechanism.

        Args:
            strategy: Voting strategy to use
            agent_weights: Optional weights for each agent (for weighted voting)

        """
        self.strategy = strategy
        self.agent_weights = agent_weights or self._default_weights()

        logger.info(
            f"VotingMechanism initialized with strategy={strategy.value}, "
            f"{len(self.agent_weights)} agent weights"
        )

    def _default_weights(self) -> dict[str, float]:
        """
        Get default agent weights.

        Default weights based on typical credibility:
        - Expert: 0.4 (highest weight due to domain knowledge)
        - Critic: 0.3 (high weight for critical analysis)
        - Innovator: 0.3 (creative but may be less practical)
        """
        return {
            "Expert": 0.4,
            "Critic": 0.3,
            "Innovator": 0.3,
            "Pragmatist": 0.35,
            "Synthesizer": 0.35,
        }

    async def vote_on_idea(
        self,
        debated_idea: DebatedIdea,
        agents: list[Any],
        round_contributions: list[RoundContribution] | None = None
    ) -> ConsensusResult:
        """
        Conduct a vote on a debated idea.

        Agents vote based on their analysis of the debate and their
        individual evaluation of the idea's merit.

        Args:
            debated_idea: The idea that was debated
            agents: List of agents participating in the vote
            round_contributions: Optional contributions from debate rounds

        Returns:
            ConsensusResult with voting outcome and consensus score

        Example:
            ```python
            result = await voting.vote_on_idea(
                debated_idea=debated_idea,
                agents=[expert, critic, innovator]
            )
            if result.passed:
                print(f"Idea accepted with {result.consensus_score:.1f}% consensus")
            ```

        """
        # Collect votes from agents
        votes = await self._collect_votes(debated_idea, agents)

        # Apply voting strategy
        if self.strategy == VotingStrategy.MAJORITY:
            return self._majority_vote(debated_idea.id, votes)
        if self.strategy == VotingStrategy.WEIGHTED:
            return self._weighted_vote(debated_idea.id, votes)
        if self.strategy == VotingStrategy.UNANIMOUS:
            return self._unanimous_vote(debated_idea.id, votes)
        if self.strategy == VotingStrategy.BORDA:
            return self._borda_count(debated_idea.id, votes)
        raise ValueError(f"Unknown voting strategy: {self.strategy}")

    async def _collect_votes(
        self,
        debated_idea: DebatedIdea,
        agents: list[Any]
    ) -> dict[str, dict[str, Any]]:
        """
        Collect votes from all agents.

        Each agent evaluates the debated idea and provides:
        - Vote (for/against/abstain)
        - Confidence (0-100)
        - Reasoning for their vote

        Args:
            debated_idea: The idea to vote on
            agents: List of agents to collect votes from

        Returns:
            Dictionary mapping agent names to their vote data

        """
        votes = {}

        for agent in agents:
            try:
                # Get agent's name
                agent_name = getattr(agent, "name", agent.__class__.__name__)

                # Simulate agent vote (in production, would call agent's vote method)
                vote_data = await self._agent_vote(agent, debated_idea)

                votes[agent_name] = vote_data

                logger.debug(
                    f"Agent {agent_name} voted: {vote_data['vote']} "
                    f"(confidence: {vote_data['confidence']:.1f})"
                )

            except Exception as e:
                logger.error(f"Error collecting vote from {agent}: {e}")
                # Continue with other agents

        return votes

    async def _agent_vote(
        self,
        agent: Any,
        debated_idea: DebatedIdea
    ) -> dict[str, Any]:
        """
        Get a single agent's vote on a debated idea.

        For MVP, simulates voting based on agent persona and debate outcome.
        In production, would call agent's actual voting method.

        Args:
            agent: The agent to get vote from
            debated_idea: The idea being voted on

        Returns:
            Dictionary with vote, confidence, and reasoning

        """
        agent_name = getattr(agent, "name", agent.__class__.__name__)

        # Get agent's weight
        weight = self.agent_weights.get(agent_name, 0.3)

        # Simulate voting based on:
        # - Agent persona (Expert, Critic, etc.)
        # - Debate quality (judge_score)
        # - Round contributions

        # For MVP: Generate pseudo-random but consistent votes
        import hashlib
        vote_seed = int(
            hashlib.md5(
                f"{agent_name}{debated_idea.id}".encode()
            ).hexdigest()[:8],
            16
        )

        # Base decision on judge score
        judge_score = debated_idea.judge_score

        # Adjust based on agent persona
        if agent_name == "Critic":
            # Critic is more skeptical
            threshold = 70
        elif agent_name == "Expert":
            # Expert is moderate
            threshold = 60
        elif agent_name == "Innovator":
            # Innovator is optimistic
            threshold = 50
        else:
            threshold = 60

        # Determine vote
        if judge_score >= threshold:
            if (vote_seed % 10) < 7:  # 70% chance of for
                vote = "for"
                confidence = min(100, judge_score + (vote_seed % 20))
            else:
                vote = "abstain"
                confidence = 50.0
        elif (vote_seed % 10) < 6:  # 60% chance of against
            vote = "against"
            confidence = min(100, (100 - judge_score) + (vote_seed % 20))
        else:
            vote = "abstain"
            confidence = 50.0

        # Generate reasoning
        reasoning = self._generate_vote_reasoning(
            agent_name=agent_name,
            vote=vote,
            debated_idea=debated_idea
        )

        return {
            "vote": vote,
            "confidence": confidence,
            "weight": weight,
            "reasoning": reasoning
        }

    def _generate_vote_reasoning(
        self,
        agent_name: str,
        vote: str,
        debated_idea: DebatedIdea
    ) -> str:
        """Generate reasoning text for an agent's vote."""
        if vote == "for":
            return f"{agent_name} supports this idea based on strong arguments and manageable concerns."
        if vote == "against":
            return f"{agent_name} opposes this idea due to significant flaws or risks identified."
        return f"{agent_name} abstains, citing insufficient evidence or need for more information."

    def _majority_vote(
        self,
        idea_id: str,
        votes: dict[str, dict[str, Any]]
    ) -> ConsensusResult:
        """
        Simple majority voting (50% + 1 to pass).

        Args:
            idea_id: ID of the idea being voted on
            votes: Dictionary of agent votes

        Returns:
            ConsensusResult with majority vote outcome

        """
        votes_for = sum(1 for v in votes.values() if v["vote"] == "for")
        votes_against = sum(1 for v in votes.values() if v["vote"] == "against")
        votes_abstain = sum(1 for v in votes.values() if v["vote"] == "abstain")
        total_votes = len(votes)

        # Determine if passed (simple majority of non-abstain votes)
        voting_votes = votes_for + votes_against
        passed = voting_votes > 0 and (votes_for / voting_votes) > 0.5

        # Calculate consensus score
        if voting_votes > 0:
            agreement_pct = votes_for / voting_votes
            consensus_score = agreement_pct * 100 if passed else (1 - agreement_pct) * 100
        else:
            consensus_score = 50.0  # Neutral if all abstained

        # Agreement level (higher when most votes align)
        if total_votes > 0:
            max_votes = max(votes_for, votes_against)
            agreement_level = (max_votes / total_votes) * 100
        else:
            agreement_level = 0.0

        return ConsensusResult(
            idea_id=idea_id,
            strategy=VotingStrategy.MAJORITY,
            consensus_score=consensus_score,
            agreement_level=agreement_level,
            votes_for=votes_for,
            votes_against=votes_against,
            votes_abstain=votes_abstain,
            total_votes=total_votes,
            individual_votes=votes,
            passed=passed
        )

    def _weighted_vote(
        self,
        idea_id: str,
        votes: dict[str, dict[str, Any]]
    ) -> ConsensusResult:
        """
        Weighted voting based on agent credibility.

        Args:
            idea_id: ID of the idea being voted on
            votes: Dictionary of agent votes with weights

        Returns:
            ConsensusResult with weighted vote outcome

        """
        # Calculate weighted totals
        weight_for = sum(
            v["weight"] for v in votes.values() if v["vote"] == "for"
        )
        weight_against = sum(
            v["weight"] for v in votes.values() if v["vote"] == "against"
        )
        sum(
            v["weight"] for v in votes.values() if v["vote"] == "abstain"
        )

        total_weight = weight_for + weight_against

        # Determine if passed (weighted majority)
        passed = total_weight > 0 and (weight_for / total_weight) > 0.5

        # Calculate consensus score
        if total_weight > 0:
            agreement_pct = weight_for / total_weight
            consensus_score = agreement_pct * 100 if passed else (1 - agreement_pct) * 100
        else:
            consensus_score = 50.0

        # Agreement level based on weight distribution
        max_weight = max(weight_for, weight_against)
        total_agent_weight = sum(self.agent_weights.get(a, 0.3) for a in votes)
        agreement_level = (max_weight / total_agent_weight) * 100 if total_agent_weight > 0 else 0.0

        # Count actual votes
        votes_for = sum(1 for v in votes.values() if v["vote"] == "for")
        votes_against = sum(1 for v in votes.values() if v["vote"] == "against")
        votes_abstain = sum(1 for v in votes.values() if v["vote"] == "abstain")

        return ConsensusResult(
            idea_id=idea_id,
            strategy=VotingStrategy.WEIGHTED,
            consensus_score=consensus_score,
            agreement_level=agreement_level,
            votes_for=votes_for,
            votes_against=votes_against,
            votes_abstain=votes_abstain,
            total_votes=len(votes),
            individual_votes=votes,
            passed=passed
        )

    def _unanimous_vote(
        self,
        idea_id: str,
        votes: dict[str, dict[str, Any]]
    ) -> ConsensusResult:
        """
        Unanimous voting (all must agree, abstains count as against).

        Args:
            idea_id: ID of the idea being voted on
            votes: Dictionary of agent votes

        Returns:
            ConsensusResult with unanimous vote outcome

        """
        votes_for = sum(1 for v in votes.values() if v["vote"] == "for")
        votes_against = sum(1 for v in votes.values() if v["vote"] == "against")
        votes_abstain = sum(1 for v in votes.values() if v["vote"] == "abstain")
        total_votes = len(votes)

        # Must be unanimous (all votes are "for")
        passed = votes_for == total_votes and votes_against == 0 and votes_abstain == 0

        # Consensus score is 100 if unanimous, 0 otherwise
        consensus_score = 100.0 if passed else 0.0

        # Agreement level
        if total_votes > 0:
            agreement_level = (votes_for / total_votes) * 100
        else:
            agreement_level = 0.0

        return ConsensusResult(
            idea_id=idea_id,
            strategy=VotingStrategy.UNANIMOUS,
            consensus_score=consensus_score,
            agreement_level=agreement_level,
            votes_for=votes_for,
            votes_against=votes_against,
            votes_abstain=votes_abstain,
            total_votes=total_votes,
            individual_votes=votes,
            passed=passed
        )

    def _borda_count(
        self,
        idea_id: str,
        votes: dict[str, dict[str, Any]]
    ) -> ConsensusResult:
        """
        Borda count ranking system.

        Agents rank ideas, and points are assigned based on rank.
        For this implementation, we use confidence scores as rankings.

        Args:
            idea_id: ID of the idea being voted on
            votes: Dictionary of agent votes with confidence scores

        Returns:
            ConsensusResult with Borda count outcome

        """
        # Calculate Borda score based on confidence
        total_score = sum(
            v["confidence"] * v["weight"]
            for v in votes.values()
            if v["vote"] == "for"
        )

        # Max possible score
        max_score = sum(
            100.0 * v["weight"]
            for v in votes.values()
        )

        # Normalize to 0-100
        consensus_score = (total_score / max_score * 100) if max_score > 0 else 0.0

        # Determine if passed (above threshold)
        threshold = 60.0
        passed = consensus_score >= threshold

        # Agreement level based on confidence alignment
        confidences = [v["confidence"] for v in votes.values()]
        if confidences:
            avg_confidence = sum(confidences) / len(confidences)
            agreement_level = avg_confidence
        else:
            agreement_level = 0.0

        votes_for = sum(1 for v in votes.values() if v["vote"] == "for")
        votes_against = sum(1 for v in votes.values() if v["vote"] == "against")
        votes_abstain = sum(1 for v in votes.values() if v["vote"] == "abstain")

        return ConsensusResult(
            idea_id=idea_id,
            strategy=VotingStrategy.BORDA,
            consensus_score=consensus_score,
            agreement_level=agreement_level,
            votes_for=votes_for,
            votes_against=votes_against,
            votes_abstain=votes_abstain,
            total_votes=len(votes),
            individual_votes=votes,
            passed=passed
        )


__all__ = [
    "ConsensusResult",
    "VotingMechanism",
    "VotingStrategy",
]
