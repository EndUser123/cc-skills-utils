"""
Data Models for Multi-Agent Debate Framework

This module defines the core data structures used in the debate system,
including debated ideas, debate rounds, and evaluation results.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from ..models import Evaluation, Idea


class DebateRound(str, Enum):
    """
    Enumeration of debate rounds in the adversarial process.

    The debate follows a structured 3-round format:
    - PRO: Expert agent presents supporting arguments
    - CON: Critic agent presents opposing arguments
    - REBUTTAL: Innovator agent provides counter-arguments
    """

    PRO = "pro"
    CON = "con"
    REBUTTAL = "rebuttal"


class RoundContribution(BaseModel):
    """
    A single contribution during a debate round.

    Represents one agent's argument or position during a specific
    round of the debate.

    Attributes:
        agent_name: Name of the agent making the contribution
        round: Which debate round this contribution belongs to
        argument: The actual argument or position statement
        reasoning_path: Sequential reasoning that led to this argument
        timestamp: When this contribution was made
        metadata: Additional flexible data about the contribution

    """

    agent_name: str = Field(
        ...,
        description="Name of the agent making the contribution"
    )
    round: DebateRound = Field(
        ...,
        description="Which debate round this belongs to"
    )
    argument: str = Field(
        ...,
        min_length=20,
        description="The argument or position statement"
    )
    reasoning_path: list[str] = Field(
        default_factory=list,
        description="Sequential reasoning that led to this argument"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this contribution was made"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional flexible data"
    )

    @field_validator("argument")
    @classmethod
    def argument_must_be_meaningful(cls, v: str) -> str:
        """Validate that argument is not just whitespace."""
        if not v.strip():
            raise ValueError("Argument cannot be empty or whitespace only")
        return v.strip()


class RoundEvaluation(BaseModel):
    """
    Evaluation of a single debate round by the Judge.

    The Judge assesses the quality, persuasiveness, and validity
    of arguments presented during each round.

    Attributes:
        round: Which debate round was evaluated
        quality_score: Quality of arguments in this round (0-100)
        persuasiveness_score: How persuasive the arguments were (0-100)
        evidence_score: Quality of evidence and reasoning (0-100)
        strengths: Specific strengths identified in this round
        weaknesses: Specific weaknesses or gaps identified
        judge_notes: Additional qualitative feedback from the Judge
        timestamp: When the evaluation was performed

    """

    round: DebateRound = Field(
        ...,
        description="Which debate round was evaluated"
    )
    quality_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Quality of arguments (0-100)"
    )
    persuasiveness_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="How persuasive the arguments were (0-100)"
    )
    evidence_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Quality of evidence and reasoning (0-100)"
    )
    strengths: list[str] = Field(
        default_factory=list,
        description="Specific strengths identified"
    )
    weaknesses: list[str] = Field(
        default_factory=list,
        description="Specific weaknesses or gaps"
    )
    judge_notes: str | None = Field(
        default=None,
        description="Additional qualitative feedback"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When evaluation was performed"
    )

    @property
    def average_score(self) -> float:
        """Calculate average score across all dimensions."""
        return (self.quality_score + self.persuasiveness_score + self.evidence_score) / 3.0


class DebateEvaluation(BaseModel):
    """
    Comprehensive evaluation of an entire debate by the Judge.

    The Judge evaluates all rounds of the debate and provides
    an overall assessment of the idea's merit based on the
    quality of the adversarial discussion.

    Attributes:
        idea_id: ID of the idea that was debated
        round_evaluations: Evaluation for each debate round
        overall_quality_score: Overall quality of the debate (0-100)
        consensus_strength: How strong the consensus is (0-100)
        winner_round: Which round had the strongest arguments
        final_verdict: Judge's final verdict on the idea
        confidence_score: Judge's confidence in the verdict (0-100)
        recommendation: Final recommendation (accept/reject/revise)
        timestamp: When the evaluation was completed

    """

    idea_id: str = Field(
        ...,
        description="ID of the idea that was debated"
    )
    round_evaluations: list[RoundEvaluation] = Field(
        ...,
        description="Evaluation for each debate round"
    )
    overall_quality_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Overall quality of the debate (0-100)"
    )
    consensus_strength: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="How strong the consensus is (0-100)"
    )
    winner_round: DebateRound = Field(
        ...,
        description="Which round had the strongest arguments"
    )
    final_verdict: str = Field(
        ...,
        description="Judge's final verdict on the idea"
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Judge's confidence in the verdict (0-100)"
    )
    recommendation: str = Field(
        ...,
        description="Final recommendation (accept/reject/revise)"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When evaluation was completed"
    )

    @field_validator("round_evaluations")
    @classmethod
    def validate_rounds(cls, v: list[RoundEvaluation]) -> list[RoundEvaluation]:
        """Ensure all 3 rounds are present."""
        if len(v) != 3:
            raise ValueError("Must have exactly 3 round evaluations")
        return v

    @field_validator("recommendation")
    @classmethod
    def validate_recommendation(cls, v: str) -> str:
        """Ensure recommendation is valid."""
        valid = {"accept", "reject", "revise"}
        if v.lower() not in valid:
            raise ValueError(f"Recommendation must be one of {valid}")
        return v.lower()


class DebatedIdea(BaseModel):
    """
    An idea that has undergone multi-agent adversarial debate.

    Extends the base Idea with debate contributions, evaluations,
    and consensus scores from the adversarial process.

    Attributes:
        original: The original idea before debate
        pro_arguments: Arguments in favor of the idea
        con_arguments: Arguments against the idea
        rebuttals: Counter-arguments to the con arguments
        contributions: All round contributions with metadata
        round_evaluations: Judge evaluation for each round
        debate_evaluation: Comprehensive debate evaluation
        judge_score: Final score assigned by the Judge (0-100)
        consensus_score: Score from multi-agent voting/consensus (0-100)
        final_score: Combined score (weighted average of judge and consensus)
        recommendation: Final recommendation (accept/reject/revise)
        debate_metadata: Additional information about the debate

    """

    original: Idea = Field(
        ...,
        description="The original idea before debate"
    )
    pro_arguments: list[str] = Field(
        default_factory=list,
        description="Arguments in favor of the idea"
    )
    con_arguments: list[str] = Field(
        default_factory=list,
        description="Arguments against the idea"
    )
    rebuttals: list[str] = Field(
        default_factory=list,
        description="Counter-arguments to the con arguments"
    )
    contributions: list[RoundContribution] = Field(
        default_factory=list,
        description="All round contributions with metadata"
    )
    round_evaluations: list[RoundEvaluation] = Field(
        default_factory=list,
        description="Judge evaluation for each round"
    )
    debate_evaluation: DebateEvaluation | None = Field(
        default=None,
        description="Comprehensive debate evaluation"
    )
    judge_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Final score assigned by the Judge (0-100)"
    )
    consensus_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Score from multi-agent voting/consensus (0-100)"
    )
    final_score: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Combined score (weighted average)"
    )
    recommendation: str = Field(
        default="revise",
        description="Final recommendation (accept/reject/revise)"
    )
    debate_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional information about the debate"
    )

    def calculate_final_score(
        self,
        judge_weight: float = 0.6,
        consensus_weight: float = 0.4
    ) -> None:
        """
        Calculate the final score as weighted average of judge and consensus.

        Args:
            judge_weight: Weight for judge score (default: 0.6)
            consensus_weight: Weight for consensus score (default: 0.4)

        """
        self.final_score = (
            self.judge_score * judge_weight +
            self.consensus_score * consensus_weight
        )

    @property
    def id(self) -> str:
        """Get the ID from the original idea."""
        return self.original.id

    def to_evaluation(self) -> Evaluation:
        """
        Convert debated idea to a standard Evaluation.

        Returns:
            Evaluation object with debate-informed scores

        """
        return Evaluation(
            idea_id=self.original.id,
            novelty_score=self.final_score * 0.9,  # Debated ideas are refined
            feasibility_score=self.final_score * 0.95,  # Debate exposes issues
            impact_score=self.final_score,
            overall_score=self.final_score,
            arguments_pro=self.pro_arguments,
            arguments_con=self.con_arguments,
            evaluator="debate_judge_and_consensus"
        )


class DebateConfig(BaseModel):
    """
    Configuration for a debate session.

    Defines parameters for how debates should be conducted,
    including number of rounds, timeouts, and scoring weights.

    Attributes:
        num_rounds: Number of debate rounds (default: 3)
        round_timeout: Timeout per round in seconds (default: 30.0)
        judge_weight: Weight for judge score in final calculation (default: 0.6)
        consensus_weight: Weight for consensus score in final calculation (default: 0.4)
        voting_strategy: Strategy for building consensus (default: "weighted")
        enable_refinement: Whether to refine scores based on debate quality (default: True)
        quality_threshold: Minimum debate quality to accept idea (default: 60.0)

    """

    num_rounds: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Number of debate rounds"
    )
    round_timeout: float = Field(
        default=30.0,
        ge=5.0,
        le=120.0,
        description="Timeout per round in seconds"
    )
    judge_weight: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Weight for judge score"
    )
    consensus_weight: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Weight for consensus score"
    )
    voting_strategy: str = Field(
        default="weighted",
        description="Strategy for building consensus"
    )
    enable_refinement: bool = Field(
        default=True,
        description="Whether to refine scores based on debate quality"
    )
    quality_threshold: float = Field(
        default=60.0,
        ge=0.0,
        le=100.0,
        description="Minimum debate quality to accept idea"
    )

    @field_validator("voting_strategy")
    @classmethod
    def validate_voting_strategy(cls, v: str) -> str:
        """Ensure voting strategy is valid."""
        valid = {"majority", "weighted", "unanimous", "borda"}
        if v.lower() not in valid:
            raise ValueError(f"Voting strategy must be one of {valid}")
        return v.lower()


__all__ = [
    "DebateConfig",
    "DebateEvaluation",
    "DebateRound",
    "DebatedIdea",
    "RoundContribution",
    "RoundEvaluation",
]
