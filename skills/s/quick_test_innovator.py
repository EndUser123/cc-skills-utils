
import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from lib.agents.innovator import InnovatorAgent
from lib.models import BrainstormContext

async def test_innovator():
    print("Testing current InnovatorAgent...")
    agent = InnovatorAgent()
    context = BrainstormContext(
        topic="A new way to organize digital files for creative professionals",
        num_ideas=3,
        goals=["No manual tagging", "Visual-first interface", "Cross-platform"],
        constraints=["Privacy-focused", "Works offline"]
    )
    
    ideas = await agent.generate_ideas(context)
    
    print(f"\nGenerated {len(ideas)} ideas:")
    for i, idea in enumerate(ideas):
        print(f"\n--- Idea {i+1} (Score: {idea.score}) ---")
        print(f"Content: {idea.content[:200]}...")
        print(f"Persona: {idea.persona}")
        
        # Test evaluation
        evaluation = await agent.evaluate_idea(idea)
        print(f"Evaluation (Novelty: {evaluation.novelty_score}, Feasibility: {evaluation.feasibility_score}, Impact: {evaluation.impact_score})")
        print(f"Pros: {evaluation.arguments_pro}")
        print(f"Cons: {evaluation.arguments_con}")

if __name__ == "__main__":
    asyncio.run(test_innovator())
