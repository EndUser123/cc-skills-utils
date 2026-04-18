"""
Tree-of-Thought Reasoning Strategy.

Implements branching reasoning where multiple thought paths
are explored in parallel and the best path is selected.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from .base import ReasoningStrategy, ThoughtBranch, ThoughtProcess

logger = logging.getLogger(__name__)


class TreeOfThoughtStrategy(ReasoningStrategy):
    """
    Tree-of-Thought reasoning strategy (MVP implementation).

    Generates multiple branching thought paths, evaluates them,
    expands the most promising branches, and returns the best path.

    Algorithm:
    1. Generate N initial branches (default: 5)
    2. Self-evaluate each branch (score 0-100)
    3. Expand top K branches (default: 3)
    4. Return best overall path

    Characteristics:
    - Multiple parallel branches
    - Competitive evaluation
    - Selective expansion of top branches
    - Returns single best path
    """

    def __init__(
        self,
        timeout: float = 60.0,
        initial_branches: int = 5,
        expansion_branches: int = 3,
        max_depth: int = 2,
        temperature: float = 0.8,
    ):
        """
        Initialize Tree-of-Thought strategy.

        Args:
        ----
            timeout: Maximum time for reasoning (seconds)
            initial_branches: Number of initial branches to generate
            expansion_branches: Number of top branches to expand
            max_depth: Maximum depth for branch expansion
            temperature: LLM temperature for generation

        """
        super().__init__(timeout=timeout)
        self.initial_branches = initial_branches
        self.expansion_branches = expansion_branches
        self.max_depth = max_depth
        self.temperature = temperature

    async def reason(
        self, prompt: str, context: dict[str, Any] | None = None
    ) -> ThoughtProcess:
        """
        Execute Tree-of-Thought reasoning.

        Generates multiple branches, evaluates them, expands the best,
        and returns the optimal reasoning path.

        Args:
        ----
            prompt: The reasoning prompt/question
            context: Optional additional context

        Returns:
        -------
            ThoughtProcess with multiple branches and the best path

        Raises:
        ------
            asyncio.TimeoutError: If reasoning exceeds timeout

        """
        start_time = time.time()
        self._log_progress(
            "Starting Tree-of-Thought reasoning",
            prompt=prompt[:100],
            initial_branches=self.initial_branches,
        )

        try:
            # Create thought process
            process = ThoughtProcess(
                strategy_used=self.get_strategy_name(),
                metadata={
                    "initial_branches": self.initial_branches,
                    "expansion_branches": self.expansion_branches,
                    "max_depth": self.max_depth,
                    "temperature": self.temperature,
                },
            )

            # Phase 1: Generate initial branches
            self._log_progress("Phase 1: Generating initial branches")
            initial_branches = await self._generate_initial_branches(prompt, context)

            if not initial_branches:
                self._log_progress("No branches generated", level="warning")
                return process

            process.branches.extend(initial_branches)
            self._log_progress(
                f"Generated {len(initial_branches)} initial branches",
                level="info",
            )

            # Check timeout
            if time.time() - start_time > self.timeout:
                self._log_progress("Timeout reached after initial generation", level="warning")
                return self._finalize_process(process, start_time)

            # Phase 2: Evaluate initial branches
            self._log_progress("Phase 2: Evaluating initial branches")
            await self._evaluate_branches(initial_branches, context)

            # Sort by score
            initial_branches.sort(key=lambda b: b.score, reverse=True)
            self._log_progress(
                "Branch evaluation complete",
                top_score=initial_branches[0].score if initial_branches else 0,
            )

            # Check timeout
            if time.time() - start_time > self.timeout:
                self._log_progress("Timeout reached after evaluation", level="warning")
                return self._finalize_process(process, start_time)

            # Phase 3: Expand top branches
            self._log_progress(
                f"Phase 3: Expanding top {self.expansion_branches} branches"
            )
            top_branches = initial_branches[: self.expansion_branches]

            expanded_branches = await self._expand_branches(
                top_branches, prompt, context
            )

            process.branches.extend(expanded_branches)
            self._log_progress(
                f"Expanded {len(expanded_branches)} branches",
                total_branches=len(process.branches),
            )

            # Phase 4: Final evaluation and selection
            self._log_progress("Phase 4: Final evaluation and selection")
            all_branches = process.branches

            # Evaluate expanded branches
            await self._evaluate_branches(expanded_branches, context)

            # Find best branch
            best_branch = max(all_branches, key=lambda b: b.score)

            process.best_path = best_branch.thoughts.copy()
            process.score = best_branch.score
            process.total_thoughts = sum(len(b.thoughts) for b in all_branches)
            process.execution_time = time.time() - start_time

            self._log_progress(
                "Tree-of-Thought reasoning complete",
                best_score=best_branch.score,
                total_branches=len(all_branches),
                total_thoughts=process.total_thoughts,
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
                return self._finalize_process(process, start_time, error=str(e))
            raise

    def get_strategy_name(self) -> str:
        """Return the strategy name."""
        return "tree_of_thought"

    async def _generate_initial_branches(
        self, prompt: str, context: dict[str, Any] | None = None
    ) -> list[ThoughtBranch]:
        """
        Generate initial branches with different starting perspectives.

        Args:
        ----
            prompt: Original reasoning prompt
            context: Additional context

        Returns:
        -------
            List of initial thought branches

        """
        branches = []

        # Create tasks for parallel generation
        tasks = []
        for i in range(self.initial_branches):
            task = self._generate_single_branch(
                prompt=prompt,
                branch_index=i,
                parent_id=None,
                depth=0,
                context=context,
            )
            tasks.append(task)

        # Execute in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self._log_progress(
                    f"Branch {i} generation failed: {result}",
                    level="warning",
                )
                continue

            if isinstance(result, ThoughtBranch):
                branches.append(result)

        return branches

    async def _generate_single_branch(
        self,
        prompt: str,
        branch_index: int,
        parent_id: str | None,
        depth: int,
        context: dict[str, Any] | None = None,
    ) -> ThoughtBranch:
        """
        Generate a single thought branch.

        Args:
        ----
            prompt: Original reasoning prompt
            branch_index: Index of this branch
            parent_id: ID of parent branch
            depth: Current depth
            context: Additional context

        Returns:
        -------
            Generated ThoughtBranch

        """
        branch = ThoughtBranch(
            branch_id=self._create_branch_id(),
            parent_id=parent_id,
            depth=depth,
            metadata={
                "branch_index": branch_index,
                "strategy": "tree_of_thought",
            },
        )

        # Generate initial thought for this branch
        thought_prompt = self._build_branch_prompt(
            prompt, branch_index, depth, context
        )

        thought = await self._generate_thought(
            prompt=thought_prompt,
            previous_thoughts=None,
            context=context,
        )

        if thought:
            branch.add_thought(thought)

        return branch

    async def _expand_branches(
        self,
        parent_branches: list[ThoughtBranch],
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> list[ThoughtBranch]:
        """
        Expand the top branches by generating child branches.

        Args:
        ----
            parent_branches: Branches to expand
            prompt: Original reasoning prompt
            context: Additional context

        Returns:
        -------
            List of expanded child branches

        """
        if not parent_branches:
            return []

        expanded = []

        for parent in parent_branches:
            # Check depth limit
            if parent.depth >= self.max_depth:
                self._log_progress(
                    f"Branch {parent.branch_id} at max depth, skipping expansion",
                    level="info",
                )
                continue

            # Generate child branches
            # For MVP, generate 2 children per parent
            for child_index in range(2):
                child = await self._generate_child_branch(
                    parent=parent,
                    child_index=child_index,
                    prompt=prompt,
                    context=context,
                )

                if child and child.thoughts:
                    expanded.append(child)

        return expanded

    async def _generate_child_branch(
        self,
        parent: ThoughtBranch,
        child_index: int,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> ThoughtBranch | None:
        """
        Generate a child branch from a parent branch.

        Args:
        ----
            parent: Parent branch
            child_index: Index of this child
            prompt: Original reasoning prompt
            context: Additional context

        Returns:
        -------
            Generated child branch or None

        """
        child = ThoughtBranch(
            branch_id=self._create_branch_id(),
            parent_id=parent.branch_id,
            depth=parent.depth + 1,
            metadata={
                "parent_index": parent.metadata.get("branch_index"),
                "child_index": child_index,
                "strategy": "tree_of_thought",
            },
        )

        # Inherit parent thoughts
        child.thoughts = parent.thoughts.copy()

        # Generate continuation thought
        thought_prompt = self._build_expansion_prompt(
            prompt, parent, child_index, context
        )

        thought = await self._generate_thought(
            prompt=thought_prompt,
            previous_thoughts=parent.thoughts,
            context=context,
        )

        if thought:
            child.add_thought(thought)

        return child

    async def _evaluate_branches(
        self, branches: list[ThoughtBranch], context: dict[str, Any] | None = None
    ) -> None:
        """
        Evaluate multiple branches in parallel.

        Args:
        ----
            branches: Branches to evaluate
            context: Additional context

        """
        if not branches:
            return

        # Create evaluation tasks
        tasks = [self._evaluate_branch(branch, context) for branch in branches]

        # Execute in parallel
        scores = await asyncio.gather(*tasks, return_exceptions=True)

        # Assign scores
        for branch, score_result in zip(branches, scores, strict=False):
            if isinstance(score_result, Exception):
                self._log_progress(
                    f"Evaluation failed for branch {branch.branch_id}: {score_result}",
                    level="warning",
                )
                branch.score = 0.0
            else:
                branch.score = score_result

    def _build_branch_prompt(
        self,
        prompt: str,
        branch_index: int,
        depth: int,
        context: dict[str, Any] | None = None,
    ) -> str:
        """
        Build a prompt for generating a branch.

        Args:
        ----
            prompt: Original prompt
            branch_index: Index of this branch
            depth: Current depth
            context: Additional context

        Returns:
        -------
            Formatted prompt

        """
        # Add diversity by giving different perspectives
        perspectives = [
            "Consider the practical implementation aspects",
            "Focus on theoretical foundations and principles",
            "Analyze potential risks and challenges",
            "Explore innovative and creative approaches",
            "Examine the problem from a user-centric perspective",
        ]

        perspective = perspectives[branch_index % len(perspectives)]

        branch_prompt = f"""Think about this question from a specific perspective:

Question: {prompt}

Perspective: {perspective}

Provide your initial thought or analysis from this perspective."""

        if context:
            branch_prompt += f"\n\nAdditional Context:\n{self._format_context(context)}"

        return branch_prompt

    def _build_expansion_prompt(
        self,
        prompt: str,
        parent: ThoughtBranch,
        child_index: int,
        context: dict[str, Any] | None = None,
    ) -> str:
        """
        Build a prompt for expanding a branch.

        Args:
        ----
            prompt: Original prompt
            parent: Parent branch
            child_index: Index of this child
            context: Additional context

        Returns:
        -------
            Formatted prompt

        """
        last_thought = parent.get_final_thought()

        expansion_prompt = f"""Continue your reasoning:

Original question: {prompt}

Your previous thought: {last_thought}

Now, take this reasoning further. What is the next logical step or insight?
Build upon your previous thought to go deeper into the analysis."""

        return expansion_prompt

    def _format_context(self, context: dict[str, Any]) -> str:
        """Format context dictionary into a string."""
        if not context:
            return ""

        lines = []
        for key, value in context.items():
            if isinstance(value, (str, int, float, bool)):
                lines.append(f"- {key}: {value}")
            elif isinstance(value, (list, dict)):
                lines.append(f"- {key}: {len(value)} items")
            else:
                lines.append(f"- {key}: {type(value).__name__}")

        return "\n".join(lines)

    def _finalize_process(
        self,
        process: ThoughtProcess,
        start_time: float,
        error: str | None = None,
    ) -> ThoughtProcess:
        """
        Finalize the thought process.

        Args:
        ----
            process: Thought process to finalize
            start_time: Process start time
            error: Optional error message

        Returns:
        -------
            Finalized ThoughtProcess

        """
        # Calculate total thoughts
        process.total_thoughts = sum(len(b.thoughts) for b in process.branches)

        # Set execution time
        process.execution_time = time.time() - start_time

        # Find best branch if available
        if process.branches:
            best_branch = max(process.branches, key=lambda b: b.score)
            process.best_path = best_branch.thoughts.copy()
            process.score = best_branch.score

        # Add error if present
        if error:
            process.metadata["error"] = error

        return process

    async def _evaluate_branch(
        self, branch: ThoughtBranch, context: dict[str, Any] | None = None
    ) -> float:
        """
        Evaluate a ToT branch.

        For ToT, we evaluate based on:
        - Number of thoughts (depth of reasoning)
        - Branch depth (hierarchical level)
        - Thought diversity (placeholder)

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

        # ToT-specific scoring
        depth_bonus = branch.depth * 10  # Bonus for being deeper in tree
        thought_bonus = min(30, len(branch.thoughts) * 5)  # More thoughts = better

        # Final score
        final_score = min(100, base_score + depth_bonus + thought_bonus)

        return float(final_score)
