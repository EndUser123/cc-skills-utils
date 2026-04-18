"""
Innovator Agent - Creative Thinking and Novel Solutions
"""

from __future__ import annotations

from ..models import BrainstormContext, Evaluation, Idea
from .base import Agent


class InnovatorAgent(Agent):
    def __init__(self, llm_config=None):
        super().__init__(
            name="Innovator",
            description="Creative thinker who generates novel, breakthrough ideas",
            llm_config=llm_config,
        )

    def _get_default_system_prompt(self) -> str:
        return """You are a creative innovator who excels at thinking outside the box and generating novel solutions."""

    async def generate_ideas(self, context: BrainstormContext) -> list[Idea]:
        """
        Generate ideas in PARALLEL for faster response.

        Note: Uses parallel LLM calls to avoid timeout issues with slow CLI providers.
        """
        import asyncio

        # Calculate number of ideas - respect the input parameter
        # For --ideas 1, generate 1 idea; for --ideas 3, generate 2 ideas
        num_ideas = max(1, min(3, context.num_ideas))

        async def generate_single_idea(idx: int) -> Idea | None:
            prompt = self._build_innovator_prompt(context, idx)
            try:
                response = await self.llm_client.generate(
                    prompt=prompt,
                    system_prompt=self.system_prompt,
                    temperature=0.9,
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
                print(f"InnovatorAgent error generating idea {idx}: {e}")
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
            novelty=85.0,
            feasibility=60.0,
            impact=85.0,
            arguments_pro=["Highly original", "Breakthrough potential"],
            arguments_con=["May be difficult to implement"],
            weights={"novelty": 0.5, "feasibility": 0.2, "impact": 0.3},
            evaluator=self.name,
        )

    def _build_innovator_prompt(self, context: BrainstormContext, idea_number: int) -> str:
        prompt = (
            f"As a creative innovator, generate a breakthrough idea for: Topic: {context.topic}. "
        )
        if context.constraints:
            prompt += (
                "Constraints (to be creatively overcome): " + ", ".join(context.constraints) + ". "
            )
        if context.goals:
            prompt += "Goals (aim high!): " + ", ".join(context.goals) + ". "
        prompt += self._get_fresh_mode_warning(context)
        prompt += f"This is innovative idea #{idea_number}. Be bold and different! Think creatively and generate a specific, detailed innovative idea."
        return prompt


__all__ = ["InnovatorAgent"]
