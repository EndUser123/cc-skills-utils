"""
Pheromone Trail Package - Tracking Successful Exploration Paths

This package implements a pheromone trail system inspired by ant colony
optimization. It tracks which exploration paths lead to successful ideas
and guides future sessions toward fruitful areas.

Usage:
    from ..pheromone import (
        PheromoneTrail,
        PathSignature,
        get_global_trail,
    )

    trail = get_global_trail()
    trail.deposit_from_session(...)
    guidance = trail.get_guidance("topic")
"""
from __future__ import annotations

from .models import (
    ExplorationGuidance,
    PathSegment,
    PathSegmentType,
    PathSignature,
    PheromoneNode,
)
from .trail import PheromoneTrail, get_global_trail

__all__ = [
    # Models
    "PathSegmentType",
    "PathSegment",
    "PathSignature",
    "PheromoneNode",
    "ExplorationGuidance",
    # Trail
    "PheromoneTrail",
    "get_global_trail",
]
