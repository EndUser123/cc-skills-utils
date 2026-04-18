"""
Advanced Convergence Algorithms for Phase 3 Brainstorming

This package implements sophisticated convergence algorithms that go beyond simple
ranking to provide intelligent idea selection, clustering, synthesis, and diversity
assurance.

Key Components:
- IdeaClustering: Semantic similarity-based clustering and deduplication
- IdeaSynthesizer: Combines complementary ideas into hybrid solutions
- AdvancedRanker: Multi-criteria decision analysis with weighted scoring
- ConvergenceEngine: Full convergence pipeline orchestrating all components

Features:
- Semantic clustering using embedding similarity
- Intelligent deduplication to remove redundant ideas
- Synthesis of complementary ideas into stronger hybrid solutions
- Multi-criteria ranking (Novelty × Feasibility × Impact)
- Diversity assurance to ensure varied perspectives
- Configurable thresholds and weights for customization

Example:
    ```python
    from ..convergence import ConvergenceEngine

    engine = ConvergenceEngine()
    converged = await engine.converge(
        ideas=generated_ideas,
        top_k=10,
        similarity_threshold=0.75,
        enable_synthesis=True
    )

    for idea in converged:
        print(f"{idea.content} (Score: {idea.final_score:.2f})")
        if idea.synthesized_from:
            print(f"  Synthesized from: {idea.synthesized_from}")
    ```

"""
from __future__ import annotations

from .clustering import (
    Cluster,
    ClusterMetrics,
    IdeaClustering,
)
from .engine import (
    ConvergedIdea,
    ConvergenceConfig,
    ConvergenceEngine,
    ConvergenceReport,
)
from .ranking import (
    AdvancedRanker,
    RankedIdea,
    RankingCriteria,
    RankingStrategy,
)
from .synthesizer import IdeaSynthesizer, SynthesizedIdea

__all__ = [
    # Clustering
    "IdeaClustering",
    "Cluster",
    "ClusterMetrics",

    # Synthesis
    "IdeaSynthesizer",
    "SynthesizedIdea",

    # Ranking
    "AdvancedRanker",
    "RankedIdea",
    "RankingCriteria",
    "RankingStrategy",

    # Engine
    "ConvergenceEngine",
    "ConvergedIdea",
    "ConvergenceConfig",
    "ConvergenceReport",
]
