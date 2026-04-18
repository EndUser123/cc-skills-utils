"""
Data Models for Brainstorm System

This module defines the core data structures used throughout the brainstorming system.
All models use Pydantic v2 for validation, serialization, and type safety.

Key Models:
- Idea: Represents a generated idea with metadata and scores
- Evaluation: Detailed assessment of an idea across multiple dimensions
- BrainstormContext: Configuration and context for brainstorming sessions
- BrainstormResult: Aggregated results from a brainstorming session
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Idea(BaseModel):
    """
    Represents a single idea generated during brainstorming.

    An idea includes the core content, the persona that generated it,
    the reasoning path taken to develop it, and various scores for ranking.

    Attributes:
        id: Unique identifier for the idea (UUID4)
        content: The main idea description or proposal
        persona: The agent persona that generated this idea
        reasoning_path: Sequential steps or thoughts that led to this idea
        score: Overall score for ranking purposes (0-100)
        next_action: Concrete next step to execute this idea
        estimated_minutes: Estimated time to complete next action (5-480 min)
        metadata: Additional flexible data about the idea
        confidence: Agent's confidence in this idea (0-1 scale) for turn-taking
        confidence_rationale: Explanation for the confidence score

    Example:
        ```python
        idea = Idea(
            content="Implement a bike-sharing system with solar-powered stations",
            persona="innovator",
            reasoning_path=[
                "Consider sustainable transportation",
                "Identify bikes as low-emission option",
                "Add solar power for sustainability",
                "Propose sharing model for accessibility"
            ],
            score=85.0,
            confidence=0.9,
            confidence_rationale="High novelty with clear implementation path",
            metadata={"category": "transportation", "emissions_impact": "high"}
        )
        ```
    """

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="Unique identifier for the idea"
    )
    content: str = Field(..., min_length=10, description="The main idea description or proposal")
    persona: str = Field(..., description="The agent persona that generated this idea")
    reasoning_path: list[str] = Field(
        default_factory=list, description="Sequential steps or thoughts that led to this idea"
    )
    score: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Overall score for ranking purposes (0-100)"
    )
    next_action: None | str = Field(
        default=None, description="Concrete next step to execute this idea (actionability)"
    )
    estimated_minutes: int = Field(
        default=60,
        ge=5,
        le=480,
        description="Estimated time to complete the next action (in minutes)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional flexible data about the idea"
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Agent's confidence in this idea (0-1 scale) for turn-taking",
    )
    confidence_rationale: str = Field(
        default="",
        description="Explanation for the confidence score (specificity, consistency, relevance, uniqueness)",
    )

    @field_validator("content")
    @classmethod
    def content_must_be_meaningful(cls, v: str) -> str:
        """Validate that content is not just whitespace."""
        if not v.strip():
            raise ValueError("Content cannot be empty or whitespace only")
        return v.strip()

    @field_validator("reasoning_path")
    @classmethod
    def reasoning_steps_must_be_valid(cls, v: list[str]) -> list[str]:
        """Validate that reasoning steps are not empty."""
        return [step.strip() for step in v if step.strip()]

    def add_reasoning_step(self, step: str) -> None:
        """
        Add a reasoning step to the idea's development path.

        Args:
            step: The reasoning step or thought to add
        """
        if step.strip():
            self.reasoning_path.append(step.strip())

    def update_score(self, new_score: float) -> None:
        """
        Update the idea's score, ensuring it stays within valid range.

        Args:
            new_score: The new score value (0-100)
        """
        self.score = max(0.0, min(100.0, new_score))


class Evaluation(BaseModel):
    """
    Detailed evaluation and assessment of an idea.

    Evaluations provide multi-dimensional scoring and qualitative arguments
    for and against an idea, enabling comprehensive assessment.

    Attributes:
        idea_id: ID of the idea being evaluated
        novelty_score: How novel or unique the idea is (0-100)
        feasibility_score: How practical or implementable the idea is (0-100)
        impact_score: Potential positive impact if implemented (0-100)
        overall_score: Weighted combination of all scores (0-100)
        arguments_pro: List of positive arguments or strengths
        arguments_con: List of negative arguments or weaknesses
        evaluator: Optional identifier for who/what performed the evaluation

    Example:
        ```python
        evaluation = Evaluation(
            idea_id="abc-123",
            novelty_score=85.0,
            feasibility_score=60.0,
            impact_score=90.0,
            overall_score=78.3,
            arguments_pro=[
                "High environmental benefit",
                "Scalable solution",
                "Low operating costs"
            ],
            arguments_con=[
                "High initial investment",
                "Requires infrastructure changes",
                "Weather dependent"
            ]
        )
        ```
    """

    idea_id: str = Field(..., description="ID of the idea being evaluated")
    novelty_score: float = Field(
        ..., ge=0.0, le=100.0, description="How novel or unique the idea is (0-100)"
    )
    feasibility_score: float = Field(
        ..., ge=0.0, le=100.0, description="How practical or implementable the idea is (0-100)"
    )
    impact_score: float = Field(
        ..., ge=0.0, le=100.0, description="Potential positive impact if implemented (0-100)"
    )
    overall_score: float = Field(
        ..., ge=0.0, le=100.0, description="Weighted combination of all scores (0-100)"
    )
    arguments_pro: list[str] = Field(
        default_factory=list, description="List of positive arguments or strengths"
    )
    arguments_con: list[str] = Field(
        default_factory=list, description="List of negative arguments or weaknesses"
    )
    evaluator: None | str = Field(
        default=None, description="Optional identifier for who/what performed the evaluation"
    )

    @field_validator("arguments_pro", "arguments_con")
    @classmethod
    def clean_arguments(cls, v: list[str]) -> list[str]:
        """Remove empty or whitespace-only arguments."""
        return [arg.strip() for arg in v if arg.strip()]

    @classmethod
    def from_scores(
        cls,
        idea_id: str,
        novelty: float,
        feasibility: float,
        impact: float,
        arguments_pro: None | list[str] = None,
        arguments_con: None | list[str] = None,
        weights: None | dict[str, float] = None,
        evaluator: None | str = None,
    ) -> "Evaluation":
        """
        Create an evaluation with automatic overall score calculation.

        Args:
            idea_id: ID of the idea being evaluated
            novelty: Novelty score (0-100)
            feasibility: Feasibility score (0-100)
            impact: Impact score (0-100)
            arguments_pro: Optional list of positive arguments
            arguments_con: Optional list of negative arguments
            weights: Optional custom weights for scoring calculation.
                     Default: {"novelty": 0.3, "feasibility": 0.3, "impact": 0.4}
            evaluator: Optional identifier for the evaluator

        Returns:
            A new Evaluation instance with calculated overall score
        """
        if weights is None:
            weights = {"novelty": 0.3, "feasibility": 0.3, "impact": 0.4}

        overall = (
            novelty * weights.get("novelty", 0.3)
            + feasibility * weights.get("feasibility", 0.3)
            + impact * weights.get("impact", 0.4)
        )

        return cls(
            idea_id=idea_id,
            novelty_score=novelty,
            feasibility_score=feasibility,
            impact_score=impact,
            overall_score=overall,
            arguments_pro=arguments_pro or [],
            arguments_con=arguments_con or [],
            evaluator=evaluator,
        )


class BrainstormContext(BaseModel):
    """
    Configuration and context for a brainstorming session.

    Defines the parameters, constraints, and goals for an ideation session.

    Attributes:
        topic: The main topic or problem to brainstorm about
        num_ideas: Target number of ideas to generate
        personas: List of persona names to use for generation
        constraints: Optional list of constraints or requirements
        goals: Optional list of specific goals to achieve
        timeout_seconds: Optional timeout for the brainstorming session
        fresh_mode: If True, agents must NOT read existing plans/solutions (prevents anchoring bias)
        metadata: Additional context or parameters

    Example:
        ```python
        context = BrainstormContext(
            topic="Improve remote team collaboration",
            num_ideas=15,
            personas=["innovator", "pragmatist", "critic"],
            constraints=["Must be GDPR compliant", "Budget under $50k"],
            goals=["Increase engagement by 30%", "Reduce meeting time"],
            fresh_mode=True  # Generate ideas without reading existing plans
        )
        ```
    """

    topic: str = Field(
        ..., min_length=5, description="The main topic or problem to brainstorm about"
    )
    num_ideas: int = Field(
        default=10, ge=1, le=100, description="Target number of ideas to generate"
    )
    personas: list[str] = Field(
        default_factory=lambda: ["innovator", "pragmatist", "critic"],
        description="List of persona names to use for generation",
    )
    constraints: list[str] = Field(
        default_factory=list, description="Optional list of constraints or requirements"
    )
    goals: list[str] = Field(
        default_factory=list, description="Optional list of specific goals to achieve"
    )
    timeout_seconds: None | int = Field(
        default=None, ge=1, description="Optional timeout for the brainstorming session"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional context or parameters"
    )
    fresh_mode: bool = Field(
        default=False,
        description="If True, agents must NOT read existing plans/solutions (prevents anchoring bias)",
    )

    @field_validator("topic")
    @classmethod
    def topic_must_be_meaningful(cls, v: str) -> str:
        """Validate that topic is not just whitespace."""
        if not v.strip():
            raise ValueError("Topic cannot be empty or whitespace only")
        return v.strip()


class BrainstormResult(BaseModel):
    """
    Aggregated results from a brainstorming session.

    Contains all generated ideas, their evaluations, and metadata about
    the brainstorming process.

    Attributes:
        ideas: All ideas generated during the session
        evaluations: Evaluations for each idea
        context: The original context used for generation
        session_id: Unique identifier for this brainstorming session
        timestamp: When the brainstorming session completed
        metadata: Additional information about the session
        metrics: Execution metrics (timings, counts, phase)

    Example:
        ```python
        # Get top 5 ideas by score
        top_ideas = result.top_ideas(5)

        # Get average scores
        avg_novelty = result.average_novelty()
        avg_feasibility = result.average_feasibility()

        # Get ideas by persona
        innovator_ideas = result.get_ideas_by_persona("innovator")
        ```
    """

    ideas: list[Idea] = Field(
        default_factory=list, description="All ideas generated during the session"
    )
    evaluations: dict[str, Evaluation] = Field(
        default_factory=dict, description="Evaluations for each idea (keyed by idea_id)"
    )
    context: BrainstormContext = Field(..., description="The original context used for generation")
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this brainstorming session",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When the brainstorming session completed"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional information about the session"
    )
    metrics: dict[str, Any] = Field(
        default_factory=dict, description="Execution metrics (timings, counts, phase)"
    )

    def add_idea(self, idea: Idea) -> None:
        """
        Add an idea to the results.

        Args:
            idea: The idea to add
        """
        self.ideas.append(idea)

    def add_evaluation(self, evaluation: Evaluation) -> None:
        """
        Add an evaluation for an idea.

        Args:
            evaluation: The evaluation to add
        """
        self.evaluations[evaluation.idea_id] = evaluation

    def top_ideas(self, n: int = 5) -> list[Idea]:
        """
        Get the top N ideas by score.

        Args:
            n: Number of top ideas to return

        Returns:
            List of the highest-scoring ideas
        """
        return sorted(self.ideas, key=lambda x: x.score, reverse=True)[:n]

    def get_ideas_by_persona(self, persona: str) -> list[Idea]:
        """
        Get all ideas generated by a specific persona.

        Args:
            persona: The persona name to filter by

        Returns:
            List of ideas from the specified persona
        """
        return [idea for idea in self.ideas if idea.persona == persona]

    def average_novelty(self) -> float:
        """
        Calculate the average novelty score across all evaluations.

        Returns:
            Average novelty score (0-100), or 0 if no evaluations
        """
        if not self.evaluations:
            return 0.0
        return sum(ev.novelty_score for ev in self.evaluations.values()) / len(self.evaluations)

    def average_feasibility(self) -> float:
        """
        Calculate the average feasibility score across all evaluations.

        Returns:
            Average feasibility score (0-100), or 0 if no evaluations
        """
        if not self.evaluations:
            return 0.0
        return sum(ev.feasibility_score for ev in self.evaluations.values()) / len(self.evaluations)

    def average_impact(self) -> float:
        """
        Calculate the average impact score across all evaluations.

        Returns:
            Average impact score (0-100), or 0 if no evaluations
        """
        if not self.evaluations:
            return 0.0
        return sum(ev.impact_score for ev in self.evaluations.values()) / len(self.evaluations)

    @property
    def total_ideas(self) -> int:
        """Get the total number of ideas generated."""
        return len(self.ideas)

    @property
    def total_evaluations(self) -> int:
        """Get the total number of evaluations performed."""
        return len(self.evaluations)


__all__ = [
    "Idea",
    "Evaluation",
    "BrainstormContext",
    "BrainstormResult",
]
