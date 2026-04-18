"""
Tree-of-Thought Branch Generator - Generate outcome scenarios for strategic options

Generates branching outcome scenarios:
- Success branches: sure, maybe, unlikely
- Failure branches: sure, maybe, unlikely
- Risk scenario branches: sure, maybe, unlikely
"""

import logging
from typing import NamedTuple

from ..models import Idea

logger = logging.getLogger(__name__)


class OutcomeBranch(NamedTuple):
    """An outcome scenario branch for a strategic option."""
    branch_type: str  # "success" | "failure" | "risk"
    likelihood: str  # "sure" | "maybe" | "unlikely"
    description: str  # What happens in this scenario
    confidence: float  # 0.0 to 1.0


class BranchGenerator:
    """
    Generate outcome scenarios for strategic options using ToT reasoning.

    Creates multiple possible outcome paths for each strategic option,
    categorized by success, failure, and risk scenarios.
    """

    # Keywords that indicate different outcome types
    SUCCESS_KEYWORDS = [
        r"success(?:ful)?",
        r"achieves?\s*\w+",
        r"works?\s+(?:well|out)",
        r"delivers?\s+\w+",
        r"enables?\s+\w+",
        r"adopts?\s+\w+",
    ]

    FAILURE_KEYWORDS = [
        r"fail(?:ure|s)?",
        r"breaks?\s+\w+",
        r"doesn?\s+(?:not|n't)\s+work",
        r"(?:unable|cannot)\s+\w+",
        r"blocks?\s+\w+",
        r"prevents?\s+\w+",
    ]

    RISK_KEYWORDS = [
        r"risk\s+(?:of|is)",
        r"danger\s+(?:of|is)",
        r"concern\s+(?:about|that)",
        r"might\s+(?:fail|go wrong)",
        r"could\s+(?:cause|lead to)",
    ]

    # Likelihood indicators
    SURE_INDICATORS = ["will", "certainly", "definitely", "guaranteed"]
    MAYBE_INDICATORS = ["may", "might", "could", "possibly", "potentially"]
    UNLIKELY_INDICATORS = ["unlikely", "rarely", "seldom", "probably not"]

    def __init__(self):
        """Initialize the branch generator."""
        self.branches: list[OutcomeBranch] = []

    def generate_for_ideas(self, ideas: list[Idea]) -> list[OutcomeBranch]:
        """
        Generate outcome branches for a list of strategic ideas.

        Args:
            ideas: List of strategic Idea objects

        Returns:
            List of OutcomeBranch objects with scenarios
        """
        self.branches = []

        for idea in ideas:
            # Generate different outcome scenarios for each idea
            self._generate_branches_for_idea(idea)

        logger.info(
            f"ToT Branch Generator: Generated {len(self.branches)} "
            f"outcome scenarios for {len(ideas)} ideas"
        )
        return self.branches

    def _generate_branches_for_idea(self, idea: Idea) -> None:
        """Generate outcome scenarios for a single idea."""
        content_lower = idea.content.lower()

        # Detect outcome type and likelihood from content
        outcomes = self._extract_outcomes(idea.content)

        # If no explicit outcomes found, generate generic ones
        if not outcomes:
            outcomes = self._generate_generic_outcomes(idea)

        for outcome in outcomes:
            self.branches.append(outcome)

    def _extract_outcomes(self, content: str) -> list[OutcomeBranch]:
        """Extract explicit outcomes mentioned in the idea content."""
        import re
        outcomes = []
        content_lower = content.lower()

        # Check for success outcomes
        for pattern in self.SUCCESS_KEYWORDS:
            if re.search(pattern, content_lower):
                likelihood = self._detect_likelihood(content_lower)
                outcomes.append(OutcomeBranch(
                    branch_type="success",
                    likelihood=likelihood,
                    description=self._extract_scenario(content, pattern),
                    confidence=self._likelihood_to_confidence(likelihood)
                ))

        # Check for failure outcomes
        for pattern in self.FAILURE_KEYWORDS:
            if re.search(pattern, content_lower):
                likelihood = self._detect_likelihood(content_lower)
                outcomes.append(OutcomeBranch(
                    branch_type="failure",
                    likelihood=likelihood,
                    description=self._extract_scenario(content, pattern),
                    confidence=self._likelihood_to_confidence(likelihood)
                ))

        # Check for risk outcomes
        for pattern in self.RISK_KEYWORDS:
            if re.search(pattern, content_lower):
                likelihood = self._detect_likelihood(content_lower)
                outcomes.append(OutcomeBranch(
                    branch_type="risk",
                    likelihood=likelihood,
                    description=self._extract_scenario(content, pattern),
                    confidence=self._likelihood_to_confidence(likelihood)
                ))

        return outcomes

    def _generate_generic_outcomes(self, idea: Idea) -> list[OutcomeBranch]:
        """Generate generic outcome scenarios for an idea."""
        # Default scenarios for each idea
        return [
            OutcomeBranch(
                branch_type="success",
                likelihood="maybe",
                description=f"'{idea.content[:60]}...' succeeds as intended",
                confidence=0.5
            ),
            OutcomeBranch(
                branch_type="failure",
                likelihood="unlikely",
                description=f"'{idea.content[:60]}...' encounters implementation challenges",
                confidence=0.3
            ),
            OutcomeBranch(
                branch_type="risk",
                likelihood="maybe",
                description=f"'{idea.content[:60]}...' requires additional resources",
                confidence=0.4
            )
        ]

    def _detect_likelihood(self, content: str) -> str:
        """Detect likelihood confidence from content keywords."""
        content_lower = content.lower()

        # Check for sure indicators
        for indicator in self.SURE_INDICATORS:
            if indicator in content_lower:
                return "sure"

        # Check for unlikely indicators
        for indicator in self.UNLIKELY_INDICATORS:
            if indicator in content_lower:
                return "unlikely"

        # Default to maybe
        return "maybe"

    def _extract_scenario(self, content: str, pattern: str) -> str:
        """Extract the scenario description surrounding a matched pattern."""
        import re
        # Find the pattern match and extract surrounding context
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            start = max(0, match.start() - 50)
            end = min(len(content), match.end() + 50)
            scenario = content[start:end].strip()
            # Clean up
            scenario = re.sub(r'\s+', ' ', scenario)
            return scenario[:200]  # Truncate if too long
        return "Scenario described in content"

    def _likelihood_to_confidence(self, likelihood: str) -> float:
        """Convert likelihood string to confidence score."""
        return {
            "sure": 0.9,
            "maybe": 0.5,
            "unlikely": 0.2,
        }.get(likelihood, 0.5)

    def prune_unlikely(self, threshold: float = 0.25) -> list[OutcomeBranch]:
        """
        Remove unlikely branches below confidence threshold.

        Args:
            threshold: Minimum confidence score (default: 0.25)

        Returns:
            Pruned list of branches
        """
        original_count = len(self.branches)
        self.branches = [b for b in self.branches if b.confidence >= threshold]
        removed = original_count - len(self.branches)

        if removed > 0:
            logger.info(
                f"ToT Branch Generator: Pruned {removed} unlikely branches "
                f"(threshold: {threshold})"
            )

        return self.branches

    def summary(self) -> dict:
        """Return summary statistics of generated branches."""
        branch_counts = {}
        likelihood_counts = {}

        for branch in self.branches:
            branch_counts[branch.branch_type] = \
                branch_counts.get(branch.branch_type, 0) + 1
            likelihood_counts[branch.likelihood] = \
                likelihood_counts.get(branch.likelihood, 0) + 1

        return {
            "total_branches": len(self.branches),
            "by_type": branch_counts,
            "by_likelihood": likelihood_counts,
        }
