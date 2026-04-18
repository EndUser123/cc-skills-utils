
import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.agents.pragmatist import PragmatistAgent
from lib.models import BrainstormContext

async def test_pragmatist_baseline():
    print("Testing PragmatistAgent Baseline...")
    agent = PragmatistAgent()
    
    context = BrainstormContext(
        topic="Scaling a Python web application to 1 million users",
        num_ideas=2,
        goals=["High availability", "Low latency"],
        constraints=["Limited budget", "Small team"]
    )
    
    print(f"\nGenerating ideas for: {context.topic}")
    ideas = await agent.generate_ideas(context)
    
    for i, idea in enumerate(ideas):
        print(f"\nIdea {i+1}:")
        print(f"Content: {idea.content[:200]}...")
        print(f"Persona: {idea.persona}")
        
        evaluation = await agent.evaluate_idea(idea)
        print(f"Evaluation: Novelty={evaluation.novelty}, Feasibility={evaluation.feasibility}, Impact={evaluation.impact}")
        print(f"Pros: {evaluation.arguments_pro}")
        print(f"Cons: {evaluation.arguments_con}")

if __name__ == "__main__":
    asyncio.run(test_pragmatist_baseline())
