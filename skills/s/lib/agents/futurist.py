"""
Futurist Agent - Long-term Strategic Implications and Speculative Scenarios
"""
from __future__ import annotations

from ..models import BrainstormContext, Evaluation, Idea
from .base import Agent


class FuturistAgent(Agent):
    """
    Agent specializing in long-term strategic implications and speculative scenarios.
    Focuses on 'Black Swan' events, exponential trends, and second-order effects.
    """

    def __init__(self, llm_config=None):
        super().__init__(
            name="Futurist",
            description="Long-term thinker who explores speculative scenarios and second-order effects",
            llm_config=llm_config
        )

    def _get_default_system_prompt(self) -> str:
        return """You are a strategic futurist who excels at identifying long-term trends, second-order effects, and potential 'Black Swan' events. 
Your goal is to look beyond immediate implementation and consider how a strategy might evolve over 5-10 years, 
considering technological shifts, societal changes, and unexpected systemic shocks. 
Think about exponential growth, feedback loops, and radical transformations."""

    async def generate_ideas(self, context: BrainstormContext) -> list[Idea]:
        ideas = []
        # Generate 4-6 ideas depending on the requested count
        num_ideas = min(6, max(4, context.num_ideas // 3))
        
        for i in range(num_ideas):
            prompt = self._build_futurist_prompt(context, i)
            try:
                response = await self.llm_client.generate(
                    prompt=prompt,
                    system_prompt=self.system_prompt,
                    temperature=0.85,
                    max_tokens=800,
                    persona=self.name
                )
                
                # Check for empty response content
                if not response or not response.content or not response.content.strip():
                    continue

                idea = Idea(
                    content=response.content,
                    persona=self.name,
                    reasoning_path=[f"Strategic foresight via {response.model_used}"],
                    score=70.0,
                    metadata={
                        "provider": response.model_used,
                        "type": "long-term-speculative"
                    }
                )
                ideas.append(idea)
            except Exception as e:
                # Log error but continue with next idea
                import sys
                print(f"[FuturistAgent] Error generating idea {i}: {e}", file=sys.stderr)
                
        return ideas

    async def evaluate_idea(self, idea: Idea) -> Evaluation:
        """Evaluate an idea from a futurist perspective."""
        prompt = f"""
        Evaluate the following idea from a futurist's perspective:
        Idea: {idea.content}
        
        Consider:
        1. Long-term Viability: Is this sustainable over 5-10 years?
        2. Second-order Effects: What unexpected consequences might this trigger?
        3. Strategic Resilience: How does this perform under systemic shock (Black Swans)?
        4. Trend Alignment: Does this leverage emerging exponential trends?
        
        Provide your evaluation in JSON format:
        {{
            "novelty": 0-100,
            "feasibility": 0-100,
            "impact": 0-100,
            "arguments_pro": ["arg1", "arg2"],
            "arguments_con": ["arg1", "arg2"]
        }}
        """
        return await self._evaluate_with_llm(idea, prompt)

    def _build_futurist_prompt(self, context: BrainstormContext, idea_number: int) -> str:
        prompt = f"As a strategic futurist, generate a long-term speculative idea for: Topic: {context.topic}. "
        
        if context.constraints:
            prompt += "Current Constraints (consider how these might dissolve or shift in the future): " + ", ".join(context.constraints) + ". "
            
        if context.goals:
            prompt += "Primary Goals: " + ", ".join(context.goals) + ". "
            
        prompt += self._get_fresh_mode_warning(context)
        
        prompt += f"""
        This is speculative idea #{idea_number}. 
        Focus on one of the following for this idea:
        - A 'Black Swan' scenario that would make this idea essential.
        - The second-order effects of successfully implementing this strategy.
        - How exponential technology (AI, quantum, etc.) transforms this topic in 5 years.
        - A radical 'outlier' perspective that challenges the current paradigm.
        
        Be specific, detailed, and provocative!
        """
        return prompt

__all__ = ["FuturistAgent"]
