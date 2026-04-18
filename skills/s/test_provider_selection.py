#!/usr/bin/env python3
"""
Quick test to see which provider gets selected.
"""
import asyncio
import sys
from pathlib import Path

# Setup sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "__csf" / "src"))
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from agents.expert import ExpertAgent


async def main():
    print("=" * 80)
    print("Testing Provider Selection")
    print("=" * 80)

    # Create ExpertAgent (no explicit provider specified)
    agent = ExpertAgent()

    # Trigger provider selection by calling _get_provider
    provider = agent.llm_client._get_provider()

    print(f"\nSelected provider: {provider.__class__.__name__}")
    print(f"Provider ID: {provider.provider_id}")

    # Try to generate a simple idea to see the actual API call
    from lib.models import BrainstormContext

    context = BrainstormContext(
        topic="test topic",
        num_ideas=1,
        fresh_mode=False,
    )

    print("\nAttempting to generate 1 idea...")
    ideas = await agent.generate_ideas(context)

    print(f"\nGenerated {len(ideas)} ideas")

if __name__ == "__main__":
    asyncio.run(main())
