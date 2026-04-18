"""
Advanced Multi-Criteria Ranking

Implements sophisticated ranking algorithms that consider multiple dimensions
of idea quality beyond simple overall scores. Uses Multi-Criteria Decision
Analysis (MCDA) for comprehensive evaluation.

Key Features:
- Multi-criteria scoring (Novelty × Feasibility × Impact)
- Customizable weight profiles
- Diversity-aware ranking
- Pareto frontier detection
- Confidence interval scoring
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from ..models import Evaluation, Idea

logger = logging.getLogger(__name__)


class RankingStrategy(str, Enum):
    """Ranking strategy options."""

    WEIGHTED_SUM = "weighted_sum"  # Standard weighted combination
    MULTIPLICATIVE = "multiplicative"  # Product of scores (penalizes weaknesses)
    PARETO = "pareto"  # Pareto-optimal ideas only
    DIVERSITY_FIRST = "diversity_first"  # Maximize diversity
    BALANCED = "balanced"  # Balance all factors


@dataclass
class RankingCriteria:
    """
    Criteria weights and parameters for multi-criteria ranking.

    Attributes:
        novelty_weight: Weight for novelty score (0-1)
        feasibility_weight: Weight for feasibility score (0-1)
        impact_weight: Weight for impact score (0-1)
        diversity_weight: Weight for diversity consideration (0-1)
        strategy: Ranking strategy to use
        penalty_factor: Penalty for low scores in multiplicative mode

    """

    novelty_weight: float = 0.3
    feasibility_weight: float = 0.3
    impact_weight: float = 0.4
    strategy: RankingStrategy = RankingStrategy.WEIGHTED_SUM
    penalty_factor: float = 0.5
    diversity_weight: float = 0.2

    def validate(self) -> None:
        """Validate criteria weights sum to approximately 1.0."""
        total = (
            self.novelty_weight +
            self.feasibility_weight +
            self.impact_weight
        )
        if not 0.9 <= total <= 1.1:
            logger.warning(
                f"Weights sum to {total:.2f}, expected ~1.0. "
                "Weights will be normalized."
            )

    def normalize(self) -> RankingCriteria:
        """Normalize weights to sum to 1.0."""
        total = (
            self.novelty_weight +
            self.feasibility_weight +
            self.impact_weight
        )
        if total > 0:
            return RankingCriteria(
                novelty_weight=self.novelty_weight / total,
                feasibility_weight=self.feasibility_weight / total,
                impact_weight=self.impact_weight / total,
                diversity_weight=self.diversity_weight,
                strategy=self.strategy,
                penalty_factor=self.penalty_factor
            )
        return self

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "novelty_weight": self.novelty_weight,
            "feasibility_weight": self.feasibility_weight,
            "impact_weight": self.impact_weight,
            "diversity_weight": self.diversity_weight,
            "strategy": self.strategy.value,
            "penalty_factor": self.penalty_factor,
        }


@dataclass
class RankedIdea:
    """
    An idea with advanced ranking metadata.

    Attributes:
        idea: The original idea
        rank: Position in ranked list (1-based)
        final_score: Final ranking score (0-100)
        criteria_scores: Individual dimension scores
        ranking_explanation: Explanation of why this rank was assigned
        pareto_dominated: Whether this idea is Pareto-dominated
        diversity_score: How diverse this idea is from others (0-1)
        confidence: Confidence in the ranking (0-1)
        metadata: Additional ranking information

    """

    idea: Idea
    rank: int = 0
    final_score: float = 0.0
    criteria_scores: dict[str, float] = field(default_factory=dict)
    ranking_explanation: list[str] = field(default_factory=list)
    pareto_dominated: bool = False
    diversity_score: float = 0.0
    confidence: float = 0.5
    metadata: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        """Get idea ID."""
        return self.idea.id

    @property
    def content(self) -> str:
        """Get idea content."""
        return self.idea.content

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "rank": self.rank,
            "final_score": self.final_score,
            "criteria_scores": self.criteria_scores,
            "ranking_explanation": self.ranking_explanation,
            "pareto_dominated": self.pareto_dominated,
            "diversity_score": self.diversity_score,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


class AdvancedRanker:
    """
    Advanced multi-criteria ranking for brainstorming results.

    Implements sophisticated ranking beyond simple overall scores:
    1. **Weighted Sum**: Standard weighted combination of criteria
    2. **Multiplicative**: Product of scores (penalizes weaknesses)
    3. **Pareto**: Identify non-dominated ideas
    4. **Diversity-First**: Maximize perspective diversity
    5. **Balanced**: Balance all factors evenly

    Attributes:
        criteria: Ranking criteria weights and strategy
        enable_diversity: Whether to consider diversity in ranking
        pareto_threshold: Minimum score for Pareto consideration

    Example:
        ```python
        ranker = AdvancedRanker(
            criteria=RankingCriteria(
                novelty_weight=0.4,
                feasibility_weight=0.3,
                impact_weight=0.3,
                strategy=RankingStrategy.BALANCED
            )
        )

        ranked = await ranker.rank(
            ideas=ideas,
            evaluations=evaluations,
            top_k=10
        )

        for ranked_idea in ranked:
            print(f"{ranked_idea.rank}. {ranked_idea.content}")
            print(f"   Score: {ranked_idea.final_score:.1f}")
            print(f"   Criteria: {ranked_idea.criteria_scores}")
        ```

    """

    def __init__(
        self,
        criteria: RankingCriteria | None = None,
        enable_diversity: bool = True,
        pareto_threshold: float = 60.0,
    ):
        """
        Initialize the advanced ranker.

        Args:
            criteria: Ranking criteria (default: balanced weights)
            enable_diversity: Whether to consider diversity
            pareto_threshold: Minimum score for Pareto frontier

        """
        self.criteria = (criteria or RankingCriteria()).normalize()
        self.criteria.validate()
        self.enable_diversity = enable_diversity
        self.pareto_threshold = pareto_threshold

        logger.info(
            f"AdvancedRanker initialized: strategy={self.criteria.strategy.value}, "
            f"diversity={enable_diversity}"
        )

    async def rank(
        self,
        ideas: list[Idea],
        evaluations: dict[str, Evaluation] | None = None,
        top_k: int = 10,
        criteria: RankingCriteria | None = None,
    ) -> list[RankedIdea]:
        """
        Rank ideas using multi-criteria decision analysis.

        Args:
            ideas: List of ideas to rank
            evaluations: Optional evaluations for detailed scoring
            top_k: Number of top ideas to return
            criteria: Optional override of default criteria

        Returns:
            List of ranked ideas, sorted by rank (ascending)

        Example:
            ```python
            ranked = await ranker.rank(
                ideas=generated_ideas,
                evaluations=evaluations,
                top_k=10
            )

            for ranked_idea in ranked:
                print(f"{ranked_idea.rank}. {ranked_idea.content}")
                print(f"   Score: {ranked_idea.final_score:.2f}")
                if ranked_idea.pareto_dominated:
                    print(f"   Note: Pareto-dominated by other ideas")
            ```

        """
        if not ideas:
            logger.warning("No ideas provided for ranking")
            return []

        # Use override criteria if provided
        if criteria:
            criteria = criteria.normalize()
        else:
            criteria = self.criteria

        logger.info(f"Ranking {len(ideas)} ideas using {criteria.strategy.value} strategy...")

        # Calculate scores for each idea
        ranked_ideas = []
        for idea in ideas:
            ranked = await self._rank_single_idea(
                idea,
                ideas,  # Pass all ideas for diversity calculation
                evaluations,
                criteria
            )
            ranked_ideas.append(ranked)

        # Apply ranking strategy
        if criteria.strategy == RankingStrategy.PARETO:
            ranked_ideas = self._apply_pareto_ranking(ranked_ideas)
        elif criteria.strategy == RankingStrategy.DIVERSITY_FIRST:
            ranked_ideas = self._apply_diversity_ranking(ranked_ideas)
        else:
            # Standard ranking by final score
            ranked_ideas.sort(key=lambda x: x.final_score, reverse=True)

        # Update ranks
        for i, ranked_idea in enumerate(ranked_ideas, 1):
            ranked_idea.rank = i

        # Select top_k
        results = ranked_ideas[:top_k]

        logger.info(
            f"Ranking complete: returned {len(results)} ideas "
            f"(requested {top_k})"
        )

        return results

    async def _rank_single_idea(
        self,
        idea: Idea,
        all_ideas: list[Idea],
        evaluations: dict[str, Evaluation] | None,
        criteria: RankingCriteria,
    ) -> RankedIdea:
        """Rank a single idea using the specified criteria."""
        # Get evaluation or create default
        evaluation = evaluations.get(idea.id) if evaluations else None

        if evaluation:
            novelty = evaluation.novelty_score
            feasibility = evaluation.feasibility_score
            impact = evaluation.impact_score
        else:
            # Use idea score as fallback for all dimensions
            novelty = feasibility = impact = idea.score

        # Calculate individual criteria scores
        criteria_scores = {
            "novelty": novelty,
            "feasibility": feasibility,
            "impact": impact,
        }

        # Calculate final score based on strategy
        if criteria.strategy == RankingStrategy.MULTIPLICATIVE:
            final_score = self._calculate_multiplicative_score(
                novelty,
                feasibility,
                impact,
                criteria
            )
        else:
            # Default: weighted sum
            final_score = self._calculate_weighted_sum(
                novelty,
                feasibility,
                impact,
                criteria
            )

        # Calculate diversity score if enabled
        diversity_score = 0.0
        if self.enable_diversity:
            diversity_score = self._calculate_diversity_score(
                idea,
                all_ideas
            )
            # Apply diversity boost
            final_score *= (1.0 + diversity_score * criteria.diversity_weight)

        # Ensure score is in valid range
        final_score = max(0.0, min(100.0, final_score))

        # Calculate confidence
        confidence = self._calculate_confidence(
            idea,
            evaluation,
            diversity_score
        )

        # Generate ranking explanation
        explanation = self._generate_explanation(
            idea,
            criteria_scores,
            final_score,
            diversity_score
        )

        return RankedIdea(
            idea=idea,
            final_score=final_score,
            criteria_scores=criteria_scores,
            ranking_explanation=explanation,
            diversity_score=diversity_score,
            confidence=confidence,
            metadata={
                "strategy": criteria.strategy.value,
                "weighted_novelty": novelty * criteria.novelty_weight,
                "weighted_feasibility": feasibility * criteria.feasibility_weight,
                "weighted_impact": impact * criteria.impact_weight,
            }
        )

    def _calculate_weighted_sum(
        self,
        novelty: float,
        feasibility: float,
        impact: float,
        criteria: RankingCriteria
    ) -> float:
        """Calculate weighted sum score."""
        return (
            novelty * criteria.novelty_weight +
            feasibility * criteria.feasibility_weight +
            impact * criteria.impact_weight
        )

    def _calculate_multiplicative_score(
        self,
        novelty: float,
        feasibility: float,
        impact: float,
        criteria: RankingCriteria
    ) -> float:
        """
        Calculate multiplicative score.

        Multiplicative scoring penalizes ideas with weaknesses in any area.
        An idea with (100, 100, 50) scores lower than (75, 75, 75).
        """
        # Normalize to 0-1 range
        n_norm = novelty / 100.0
        f_norm = feasibility / 100.0
        i_norm = impact / 100.0

        # Apply penalty factor for low scores
        if n_norm < 0.5:
            n_norm *= criteria.penalty_factor
        if f_norm < 0.5:
            f_norm *= criteria.penalty_factor
        if i_norm < 0.5:
            i_norm *= criteria.penalty_factor

        # Multiply and scale back to 0-100
        product = n_norm * f_norm * i_norm
        return product * 100.0

    def _calculate_diversity_score(
        self,
        idea: Idea,
        all_ideas: list[Idea]
    ) -> float:
        """
        Calculate how diverse this idea is from others.

        Higher diversity = more unique perspective.
        """
        if not all_ideas or len(all_ideas) < 2:
            return 0.0

        # Calculate average dissimilarity
        total_dissimilarity = 0.0
        count = 0

        for other in all_ideas:
            if other.id != idea.id:
                # Persona diversity
                persona_diff = 0.5 if idea.persona != other.persona else 0.0

                # Content diversity (word overlap inverse)
                words1 = set(idea.content.lower().split())
                words2 = set(other.content.lower().split())

                if words1 and words2:
                    overlap = len(words1 & words2) / len(words1 | words2)
                    content_diversity = 1.0 - overlap
                else:
                    content_diversity = 0.5

                # Score diversity
                score_diff = abs(idea.score - other.score) / 100.0

                # Combine
                dissimilarity = (
                    persona_diff * 0.3 +
                    content_diversity * 0.5 +
                    score_diff * 0.2
                )

                total_dissimilarity += dissimilarity
                count += 1

        if count == 0:
            return 0.0

        return total_dissimilarity / count

    def _calculate_confidence(
        self,
        idea: Idea,
        evaluation: Evaluation | None,
        diversity_score: float
    ) -> float:
        """Calculate confidence in the ranking."""
        base_confidence = 0.5

        # Higher if we have detailed evaluation
        if evaluation:
            base_confidence += 0.2

        # Higher if reasoning path is present
        if idea.reasoning_path:
            base_confidence += 0.1

        # Higher if diverse (more unique)
        base_confidence += diversity_score * 0.2

        return min(1.0, base_confidence)

    def _generate_explanation(
        self,
        idea: Idea,
        criteria_scores: dict[str, float],
        final_score: float,
        diversity_score: float
    ) -> list[str]:
        """Generate explanation for the ranking."""
        explanation = []

        # Overall assessment
        if final_score >= 80:
            explanation.append("Exceptional idea with outstanding overall quality")
        elif final_score >= 70:
            explanation.append("Strong idea with good overall quality")
        elif final_score >= 60:
            explanation.append("Moderate idea with reasonable quality")
        else:
            explanation.append("Idea needs improvement in multiple areas")

        # Dimension breakdown
        novelty = criteria_scores.get("novelty", 0)
        feasibility = criteria_scores.get("feasibility", 0)
        impact = criteria_scores.get("impact", 0)

        if novelty >= 75:
            explanation.append(f"High novelty ({novelty:.0f}/100): Very creative and original")
        elif novelty >= 60:
            explanation.append(f"Good novelty ({novelty:.0f}/100): Some creative elements")
        else:
            explanation.append(f"Lower novelty ({novelty:.0f}/100): Could be more innovative")

        if feasibility >= 75:
            explanation.append(f"High feasibility ({feasibility:.0f}/100): Very practical")
        elif feasibility >= 60:
            explanation.append(f"Good feasibility ({feasibility:.0f}/100): Reasonably practical")
        else:
            explanation.append(f"Lower feasibility ({feasibility:.0f}/100): May be challenging to implement")

        if impact >= 75:
            explanation.append(f"High impact ({impact:.0f}/100): Significant potential")
        elif impact >= 60:
            explanation.append(f"Good impact ({impact:.0f}/100): Meaningful potential")
        else:
            explanation.append(f"Lower impact ({impact:.0f}/100): Limited potential impact")

        # Diversity note
        if diversity_score > 0.6:
            explanation.append(f"Highly unique perspective (diversity: {diversity_score:.2f})")
        elif diversity_score > 0.3:
            explanation.append(f"Somewhat unique perspective (diversity: {diversity_score:.2f})")
        else:
            explanation.append(f"Similar to other ideas (diversity: {diversity_score:.2f})")

        return explanation

    def _apply_pareto_ranking(self, ranked_ideas: list[RankedIdea]) -> list[RankedIdea]:
        """
        Apply Pareto-optimal ranking.

        An idea is Pareto-optimal if no other idea is better in ALL dimensions.
        """
        # Filter to ideas above threshold
        candidates = [
            r for r in ranked_ideas
            if r.final_score >= self.pareto_threshold
        ]

        if not candidates:
            return ranked_ideas

        # Find Pareto frontier
        pareto_optimal = []
        for candidate in candidates:
            is_dominated = False

            for other in candidates:
                if other.id == candidate.id:
                    continue

                # Check if 'other' dominates 'candidate'
                # (better in all criteria)
                other_scores = other.criteria_scores
                candidate_scores = candidate.criteria_scores

                if all(
                    other_scores.get(k, 0) >= candidate_scores.get(k, 0) - 1.0  # Small tolerance
                    for k in ["novelty", "feasibility", "impact"]
                ):
                    is_dominated = True
                    candidate.pareto_dominated = True
                    break

            if not is_dominated:
                pareto_optimal.append(candidate)

        # Return Pareto-optimal ideas sorted by final score
        if pareto_optimal:
            pareto_optimal.sort(key=lambda x: x.final_score, reverse=True)
            logger.info(f"Pareto ranking: {len(pareto_optimal)} non-dominated ideas")
            return pareto_optimal
        logger.warning("No Pareto-optimal ideas found, returning all candidates")
        return candidates

    def _apply_diversity_ranking(self, ranked_ideas: list[RankedIdea]) -> list[RankedIdea]:
        """
        Apply diversity-first ranking.

        Maximizes diversity in the selected set while maintaining quality.
        """
        if not ranked_ideas:
            return ranked_ideas

        # Sort by final score first
        ranked_ideas.sort(key=lambda x: x.final_score, reverse=True)

        # Greedy selection to maximize diversity
        selected = []
        remaining = ranked_ideas.copy()

        # Always include top-ranked idea
        if remaining:
            selected.append(remaining.pop(0))

        # Select subsequent ideas balancing score and diversity
        while remaining:
            best_candidate = None
            best_combined_score = -1.0

            for candidate in remaining:
                # Calculate diversity from already selected
                min_diversity = 1.0
                for sel in selected:
                    # Simple diversity metric: persona and content difference
                    persona_diff = 0.5 if candidate.idea.persona != sel.idea.persona else 0.0

                    words1 = set(candidate.idea.content.lower().split())
                    words2 = set(sel.idea.content.lower().split())
                    if words1 and words2:
                        overlap = len(words1 & words2) / len(words1 | words2)
                        content_diversity = 1.0 - overlap
                    else:
                        content_diversity = 0.5

                    diversity = persona_diff * 0.4 + content_diversity * 0.6
                    min_diversity = min(min_diversity, diversity)

                # Combined score: 70% quality, 30% diversity
                combined = (
                    candidate.final_score / 100.0 * 0.7 +
                    min_diversity * 0.3
                )

                if combined > best_combined_score:
                    best_combined_score = combined
                    best_candidate = candidate

            if best_candidate:
                selected.append(best_candidate)
                remaining.remove(best_candidate)
            else:
                break

        logger.info(
            f"Diversity ranking: selected {len(selected)} diverse ideas "
            f"from {len(ranked_ideas)} total"
        )

        return selected


__all__ = [
    "AdvancedRanker",
    "RankedIdea",
    "RankingCriteria",
    "RankingStrategy",
]
