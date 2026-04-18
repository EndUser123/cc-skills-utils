#!/usr/bin/env python3
"""
Test for Structural Synthesis Strategy.

Verifies that:
1. IdeaSynthesizer accepts got_analysis data.
2. The 'structural' strategy uses GoT data to find connections.
3. Hybrid ideas are generated correctly with structural context.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Setup sys.path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.convergence.clustering import Cluster
from lib.convergence.synthesizer import IdeaSynthesizer
from lib.models import Idea


async def test_structural_synthesis():
    print("Starting structural synthesis test...")

    # 1. Setup mock ideas
    idea1 = Idea(
        id="idea-1",
        content="Deploy a fleet of autonomous electric drones for last-mile delivery.",
        persona="Innovator",
        score=80.0,
    )
    idea2 = Idea(
        id="idea-2",
        content="Establish a network of neighborhood micro-hubs for package sorting.",
        persona="Pragmatist",
        score=75.0,
    )

    cluster = Cluster(ideas=[idea1, idea2], representative_id="idea-1")

    # 2. Setup mock GoT analysis
    got_analysis = {
        "nodes": [
            {"type": "Autonomous Drones", "content": "Electric delivery drones"},
            {"type": "Micro-hubs", "content": "Neighborhood sorting centers"},
        ],
        "edges": [
            {
                "from": "Micro-hubs",
                "to": "Autonomous Drones",
                "relationship": "Provides landing and charging infrastructure",
            }
        ],
        "summary": {"total_nodes": 2, "total_edges": 1, "cycles_detected": 0},
    }

    # 3. Initialize synthesizer with mock LLM client
    # We want to verify that the prompt sent to LLM contains the GoT data
    synthesizer = IdeaSynthesizer(llm_config=MagicMock())
    synthesizer.llm_client.generate = AsyncMock()

    # Mock response
    mock_response = MagicMock()
    mock_response.content = "[Title: Integrated Drone Hub Network]\n[Problem: Last-mile delivery efficiency]\n[Synthesis: A network of hubs where drones land and charge.]\n[Synergies: Hubs provide charging, drones provide speed.]\n[Reasoning: Structural integration of infrastructure and vehicles.]"
    mock_response.model_used = "mock-model"
    synthesizer.llm_client.generate.return_value = mock_response

    # 4. Run synthesis with 'structural' strategy
    print("Running structural synthesis...")
    results = await synthesizer.synthesize(
        cluster=cluster, strategy="structural", max_results=1, got_analysis=got_analysis
    )

    # 5. Verify results
    assert len(results) > 0
    syn_idea = results[0]
    assert syn_idea.synthesis_type == "structural"
    assert "structural integration" in syn_idea.reasoning[-1].lower()

    # Verify LLM call contained GoT data
    args, kwargs = synthesizer.llm_client.generate.call_args
    prompt = kwargs.get("prompt", "")
    assert "Graph-of-Thought" in prompt
    assert "Provides landing and charging infrastructure" in prompt

    print("[PASS] Structural synthesis test successful!")


if __name__ == "__main__":
    try:
        asyncio.run(test_structural_synthesis())
    except Exception as e:
        print(f"[FAIL] Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
