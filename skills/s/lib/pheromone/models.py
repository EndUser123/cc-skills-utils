"""
Pheromone Trail Models - Tracking Successful Exploration Paths

This module defines the data models for tracking which exploration paths
lead to successful ideas, enabling future sessions to follow "scent trails"
toward fruitful ideation areas.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class PathSegmentType(str, Enum):
    """Types of segments in an exploration path."""

    # Initial topic/entry point
    TOPIC = "topic"

    # Persona choice
    PERSONA = "persona"

    # Reasoning direction
    DIRECTION = "direction"

    # Semantic domain shift
    DOMAIN_SHIFT = "domain"

    # Creative technique used
    TECHNIQUE = "technique"


@dataclass
class PathSegment:
    """
    A single segment of an exploration path.

    Segments represent decision points or steps in the ideation process.

    Attributes:
        segment_type: Type of path segment
        value: The actual value (e.g., "innovator", "healthcare", "lateral thinking")
        weight: Importance weight for this segment (0-1)
    """
    segment_type: PathSegmentType
    value: str
    weight: float = 1.0

    def signature(self) -> str:
        """Generate a unique signature for this segment."""
        content = f"{self.segment_type.value}:{self.value.lower()}"
        return hashlib.md5(content.encode()).hexdigest()[:8]

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "segment_type": self.segment_type.value,
            "value": self.value,
            "weight": self.weight,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PathSegment:
        """Create from dictionary storage."""
        return cls(
            segment_type=PathSegmentType(data["segment_type"]),
            value=data["value"],
            weight=data.get("weight", 1.0),
        )


@dataclass
class PathSignature:
    """
    A unique signature for an exploration path.

    The signature identifies the "shape" of an exploration independent
    of specific content, allowing us to track which exploration patterns
    lead to success.

    Attributes:
        segments: List of path segments defining this signature
        hash: Unique hash for this signature
        created_at: When this signature was first seen
    """
    segments: list[PathSegment] = field(default_factory=list)
    hash: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def __post_init__(self):
        """Generate hash from segments after initialization."""
        if not self.hash and self.segments:
            content = "|".join(f"{s.segment_type.value}:{s.value}" for s in self.segments)
            self.hash = hashlib.md5(content.encode()).hexdigest()[:12]

    @classmethod
    def from_idea(
        cls,
        topic: str,
        persona: str,
        reasoning_path: list[str],
        domains: list[str] | None = None,
    ) -> PathSignature:
        """
        Create a path signature from an idea and its generation context.

        Args:
            topic: The original brainstorm topic
            persona: Persona that generated the idea
            reasoning_path: Reasoning steps taken
            domains: Detected domain keywords

        Returns:
            A PathSignature representing this exploration path
        """
        segments = [
            PathSegment(PathSegmentType.TOPIC, topic[:50], weight=0.5),
            PathSegment(PathSegmentType.PERSONA, persona, weight=1.0),
        ]

        # Extract key directions from reasoning path
        if reasoning_path:
            # Use first and last reasoning steps as key direction markers
            if len(reasoning_path) > 0:
                first_step = reasoning_path[0][:30]
                segments.append(PathSegment(PathSegmentType.DIRECTION, first_step, weight=0.8))

            if len(reasoning_path) > 1:
                last_step = reasoning_path[-1][:30]
                segments.append(PathSegment(PathSegmentType.DIRECTION, last_step, weight=0.6))

        # Add domains if provided
        if domains:
            for domain in domains[:3]:  # Limit to top 3 domains
                segments.append(PathSegment(PathSegmentType.DOMAIN_SHIFT, domain, weight=0.7))

        return cls(segments=segments)

    def similarity(self, other: PathSignature) -> float:
        """
        Calculate similarity between two path signatures.

        Uses weighted Jaccard similarity on segment types.

        Args:
            other: Another path signature

        Returns:
            Similarity score (0-1)
        """
        if not self.segments or not other.segments:
            return 0.0

        # Create weighted sets
        self_set = {(s.segment_type, s.value): s.weight for s in self.segments}
        other_set = {(s.segment_type, s.value): s.weight for s in other.segments}

        # Calculate weighted Jaccard
        all_keys = set(self_set.keys()) | set(other_set.keys())

        if not all_keys:
            return 0.0

        intersection_sum = sum(min(self_set.get(k, 0), other_set.get(k, 0)) for k in all_keys)
        union_sum = sum(max(self_set.get(k, 0), other_set.get(k, 0)) for k in all_keys)

        return intersection_sum / union_sum if union_sum > 0 else 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "segments": [s.to_dict() for s in self.segments],
            "hash": self.hash,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PathSignature:
        """Create from dictionary storage."""
        return cls(
            segments=[PathSegment.from_dict(s) for s in data.get("segments", [])],
            hash=data.get("hash", ""),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )


@dataclass
class PheromoneNode:
    """
    A node in the pheromone trail graph.

    Nodes represent exploration states with accumulated pheromone strength.

    Attributes:
        id: Unique identifier
        signature_hash: Hash of the path signature this node represents
        pheromone_strength: Current pheromone level (0-1000)
        deposit_count: Number of times pheromones were deposited
        last_deposit: Timestamp of most recent deposit
        last_evaporation: Timestamp of most recent evaporation
        success_scores: List of scores that contributed to this node
        metadata: Additional data about this node
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    signature_hash: str = ""
    pheromone_strength: float = 0.0
    deposit_count: int = 0
    last_deposit: str = ""
    last_evaporation: str = field(default_factory=lambda: datetime.now().isoformat())
    success_scores: list[float] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Constants
    MAX_STRENGTH = 1000.0
    EVAPORATION_RATE = 0.95  # Retains 95% per day
    DEPOSIT_AMOUNT = 100.0  # Base deposit per successful idea

    @property
    def avg_success(self) -> float:
        """Average success score for this node."""
        if not self.success_scores:
            return 0.0
        return sum(self.success_scores) / len(self.success_scores)

    @property
    def age_hours(self) -> float:
        """Hours since last deposit."""
        if not self.last_deposit:
            return 0.0
        try:
            deposit_time = datetime.fromisoformat(self.last_deposit)
            age = datetime.now() - deposit_time
            return age.total_seconds() / 3600
        except (ValueError, OSError):
            return 0.0

    def deposit(self, score: float, weight: float = 1.0) -> float:
        """
        Deposit pheromones from a successful outcome.

        Args:
            score: Success score (0-100) of the outcome
            weight: Multiplier for deposit amount

        Returns:
            New pheromone strength
        """
        # Deposit amount scales with score and weight
        amount = self.DEPOSIT_AMOUNT * (score / 100.0) * weight

        # Add to strength (capped at MAX)
        self.pheromone_strength = min(self.MAX_STRENGTH, self.pheromone_strength + amount)
        self.deposit_count += 1
        self.last_deposit = datetime.now().isoformat()
        self.success_scores.append(score)

        return self.pheromone_strength

    def evaporate(self, hours_passed: float | None = None) -> float:
        """
        Apply evaporation to pheromone strength.

        Args:
            hours_passed: Hours since last evaporation (uses age if None)

        Returns:
            New pheromone strength
        """
        if hours_passed is None:
            hours_passed = self.age_hours

        # Evaporation formula: strength = strength * rate^(hours/24)
        # Rate is applied per day, so we adjust for hours
        daily_rate = self.EVAPORATION_RATE
        days_passed = hours_passed / 24.0
        decay_factor = daily_rate ** days_passed

        self.pheromone_strength *= decay_factor
        self.last_evaporation = datetime.now().isoformat()

        return self.pheromone_strength

    @property
    def is_fresh(self) -> bool:
        """Check if this node has recent deposits (< 7 days)."""
        if not self.last_deposit:
            return False
        return self.age_hours < 168

    @property
    def is_strong(self) -> bool:
        """Check if this node has significant pheromone strength."""
        return self.pheromone_strength > 200.0

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "signature_hash": self.signature_hash,
            "pheromone_strength": self.pheromone_strength,
            "deposit_count": self.deposit_count,
            "last_deposit": self.last_deposit,
            "last_evaporation": self.last_evaporation,
            "success_scores": self.success_scores,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PheromoneNode:
        """Create from dictionary storage."""
        return cls(
            id=data["id"],
            signature_hash=data["signature_hash"],
            pheromone_strength=data.get("pheromone_strength", 0.0),
            deposit_count=data.get("deposit_count", 0),
            last_deposit=data.get("last_deposit", ""),
            last_evaporation=data.get("last_evaporation", ""),
            success_scores=data.get("success_scores", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ExplorationGuidance:
    """
    Guidance for exploration based on pheromone trails.

    Provides recommendations for which paths to explore.

    Attributes:
        suggested_personas: Personas with high pheromone for this topic
        suggested_domains: Domains that have been successful
        suggested_directions: Reasoning directions to try
        avoid_paths: Paths with weak or negative pheromone
        confidence: How confident the guidance is (0-1)
    """
    suggested_personas: list[tuple[str, float]] = field(default_factory=list)  # (persona, strength)
    suggested_domains: list[tuple[str, float]] = field(default_factory=list)
    suggested_directions: list[tuple[str, float]] = field(default_factory=list)
    avoid_paths: list[str] = field(default_factory=list)
    confidence: float = 0.0
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "suggested_personas": self.suggested_personas,
            "suggested_domains": self.suggested_domains,
            "suggested_directions": self.suggested_directions,
            "avoid_paths": self.avoid_paths,
            "confidence": self.confidence,
            "generated_at": self.generated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ExplorationGuidance:
        """Create from dictionary."""
        return cls(
            suggested_personas=data.get("suggested_personas", []),
            suggested_domains=data.get("suggested_domains", []),
            suggested_directions=data.get("suggested_directions", []),
            avoid_paths=data.get("avoid_paths", []),
            confidence=data.get("confidence", 0.0),
            generated_at=data.get("generated_at", datetime.now().isoformat()),
        )
