"""
Brainstorm Reasoning Strategies Module.

This module provides various reasoning strategies for the brainstorming system:
- Chain-of-Thought: Sequential, linear reasoning
- Tree-of-Thought: Branching, competitive reasoning
- Graph-of-Thought: Future graph-based reasoning (placeholder)

Usage:
    from ..reasoning import (
        ChainOfThoughtStrategy,
        TreeOfThoughtStrategy,
        GraphOfThoughtStrategy,
        ReasoningStrategy,
        ThoughtProcess,
        ThoughtBranch,
    )

    # Create a strategy
    strategy = ChainOfThoughtStrategy(timeout=30.0)

    # Execute reasoning
    result = await strategy.reason(
        prompt="How should I design this system?",
        context={"requirements": [...]}
    )

    # Access results
    print(result.best_path)  # List of thoughts
    print(result.score)      # Confidence score
"""
from __future__ import annotations

from .base import ReasoningStrategy, ThoughtBranch, ThoughtProcess
from .chain_of_thought import ChainOfThoughtStrategy
from .graph_of_thought import GraphOfThoughtStrategy
from .tree_of_thought import TreeOfThoughtStrategy


# Strategy factory for easy instantiation
def create_strategy(
    strategy_type: str,
    **kwargs,
) -> ReasoningStrategy:
    """
    Create a reasoning strategy by type.

    Args:
    ----
        strategy_type: Type of strategy to create
            - "chain_of_thought" or "cot"
            - "tree_of_thought" or "tot"
            - "graph_of_thought" or "got"
        **kwargs: Additional arguments passed to strategy constructor

    Returns:
    -------
        Instantiated reasoning strategy

    Raises:
    ------
        ValueError: If strategy_type is unknown

    Examples:
    --------
        # Create Chain-of-Thought strategy
        strategy = create_strategy("cot", timeout=30.0, max_thoughts=5)

        # Create Tree-of-Thought strategy
        strategy = create_strategy("tot", timeout=60.0, initial_branches=5)

    """
    strategy_type_lower = strategy_type.lower().replace("-", "_")

    strategy_classes = {
        "chain_of_thought": ChainOfThoughtStrategy,
        "cot": ChainOfThoughtStrategy,
        "tree_of_thought": TreeOfThoughtStrategy,
        "tot": TreeOfThoughtStrategy,
        "graph_of_thought": GraphOfThoughtStrategy,
        "got": GraphOfThoughtStrategy,
    }

    strategy_class = strategy_classes.get(strategy_type_lower)

    if strategy_class is None:
        raise ValueError(
            f"Unknown strategy type: {strategy_type}. "
            f"Valid options: {list(set(strategy_classes.keys()))}"
        )

    return strategy_class(**kwargs)


__all__ = [
    # Base classes
    "ReasoningStrategy",
    "ThoughtProcess",
    "ThoughtBranch",
    # Strategy implementations
    "ChainOfThoughtStrategy",
    "TreeOfThoughtStrategy",
    "GraphOfThoughtStrategy",
    # Factory function
    "create_strategy",
]
