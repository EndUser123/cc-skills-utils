"""
Pragmatist Agent - Implementation-Focused Practical Solutions
"""

from __future__ import annotations

from ..models import BrainstormContext, Evaluation, Idea
from .base import Agent


class PragmatistAgent(Agent):
    def __init__(self, llm_config=None):
        super().__init__(
            name="Pragmatist",
            description="Implementation-focused agent who generates practical ideas",
            llm_config=llm_config,
        )

    def _get_default_system_prompt(self) -> str:
        return """You are a pragmatist who focuses on practical, implementable solutions."""

    async def generate_ideas(self, context: BrainstormContext) -> list[Idea]:
        """
        Generate ideas in PARALLEL for faster response.

        Note: Uses parallel LLM calls to avoid timeout issues with slow CLI providers.
        """
        import asyncio

        # Calculate number of ideas - respect the input parameter
        num_ideas = max(1, min(3, context.num_ideas))

        async def generate_single_idea(idx: int) -> Idea | None:
            prompt = f"As a pragmatist, generate a practical idea for: Topic: {context.topic}. This is practical idea #{idx + 1}. Focus on execution!"
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
                    score=80.0,
                    metadata={"provider": response.model_used},
                )
            except Exception as e:
                print(f"PragmatistAgent error generating idea {idx}: {e}")
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
            novelty=55.0,
            feasibility=90.0,
            impact=70.0,
            arguments_pro=["Highly implementable", "Clear execution path"],
            arguments_con=["May not be innovative"],
            weights={"novelty": 0.2, "feasibility": 0.5, "impact": 0.3},
            evaluator=self.name,
        )


__all__ = ["PragmatistAgent"]
