#!/usr/bin/env python3
"""
Test cognitive frameworks to measure value add.

Tests each cognitive framework (first-principles, lateral, SCAMPER, etc.)
and measures:
1. Idea count per framework
2. Unique ideas (not in baseline)
3. Content overlap with baseline
"""

import asyncio
import sys
from pathlib import Path

# Add scripts/lib to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from scripts.run_heavy import TopicSelection, run_heavy


async def test_framework(topic: str, framework_prompt: str):
    """Test a single cognitive framework."""
    enhanced_topic = f"{topic}\n\nAPPROACH CONSTRAINT: {framework_prompt}"

    result = await run_heavy(
        topic_meta=TopicSelection(topic=enhanced_topic, source="explicit", confidence=1.0),
        personas=["expert"],
        timeout=60.0,
        num_ideas=3,
        use_mock=False,
        local_repetition=0,
        llm_config=None,
        debate_mode="none",
        enable_pheromone_trail=False,
        enable_replay_buffer=False,
    )

    ideas = result.ideas if hasattr(result, 'ideas') else []
    return [idea.content for idea in ideas]


async def main():
    topic = "API testing strategies"

    # Cognitive frameworks to test
    frameworks = {
        "first-principles": "Use first-principles thinking. Challenge fundamental assumptions.",
        "lateral": "Use lateral thinking. Consider random entry points and unexpected connections.",
        "scamper": "Use SCAMPER technique (Substitute, Combine, Adapt, Modify, Put to other uses, Eliminate, Reverse).",
        "reverse": "Use reverse engineering. Start from the ideal outcome and work backwards.",
        "six-hats": "Use Six Thinking Hats. Consider facts, feelings, caution, benefits, creativity, and process separately.",
    }

    print(f"Testing cognitive frameworks for: {topic}\n")
    print("=" * 80)

    # Get baseline
    print("1. Testing baseline (no cognitive framework)...")
    baseline_result = await test_framework(topic, "")
    baseline_ideas = set(baseline_result)
    print(f"   Baseline: {len(baseline_ideas)} ideas\n")

    # Test each framework
    framework_results = {}
    for name, prompt in frameworks.items():
        print(f"2. Testing {name}...")
        ideas = await test_framework(topic, prompt)
        unique_ideas = set(ideas) - baseline_ideas
        overlap_pct = len(set(ideas) & baseline_ideas) / len(baseline_ideas) * 100 if baseline_ideas else 0

        framework_results[name] = {
            "total_ideas": len(ideas),
            "unique_ideas": len(unique_ideas),
            "overlap_pct": overlap_pct,
            "ideas": ideas,
        }

        print(f"   Total: {len(ideas)}, Unique: {len(unique_ideas)}, Overlap: {overlap_pct:.1f}%\n")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY: Cognitive Framework Value Add")
    print("=" * 80)

    for name, data in framework_results.items():
        print(f"\n{name}:")
        print(f"  Total ideas: {data['total_ideas']}")
        print(f"  Unique ideas: {data['unique_ideas']}")
        print(f"  Overlap with baseline: {data['overlap_pct']:.1f}%")

    if all(f["unique_ideas"] == 0 for f in framework_results.values()):
        print("\n🚨 RESULT: All frameworks produced 0 unique ideas beyond baseline.")
        print("   RECOMMENDATION: Remove --local-llm-repetition feature.")
    else:
        best = max(framework_results.items(), key=lambda x: x[1]["unique_ideas"])
        print(f"\n✅ Best framework: {best[0]} with {best[1]['unique_ideas']} unique ideas")
        print("   RECOMMENDATION: Consider using this framework by default.")


if __name__ == "__main__":
    asyncio.run(main())
