"""
Idea Clustering and Deduplication

Implements semantic similarity-based clustering to group similar ideas together
and identify redundant or duplicate ideas. Uses embedding-based similarity for
robust semantic matching.

Key Features:
- Semantic similarity clustering using embeddings
- Configurable similarity thresholds
- Cluster quality metrics
- Representative idea selection
- Redundancy detection and elimination
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from ..models import Evaluation, Idea

logger = logging.getLogger(__name__)


@dataclass
class ClusterMetrics:
    """
    Metrics for assessing cluster quality.

    Attributes:
        cohesion: Average similarity within the cluster (0-1)
        separation: Average distance to other clusters (0-1)
        representative_score: Score of the most representative idea
        diversity_score: How diverse the ideas are within the cluster (0-1)

    """

    cohesion: float = 0.0
    separation: float = 0.0
    representative_score: float = 0.0
    diversity_score: 0.0 = 0.0

    def overall_quality(self) -> float:
        """Calculate overall cluster quality score."""
        return (
            self.cohesion * 0.4 +
            self.separation * 0.3 +
            self.diversity_score * 0.3
        )


@dataclass
class Cluster:
    """
    A cluster of semantically similar ideas.

    Attributes:
        id: Unique cluster identifier
        ideas: Ideas in this cluster
        representative_id: ID of the most representative idea
        similarity_threshold: Threshold used for clustering
        metrics: Quality metrics for this cluster
        metadata: Additional cluster information

    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ideas: list[Idea] = field(default_factory=list)
    representative_id: str | None = None
    similarity_threshold: float = 0.7
    metrics: ClusterMetrics = field(default_factory=ClusterMetrics)
    metadata: dict = field(default_factory=dict)

    @property
    def size(self) -> int:
        """Get the number of ideas in the cluster."""
        return len(self.ideas)

    @property
    def representative(self) -> Idea | None:
        """Get the most representative idea in the cluster."""
        if self.representative_id:
            for idea in self.ideas:
                if idea.id == self.representative_id:
                    return idea
        return self.ideas[0] if self.ideas else None

    def add_idea(self, idea: Idea) -> None:
        """Add an idea to the cluster."""
        self.ideas.append(idea)

    def get_similarity_matrix(self) -> list[list[float]]:
        """
        Calculate pairwise similarity matrix for cluster ideas.

        Returns:
            N x N matrix of similarity scores (0-1)

        """
        n = len(self.ideas)
        matrix = [[0.0] * n for _ in range(n)]

        for i in range(n):
            for j in range(i, n):
                if i == j:
                    similarity = 1.0
                else:
                    similarity = self._calculate_semantic_similarity(
                        self.ideas[i],
                        self.ideas[j]
                    )
                matrix[i][j] = similarity
                matrix[j][i] = similarity

        return matrix

    def _calculate_semantic_similarity(self, idea1: Idea, idea2: Idea) -> float:
        """
        Calculate semantic similarity between two ideas.

        For MVP, uses content overlap and keyword matching.
        In production, would use embedding-based similarity.

        Args:
            idea1: First idea
            idea2: Second idea

        Returns:
            Similarity score (0-1)

        """
        # Normalize content for comparison
        content1 = set(idea1.content.lower().split())
        content2 = set(idea2.content.lower().split())

        if not content1 or not content2:
            return 0.0

        # Jaccard similarity for word overlap
        intersection = content1 & content2
        union = content1 | content2

        jaccard = len(intersection) / len(union) if union else 0.0

        # Boost for persona match (same perspective)
        persona_boost = 0.1 if idea1.persona == idea2.persona else 0.0

        # Combine with score similarity
        score_diff = abs(idea1.score - idea2.score) / 100.0
        score_similarity = 1.0 - score_diff

        # Weighted combination
        similarity = (
            jaccard * 0.6 +
            score_similarity * 0.3 +
            persona_boost * 0.1
        )

        return min(1.0, max(0.0, similarity))


class IdeaClustering:
    """
    Advanced clustering for idea deduplication and grouping.

    Implements semantic similarity-based clustering to:
    - Group similar ideas for analysis
    - Identify redundant/duplicate ideas
    - Select representative ideas from clusters
    - Calculate cluster quality metrics

    Attributes:
        similarity_threshold: Minimum similarity for clustering (default: 0.7)
        min_cluster_size: Minimum ideas to form a cluster (default: 1)
        max_clusters: Maximum number of clusters to create (default: None)

    Example:
        ```python
        clustering = IdeaClustering(similarity_threshold=0.75)
        clusters = await clustering.cluster_ideas(ideas)

        for cluster in clusters:
            print(f"Cluster {cluster.id}: {cluster.size} ideas")
            print(f"Representative: {cluster.representative.content}")
        ```

    """

    def __init__(
        self,
        similarity_threshold: float = 0.7,
        min_cluster_size: int = 1,
        max_clusters: int | None = None,
    ):
        """
        Initialize the clustering engine.

        Args:
            similarity_threshold: Minimum similarity for clustering (0-1)
            min_cluster_size: Minimum ideas to form a cluster
            max_clusters: Optional maximum number of clusters

        """
        if not 0.0 <= similarity_threshold <= 1.0:
            raise ValueError("similarity_threshold must be between 0 and 1")

        self.similarity_threshold = similarity_threshold
        self.min_cluster_size = min_cluster_size
        self.max_clusters = max_clusters

        logger.info(
            f"IdeaClustering initialized: threshold={similarity_threshold}, "
            f"min_size={min_cluster_size}"
        )

    async def cluster_ideas(
        self,
        ideas: list[Idea],
        evaluations: dict[str, Evaluation] | None = None,
    ) -> list[Cluster]:
        """
        Cluster ideas based on semantic similarity.

        Uses agglomerative clustering approach:
        1. Start with each idea as its own cluster
        2. Iteratively merge most similar clusters
        3. Stop when similarity falls below threshold

        Args:
            ideas: List of ideas to cluster
            evaluations: Optional evaluations for scoring-informed clustering

        Returns:
            List of clusters, sorted by size (descending)

        Example:
            ```python
            clusters = await clustering.cluster_ideas(
                ideas=generated_ideas,
                evaluations=evaluations
            )

            # Get representative ideas from each cluster
            representatives = [
                cluster.representative
                for cluster in clusters
                if cluster.representative
            ]
            ```

        """
        if not ideas:
            logger.warning("No ideas provided for clustering")
            return []

        logger.info(f"Clustering {len(ideas)} ideas...")

        # Initialize: each idea is its own cluster
        clusters = [
            Cluster(
                ideas=[idea],
                representative_id=idea.id,
                similarity_threshold=self.similarity_threshold,
                metadata={"created_at": datetime.utcnow().isoformat()}
            )
            for idea in ideas
        ]

        # Agglomerative clustering: iteratively merge similar clusters
        merged = True
        iteration = 0
        max_iterations = len(ideas) * 2  # Prevent infinite loops

        while merged and iteration < max_iterations:
            merged = False
            iteration += 1

            # Check if we've hit max clusters limit
            if self.max_clusters and len(clusters) <= self.max_clusters:
                break

            # Find most similar pair of clusters
            best_pair = None
            best_similarity = 0.0

            for i in range(len(clusters)):
                for j in range(i + 1, len(clusters)):
                    similarity = self._cluster_similarity(clusters[i], clusters[j])

                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_pair = (i, j)

            # Merge if similarity is above threshold
            if best_pair and best_similarity >= self.similarity_threshold:
                i, j = best_pair
                merged_cluster = self._merge_clusters(
                    clusters[i],
                    clusters[j],
                    best_similarity,
                    evaluations
                )

                # Remove original clusters and add merged one
                clusters.pop(max(i, j))
                clusters.pop(min(i, j))
                clusters.append(merged_cluster)

                merged = True
                logger.debug(
                    f"Merged clusters {iteration}: "
                    f"similarity={best_similarity:.3f}, "
                    f"remaining={len(clusters)}"
                )

        # Filter by min cluster size
        clusters = [c for c in clusters if c.size >= self.min_cluster_size]

        # Calculate metrics for each cluster
        for cluster in clusters:
            cluster.metrics = self._calculate_cluster_metrics(
                cluster,
                clusters,
                evaluations
            )

        # Sort by cluster size (largest first)
        clusters.sort(key=lambda c: c.size, reverse=True)

        logger.info(
            f"Clustering complete: {len(clusters)} clusters, "
            f"{iteration} iterations"
        )

        return clusters

    async def deduplicate(
        self,
        ideas: list[Idea],
        clusters: list[Cluster] | None = None,
    ) -> tuple[list[Idea], dict[str, list[str]]]:
        """
        Remove duplicate ideas by selecting representatives from clusters.

        Args:
            ideas: List of ideas to deduplicate
            clusters: Optional pre-computed clusters (will compute if None)

        Returns:
            Tuple of (deduplicated_ideas, duplication_map)
            where duplication_map maps kept_idea_id -> [removed_duplicate_ids]

        Example:
            ```python
            unique_ideas, dup_map = await clustering.deduplicate(ideas)

            print(f"Reduced from {len(ideas)} to {len(unique_ideas)} ideas")
            for kept_id, duplicate_ids in dup_map.items():
                print(f"  {kept_id}: replaced {len(duplicate_ids)} duplicates")
            ```

        """
        if not ideas:
            return [], {}

        # Compute clusters if not provided
        if clusters is None:
            clusters = await self.cluster_ideas(ideas)

        # Select representative from each cluster
        deduplicated = []
        duplication_map: dict[str, list[str]] = {}

        for cluster in clusters:
            representative = cluster.representative
            if representative:
                deduplicated.append(representative)

                # Track which ideas this representative replaces
                duplicate_ids = [
                    idea.id for idea in cluster.ideas
                    if idea.id != representative.id
                ]
                if duplicate_ids:
                    duplication_map[representative.id] = duplicate_ids

        logger.info(
            f"Deduplication: {len(ideas)} -> {len(deduplicated)} ideas "
            f"({len(duplication_map)} clusters)"
        )

        return deduplicated, duplication_map

    def _cluster_similarity(
        self,
        cluster1: Cluster,
        cluster2: Cluster
    ) -> float:
        """
        Calculate similarity between two clusters.

        Uses average linkage: average of all pairwise similarities.

        Args:
            cluster1: First cluster
            cluster2: Second cluster

        Returns:
            Similarity score (0-1)

        """
        if not cluster1.ideas or not cluster2.ideas:
            return 0.0

        similarities = []
        for idea1 in cluster1.ideas:
            for idea2 in cluster2.ideas:
                sim = cluster1._calculate_semantic_similarity(idea1, idea2)
                similarities.append(sim)

        return sum(similarities) / len(similarities) if similarities else 0.0

    def _merge_clusters(
        self,
        cluster1: Cluster,
        cluster2: Cluster,
        similarity: float,
        evaluations: dict[str, Evaluation] | None = None,
    ) -> Cluster:
        """
        Merge two clusters into a single cluster.

        Args:
            cluster1: First cluster
            cluster2: Second cluster
            similarity: Calculated similarity between clusters
            evaluations: Optional evaluations for representative selection

        Returns:
            Merged cluster

        """
        merged = Cluster(
            ideas=cluster1.ideas + cluster2.ideas,
            similarity_threshold=self.similarity_threshold,
            metadata={
                "merged_from": [cluster1.id, cluster2.id],
                "merge_similarity": similarity,
                "merged_at": datetime.utcnow().isoformat(),
            }
        )

        # Select best representative based on score
        all_ideas = merged.ideas
        if evaluations:
            # Use evaluation scores if available
            best_idea = max(
                all_ideas,
                key=lambda i: evaluations.get(i.id, Evaluation(
                    idea_id=i.id,
                    novelty_score=0.0,
                    feasibility_score=0.0,
                    impact_score=0.0,
                    overall_score=i.score
                )).overall_score
            )
        else:
            # Use idea scores
            best_idea = max(all_ideas, key=lambda i: i.score)

        merged.representative_id = best_idea.id

        return merged

    def _calculate_cluster_metrics(
        self,
        cluster: Cluster,
        all_clusters: list[Cluster],
        evaluations: dict[str, Evaluation] | None = None,
    ) -> ClusterMetrics:
        """
        Calculate quality metrics for a cluster.

        Args:
            cluster: Cluster to calculate metrics for
            all_clusters: All clusters (for separation calculation)
            evaluations: Optional evaluations

        Returns:
            ClusterMetrics object

        """
        # Cohesion: average pairwise similarity within cluster
        sim_matrix = cluster.get_similarity_matrix()
        n = len(cluster.ideas)

        if n > 1:
            # Get upper triangle (excluding diagonal)
            upper_triangular = [
                sim_matrix[i][j]
                for i in range(n)
                for j in range(i + 1, n)
            ]
            cohesion = sum(upper_triangular) / len(upper_triangular)
        else:
            cohesion = 1.0  # Single idea is perfectly cohesive

        # Separation: average distance to other clusters
        separations = []
        for other in all_clusters:
            if other.id != cluster.id:
                sep = 1.0 - self._cluster_similarity(cluster, other)
                separations.append(sep)

        separation = sum(separations) / len(separations) if separations else 0.5

        # Representative score
        if cluster.representative:
            if evaluations and cluster.representative.id in evaluations:
                rep_score = evaluations[cluster.representative.id].overall_score
            else:
                rep_score = cluster.representative.score
        else:
            rep_score = 0.0

        # Diversity: variance in scores within cluster
        if cluster.ideas:
            scores = [idea.score for idea in cluster.ideas]
            mean_score = sum(scores) / len(scores)
            variance = sum((s - mean_score) ** 2 for s in scores) / len(scores)
            diversity_score = min(1.0, variance / 2500.0)  # Normalize roughly
        else:
            diversity_score = 0.0

        return ClusterMetrics(
            cohesion=cohesion,
            separation=separation,
            representative_score=rep_score,
            diversity_score=diversity_score
        )


__all__ = [
    "Cluster",
    "ClusterMetrics",
    "IdeaClustering",
]
