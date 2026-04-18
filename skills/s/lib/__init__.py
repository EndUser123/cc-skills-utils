"""
Brainstorm Library - Multi-Perspective Ideation System

This library provides a framework for generating and evaluating ideas from multiple
perspectives using specialized AI agents. It implements a multi-agent system where
each agent represents a different thinking style or persona.

Key Components:
- Models: Data structures for ideas, evaluations, and results
- Agents: Base classes and specialized agent implementations
- Orchestration: Coordination of multi-agent brainstorming sessions
- Debate: Adversarial debate framework for stress-testing ideas
- Convergence: Consensus-building and ranking strategies
- Memory: Session management and persistence
- Pheromone: Learning from previous brainstorming sessions
- Replay: Experience replay for improved idea generation

Example:
    ```python
    from .lib import BrainstormOrchestrator, BrainstormContext

    context = BrainstormContext(
        topic="Develop a sustainable transportation system",
        num_ideas=10,
        personas=["innovator", "pragmatist", "critic"]
    )

    orchestrator = BrainstormOrchestrator()
    result = await orchestrator.brainstorm(context)

    print(f"Generated {len(result.ideas)} ideas")
    for idea in result.top_ideas(5):
        print(f"- {idea.content} (Score: {idea.score})")
    ```

Advanced Features:
    ```python
    from .lib import BrainstormOrchestrator, DebateArena, VotingStrategy

    # Enable full debate mode
    orchestrator = BrainstormOrchestrator(enable_full_debate=True)

    # Or use DebateArena directly
    arena = DebateArena(
        voting_strategy=VotingStrategy.BORDA,
        num_rounds=3
    )
    ```

"""

from __future__ import annotations

__version__ = "3.0.0"
__author__ = "CSF Development Team"

# Core imports
from .agents.base import Agent, AgentLLMClient

# Convergence engine
from .convergence.engine import ConvergenceEngine
from .convergence.ranking import RankingStrategy

# Debate framework
from .debate.arena import DebateArena, DebateConfig
from .debate.judge import DebateEvaluation, JudgeAgent, RoundEvaluation
from .debate.voting import (
    ConsensusResult,
    VotingMechanism,
    VotingStrategy,
)

# Memory systems
from .memory.brainstorm_memory import BrainstormMemory
from .models import (
    BrainstormContext,
    BrainstormResult,
    Evaluation,
    Idea,
)
from .orchestrator import BrainstormOrchestrator

# Scheduling system
from .scheduler import (
    ConfidenceScheduler,
    SchedulingStrategy,
    TurnOrder,
)

__all__ = [
    # Core
    "Agent",
    "AgentLLMClient",
    "BrainstormContext",
    "BrainstormOrchestrator",
    "BrainstormResult",
    "Evaluation",
    "Idea",
    # Debate
    "ConsensusResult",
    "DebateArena",
    "DebateConfig",
    "DebateEvaluation",
    "JudgeAgent",
    "RoundEvaluation",
    "VotingMechanism",
    "VotingStrategy",
    # Convergence
    "ConvergenceEngine",
    "RankingStrategy",
    # Memory
    "BrainstormMemory",
    # Scheduling
    "ConfidenceScheduler",
    "SchedulingStrategy",
    "TurnOrder",
]
