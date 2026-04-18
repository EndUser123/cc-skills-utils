"""
Smoke tests for /s skill library imports.

Tests that all core modules can be imported successfully.
Run with: python -m pytest lib/tests/test_imports.py -v
"""

import pytest


def test_core_imports():
    """Test core library imports."""
    from lib import (
        BrainstormContext,
        BrainstormOrchestrator,
        BrainstormResult,
        Evaluation,
        Idea,
    )
    assert BrainstormContext is not None
    assert BrainstormOrchestrator is not None
    assert BrainstormResult is not None
    assert Evaluation is not None
    assert Idea is not None


def test_debate_imports():
    """Test debate framework imports."""
    from lib import (
        ConsensusResult,
        DebateArena,
        DebateConfig,
        DebateEvaluation,
        JudgeAgent,
        RoundEvaluation,
        VotingMechanism,
        VotingStrategy,
    )
    assert DebateArena is not None
    assert DebateConfig is not None
    assert VotingStrategy is not None
    assert ConsensusResult is not None
    assert DebateEvaluation is not None
    assert JudgeAgent is not None
    assert RoundEvaluation is not None
    assert VotingMechanism is not None


def test_convergence_imports():
    """Test convergence engine imports."""
    from lib import ConvergenceEngine, RankingStrategy
    assert ConvergenceEngine is not None
    assert RankingStrategy is not None


def test_agent_imports():
    """Test agent imports."""
    from lib import Agent, AgentLLMClient
    assert Agent is not None
    assert AgentLLMClient is not None


def test_memory_imports():
    """Test memory system imports."""
    from lib import BrainstormMemory
    assert BrainstormMemory is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
