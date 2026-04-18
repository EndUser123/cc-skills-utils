"""
Realised-Value Replay Buffer Models

This module defines the data models for the replay buffer system that stores
and retrieves successful ideas from previous brainstorming sessions.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ReplayStatus(str, Enum):
    """Status of a replayed idea."""

    # Never replayed
    FRESH = "fresh"

    # Replayed with success
    SUCCESS = "success"

    # Replayed but needs adaptation
    ADAPTED = "adapted"

    # Replayed but failed/not useful
    FAILED = "failed"


@dataclass
class ReplayRecord:
    """
    A record of an idea stored in the replay buffer.

    Tracks successful ideas from previous sessions and their realized value
    when replayed in new contexts.

    Attributes:
        id: Unique identifier
        original_idea_id: ID of the original idea
        content: The idea content
        persona: Persona that generated the idea
        reasoning_path: Original reasoning steps
        original_score: Score from original session
        contexts_used: List of context topics where this was used
        success_scores: List of realized success scores
        replay_count: Total number of times replayed
        success_count: Number of successful replays
        adaptation_history: How this idea was adapted
        tags: Searchable tags
        status: Current replay status
        created_at: When first stored
        last_replayed: Most recent replay
        effectiveness_trend: Recent success scores (latest first)
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    original_idea_id: str = ""
    content: str = ""
    persona: str = ""
    reasoning_path: list[str] = field(default_factory=list)
    original_score: float = 0.0

    # Tracking
    contexts_used: list[str] = field(default_factory=list)
    success_scores: list[float] = field(default_factory=list)
    replay_count: int = 0
    success_count: int = 0
    adaptation_history: list[dict] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    status: ReplayStatus = ReplayStatus.FRESH

    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_replayed: str = ""
    effectiveness_trend: list[float] = field(default_factory=list)

    # Constants
    MIN_SUCCESS_SCORE = 60.0
    MIN_REPLAYS_FOR_TREND = 3

    @property
    def avg_success(self) -> float:
        """Average realized success score."""
        if not self.success_scores:
            return 0.0
        return sum(self.success_scores) / len(self.success_scores)

    @property
    def success_rate(self) -> float:
        """Success rate as ratio (0-1)."""
        if self.replay_count == 0:
            return 0.0
        return self.success_count / self.replay_count

    @property
    def effectiveness(self) -> float:
        """
        Overall effectiveness score (0-100).

        Combines average success with success rate and recency bonus.
        """
        if self.replay_count == 0:
            return self.original_score

        base = self.avg_success * 0.6 + self.success_rate * 100 * 0.4

        # Recency bonus: more recent successes weighted higher
        if len(self.effectiveness_trend) >= 2:
            recent_avg = sum(self.effectiveness_trend[:3]) / min(3, len(self.effectiveness_trend))
            recency_bonus = (recent_avg - self.avg_success) * 0.2
            base = max(0, min(100, base + recency_bonus))

        return base

    @property
    def is_proven(self) -> bool:
        """Check if this idea has proven success (multiple replays, good scores)."""
        return (
            self.replay_count >= 2 and
            self.success_rate >= 0.5 and
            self.avg_success >= self.MIN_SUCCESS_SCORE
        )

    @property
    def age_hours(self) -> float:
        """Hours since creation."""
        try:
            created = datetime.fromisoformat(self.created_at)
            age = datetime.now() - created
            return age.total_seconds() / 3600
        except (ValueError, OSError):
            return 0.0

    def record_replay(
        self,
        context_topic: str,
        success_score: float,
        adaptation: str | None = None,
    ) -> None:
        """
        Record a replay event.

        Args:
            context_topic: The topic this was replayed in
            success_score: How successful the replay was (0-100)
            adaptation: Optional description of how the idea was adapted
        """
        self.replay_count += 1
        self.last_replayed = datetime.now().isoformat()

        if success_score >= self.MIN_SUCCESS_SCORE:
            self.success_count += 1
            self.status = ReplayStatus.SUCCESS
        elif success_score >= 40.0:
            self.status = ReplayStatus.ADAPTED
        else:
            self.status = ReplayStatus.FAILED

        self.success_scores.append(success_score)
        self.effectiveness_trend.insert(0, success_score)  # Prepend for latest-first

        # Keep trend at reasonable size
        if len(self.effectiveness_trend) > 10:
            self.effectiveness_trend = self.effectiveness_trend[:10]

        if context_topic and context_topic not in self.contexts_used:
            self.contexts_used.append(context_topic)

        if adaptation:
            self.adaptation_history.append({
                "context": context_topic,
                "adaptation": adaptation,
                "score": success_score,
                "timestamp": self.last_replayed,
            })

    def adapt_to_context(self, new_context: str) -> str:
        """
        Generate adapted content for a new context.

        Args:
            new_context: The new topic/context

        Returns:
            Adapted idea content
        """
        # Find most similar previous context
        best_adaptation = None
        if self.adaptation_history:
            best_adaptation = self.adaptation_history[0]

        # Start with original content
        adapted = self.content

        # If we have successful adaptations, use their patterns
        if best_adaptation and best_adaptation.get("score", 0) >= 60:
            adaptation_note = best_adaptation.get("adaptation", "")
            if adaptation_note:
                adapted = f"{adapted} (Previously adapted: {adaptation_note})"

        return adapted

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "original_idea_id": self.original_idea_id,
            "content": self.content,
            "persona": self.persona,
            "reasoning_path": self.reasoning_path,
            "original_score": self.original_score,
            "contexts_used": self.contexts_used,
            "success_scores": self.success_scores,
            "replay_count": self.replay_count,
            "success_count": self.success_count,
            "adaptation_history": self.adaptation_history,
            "tags": self.tags,
            "status": self.status.value,
            "created_at": self.created_at,
            "last_replayed": self.last_replayed,
            "effectiveness_trend": self.effectiveness_trend,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ReplayRecord:
        """Create from dictionary storage."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            original_idea_id=data.get("original_idea_id", ""),
            content=data.get("content", ""),
            persona=data.get("persona", ""),
            reasoning_path=data.get("reasoning_path", []),
            original_score=data.get("original_score", 0.0),
            contexts_used=data.get("contexts_used", []),
            success_scores=data.get("success_scores", []),
            replay_count=data.get("replay_count", 0),
            success_count=data.get("success_count", 0),
            adaptation_history=data.get("adaptation_history", []),
            tags=data.get("tags", []),
            status=ReplayStatus(data.get("status", "fresh")),
            created_at=data.get("created_at", datetime.now().isoformat()),
            last_replayed=data.get("last_replayed", ""),
            effectiveness_trend=data.get("effectiveness_trend", []),
        )

    @classmethod
    def from_idea(
        cls,
        idea_id: str,
        content: str,
        persona: str,
        reasoning_path: list[str],
        score: float,
        tags: list[str] | None = None,
    ) -> ReplayRecord:
        """Create a replay record from an Idea."""
        return cls(
            original_idea_id=idea_id,
            content=content,
            persona=persona,
            reasoning_path=reasoning_path,
            original_score=score,
            tags=tags or [],
        )


@dataclass
class ReplayCandidate:
    """
    A candidate idea from the replay buffer for current session.

    Attributes:
        record: The underlying replay record
        similarity_score: How similar to current topic (0-1)
        relevance_score: Combined relevance metric (0-1)
        adapted_content: Content adapted for current context
        replay_reason: Why this was suggested
    """
    record: ReplayRecord
    similarity_score: float = 0.0
    relevance_score: float = 0.0
    adapted_content: str = ""
    replay_reason: str = ""

    @property
    def priority(self) -> float:
        """Priority score for ranking (higher = better)."""
        # Combine effectiveness, relevance, and success rate
        return (
            self.record.effectiveness * 0.4 +
            self.relevance_score * 100 * 0.4 +
            self.record.success_rate * 100 * 0.2
        )

    def to_idea_dict(self) -> dict:
        """Convert to idea-like dictionary for integration."""
        return {
            "content": self.adapted_content or self.record.content,
            "persona": self.record.persona,
            "reasoning_path": self.record.reasoning_path + [
                f"[Replayed from previous success with {self.record.original_score:.0f} score]"
            ],
            "score": self.record.effectiveness,
            "metadata": {
                "replay_source": self.record.id,
                "original_idea_id": self.record.original_idea_id,
                "similarity": self.similarity_score,
                "replay_reason": self.replay_reason,
            },
        }


@dataclass
class ReplaySummary:
    """
    Summary statistics for the replay buffer.

    Attributes:
        total_records: Total number of stored ideas
        proven_records: Number of proven (multi-success) ideas
        avg_replay_count: Average replays per idea
        avg_success_rate: Average success rate across all
        top_personas: Most successful personas
        freshness_ratio: Ratio of fresh vs replayed ideas
    """
    total_records: int = 0
    proven_records: int = 0
    avg_replay_count: float = 0.0
    avg_success_rate: float = 0.0
    top_personas: list[tuple[str, float]] = field(default_factory=list)
    freshness_ratio: float = 0.0
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_records": self.total_records,
            "proven_records": self.proven_records,
            "avg_replay_count": self.avg_replay_count,
            "avg_success_rate": self.avg_success_rate,
            "top_personas": self.top_personas,
            "freshness_ratio": self.freshness_ratio,
            "generated_at": self.generated_at,
        }
