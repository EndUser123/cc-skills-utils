#!/usr/bin/env python3
"""
Run cognitive frameworks test 5 times to observe reliability patterns.
"""

import asyncio
import sys
from collections import defaultdict
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
    return len([idea for idea in ideas if idea.content and len(idea.content) >= 10])


async def main():
    topic = "API testing strategies"

    # Cognitive frameworks to test
    frameworks = {
        "first-principles": "Use first-principles thinking. List 3 assumptions everyone makes about this problem. Then challenge each one with a counter-approach.",
        "lateral": "Use lateral thinking. Take this problem and apply it to a completely different domain (cooking, sports, nature). What does that analogy suggest?",
        "scamper": "Use SCAMPER. Answer these 3 questions: 1) What component could be removed? 2) What two things could be combined? 3) What if this was used for the opposite purpose?",
        "reverse": "Use reverse engineering. Fast-forward 2 years: this problem is solved. What does the solution look like? Now list the 3 steps that happened right before that success.",
        "six-hats": "Use Six Thinking Hats. Give me 3 perspectives: 1) The skeptic's biggest worry, 2) The optimist's dream outcome, 3) The creative wildest idea.",
    }

    print(f"Running cognitive frameworks 5 times each for: {topic}\n")
    print("=" * 80)

    # Test each framework 5 times
    results = defaultdict(list)

    for run_num in range(1, 6):
        print(f"\n--- RUN {run_num} ---")

        for name, prompt in frameworks.items():
            count = await test_framework(topic, prompt)
            results[name].append(count)
            print(f"  {name}: {count} ideas")

    # Summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY: 5-Run Reliability Analysis")
    print("=" * 80)

    for name, counts in results.items():
        avg = sum(counts) / len(counts)
        min_val = min(counts)
        max_val = max(counts)
        reliability = sum(1 for c in counts if c >= 3) / len(counts) * 100

        print(f"\n{name}:")
        print(f"  Results: {counts}")
        print(f"  Average: {avg:.1f}")
        print(f"  Range: {min_val}-{max_val}")
        print(f"  Reliability (≥3 ideas): {reliability:.0f}%")

    print("\n" + "=" * 80)
    print("CONCLUSION:")

    # Calculate overall reliability
    all_3_plus = [name for name, counts in results.items() if all(c >= 3 for c in counts)]
    sometimes_3 = [name for name, counts in results.items() if any(c >= 3 for c in counts) and not all(c >= 3 for c in counts)]
    never_3 = [name for name, counts in results.items() if all(c < 3 for c in counts)]

    if all_3_plus:
        print(f"  ✅ Always reliable (≥3 ideas): {', '.join(all_3_plus)}")
    if sometimes_3:
        print(f"  ⚠️  Sometimes reliable: {', '.join(sometimes_3)}")
    if never_3:
        print(f"  ❌ Never reliable (≥3 ideas): {', '.join(never_3)}")


if __name__ == "__main__":
    asyncio.run(main())
