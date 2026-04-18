"""
Base Reasoning Strategy Module.

Defines the abstract interface for all reasoning strategies
used in the brainstorming system.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ThoughtBranch(BaseModel):
    """
    Represents a single branch in the reasoning process.

    Attributes
    ----------
    thoughts: List[str]
        Sequential thoughts in this branch
    score: float
        Confidence score for this branch (0-100)
    depth: int
        Depth level of this branch in the reasoning tree
    parent_id: Optional[str]
        ID of parent branch if this is a child branch
    branch_id: str
        Unique identifier for this branch
    metadata: Dict[str, Any]
        Additional information about the branch

    """

    thoughts: list[str] = Field(default_factory=list)
    score: float = 0.0
    depth: int = 0
    parent_id: str | None = None
    branch_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    def add_thought(self, thought: str) -> None:
        """Add a thought to this branch."""
        self.thoughts.append(thought)

    def get_final_thought(self) -> str:
        """Get the last thought in the branch."""
        return self.thoughts[-1] if self.thoughts else ""


class ThoughtProcess(BaseModel):
    """
    Represents the complete reasoning process with multiple branches.

    Attributes
    ----------
    branches: List[ThoughtBranch]
        All explored branches in the reasoning process
    best_path: List[str]
        The best sequence of thoughts identified
    score: float
        Confidence score for the best path (0-100)
    strategy_used: str
        Name of the reasoning strategy used
    total_thoughts: int
        Total number of thoughts generated across all branches
    execution_time: float
        Time taken to complete reasoning in seconds
    metadata: Dict[str, Any]
        Additional information about the reasoning process

    """

    branches: list[ThoughtBranch] = Field(default_factory=list)
    best_path: list[str] = Field(default_factory=list)
    score: float = 0.0
    strategy_used: str = ""
    total_thoughts: int = 0
    execution_time: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)

    def get_best_branch(self) -> ThoughtBranch | None:
        """Get the branch with the highest score."""
        if not self.branches:
            return None
        return max(self.branches, key=lambda b: b.score)

    def get_summary(self) -> str:
        """Get a summary of the reasoning process."""
        return (
            f"Strategy: {self.strategy_used}\n"
            f"Branches explored: {len(self.branches)}\n"
            f"Total thoughts: {self.total_thoughts}\n"
            f"Best score: {self.score:.1f}/100\n"
            f"Execution time: {self.execution_time:.2f}s"
        )


class ReasoningStrategy(ABC):
    """
    Abstract base class for reasoning strategies.

    All reasoning strategies must implement the `reason` method
    which takes a prompt and optional context, and returns a
    ThoughtProcess representing the reasoning results.
    """

    def __init__(self, timeout: float = 30.0):
        """
        Initialize the reasoning strategy.

        Args:
        ----
            timeout: Maximum time in seconds for reasoning (default: 30.0)

        """
        self.timeout = timeout
        self._llm_generate_func = None

    def set_llm_generate_func(self, generate_func: Any) -> None:
        """
        Set the LLM generation function.

        Args:
        ----
            generate_func: A callable that takes a prompt (str) and returns a str
                           (usually an async function).

        """
        self._llm_generate_func = generate_func

    @abstractmethod
    async def reason(
        self, prompt: str, context: dict[str, Any] | None = None
    ) -> ThoughtProcess:
        """
        Execute reasoning on the given prompt.

        Args:
        ----
            prompt: The reasoning prompt/question
            context: Optional additional context for reasoning

        Returns:
        -------
            ThoughtProcess containing the reasoning results

        Raises:
        ------
            asyncio.TimeoutError: If reasoning exceeds timeout

        """

    @abstractmethod
    def get_strategy_name(self) -> str:
        """Return the name of this reasoning strategy."""

    async def _generate_thought(
        self,
        prompt: str,
        previous_thoughts: list[str] | None = None,
        context: dict[str, Any] | None = None,
    ) -> str:
        """
        Generate a single thought using the LLM.

        Args:
        ----
            prompt: The thinking prompt
            previous_thoughts: Previous thoughts for context
            context: Additional context

        Returns:
        -------
            Generated thought string

        """
        if self._llm_generate_func:
            try:
                # Call the provided generation function
                # Handle both sync and async functions
                if asyncio.iscoroutinefunction(self._llm_generate_func):
                    return await self._llm_generate_func(prompt)
                else:
                    return self._llm_generate_func(prompt)
            except Exception as e:
                self._log_progress(f"Error generating thought: {e}", level="error")
                return f"Error: {e}"

        # Fallback to placeholder if no generate function provided
        if previous_thoughts:
            return f"Continuing from: {previous_thoughts[-1][:50]}..."

        return f"Initial thought about: {prompt[:50]}..."

    async def _evaluate_branch(
        self, branch: ThoughtBranch, context: dict[str, Any] | None = None
    ) -> float:
        """
        Evaluate a reasoning branch and return a score.

        Args:
        ----
            branch: The branch to evaluate
            context: Additional context for evaluation

        Returns:
        -------
            Score between 0 and 100

        """
        # Placeholder evaluation - actual implementation would use LLM
        # Base score on depth and number of thoughts
        base_score = min(100, len(branch.thoughts) * 10 + branch.depth * 5)

        # Could be enhanced with actual LLM evaluation
        return float(base_score)

    def _create_branch_id(self) -> str:
        """Generate a unique branch ID."""
        import random
        import time

        return f"branch_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"

    def _log_progress(
        self, message: str, level: str = "info", **kwargs
    ) -> None:
        """
        Log progress with consistent formatting.

        Args:
        ----
            message: Log message
            level: Log level (debug, info, warning, error)
            **kwargs: Additional context to log

        """
        log_func = getattr(logger, level, logger.info)
        log_msg = f"[{self.get_strategy_name()}] {message}"

        if kwargs:
            log_msg += f" - {kwargs}"

        log_func(log_msg)
