"""
Idea Synthesis and Combination

Implements intelligent synthesis of complementary ideas into stronger hybrid
solutions. Identifies ideas that work well together and combines them to create
integrated approaches.

Key Features:
- Complementary idea identification
- Hybrid idea generation
- Synthesis quality scoring
- Conflict detection and resolution
- Multi-source attribution
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

from ..models import Evaluation, Idea
from ..agents.base import AgentLLMClient

logger = logging.getLogger(__name__)


@dataclass
class SynthesizedIdea:
    """
    An idea created by synthesizing multiple source ideas.

    Attributes:
        id: Unique identifier for the synthesized idea
        content: The synthesized hybrid idea content
        synthesized_from: List of source idea IDs that were combined
        synthesis_type: Type of synthesis performed
        complementarity_score: How well the source ideas complement each other (0-1)
        synthesis_quality: Quality of the synthesis (0-1)
        conflicts_detected: Any conflicts detected in synthesis
        reasoning: Explanation of how synthesis was achieved
        metadata: Additional synthesis information

    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    synthesized_from: list[str] = field(default_factory=list)
    synthesis_type: str = "hybrid"  # hybrid, enhanced, integrated, etc.
    complementarity_score: float = 0.0
    synthesis_quality: float = 0.0
    conflicts_detected: list[str] = field(default_factory=list)
    reasoning: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def num_sources(self) -> int:
        """Get the number of source ideas."""
        return len(self.synthesized_from)

    def to_idea(self, persona: str = "synthesizer", score: float = 70.0) -> Idea:
        """
        Convert to a standard Idea object.

        Args:
            persona: Persona to attribute synthesis to
            score: Initial score for the idea

        Returns:
            Idea object with synthesized content

        """
        return Idea(
            content=self.content,
            persona=persona,
            reasoning_path=self.reasoning,
            score=score,
            metadata={
                "synthesized": True,
                "synthesis_type": self.synthesis_type,
                "num_sources": self.num_sources,
                "source_ids": self.synthesized_from,
                "complementarity": self.complementarity_score,
                "synthesis_quality": self.synthesis_quality,
                **self.metadata
            }
        )


class IdeaSynthesizer:
    """
    Synthesizes complementary ideas into stronger hybrid solutions.

    Implements multi-strategy synthesis:
    1. **Complementary Pairing**: Combines ideas that address different aspects
    2. **Enhancement**: Uses one idea to improve or strengthen another
    3. **Integration**: Merges multiple ideas into a cohesive solution
    4. **Abstraction**: Extracts common principles to create a higher-level idea

    Attributes:
        complementarity_threshold: Minimum complementarity to synthesize (default: 0.6)
        max_synthesis_sources: Maximum source ideas to combine (default: 3)
        enable_conflict_detection: Whether to detect conflicts (default: True)

    Example:
        ```python
        synthesizer = IdeaSynthesizer(complementarity_threshold=0.7)

        # Synthesize from a cluster of related ideas
        synthesized = await synthesizer.synthesize(cluster)

        for syn_idea in synthesized:
            print(f"Hybrid: {syn_idea.content}")
            print(f"  From {syn_idea.num_sources} ideas")
            print(f"  Quality: {syn_idea.synthesis_quality:.2f}")
        ```

    """

    def __init__(
        self,
        complementarity_threshold: float = 0.6,
        max_synthesis_sources: int = 3,
        enable_conflict_detection: bool = True,
        llm_config=None,
    ):
        """
        Initialize the idea synthesizer.

        Args:
            complementarity_threshold: Min complementarity score to synthesize (0-1)
            max_synthesis_sources: Maximum source ideas to combine
            enable_conflict_detection: Whether to detect and report conflicts
            llm_config: Optional LLMConfig for real LLM synthesis

        """
        if not 0.0 <= complementarity_threshold <= 1.0:
            raise ValueError("complementarity_threshold must be between 0 and 1")

        if max_synthesis_sources < 2:
            raise ValueError("max_synthesis_sources must be at least 2")

        self.complementarity_threshold = complementarity_threshold
        self.max_synthesis_sources = max_synthesis_sources
        self.enable_conflict_detection = enable_conflict_detection

        # LLM client for real synthesis
        self.llm_client = AgentLLMClient(config=llm_config)

        logger.info(
            f"IdeaSynthesizer initialized: threshold={complementarity_threshold}, "
            f"max_sources={max_synthesis_sources}, "
            f"llm_mode={'REAL' if llm_config else 'MOCK'}"
        )

    async def synthesize(
        self,
        cluster,  # Cluster object from clustering module
        strategy: str = "auto",
        max_results: int = 3,
        evaluations: dict[str, Evaluation] | None = None,
    ) -> list[SynthesizedIdea]:
        """
        Synthesize new ideas from a cluster of related ideas.

        Args:
            cluster: Cluster of ideas to synthesize
            strategy: Synthesis strategy ("auto", "complementary", "enhancement", "integration")
            max_results: Maximum number of synthesized ideas to return
            evaluations: Optional evaluations for quality-aware synthesis

        Returns:
            List of synthesized ideas, sorted by quality (descending)

        Example:
            ```python
            synthesized = await synthesizer.synthesize(
                cluster=idea_cluster,
                strategy="complementary",
                max_results=2
            )

            for syn_idea in synthesized:
                idea = syn_idea.to_idea()
                result.add_idea(idea)
            ```

        """
        if not cluster or not cluster.ideas:
            logger.warning("Empty cluster provided for synthesis")
            return []

        if len(cluster.ideas) < 2:
            logger.warning("Cluster has fewer than 2 ideas, cannot synthesize")
            return []

        logger.info(f"Synthesizing from cluster with {cluster.size} ideas...")

        synthesized = []

        # Auto-select strategy if needed
        if strategy == "auto":
            strategy = self._select_strategy(cluster, evaluations)

        # Generate synthesis based on strategy
        if strategy == "complementary":
            synthesized = await self._synthesize_complementary(
                cluster,
                max_results,
                evaluations
            )
        elif strategy == "enhancement":
            synthesized = await self._synthesize_enhancement(
                cluster,
                max_results,
                evaluations
            )
        elif strategy == "integration":
            synthesized = await self._synthesize_integration(
                cluster,
                max_results,
                evaluations
            )
        else:
            logger.warning(f"Unknown strategy: {strategy}, using complementary")
            synthesized = await self._synthesize_complementary(
                cluster,
                max_results,
                evaluations
            )

        # Sort by synthesis quality
        synthesized.sort(key=lambda x: x.synthesis_quality, reverse=True)

        # Return top results
        results = synthesized[:max_results]

        logger.info(
            f"Synthesis complete: {len(results)} new ideas generated "
            f"using {strategy} strategy"
        )

        return results

    async def synthesize_from_lists(
        self,
        ideas: list[Idea],
        evaluations: dict[str, Evaluation] | None = None,
    ) -> list[SynthesizedIdea]:
        """
        Synthesize ideas from multiple lists/perspectives.

        Useful for combining ideas from different personas or approaches.

        Args:
            ideas: List of ideas to synthesize
            evaluations: Optional evaluations

        Returns:
            List of synthesized ideas

        Example:
            ```python
            # Combine ideas from different personas
            innovator_ideas = result.get_ideas_by_persona("innovator")
            pragmatist_ideas = result.get_ideas_by_persona("pragmatist")

            all_ideas = innovator_ideas + pragmatist_ideas
            synthesized = await synthesizer.synthesize_from_lists(all_ideas)
            ```

        """
        if not ideas:
            return []

        # Group ideas by persona
        by_persona: dict[str, list[Idea]] = {}
        for idea in ideas:
            if idea.persona not in by_persona:
                by_persona[idea.persona] = []
            by_persona[idea.persona].append(idea)

        # If we have multiple personas, synthesize cross-persona
        if len(by_persona) > 1:
            synthesized = []

            # Try pairing ideas from different personas
            personas = list(by_persona.keys())
            for i in range(len(personas)):
                for j in range(i + 1, len(personas)):
                    persona1, persona2 = personas[i], personas[j]

                    for idea1 in by_persona[persona1][:2]:  # Top 2 from each
                        for idea2 in by_persona[persona2][:2]:
                            # Check complementarity
                            complementarity = self._calculate_complementarity(
                                idea1,
                                idea2,
                                evaluations
                            )

                            if complementarity >= self.complementarity_threshold:
                                syn_idea = await self._create_hybrid_idea(
                                    [idea1, idea2],
                                    complementarity,
                                    "cross_persona",
                                    evaluations
                                )
                                if syn_idea:
                                    synthesized.append(syn_idea)

            return synthesized
        # Single persona - use regular synthesis
        # Create a mock cluster and use regular synthesis
        from .clustering import Cluster

        cluster = Cluster(ideas=ideas)
        return await self.synthesize(cluster, evaluations=evaluations)

    def _select_strategy(
        self,
        cluster,
        evaluations: dict[str, Evaluation] | None = None,
    ) -> str:
        """
        Automatically select the best synthesis strategy for a cluster.

        Args:
            cluster: Cluster to analyze
            evaluations: Optional evaluations

        Returns:
            Selected strategy name

        """
        # Analyze cluster characteristics
        personas = {idea.persona for idea in cluster.ideas}

        # Cross-persona: use integration
        if len(personas) > 1:
            return "integration"

        # High diversity: use complementary
        if cluster.metrics.diversity_score > 0.5:
            return "complementary"

        # Low cohesion: use enhancement
        if cluster.metrics.cohesion < 0.6:
            return "enhancement"

        # Default: complementary
        return "complementary"

    async def _synthesize_complementary(
        self,
        cluster,
        max_results: int,
        evaluations: dict[str, Evaluation] | None = None,
    ) -> list[SynthesizedIdea]:
        """
        Synthesize by pairing complementary ideas.

        Finds pairs of ideas that address different aspects and combines them.
        """
        synthesized = []
        ideas = cluster.ideas

        # Find complementary pairs
        pairs = []
        for i in range(len(ideas)):
            for j in range(i + 1, len(ideas)):
                complementarity = self._calculate_complementarity(
                    ideas[i],
                    ideas[j],
                    evaluations
                )

                if complementarity >= self.complementarity_threshold:
                    pairs.append((i, j, complementarity))

        # Sort by complementarity
        pairs.sort(key=lambda x: x[2], reverse=True)

        # Synthesize top pairs
        for i, j, complementarity in pairs[:max_results]:
            syn_idea = await self._create_hybrid_idea(
                [ideas[i], ideas[j]],
                complementarity,
                "complementary",
                evaluations
            )
            if syn_idea:
                synthesized.append(syn_idea)

        return synthesized

    async def _synthesize_enhancement(
        self,
        cluster,
        max_results: int,
        evaluations: dict[str, Evaluation] | None = None,
    ) -> list[SynthesizedIdea]:
        """
        Synthesize by using one idea to enhance another.

        Takes the strongest idea and enhances it with elements from others.
        """
        synthesized = []
        ideas = cluster.ideas

        # Sort by score
        sorted_ideas = sorted(
            ideas,
            key=lambda x: x.score,
            reverse=True
        )

        # Use top idea as base, enhance with others
        base_idea = sorted_ideas[0]
        enhancers = sorted_ideas[1:4]  # Top 3 enhancers

        for enhancer in enhancers[:max_results]:
            complementarity = self._calculate_complementarity(
                base_idea,
                enhancer,
                evaluations
            )

            syn_idea = await self._create_enhanced_idea(
                base_idea,
                enhancer,
                complementarity,
                evaluations
            )
            if syn_idea:
                synthesized.append(syn_idea)

        return synthesized

    async def _synthesize_integration(
        self,
        cluster,
        max_results: int,
        evaluations: dict[str, Evaluation] | None = None,
    ) -> list[SynthesizedIdea]:
        """
        Synthesize by integrating multiple ideas into a cohesive solution.

        Merges the best aspects of several ideas.
        """
        synthesized = []

        # Take top scoring ideas
        top_ideas = sorted(
            cluster.ideas,
            key=lambda x: x.score,
            reverse=True
        )[:4]

        if len(top_ideas) < 2:
            return []

        # Calculate overall complementarity
        complementarity = self._calculate_group_complementarity(
            top_ideas,
            evaluations
        )

        # Create integrated synthesis
        syn_idea = await self._create_integrated_idea(
            top_ideas,
            complementarity,
            evaluations
        )

        if syn_idea:
            synthesized.append(syn_idea)

        return synthesized

    def _calculate_complementarity(
        self,
        idea1: Idea,
        idea2: Idea,
        evaluations: dict[str, Evaluation] | None = None,
    ) -> float:
        """
        Calculate how well two ideas complement each other.

        High complementarity means ideas address different aspects
        and work well together.

        Args:
            idea1: First idea
            idea2: Second idea
            evaluations: Optional evaluations for deeper analysis

        Returns:
            Complementarity score (0-1)

        """
        # Different personas = higher complementarity
        persona_boost = 0.3 if idea1.persona != idea2.persona else 0.0

        # Content dissimilarity (different aspects) = good for complementarity
        words1 = set(idea1.content.lower().split())
        words2 = set(idea2.content.lower().split())

        if words1 and words2:
            overlap = len(words1 & words2) / len(words1 | words2)
            dissimilarity = 1.0 - overlap
        else:
            dissimilarity = 0.5

        # Score balance (different strengths = complementary)
        score_diff = abs(idea1.score - idea2.score) / 100.0
        balance_factor = min(0.2, score_diff * 0.5)

        # If we have evaluations, use them for deeper analysis
        if evaluations:
            eval1 = evaluations.get(idea1.id)
            eval2 = evaluations.get(idea2.id)

            if eval1 and eval2:
                # Complementary strengths (e.g., high novelty + high feasibility)
                novelty_diff = abs(eval1.novelty_score - eval2.novelty_score) / 100.0
                feasibility_diff = abs(eval1.feasibility_score - eval2.feasibility_score) / 100.0
                impact_diff = abs(eval1.impact_score - eval2.impact_score) / 100.0

                # High variance in dimensions = complementary
                dimension_complementarity = (novelty_diff + feasibility_diff + impact_diff) / 3.0
            else:
                dimension_complementarity = 0.3
        else:
            dimension_complementarity = 0.3

        # Combine factors
        complementarity = (
            persona_boost * 0.3 +
            dissimilarity * 0.3 +
            balance_factor * 0.1 +
            dimension_complementarity * 0.3
        )

        return min(1.0, max(0.0, complementarity))

    def _calculate_group_complementarity(
        self,
        ideas: list[Idea],
        evaluations: dict[str, Evaluation] | None = None,
    ) -> float:
        """Calculate average pairwise complementarity for a group."""
        if len(ideas) < 2:
            return 0.0

        total = 0.0
        count = 0

        for i in range(len(ideas)):
            for j in range(i + 1, len(ideas)):
                total += self._calculate_complementarity(
                    ideas[i],
                    ideas[j],
                    evaluations
                )
                count += 1

        return total / count if count > 0 else 0.0

    async def _create_hybrid_idea(
        self,
        source_ideas: list[Idea],
        complementarity: float,
        synthesis_type: str,
        evaluations: dict[str, Evaluation] | None = None,
    ) -> SynthesizedIdea | None:
        """Create a hybrid idea from multiple sources using LLM-driven synthesis."""
        if len(source_ideas) < 2:
            return None

        # Prepare source descriptions
        source_context = ""
        for i, idea in enumerate(source_ideas, 1):
            source_context += f"--- Idea #{i} (Persona: {idea.persona}) ---\n{idea.content}\n\n"

        # System prompt for synthesis
        system_prompt = """You are a master strategist and conceptual synthesizer. Your goal is to combine multiple strategic ideas into a single, cohesive, and superior hybrid solution.

Identify synergies where the combined value is greater than the sum of its parts.
Address potential conflicts or trade-offs between source ideas.
Create a solution that is structurally sound and strategically superior.
Maintain a high-level strategic perspective and avoid generic corporate-speak.

Structure your response as follows:
[Title: A concise, catchy title for the hybrid solution]
[Problem: Brief summary of the core challenge addressed]
[Synthesis: A detailed description of the integrated solution]
[Synergies: Explain exactly how Idea A and Idea B amplify each other]
[Reasoning: Your strategic rationale for this combination]"""

        prompt = f"""Synthesize a superior hybrid solution from these complementary ideas:

{source_context}

The objective is to create a '{synthesis_type}' synthesis with a focus on maximizing strategic impact.
Complementarity score: {complementarity:.2f}

Generate the synthesized solution following the requested structure."""

        # Generate synthesis using LLM
        try:
            # P0-3: AgentLLMClient handles prompt sanitization
            response = await self.llm_client.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.8,  # Higher temperature for creative synthesis
                max_tokens=1500,
            )
            hybrid_content = response.content
            model_used = getattr(response, 'model_used', 'unknown')
        except Exception as e:
            logger.warning(f"LLM synthesis failed, falling back to basic merge: {e}")
            # Fallback to basic merge (preserving original logic)
            contents = [idea.content for idea in source_ideas]
            hybrid_content = f"Hybrid Solution combining {len(source_ideas)} approaches:\n\n"
            for i, content in enumerate(contents[:3], 1):
                first_sentence = content.split(".")[0] + "."
                hybrid_content += f"{i}. {first_sentence}\n"
            hybrid_content += "\nSynthesis (Fallback): Integrated multiple approaches into a comprehensive solution."
            model_used = "fallback-heuristic"

        # Build reasoning
        reasoning = [
            f"Identified {len(source_ideas)} complementary ideas",
            f"Complementarity score: {complementarity:.2f}",
            f"Applied LLM-driven '{synthesis_type}' synthesis using {model_used}",
            "Extracted synergies and resolved potential trade-offs"
        ]

        # Detect conflicts
        conflicts = self._detect_conflicts(source_ideas) if self.enable_conflict_detection else []

        # Calculate quality
        quality = self._calculate_synthesis_quality(
            source_ideas,
            complementarity,
            conflicts,
            evaluations
        )

        return SynthesizedIdea(
            content=hybrid_content,
            synthesized_from=[idea.id for idea in source_ideas],
            synthesis_type=synthesis_type,
            complementarity_score=complementarity,
            synthesis_quality=quality,
            conflicts_detected=conflicts,
            reasoning=reasoning,
            metadata={
                "source_personas": [idea.persona for idea in source_ideas],
                "avg_source_score": sum(idea.score for idea in source_ideas) / len(source_ideas),
                "synthesis_model": model_used
            }
        )

    def _create_enhanced_idea(
        self,
        base_idea: Idea,
        enhancer_idea: Idea,
        complementarity: float,
        evaluations: dict[str, Evaluation] | None = None,
    ) -> SynthesizedIdea | None:
        """Create an enhanced idea by adding improvements."""
        enhanced_content = f"Enhanced Solution:\n\n{base_idea.content}\n\nEnhancements: This solution builds upon the core approach by adding complementary elements that strengthen its feasibility and impact."

        reasoning = [
            f"Selected base idea (score: {base_idea.score:.1f})",
            f"Identified enhancement opportunity (complementarity: {complementarity:.2f})",
            "Integrated improvements while preserving core approach",
            "Created stronger, more comprehensive solution"
        ]

        conflicts = self._detect_conflicts([base_idea, enhancer_idea]) if self.enable_conflict_detection else []
        quality = self._calculate_synthesis_quality(
            [base_idea, enhancer_idea],
            complementarity,
            conflicts,
            evaluations
        )

        return SynthesizedIdea(
            content=enhanced_content,
            synthesized_from=[base_idea.id, enhancer_idea.id],
            synthesis_type="enhanced",
            complementarity_score=complementarity,
            synthesis_quality=quality,
            conflicts_detected=conflicts,
            reasoning=reasoning,
            metadata={
                "base_idea": base_idea.id,
                "enhancer_idea": enhancer_idea.id,
                "base_score": base_idea.score,
                "enhancer_score": enhancer_idea.score
            }
        )

    def _create_integrated_idea(
        self,
        source_ideas: list[Idea],
        complementarity: float,
        evaluations: dict[str, Evaluation] | None = None,
    ) -> SynthesizedIdea | None:
        """Create an integrated idea from multiple sources."""
        integrated_content = f"Integrated Solution synthesizing {len(source_ideas)} perspectives:\n\n"

        for i, idea in enumerate(source_ideas, 1):
            integrated_content += f"{i}. [{idea.persona}] {idea.content[:100]}...\n"

        integrated_content += "\nIntegration: This comprehensive solution weaves together the best aspects of each approach into a unified strategy that leverages multiple perspectives and strengths."

        reasoning = [
            f"Analyzed {len(source_ideas)} candidate ideas",
            f"Group complementarity: {complementarity:.2f}",
            "Identified synergies and common themes",
            "Created integrated solution combining all perspectives"
        ]

        conflicts = self._detect_conflicts(source_ideas) if self.enable_conflict_detection else []
        quality = self._calculate_synthesis_quality(
            source_ideas,
            complementarity,
            conflicts,
            evaluations
        )

        return SynthesizedIdea(
            content=integrated_content,
            synthesized_from=[idea.id for idea in source_ideas],
            synthesis_type="integrated",
            complementarity_score=complementarity,
            synthesis_quality=quality,
            conflicts_detected=conflicts,
            reasoning=reasoning,
            metadata={
                "num_sources": len(source_ideas),
                "personas": list({idea.persona for idea in source_ideas}),
                "integration_depth": "full"
            }
        )

    def _detect_conflicts(self, ideas: list[Idea]) -> list[str]:
        """Detect potential conflicts between ideas."""
        conflicts = []

        # Check for contradictory keywords
        contradictory_pairs = [
            ("increase", "decrease"),
            ("expand", "reduce"),
            ("add", "remove"),
            ("complex", "simple"),
        ]

        for word1, word2 in contradictory_pairs:
            for idea in ideas:
                content_lower = idea.content.lower()
                if word1 in content_lower and word2 in content_lower:
                    conflicts.append(
                        f"Potential contradiction: {word1} vs {word2}"
                    )

        # Check for persona conflicts
        personas = {idea.persona for idea in ideas}
        if "critic" in personas and "innovator" in personas:
            conflicts.append("Personality conflict: critic vs innovator perspectives")

        return conflicts

    def _calculate_synthesis_quality(
        self,
        source_ideas: list[Idea],
        complementarity: float,
        conflicts: list[str],
        evaluations: dict[str, Evaluation] | None = None,
    ) -> float:
        """Calculate overall quality of a synthesis."""
        # Base quality from complementarity
        quality = complementarity * 0.5

        # Penalty for conflicts
        conflict_penalty = len(conflicts) * 0.1
        quality -= conflict_penalty

        # Bonus for multiple high-quality sources
        if evaluations:
            avg_score = sum(
                evaluations.get(idea.id, Evaluation(
                    idea_id=idea.id,
                    novelty_score=0.0,
                    feasibility_score=0.0,
                    impact_score=0.0,
                    overall_score=idea.score
                )).overall_score
                for idea in source_ideas
            ) / len(source_ideas)

            quality += (avg_score / 100.0) * 0.3
        else:
            avg_score = sum(idea.score for idea in source_ideas) / len(source_ideas)
            quality += (avg_score / 100.0) * 0.3

        # Bonus for synthesis type
        if len(source_ideas) >= 3:
            quality += 0.1  # Multi-source synthesis is valuable

        return min(1.0, max(0.0, quality))


__all__ = [
    "IdeaSynthesizer",
    "SynthesizedIdea",
]
