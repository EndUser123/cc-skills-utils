"""
Graph-of-Thought Planner - Extract strategic nodes from brainstorm ideas

Extracts and categorizes strategy nodes from multi-persona brainstorming:
- Constraints: Requirements like "Budget < $1000"
- Ideas: Approaches like "Use microservices"
- Risks: Concerns like "Complexity overhead"
- Components: System boundaries like "API Gateway"
- Data flows: Communication paths like "Client → API"
"""

import logging
import re
from typing import NamedTuple

from ..models import Idea

logger = logging.getLogger(__name__)


class StrategyNode(NamedTuple):
    """A strategic node extracted from brainstorm ideas."""
    node_type: str  # "constraint" | "idea" | "risk" | "component" | "data_flow"
    content: str  # The node description
    source_idea: str  # Which idea this came from
    persona: str  # Which persona generated this


class GotPlanner:
    """
    Extract strategy nodes from multi-persona brainstorming output.

    Uses pattern matching and keyword detection to categorize strategic
    elements from the raw brainstorm ideas.
    """

    # Pattern indicators for each node type
    CONSTRAINT_PATTERNS = [
        r"must\s+(?:be|use|have)",
        r"required?\s+to",
        r"cannot\s+\w+",
        r"shall\s+\w+",
        r"<\s*\$\s*[\d,]+",  # Budget constraints
        r"<\s*[\d.]+\s*(?:days?|weeks?|months?|hours?)",  # Time constraints
    ]

    IDEA_PATTERNS = [
        r"should\s+(?:use|adopt|implement)",
        r"consider\s+using",
        r"(?:suggest|propose|recommend)",
        r"approach:\s*\w+",
        r"strategy:\s*\w+",
    ]

    RISK_PATTERNS = [
        r"risk\s+(?:of|is|that)",
        r"danger\s+(?:of|is)",
        r"(?:concern|worry)\s+(?:about|that)",
        r"might\s+(?:fail|break|cause)",
        r"could\s+(?:lead to|result in)",
    ]

    COMPONENT_PATTERNS = [
        r"(?:service|component|module|system):\s*\w+",
        r"\w+\s+(?:service|component|module)",
        r"(?:api|database|cache|queue):\s*\w+",
    ]

    DATA_FLOW_PATTERNS = [
        r"→",
        r"=>",
        r"flows?\s+to",
        r"sends?\s+to",
        r"communicates?\s+with",
    ]

    def __init__(self):
        """Initialize the GoT planner."""
        self.nodes: list[StrategyNode] = []

    def extract_from_ideas(self, ideas: list[Idea]) -> list[StrategyNode]:
        """
        Extract strategy nodes from a list of brainstorm ideas.

        Args:
            ideas: List of Idea objects from brainstorm phase

        Returns:
            List of StrategyNode objects categorized by type
        """
        self.nodes = []

        for idea in ideas:
            # Extract persona name from idea source if available
            persona = getattr(idea, 'persona', 'unknown')

            # Try to extract each type of node from this idea
            self._extract_nodes(idea, persona, "constraint", self.CONSTRAINT_PATTERNS)
            self._extract_nodes(idea, persona, "idea", self.IDEA_PATTERNS)
            self._extract_nodes(idea, persona, "risk", self.RISK_PATTERNS)
            self._extract_nodes(idea, persona, "component", self.COMPONENT_PATTERNS)
            self._extract_nodes(idea, persona, "data_flow", self.DATA_FLOW_PATTERNS)

        logger.info(f"GoT Planner: Extracted {len(self.nodes)} strategy nodes from {len(ideas)} ideas")
        return self.nodes

    def _extract_nodes(
        self,
        idea: Idea,
        persona: str,
        node_type: str,
        patterns: list[str]
    ) -> None:
        """Extract nodes of a specific type using pattern matching."""
        content_lower = idea.content.lower()

        for pattern in patterns:
            matches = re.finditer(pattern, content_lower, re.IGNORECASE)
            for match in matches:
                # Extract the relevant phrase (surrounding context)
                start = max(0, match.start() - 30)
                end = min(len(idea.content), match.end() + 30)
                phrase = idea.content[start:end].strip()

                # Clean up the phrase
                phrase = re.sub(r'\s+', ' ', phrase)
                if len(phrase) > 200:  # Truncate very long matches
                    phrase = phrase[:200] + "..."

                node = StrategyNode(
                    node_type=node_type,
                    content=phrase,
                    source_idea=idea.content[:100],  # Store source reference
                    persona=persona
                )
                self.nodes.append(node)

    def get_nodes_by_type(self, node_type: str) -> list[StrategyNode]:
        """Get all nodes of a specific type."""
        return [n for n in self.nodes if n.node_type == node_type]

    def summary(self) -> dict:
        """Return summary statistics of extracted nodes."""
        type_counts = {}
        for node in self.nodes:
            type_counts[node.node_type] = type_counts.get(node.node_type, 0) + 1

        return {
            "total_nodes": len(self.nodes),
            "by_type": type_counts,
            "constraints": len(self.get_nodes_by_type("constraint")),
            "ideas": len(self.get_nodes_by_type("idea")),
            "risks": len(self.get_nodes_by_type("risk")),
            "components": len(self.get_nodes_by_type("component")),
            "data_flows": len(self.get_nodes_by_type("data_flow")),
        }
