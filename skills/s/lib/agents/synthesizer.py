"""
Synthesizer Agent - Idea Combination and Integration
"""

from __future__ import annotations

from ..models import BrainstormContext, Evaluation, Idea
from .base import Agent


class SynthesizerAgent(Agent):
    def __init__(self, llm_config=None):
        super().__init__(
            name="Synthesizer",
            description="Idea integrator who combines concepts into holistic solutions",
            llm_config=llm_config,
        )

    def _get_default_system_prompt(self) -> str:
        return """You are a synthesizer who excels at combining ideas and creating integrated solutions."""

    async def generate_ideas(self, context: BrainstormContext) -> list[Idea]:
        """
        Generate ideas in PARALLEL for faster response.

        Note: Uses parallel LLM calls to avoid timeout issues with slow CLI providers.
        """
        import asyncio

        # Calculate number of ideas - respect the input parameter
        num_ideas = max(1, min(3, context.num_ideas))

        async def generate_single_idea(idx: int) -> Idea | None:
            prompt = f"As a synthesizer, generate an integrated idea for: Topic: {context.topic}. This is integrated idea #{idx + 1}. Think about connections!"
            prompt += self._get_fresh_mode_warning(context)
            try:
                response = await self.llm_client.generate(
                    prompt=prompt,
                    system_prompt=self.system_prompt,
                    temperature=0.7,
                    max_tokens=800,
                    persona=self.name,
                )
                return Idea(
                    content=response.content,
                    persona=self.name,
                    reasoning_path=[f"Generated via {response.model_used}"],
                    score=75.0,
                    metadata={"provider": response.model_used},
                )
            except Exception as e:
                print(f"SynthesizerAgent error generating idea {idx}: {e}")
                return None

        # Generate all ideas in PARALLEL
        tasks = [generate_single_idea(i) for i in range(num_ideas)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out None and exceptions
        ideas = [r for r in results if isinstance(r, Idea)]
        return ideas

    async def evaluate_idea(self, idea: Idea) -> Evaluation:
        """Evaluate idea using LLM with synthesizer lens (integration, holistic)."""
        prompt = f"""Evaluate this idea from a synthesizer's perspective:

IDEA: {idea.content}
PERSONA: {idea.persona}

Provide your evaluation as JSON:
{{
    "novelty": <0-100, how novel is this idea>,
    "feasibility": <0-100, how implementable is this>,
    "impact": <0-100, what impact would this have>,
    "arguments_pro": ["specific reason 1", "specific reason 2"],
    "arguments_con": ["concern 1", "concern 2"]
}}

Synthesizer perspective: Prioritize integration, synergy, and holistic thinking. Reward comprehensive solutions."""
        return await self._evaluate_with_llm(idea, prompt)


__all__ = ["SynthesizerAgent"]
