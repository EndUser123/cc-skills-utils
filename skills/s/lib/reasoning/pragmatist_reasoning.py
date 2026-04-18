"""
Pragmatist Reasoning Strategy.

Implements a reasoning flow focused on practical execution, 
feasibility, and clear action steps.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .base import ReasoningStrategy, ThoughtBranch, ThoughtProcess

logger = logging.getLogger(__name__)


class PragmatistReasoning(ReasoningStrategy):
    """
    Pragmatist reasoning strategy.

    Focuses on:
    1. Feasibility and implementation details.
    2. Identifying potential execution roadblocks.
    3. Resource requirements and constraints.
    4. Concrete, actionable next steps.
    """

    def __init__(
        self,
        timeout: float = 30.0,
        max_thoughts: int = 4,
        temperature: float = 0.4,  # Lower temperature for more grounded thinking
    ):
        """
        Initialize Pragmatist reasoning strategy.

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
        Execute Pragmatist reasoning.

        Args:
        ----
            prompt: The reasoning prompt/question
            context: Optional additional context

        Returns:
        -------
            ThoughtProcess with the practical reasoning path
        """
        start_time = time.time()
        self._log_progress("Starting Pragmatist reasoning", prompt=prompt[:100])

        try:
            process = ThoughtProcess(
                strategy_used=self.get_strategy_name(),
                metadata={"max_thoughts": self.max_thoughts, "temperature": self.temperature},
            )

            branch = ThoughtBranch(
                branch_id=self._create_branch_id(),
                depth=0,
                metadata={"strategy": "pragmatist"},
            )

            thoughts_generated = 0

            # Step-by-step pragmatist reasoning
            steps = [
                "Feasibility Analysis: Is this realistic with current resources?",
                "Implementation Path: What are the specific technical/operational steps?",
                "Risk Mitigation: What could go wrong and how do we handle it?",
                "Action Plan: What is the immediate, concrete next step?"
            ]

            for i in range(min(self.max_thoughts, len(steps))):
                if time.time() - start_time > self.timeout:
                    self._log_progress("Timeout reached", level="warning")
                    break

                step_focus = steps[i]
                thought = await self._generate_pragmatic_thought(
                    prompt=prompt,
                    previous_thoughts=branch.thoughts,
                    step_focus=step_focus,
                    context=context,
                )

                if thought:
                    branch.add_thought(thought)
                    thoughts_generated += 1
                else:
                    break

            branch.score = await self._evaluate_branch(branch, context)
            process.branches.append(branch)
            process.best_path = branch.thoughts.copy()
            process.score = branch.score
            process.total_thoughts = thoughts_generated
            process.execution_time = time.time() - start_time

            return process

        except Exception as e:
            self._log_progress(f"Error during reasoning: {e}", level="error")
            if "process" in locals():
                process.execution_time = time.time() - start_time
                return process
            raise

    def get_strategy_name(self) -> str:
        return "pragmatist_reasoning"

    async def _generate_pragmatic_thought(
        self,
        prompt: str,
        previous_thoughts: list[str],
        step_focus: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        # Build a prompt that forces the LLM to focus on the specific pragmatist step
        thinking_prompt = f"""Topic/Goal: {prompt}

You are thinking as a Pragmatist. 
Current Focus: {step_focus}

Previous steps in your reasoning:
{chr(10).join(f"- {t}" for t in previous_thoughts) if previous_thoughts else "None"}

Please provide a detailed, practical analysis for the current focus. 
Be specific, grounded in reality, and execution-oriented."""

        if context:
            thinking_prompt += f"\n\nContext: {context}"

        return await self._generate_thought(thinking_prompt)
