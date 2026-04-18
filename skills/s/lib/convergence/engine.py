"""
Convergence Engine - Full Pipeline Orchestrator

Orchestrates the complete convergence pipeline including clustering,
deduplication, synthesis, and advanced ranking to produce the final
set of converged ideas.

Pipeline:
1. Cluster similar ideas (optional)
2. Deduplicate to remove redundancy (optional)
3. Synthesize complementary ideas (optional)
4. Apply advanced ranking
5. Ensure diversity in final set
6. Generate comprehensive report
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..models import Evaluation, Idea
from .clustering import (
    IdeaClustering,
)
from .ranking import (
    AdvancedRanker,
    RankedIdea,
    RankingCriteria,
    RankingStrategy,
)
from .synthesizer import (
    IdeaSynthesizer,
    SynthesizedIdea,
)

logger = logging.getLogger(__name__)


@dataclass
class ConvergenceConfig:
    """
    Configuration for the convergence pipeline.

    Attributes:
        enable_clustering: Whether to perform clustering
        enable_deduplication: Whether to deduplicate ideas
        enable_synthesis: Whether to synthesize new ideas
        similarity_threshold: Threshold for clustering (0-1)
        complementarity_threshold: Threshold for synthesis (0-1)
        ranking_strategy: Strategy for ranking
        top_k: Number of final ideas to return
        diversity_threshold: Minimum diversity for final set
        max_synthesis_per_cluster: Max synthesized ideas per cluster

    """

    enable_clustering: bool = True
    enable_deduplication: bool = True
    enable_synthesis: bool = True
    similarity_threshold: float = 0.75
    complementarity_threshold: float = 0.65
    ranking_strategy: RankingStrategy = RankingStrategy.BALANCED
    top_k: int = 10
    diversity_threshold: float = 0.3
    max_synthesis_per_cluster: int = 2
    clustering_min_cluster_size: int = 1

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "enable_clustering": self.enable_clustering,
            "enable_deduplication": self.enable_deduplication,
            "enable_synthesis": self.enable_synthesis,
            "similarity_threshold": self.similarity_threshold,
            "complementarity_threshold": self.complementarity_threshold,
            "ranking_strategy": self.ranking_strategy.value,
            "top_k": self.top_k,
            "diversity_threshold": self.diversity_threshold,
            "max_synthesis_per_cluster": self.max_synthesis_per_cluster,
            "clustering_min_cluster_size": self.clustering_min_cluster_size,
        }


@dataclass
class ConvergedIdea:
    """
    A converged idea with full metadata.

    Attributes:
        idea: The final idea (may be original or synthesized)
        rank: Final rank (1-based)
        cluster_id: Cluster this idea came from (if clustered)
        synthesized_from: Source idea IDs if synthesized
        synthesis_quality: Quality score if synthesized
        deduplicates: List of duplicate IDs this replaces
        final_score: Final convergence score
        metadata: Additional convergence information

    """

    idea: Idea
    rank: int = 0
    cluster_id: str | None = None
    synthesized_from: list[str] = field(default_factory=list)
    synthesis_quality: float = 0.0
    deduplicates: list[str] = field(default_factory=list)
    final_score: float = 0.0
    metadata: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        """Get idea ID."""
        return self.idea.id

    @property
    def content(self) -> str:
        """Get idea content."""
        return self.idea.content

    @property
    def is_synthesized(self) -> bool:
        """Whether this is a synthesized idea."""
        return len(self.synthesized_from) > 0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "rank": self.rank,
            "cluster_id": self.cluster_id,
            "synthesized_from": self.synthesized_from,
            "synthesis_quality": self.synthesis_quality,
            "deduplicates": self.deduplicates,
            "final_score": self.final_score,
            "is_synthesized": self.is_synthesized,
            "persona": self.idea.persona,
            "score": self.idea.score,
            "metadata": self.metadata,
        }


@dataclass
class ConvergenceReport:
    """
    Comprehensive report on the convergence process.

    Attributes:
        total_input_ideas: Number of ideas input
        total_output_ideas: Number of ideas output
        clusters_created: Number of clusters created
        duplicates_removed: Number of duplicates removed
        ideas_synthesized: Number of new ideas synthesized
        final_diversity_score: Diversity of final set
        processing_time_seconds: Time taken for convergence
        config: Configuration used
        phase_results: Results from each phase
        metadata: Additional report information

    """

    total_input_ideas: int = 0
    total_output_ideas: int = 0
    clusters_created: int = 0
    duplicates_removed: int = 0
    ideas_synthesized: int = 0
    final_diversity_score: float = 0.0
    processing_time_seconds: float = 0.0
    config: ConvergenceConfig = field(default_factory=ConvergenceConfig)
    phase_results: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_input_ideas": self.total_input_ideas,
            "total_output_ideas": self.total_output_ideas,
            "clusters_created": self.clusters_created,
            "duplicates_removed": self.duplicates_removed,
            "ideas_synthesized": self.ideas_synthesized,
            "final_diversity_score": self.final_diversity_score,
            "processing_time_seconds": self.processing_time_seconds,
            "config": self.config.to_dict(),
            "phase_results": self.phase_results,
            "metadata": self.metadata,
        }


class ConvergenceEngine:
    """
    Full convergence pipeline orchestrator.

    Coordinates clustering, deduplication, synthesis, and ranking
    to produce a high-quality, diverse set of converged ideas.

    Pipeline Steps:
    1. **Optional Clustering**: Group similar ideas together
    2. **Optional Deduplication**: Remove redundant ideas
    3. **Optional Synthesis**: Create hybrid ideas from clusters
    4. **Ranking**: Apply multi-criteria ranking
    5. **Diversity Assurance**: Ensure final set has diverse perspectives
    6. **Reporting**: Generate comprehensive convergence report

    Attributes:
        config: Convergence configuration
        clustering: Idea clustering engine
        synthesizer: Idea synthesis engine
        ranker: Advanced ranking engine

    Example:
        ```python
        engine = ConvergenceEngine(
            config=ConvergenceConfig(
                enable_clustering=True,
                enable_synthesis=True,
                top_k=10
            )
        )

        converged, report = await engine.converge(
            ideas=generated_ideas,
            evaluations=evaluations
        )

        print(f"Converged to {len(converged)} ideas")
        for conv in converged:
            print(f"{conv.rank}. {conv.content}")
            if conv.is_synthesized:
                print(f"   Synthesized from {conv.synthesized_from}")

        print(f"Report: {report.to_dict()}")
        ```

    """

    def __init__(
        self,
        config: ConvergenceConfig | None = None,
    ):
        """
        Initialize the convergence engine.

        Args:
            config: Convergence configuration (default: sensible defaults)

        """
        self.config = config or ConvergenceConfig()

        # Initialize sub-components
        self.clustering = IdeaClustering(
            similarity_threshold=self.config.similarity_threshold,
            min_cluster_size=self.config.clustering_min_cluster_size,
        )

        self.synthesizer = IdeaSynthesizer(
            complementarity_threshold=self.config.complementarity_threshold,
        )

        ranking_criteria = RankingCriteria(
            strategy=self.config.ranking_strategy,
        )
        self.ranker = AdvancedRanker(
            criteria=ranking_criteria,
            enable_diversity=True,
        )

        logger.info(
            f"ConvergenceEngine initialized with config: "
            f"clustering={self.config.enable_clustering}, "
            f"deduplication={self.config.enable_deduplication}, "
            f"synthesis={self.config.enable_synthesis}, "
            f"top_k={self.config.top_k}"
        )

    async def converge(
        self,
        ideas: list[Idea],
        evaluations: dict[str, Evaluation] | None = None,
        config: ConvergenceConfig | None = None,
    ) -> tuple[list[ConvergedIdea], ConvergenceReport]:
        """
        Run the full convergence pipeline.

        Args:
            ideas: Ideas to converge
            evaluations: Optional evaluations for ranking
            config: Optional config override

        Returns:
            Tuple of (converged_ideas, report)

        Example:
            ```python
            converged, report = await engine.converge(
                ideas=ideas,
                evaluations=evaluations,
                config=ConvergenceConfig(top_k=5, enable_synthesis=True)
            )

            for conv_idea in converged:
                print(f"{conv_idea.rank}. {conv_idea.content}")
                print(f"   Score: {conv_idea.final_score:.2f}")

            print(f"\\nReport: {report.to_dict()}")
            ```

        """
        import time
        start_time = time.time()

        # Use override config if provided
        if config:
            self.config = config

        logger.info(f"Starting convergence pipeline with {len(ideas)} ideas...")

        # Initialize report
        report = ConvergenceReport(
            total_input_ideas=len(ideas),
            config=self.config,
        )

        # Track ideas through pipeline
        current_ideas = ideas.copy()
        phase_results = {}

        # Phase 1: Clustering (optional)
        clusters = []
        if self.config.enable_clustering:
            logger.info("Phase 1: Clustering ideas...")
            clusters = await self.clustering.cluster_ideas(
                current_ideas,
                evaluations
            )
            report.clusters_created = len(clusters)
            phase_results["clustering"] = {
                "clusters": len(clusters),
                "avg_cluster_size": sum(c.size for c in clusters) / len(clusters) if clusters else 0,
            }
            logger.info(f"  Created {len(clusters)} clusters")
        else:
            # Create mock clusters (one per idea)
            from .clustering import Cluster
            clusters = [
                Cluster(ideas=[idea], representative_id=idea.id)
                for idea in current_ideas
            ]

        # Phase 2: Deduplication (optional)
        deduplication_map: dict[str, list[str]] = {}
        if self.config.enable_deduplication and self.config.enable_clustering:
            logger.info("Phase 2: Deduplicating ideas...")
            current_ideas, deduplication_map = await self.clustering.deduplicate(
                ideas=current_ideas,
                clusters=clusters,
            )
            report.duplicates_removed = len(ideas) - len(current_ideas)
            phase_results["deduplication"] = {
                "duplicates_removed": report.duplicates_removed,
                "retained_ideas": len(current_ideas),
            }
            logger.info(f"  Removed {report.duplicates_removed} duplicates")
        else:
            deduplication_map = {idea.id: [] for idea in current_ideas}

        # Phase 3: Synthesis (optional)
        synthesized_ideas: list[SynthesizedIdea] = []
        if self.config.enable_synthesis and clusters:
            logger.info("Phase 3: Synthesizing ideas...")
            for cluster in clusters:
                if cluster.size >= 2:  # Only synthesize from clusters with 2+ ideas
                    syn_from_cluster = await self.synthesizer.synthesize(
                        cluster=cluster,
                        max_results=self.config.max_synthesis_per_cluster,
                        evaluations=evaluations,
                    )
                    synthesized_ideas.extend(syn_from_cluster)

            report.ideas_synthesized = len(synthesized_ideas)
            phase_results["synthesis"] = {
                "synthesized": report.ideas_synthesized,
                "avg_quality": sum(s.synthesis_quality for s in synthesized_ideas) / len(synthesized_ideas) if synthesized_ideas else 0,
            }
            logger.info(f"  Synthesized {report.ideas_synthesized} new ideas")

            # Convert synthesized ideas to Idea objects
            for syn_idea in synthesized_ideas:
                idea = syn_idea.to_idea(
                    persona="synthesizer",
                    score=syn_idea.synthesis_quality * 100
                )
                current_ideas.append(idea)

        # Phase 4: Ranking
        logger.info("Phase 4: Ranking ideas...")
        ranked = await self.ranker.rank(
            ideas=current_ideas,
            evaluations=evaluations,
            top_k=self.config.top_k * 2,  # Get more for diversity filtering
            criteria=RankingCriteria(strategy=self.config.ranking_strategy),
        )
        logger.info(f"  Ranked {len(ranked)} ideas")

        # Phase 5: Diversity Assurance
        logger.info("Phase 5: Ensuring diversity...")
        final_ranked = self._ensure_diversity(
            ranked_ideas=ranked,
            top_k=self.config.top_k
        )
        logger.info(f"  Selected {len(final_ranked)} diverse ideas")

        # Phase 6: Create ConvergedIdea objects
        converged = []
        for ranked_idea in final_ranked:
            # Find cluster ID
            cluster_id = None
            for cluster in clusters:
                if any(idea.id == ranked_idea.id for idea in cluster.ideas):
                    cluster_id = cluster.id
                    break

            # Check if synthesized
            synthesized_from = []
            synthesis_quality = 0.0
            for syn_idea in synthesized_ideas:
                if syn_idea.id == ranked_idea.id:
                    synthesized_from = syn_idea.synthesized_from
                    synthesis_quality = syn_idea.synthesis_quality
                    break

            # Check deduplicates
            deduplicates = []
            for kept_id, dup_ids in deduplication_map.items():
                if kept_id == ranked_idea.id:
                    deduplicates = dup_ids
                    break

            converged_idea = ConvergedIdea(
                idea=ranked_idea.idea,
                rank=ranked_idea.rank,
                cluster_id=cluster_id,
                synthesized_from=synthesized_from,
                synthesis_quality=synthesis_quality,
                deduplicates=deduplicates,
                final_score=ranked_idea.final_score,
                metadata={
                    "criteria_scores": ranked_idea.criteria_scores,
                    "diversity_score": ranked_idea.diversity_score,
                    "confidence": ranked_idea.confidence,
                    "pareto_dominated": ranked_idea.pareto_dominated,
                }
            )
            converged.append(converged_idea)

        # Calculate final metrics
        report.total_output_ideas = len(converged)
        report.final_diversity_score = self._calculate_set_diversity(converged)
        report.processing_time_seconds = time.time() - start_time
        report.phase_results = phase_results

        logger.info(
            f"Convergence complete: {len(ideas)} -> {len(converged)} ideas "
            f"in {report.processing_time_seconds:.2f}s"
        )

        return converged, report

    def _ensure_diversity(
        self,
        ranked_ideas: list[RankedIdea],
        top_k: int
    ) -> list[RankedIdea]:
        """
        Ensure final set has diverse perspectives.

        Uses greedy selection to balance quality with diversity.
        """
        if len(ranked_ideas) <= top_k:
            return ranked_ideas

        selected = []
        remaining = ranked_ideas.copy()

        # Always include top-ranked
        if remaining:
            selected.append(remaining.pop(0))

        # Greedy selection for diversity
        while remaining and len(selected) < top_k:
            best_candidate = None
            best_score = -1.0

            for candidate in remaining:
                # Calculate minimum diversity from selected
                min_div = 1.0
                for _sel in selected:
                    # Use diversity score from candidate
                    div = candidate.diversity_score
                    min_div = min(min_div, div)

                # Combined: quality (60%) + diversity (40%)
                combined = (
                    candidate.final_score / 100.0 * 0.6 +
                    min_div * 0.4
                )

                if combined > best_score:
                    best_score = combined
                    best_candidate = candidate

            if best_candidate:
                selected.append(best_candidate)
                remaining.remove(best_candidate)
            else:
                break

        return selected

    def _calculate_set_diversity(self, converged: list[ConvergedIdea]) -> float:
        """Calculate diversity of the final converged set."""
        if not converged or len(converged) < 2:
            return 0.0

        # Calculate average pairwise diversity
        total_diversity = 0.0
        count = 0

        for i in range(len(converged)):
            for j in range(i + 1, len(converged)):
                # Persona diversity
                persona_diff = (
                    0.5 if converged[i].idea.persona != converged[j].idea.persona
                    else 0.0
                )

                # Content diversity
                words1 = set(converged[i].idea.content.lower().split())
                words2 = set(converged[j].idea.content.lower().split())

                if words1 and words2:
                    overlap = len(words1 & words2) / len(words1 | words2)
                    content_div = 1.0 - overlap
                else:
                    content_div = 0.5

                # Score diversity
                score_diff = abs(converged[i].final_score - converged[j].final_score) / 100.0

                # Combine
                diversity = persona_diff * 0.3 + content_div * 0.5 + score_diff * 0.2
                total_diversity += diversity
                count += 1

        return total_diversity / count if count > 0 else 0.0


__all__ = [
    "ConvergedIdea",
    "ConvergenceConfig",
    "ConvergenceEngine",
    "ConvergenceReport",
]
