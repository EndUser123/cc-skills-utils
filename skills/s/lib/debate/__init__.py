"""
Multi-Agent Debate Framework for Phase 2 Discussion

This package implements adversarial debate between multiple agent personas
to stress-test ideas through structured argumentation. The debate framework
includes:

- DebateArena: Orchestrates multi-round debates between agents
- JudgeAgent: Evaluates debate quality and assigns scores
- VotingMechanism: Implements consensus-building through voting

The debate follows a 3-round structure:
1. Pro arguments (Expert supports idea)
2. Con arguments (Critic challenges idea)
3. Rebuttal (Innovator provides counter-arguments)

Each round is evaluated by the Judge, and final scores incorporate
both judge evaluation and multi-agent consensus through voting.
"""
from __future__ import annotations

from .arena import DebateArena, DebateConfig
from .judge import DebateEvaluation, JudgeAgent, RoundEvaluation
from .voting import (
    ConsensusResult,
    VotingMechanism,
    VotingStrategy,
)

__all__ = [
    "ConsensusResult",
    "DebateArena",
    "DebateConfig",
    "DebateEvaluation",
    "JudgeAgent",
    "RoundEvaluation",
    "VotingMechanism",
    "VotingStrategy",
]
