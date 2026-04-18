"""
Critic Agent - Flaw Detection and Risk Analysis
"""

from __future__ import annotations

from ..models import BrainstormContext, Evaluation, Idea
from .base import Agent


class CriticAgent(Agent):
    def __init__(self, llm_config=None):
        super().__init__(
            name="Critic",
            description="Critical analyst who finds flaws and risks",
            llm_config=llm_config,
        )

    def _get_default_system_prompt(self) -> str:
        return """You are a critical analyst with expertise in identifying risks, flaws, and potential problems."""

    async def generate_ideas(self, context: BrainstormContext) -> list[Idea]:
        """
        Generate ideas in PARALLEL for faster response.

        Note: Uses parallel LLM calls to avoid timeout issues with slow CLI providers.
        """
        import asyncio

        # Calculate number of ideas - respect the input parameter
        num_ideas = max(1, min(3, context.num_ideas))

        async def generate_single_idea(idx: int) -> Idea | None:
            prompt = f"As a critical analyst, generate a risk-aware idea for: Topic: {context.topic}. This is idea #{idx + 1}. Think critically about risks and mitigations."
            prompt += self._get_fresh_mode_warning(context)
            try:
                response = await self.llm_client.generate(
                    prompt=prompt,
                    system_prompt=self.system_prompt,
                    temperature=0.5,
                    max_tokens=800,
                    persona=self.name,
                )
                return Idea(
                    content=response.content,
                    persona=self.name,
                    reasoning_path=[f"Generated via {response.model_used}"],
                    score=65.0,
                    metadata={"provider": response.model_used},
                )
            except Exception as e:
                print(f"CriticAgent error generating idea {idx}: {e}")
                return None

        # Generate all ideas in PARALLEL
        tasks = [generate_single_idea(i) for i in range(num_ideas)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out None and exceptions
        ideas = [r for r in results if isinstance(r, Idea)]
        return ideas

    async def evaluate_idea(self, idea: Idea) -> Evaluation:
        return Evaluation.from_scores(
            idea_id=idea.id,
            novelty=50.0,
            feasibility=55.0,
            impact=60.0,
            arguments_pro=["Problem identified"],
            arguments_con=["High risk", "Uncertain feasibility"],
            weights={"novelty": 0.2, "feasibility": 0.4, "impact": 0.4},
            evaluator=self.name,
        )


__all__ = ["CriticAgent"]
