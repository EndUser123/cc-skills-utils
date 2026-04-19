#!/usr/bin/env python3
"""Semantic clustering for Layer 1B pre-filtering.

This module provides lightweight semantic clustering to reduce token count
while preserving diversity by grouping similar results and keeping top-N
from each cluster.

Research Basis:
- Hybrid search systems use "semantic reranker on fused candidate set"
- Two-stage semantic filtering: clustering → LLM reranker
- Reduces 30-40 items → 20-25 items before Layer 2

Performance Requirements:
- Processing time < 500ms for 40 items
- Better than URL-based deduplication (catches semantic duplicates)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class Cluster:
    """Represents a cluster of semantically similar results."""
    cluster_id: int
    items: list[Any]  # SearchResult objects
    similarity_threshold: float


def normalize_text(text: str) -> str:
    """Normalize text for similarity comparison.

    Args:
        text: Input text

    Returns:
        Normalized text (lowercase, no punctuation, extra whitespace removed)
    """
    if not text:
        return ""

    # Convert to lowercase
    text = text.lower()

    # Remove punctuation
    text = re.sub(r'[^\w\s]', ' ', text)

    # Remove extra whitespace
    text = ' '.join(text.split())

    return text


def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate simple text similarity using word overlap.

    Args:
        text1: First text
        text2: Second text

    Returns:
        Similarity score from 0.0 to 1.0
    """
    if not text1 or not text2:
        return 0.0

    # Normalize texts
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)

    # Split into words
    words1 = set(norm1.split())
    words2 = set(norm2.split())

    # Calculate Jaccard similarity: intersection / union
    if not words1 or not words2:
        return 0.0

    intersection = words1.intersection(words2)
    union = words1.union(words2)

    similarity = len(intersection) / len(union) if union else 0.0

    return similarity


def cluster_results(
    results: list[Any],
    similarity_threshold: float = 0.4
) -> list[Cluster]:
    """Cluster search results based on semantic similarity.

    Args:
        results: List of search results (must have title and content attributes)
        similarity_threshold: Minimum similarity to group in same cluster (0.0-1.0)

    Returns:
        List of clusters, each containing similar results
    """
    if not results:
        return []

    clusters = []
    cluster_counter = 0

    for result in results:
        # Get text from result
        title = getattr(result, 'title', '')
        content = getattr(result, 'content', '')
        combined_text = f"{title} {content}"

        # Try to find existing cluster with high similarity
        assigned = False

        for cluster in clusters:
            # Compare with first item in cluster as representative
            if not cluster.items:
                continue

            representative = cluster.items[0]
            rep_title = getattr(representative, 'title', '')
            rep_content = getattr(representative, 'content', '')
            rep_combined = f"{rep_title} {rep_content}"

            similarity = calculate_similarity(combined_text, rep_combined)

            if similarity >= similarity_threshold:
                cluster.items.append(result)
                assigned = True
                break

        # If not assigned to any cluster, create new cluster
        if not assigned:
            new_cluster = Cluster(
                cluster_id=cluster_counter,
                items=[result],
                similarity_threshold=similarity_threshold
            )
            clusters.append(new_cluster)
            cluster_counter += 1

    return clusters


def select_top_from_cluster(
    cluster: Cluster,
    max_items: int = 2
) -> list[Any]:
    """Select top-N items from a cluster based on score.

    Args:
        cluster: Cluster of results
        max_items: Maximum items to select from this cluster

    Returns:
        Top-N items sorted by score
    """
    if not cluster.items:
        return []

    # Sort by score (descending)
    sorted_items = sorted(
        cluster.items,
        key=lambda x: getattr(x, 'score', 0.0),
        reverse=True
    )

    # For larger clusters, keep more items
    # Scale: 1 cluster → 2 items, 5 clusters → 3 items each
    cluster_size = len(cluster.items)
    if cluster_size >= 5:
        max_items = min(max_items + 1, 4)

    return sorted_items[:max_items]


def apply_semantic_clustering(
    results: list[Any],
    similarity_threshold: float = 0.4,
    max_results: int = 25
) -> list[Any]:
    """Apply semantic clustering to reduce result count while preserving diversity.

    Args:
        results: List of search results
        similarity_threshold: Similarity threshold for clustering (0.0-1.0)
        max_results: Maximum results to return

    Returns:
        Filtered list of results with diversity preserved
    """
    if len(results) <= max_results:
        return results

    # Cluster results
    clusters = cluster_results(results, similarity_threshold)

    # Select top items from each cluster
    diverse_results = []

    for cluster in clusters:
        top_items = select_top_from_cluster(cluster)
        diverse_results.extend(top_items)

    # If still too many results, truncate by score
    if len(diverse_results) > max_results:
        diverse_results.sort(
            key=lambda x: getattr(x, 'score', 0.0),
            reverse=True
        )
        diverse_results = diverse_results[:max_results]

    return diverse_results


def get_clustering_stats(
    original_count: int,
    results: list[Any],
    similarity_threshold: float = 0.4
) -> dict[str, Any]:
    """Get statistics about clustering performance.

    Args:
        original_count: Original number of results before clustering
        results: Results after clustering
        similarity_threshold: Similarity threshold used

    Returns:
        Dict with clustering statistics
    """
    clusters = cluster_results(results, similarity_threshold)

    # Calculate cluster size distribution
    cluster_sizes = [len(c.items) for c in clusters]

    return {
        "original_count": original_count,
        "clustered_count": len(results),
        "num_clusters": len(clusters),
        "avg_cluster_size": sum(cluster_sizes) / len(cluster_sizes) if cluster_sizes else 0,
        "max_cluster_size": max(cluster_sizes) if cluster_sizes else 0,
        "min_cluster_size": min(cluster_sizes) if cluster_sizes else 0,
        "reduction_ratio": len(results) / original_count if original_count > 0 else 1.0,
        "similarity_threshold": similarity_threshold,
    }
