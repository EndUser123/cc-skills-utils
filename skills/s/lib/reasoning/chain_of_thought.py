"""
Chain-of-Thought Reasoning Strategy.

Implements sequential, step-by-step reasoning where thoughts
build upon each other in a linear fashion.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .base import ReasoningStrategy, ThoughtBranch, ThoughtProcess

logger = logging.getLogger(__name__)


class ChainOfThoughtStrategy(ReasoningStrategy):
    """
    Chain-of-Thought reasoning strategy.

    Generates thoughts sequentially, where each thought builds
    upon the previous ones in a linear progression.

    Characteristics:
    - Single branch of reasoning
    - Sequential thought generation
    - Each thought depends on previous thoughts
    - Returns the single thought path as the best path
    """

    def __init__(
        self,
        timeout: float = 30.0,
        max_thoughts: int = 5,
        temperature: float = 0.7,
    ):
        """
        Initialize Chain-of-Thought strategy.

        Args:
        ----
            timeout: Maximum time for reasoning (seconds)
            max_thoughts: Maximum number of thoughts to generate
            temperature: LLM temperature for generation

        """
        super().__init__(timeout=timeout)
        self.max_thoughts = max_thoughts
        self.temperature = temperature

    async def reason(
        self, prompt: str, context: dict[str, Any] | None = None
    ) -> ThoughtProcess:
        """
        Execute Chain-of-Thought reasoning.

        Generates a sequence of thoughts, each building on the previous,
        to explore the reasoning space in a linear fashion.

        Args:
        ----
            prompt: The reasoning prompt/question
            context: Optional additional context

        Returns:
        -------
            ThoughtProcess with a single branch containing
            the sequential reasoning chain

        Raises:
        ------
            asyncio.TimeoutError: If reasoning exceeds timeout

        """
        start_time = time.time()
        self._log_progress("Starting Chain-of-Thought reasoning", prompt=prompt[:100])

        try:
            # Create thought process
            process = ThoughtProcess(
                strategy_used=self.get_strategy_name(),
                metadata={"max_thoughts": self.max_thoughts, "temperature": self.temperature},
            )

            # Create initial branch
            branch = ThoughtBranch(
                branch_id=self._create_branch_id(),
                depth=0,
                metadata={"strategy": "chain_of_thought"},
            )

            # Generate sequential thoughts
            thoughts_generated = 0

            for i in range(self.max_thoughts):
                # Check timeout
                if time.time() - start_time > self.timeout:
                    self._log_progress(
                        "Timeout reached, stopping reasoning",
                        level="warning",
                        thoughts_generated=thoughts_generated,
                    )
                    break

                # Generate next thought
                thought = await self._generate_cot_thought(
                    prompt=prompt,
                    previous_thoughts=branch.thoughts,
                    thought_number=i + 1,
                    context=context,
                )

                if thought:
                    branch.add_thought(thought)
                    thoughts_generated += 1
                    self._log_progress(
                        f"Generated thought {i + 1}/{self.max_thoughts}",
                        thought_length=len(thought),
                    )
                else:
                    self._log_progress(
                        "Thought generation returned empty, stopping",
                        level="warning",
                        thought_number=i + 1,
                    )
                    break

            # Calculate score
            branch.score = await self._evaluate_branch(branch, context)

            # Update process
            process.branches.append(branch)
            process.best_path = branch.thoughts.copy()
            process.score = branch.score
            process.total_thoughts = thoughts_generated
            process.execution_time = time.time() - start_time

            self._log_progress(
                "Chain-of-Thought reasoning complete",
                thoughts=thoughts_generated,
                score=branch.score,
                time=process.execution_time,
            )

            return process

        except Exception as e:
            self._log_progress(
                f"Error during reasoning: {e}",
                level="error",
                error_type=type(e).__name__,
            )
            # Return partial process if available
            if "process" in locals():
                process.execution_time = time.time() - start_time
                process.metadata["error"] = str(e)
                return process
            raise

    def get_strategy_name(self) -> str:
        """Return the strategy name."""
        return "chain_of_thought"

    async def _generate_cot_thought(
        self,
        prompt: str,
        previous_thoughts: list[str],
        thought_number: int,
        context: dict[str, Any] | None = None,
    ) -> str:
        """
        Generate a single thought in the chain.

        Args:
        ----
            prompt: Original reasoning prompt
            previous_thoughts: Previously generated thoughts
            thought_number: Current thought number (1-indexed)
            context: Additional context

        Returns:
        -------
            Generated thought string

        """
        # Build the thinking prompt
        if thought_number == 1:
            # First thought - start fresh
            thinking_prompt = self._build_initial_prompt(prompt, context)
        else:
            # Subsequent thoughts - build on previous
            thinking_prompt = self._build_continuation_prompt(
                prompt, previous_thoughts, thought_number, context
            )

        # Use the base class method or connect to actual LLM
        thought = await self._generate_thought(
            prompt=thinking_prompt,
            previous_thoughts=previous_thoughts,
            context=context,
        )

        return thought

    def _build_initial_prompt(
        self, prompt: str, context: dict[str, Any] | None = None
    ) -> str:
        """
        Build the prompt for the first thought.

        Args:
        ----
            prompt: Original prompt
            context: Additional context

        Returns:
        -------
            Formatted prompt for initial thought generation

        """
        cot_prompt = f"""Think step by step about the following question:

{prompt}

Start by breaking down the problem and identifying the key components.
Provide your first step of reasoning."""

        if context:
            cot_prompt += f"\n\nAdditional Context:\n{self._format_context(context)}"

        return cot_prompt

    def _build_continuation_prompt(
        self,
        prompt: str,
        previous_thoughts: list[str],
        thought_number: int,
        context: dict[str, Any] | None = None,
    ) -> str:
        """
        Build the prompt for continuing the thought chain.

        Args:
        ----
            prompt: Original prompt
            previous_thoughts: Previously generated thoughts
            thought_number: Current thought number
            context: Additional context

        Returns:
        -------
            Formatted prompt for continuing reasoning

        """
        # Show recent thoughts for context
        recent_thoughts = previous_thoughts[-2:]  # Last 2 thoughts
        thoughts_text = "\n".join(
            f"{i + 1}. {thought}" for i, thought in enumerate(recent_thoughts)
        )

        continuation_prompt = f"""Original question: {prompt}

Your previous reasoning steps:
{thoughts_text}

Continue your reasoning. What is the next logical step or insight?
Provide step {thought_number} of your thinking process."""

        return continuation_prompt

    def _format_context(self, context: dict[str, Any]) -> str:
        """
        Format context dictionary into a string.

        Args:
        ----
            context: Context dictionary

        Returns:
        -------
            Formatted context string

        """
        if not context:
            return ""

        lines = []
        for key, value in context.items():
            if isinstance(value, (str, int, float, bool)):
                lines.append(f"- {key}: {value}")
            elif isinstance(value, list):
                lines.append(f"- {key}: {len(value)} items")
            elif isinstance(value, dict):
                lines.append(f"- {key}: {len(value)} keys")
            else:
                lines.append(f"- {key}: {type(value).__name__}")

        return "\n".join(lines)

    async def _evaluate_branch(
        self, branch: ThoughtBranch, context: dict[str, Any] | None = None
    ) -> float:
        """
        Evaluate the CoT branch.

        For CoT, we evaluate based on:
        - Number of thoughts (more is generally better)
        - Progression depth
        - Thought quality (placeholder for now)

        Args:
        ----
            branch: Branch to evaluate
            context: Additional context

        Returns:
        -------
            Score between 0 and 100

        """
        # Base score from parent class
        base_score = await super()._evaluate_branch(branch, context)

        # Adjust for CoT-specific factors
        thought_quality_bonus = min(20, len(branch.thoughts) * 4)

        # Final score
        final_score = min(100, base_score + thought_quality_bonus)

        return float(final_score)
