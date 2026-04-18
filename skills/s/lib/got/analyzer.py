"""
Graph-of-Thought Edge Analyzer - Detect relationships between strategic nodes

Analyzes relationships between strategy nodes:
- Supports: One option enables another
- Contradicts: One option conflicts with another
- Depends: One option requires another
- Unrelated: No direct relationship
"""

import logging
from typing import NamedTuple

from .planner import StrategyNode

logger = logging.getLogger(__name__)


class Edge(NamedTuple):
    """A relationship edge between two strategy nodes."""
    source: StrategyNode
    target: StrategyNode
    relationship: str  # "supports" | "contradicts" | "depends" | "unrelated"
    confidence: float  # 0.0 to 1.0


class GotEdgeAnalyzer:
    """
    Detect relationships between strategic options using semantic analysis.

    Uses keyword matching and sentiment analysis to identify how different
    strategic options relate to each other.
    """

    # Contradiction keywords - indicate conflicting approaches
    CONTRADICTION_PAIRS = [
        ("monolith", "microservice"),
        ("stateless", "stateful"),
        ("sql", "nosql"),
        ("sync", "async"),
        ("centralized", "decentralized"),
        ("vendor", "custom"),
        ("buy", "build"),
        ("fast", "secure"),  # Often trade-offs
    ]

    # Dependency keywords - indicate prerequisite relationships
    DEPENDENCY_PATTERNS = [
        r"(?:requires|needs|depends on)\s+\w+",
        r"(?:before|after|precede)\s+\w+",
        r"(?:build on|based on)\s+\w+",
    ]

    # Support keywords - indicate enabling relationships
    SUPPORT_PATTERNS = [
        r"(?:enables|supports|allows|facilitates)\s+\w+",
        r"(?:helps|aids|improves)\s+\w+",
        r"(?:good for|suitable for)\s+\w+",
    ]

    def __init__(self):
        """Initialize the edge analyzer."""
        self.edges: list[Edge] = []

    def analyze_relationships(
        self,
        nodes: list[StrategyNode]
    ) -> list[Edge]:
        """
        Analyze relationships between all pairs of strategy nodes.

        Args:
            nodes: List of StrategyNode objects from planner

        Returns:
            List of Edge objects representing detected relationships
        """
        self.edges = []
        ideas = [n for n in nodes if n.node_type == "idea"]

        # Analyze idea-to-idea relationships
        for i, node_a in enumerate(ideas):
            for node_b in ideas[i + 1:]:
                edge = self._analyze_pair(node_a, node_b)
                if edge.relationship != "unrelated":
                    self.edges.append(edge)

        logger.info(
            f"GoT Edge Analyzer: Found {len(self.edges)} relationships "
            f"between {len(ideas)} ideas"
        )
        return self.edges

    def _analyze_pair(self, node_a: StrategyNode, node_b: StrategyNode) -> Edge:
        """Analyze relationship between a pair of nodes."""
        content_a = node_a.content.lower()
        content_b = node_b.content.lower()

        # Check for contradictions first (highest priority)
        contradiction = self._check_contradiction(content_a, content_b)
        if contradiction:
            return Edge(
                source=node_a,
                target=node_b,
                relationship="contradicts",
                confidence=0.8
            )

        # Check for dependencies
        dependency = self._check_dependency(content_a, content_b)
        if dependency:
            return Edge(
                source=node_a,
                target=node_b,
                relationship="depends",
                confidence=0.7
            )

        # Check for support relationships
        support = self._check_support(content_a, content_b)
        if support:
            return Edge(
                source=node_a,
                target=node_b,
                relationship="supports",
                confidence=0.6
            )

        # Default: no clear relationship
        return Edge(
            source=node_a,
            target=node_b,
            relationship="unrelated",
            confidence=0.0
        )

    def _check_contradiction(self, content_a: str, content_b: str) -> bool:
        """Check if two contents contradict each other."""
        for term_a, term_b in self.CONTRADICTION_PAIRS:
            # Check if term_a is in content_a and term_b in content_b (or vice versa)
            if (term_a in content_a and term_b in content_b) or \
               (term_b in content_a and term_a in content_b):
                return True
        return False

    def _check_dependency(self, content_a: str, content_b: str) -> bool:
        """Check if content_a depends on content_b."""
        import re
        for pattern in self.DEPENDENCY_PATTERNS:
            if re.search(pattern, content_a):
                # Extract what it depends on and check if it's in content_b
                match = re.search(pattern, content_a)
                if match:
                    dependency_phrase = match.group(0)
                    # Simple check: does content_b contain related terms?
                    words_b = set(content_b.split())
                    words_a = set(dependency_phrase.split())
                    if words_a & words_b:  # Any overlap
                        return True
        return False

    def _check_support(self, content_a: str, content_b: str) -> bool:
        """Check if content_a supports content_b."""
        import re
        for pattern in self.SUPPORT_PATTERNS:
            if re.search(pattern, content_a):
                match = re.search(pattern, content_a)
                if match:
                    support_phrase = match.group(0)
                    words_b = set(content_b.split())
                    words_a = set(support_phrase.split())
                    if words_a & words_b:
                        return True
        return False

    def detect_cycles(self) -> list[list[StrategyNode]]:
        """
        Detect circular dependencies in the graph.

        Returns:
            List of cycles (each cycle is a list of nodes)
        """
        # Build adjacency list
        graph = {}
        for edge in self.edges:
            if edge.relationship == "depends":
                graph.setdefault(edge.source, []).append(edge.target)

        # DFS-based cycle detection
        cycles = []
        visited = set()
        rec_stack = set()
        path = []

        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    # Found a cycle - extract it
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)

            path.pop()
            rec_stack.remove(node)
            return False

        for node in graph:
            if node not in visited:
                dfs(node)

        if cycles:
            logger.warning(f"GoT Edge Analyzer: Detected {len(cycles)} circular dependencies")

        return cycles

    def summary(self) -> dict:
        """Return summary statistics of detected edges."""
        relationship_counts = {}
        for edge in self.edges:
            relationship_counts[edge.relationship] = \
                relationship_counts.get(edge.relationship, 0) + 1

        cycles = self.detect_cycles()

        return {
            "total_edges": len(self.edges),
            "by_relationship": relationship_counts,
            "cycles_detected": len(cycles),
        }
