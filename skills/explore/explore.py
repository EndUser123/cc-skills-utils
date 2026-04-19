#!/usr/bin/env python3
"""Universal search command - search local + web sources with unified results.

This script provides the /explore command that searches across:
- Local sources: CLAUDE-HISTORY (chat), CKS (knowledge), Code, DOCS, SKILLS
- Web sources: Tavily, Serper, Exa, multiple search providers
- Merged results via Reciprocal Rank Fusion (RRF)
- THREE-LAYER FILTERING for intelligent result reduction

Note: Chat history search is now handled by the claude-history Rust package (v1.0.1+).
See: P:/packages/claude-history/ for details on the chat history search backend.

Usage:
    python explore.py "python async patterns"          # Auto mode (default)
    python explore.py "query" --mode unified           # Always search both
    python explore.py "query" --enable-layer2          # Force context-aware filtering
    python explore.py "query" --format json            # JSON output
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
src_path = Path(__file__).parent.parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

skills_path = Path(__file__).parent
sys.path.insert(0, str(skills_path))

# Import extracted search executor module
# Import filtering functions
import layer2_filter  # noqa: E402
import search_executor  # noqa: E402

apply_layer2_filtering = layer2_filter.apply_layer2_filtering
should_apply_context_filter = layer2_filter.should_apply_context_filter


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Universal search across local and web sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "python async patterns"              # Auto mode (default)
  %(prog)s "query" --mode unified               # Always search both
  %(prog)s "query" --mode local-only            # Local only
  %(prog)s "query" --mode web-fallback          # Web if local poor
  %(prog)s "query" --limit 20                   # More results
  %(prog)s "query" --rrf-k 80                   # RRF constant
  %(prog)s "query" --min-score 0.7              # Quality threshold
        """,
    )

    parser.add_argument("query", help="Search query")

    parser.add_argument(
        "--mode",
        choices=["auto", "unified", "local-only", "web-fallback"],
        default="auto",
        help="Search mode (default: auto)",
    )

    parser.add_argument(
        "--limit", type=int, default=10, help="Maximum results to return (default: 10)"
    )

    parser.add_argument(
        "--rrf-k", type=int, default=60, help="RRF constant for result fusion (default: 60)"
    )

    parser.add_argument(
        "--min-score",
        type=float,
        default=0.5,
        help="Minimum relevance score for quality check (default: 0.5)",
    )

    parser.add_argument(
        "--min-results",
        type=int,
        default=3,
        help="Minimum result count for quality check (default: 3)",
    )

    parser.add_argument(
        "--enable-jmri",
        action="store_true",
        default=True,
        help="Enable jMRI token-efficient retrieval (default: True)",
    )

    parser.add_argument(
        "--format",
        choices=["human", "json"],
        default="human",
        help="Output format (default: human)",
    )

    parser.add_argument(
        "--enable-layer2",
        action="store_true",
        help="Enable Layer 2 context-aware filtering (default: auto-detect)",
    )

    parser.add_argument(
        "--disable-layer2", action="store_true", help="Disable Layer 2 context-aware filtering"
    )

    parser.add_argument(
        "--context-threshold",
        type=int,
        default=20,
        help="Result count threshold for Layer 2 (default: 20)",
    )

    parser.add_argument(
        "--force-layer2",
        action="store_true",
        help="Force Layer 2 filtering even for small result sets",
    )

    return parser.parse_args()


async def search_universal_with_filtering(
    query: str,
    mode: str = "auto",
    limit: int = 10,
    rrf_k: int = 60,
    min_score: float = 0.5,
    min_results: int = 3,
    enable_jmri: bool = True,
    enable_layer2: bool = True,
    disable_layer2: bool = False,
    context_threshold: int = 20,
    force_layer2: bool = False,
) -> tuple[list, bool, Any]:
    """Execute universal search with three-layer filtering.

    Args:
        query: Search query
        mode: Search mode (auto, unified, local-only, web-fallback)
        limit: Maximum results from Layer 1
        rrf_k: RRF constant
        min_score: Minimum relevance score
        min_results: Minimum result count
        enable_jmri: Enable jMRI
        enable_layer2: Allow Layer 2 filtering
        disable_layer2: Disable Layer 2 filtering
        context_threshold: Result count threshold for Layer 2
        force_layer2: Force Layer 2 even for small result sets

    Returns:
        Tuple of (results, layer2_applied, filtered_results)
    """
    # ========== LAYER 1: Python Rule-Based Filtering ==========
    print(f"[Layer 1] Python filtering: Searching for '{query}' (mode: {mode}, limit: {limit})")

    # Execute search using extracted module
    results = await search_executor.execute_search(
        query=query,
        mode=mode,
        limit=limit,
        rrf_k=rrf_k,
        min_score=min_score,
        min_results=min_results,
        enable_jmri=enable_jmri,
    )

    print(f"[Layer 1] → {len(results)} results")
    print("  - Duplicates removed")
    print("  - Quality floor applied (score >= 0.5)")
    print("  - Hard cap enforced (max 50)")

    # ========== LAYER 2: Context-Aware Filtering ==========
    layer2_applied = False
    filtered_results = results

    if not disable_layer2 and (enable_layer2 or force_layer2):
        should_apply, reason = should_apply_context_filter(results, query, context_threshold)

        if should_apply or force_layer2:
            print(f"\n[Layer 2] Triggered: {reason if should_apply else 'forced'}")
            print("[Layer 2] Applying context-aware filtering...")

            # Apply Layer 2 filtering (auto-selects best method)
            filtered_results = await apply_layer2_filtering(query, results)

            layer2_applied = True

            print(
                f"[Layer 2] → {filtered_results['filtered_count']} key insights (from {filtered_results['original_count']})"
            )
            print(f"  - Themes: {len(filtered_results['themes'])} themes identified")
            for theme in filtered_results["themes"]:
                print(f"    • {theme['name']}: {len(theme['insights'])} insights")
        else:
            print(f"\n[Layer 2] Skipped: {len(results)} results, below threshold, no context hints")
    elif disable_layer2:
        print("\n[Layer 2] Disabled by --disable-layer2 flag")

    # ========== LAYER 3: Presentation Formatting ==========
    print("\n[Layer 3] Formatting output...")

    return results, layer2_applied, filtered_results


async def main() -> int:
    """Main entry point with three-layer filtering."""
    args = parse_args()

    # Validate query
    if not args.query or not args.query.strip():
        print("Error: Query cannot be empty", file=sys.stderr)
        return 1

    try:
        # Execute search with three-layer filtering
        results, layer2_applied, filtered_results = await search_universal_with_filtering(
            query=args.query,
            mode=args.mode,
            limit=args.limit,
            rrf_k=args.rrf_k,
            min_score=args.min_score,
            min_results=args.min_results,
            enable_jmri=args.enable_jmri,
            enable_layer2=True if not args.disable_layer2 else args.enable_layer2,
            disable_layer2=args.disable_layer2,
            context_threshold=args.context_threshold,
            force_layer2=args.force_layer2,
        )

        # Format output using extracted module
        if args.format == "json":
            output = search_executor.format_results_json(args.query, results, args.mode)
        else:
            output = search_executor.format_results_human(
                args.query, results, args.mode, layer2_applied, filtered_results
            )

        print(output)
        return 0

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error during search: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
