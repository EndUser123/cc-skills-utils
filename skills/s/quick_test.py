#!/usr/bin/env python3
"""Quick test to see provider selection with debug output."""
import asyncio
import sys
from pathlib import Path

# Setup paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "lib"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "__csf" / "src"))

from scripts.run_heavy import TopicSelection, run_heavy


async def main():
    print("=" * 80)
    print("Quick Provider Selection Test")
    print("=" * 80)

    result = await run_heavy(
        topic_meta=TopicSelection(topic="test topic", source="explicit", confidence=1.0),
        personas=["expert"],
        timeout=60.0,
        num_ideas=1,
        use_mock=False,
        local_repetition=0,
        llm_config=None,
        debate_mode="none",
        enable_pheromone_trail=False,
        enable_replay_buffer=False,
    )

    ideas = result.ideas if hasattr(result, 'ideas') else []
    print(f"\nGenerated {len(ideas)} ideas")

if __name__ == "__main__":
    asyncio.run(main())
