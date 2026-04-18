"""
Realised-Value Replay Buffer Package

This package implements a replay buffer system for storing and retrieving
successful ideas from previous brainstorming sessions.

Usage:
    from ..replay import (
        ReplayRecord,
        ReplayBuffer,
        get_global_buffer,
    )

    buffer = get_global_buffer()
    buffer.add_from_session(session_id, topic, ideas)
    candidates = buffer.find_candidates(topic)
"""
from __future__ import annotations

from .buffer import ReplayBuffer, get_global_buffer
from .models import (
    ReplayCandidate,
    ReplayRecord,
    ReplayStatus,
    ReplaySummary,
)

__all__ = [
    # Models
    "ReplayStatus",
    "ReplayRecord",
    "ReplayCandidate",
    "ReplaySummary",
    # Buffer
    "ReplayBuffer",
    "get_global_buffer",
]
