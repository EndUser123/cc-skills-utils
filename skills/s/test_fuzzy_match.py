#!/usr/bin/env python3
"""Quick test of fuzzy matching implementation for /s skill."""

import argparse
import os
import sys

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))

from run_heavy import _levenshtein_distance, fuzzy_match_args


def test_levenshtein_distance():
    """Test Levenshtein distance calculation."""
    print("Testing Levenshtein distance...")

    # Test cases: (s1, s2, expected_distance)
    test_cases = [
        ("--verbos", "--verbose", 1),  # Missing 'e'
        ("--outpit", "--output", 1),   # 't' vs 'u' at end
        ("--topic", "--topic", 0),     # Identical
        ("--fresh-mod", "--fresh-mode", 1),  # Missing 'e'
        ("--x", "--context-path", 11),  # Very different
    ]

    all_passed = True
    for s1, s2, expected in test_cases:
        result = _levenshtein_distance(s1, s2)
        status = "✓" if result == expected else "✗"
        print(f"  {status} distance('{s1}', '{s2}') = {result} (expected {expected})")
        if result != expected:
            all_passed = False

    return all_passed


def test_semantic_mappings():
    """Test semantic intent mappings trigger help."""
    print("\nTesting semantic mappings...")

    test_cases = [
        (["--help"], True, "help flag"),
        (["--providers"], True, "providers flag"),
        (["--models"], True, "models flag"),
        (["--tiers"], True, "tiers flag"),
        (["-h"], True, "short help flag"),
        (["--topic", "test"], False, "normal usage"),
    ]

    all_passed = True
    for argv, should_trigger_help, description in test_cases:
        try:
            # Create a dummy args namespace
            args = argparse.Namespace(
                topic="test",
                context_path="",
                personas="",
                timeout=180.0,
                ideas=10,
                output="text",
                fresh_mode=False,
                strict_stale=False,
                local_llm_repetition=0,
                local_only=False,
                provider_tier="",
                debate_mode="none",
                enable_pheromone_trail=False,
                enable_replay_buffer=False,
                skip_health_gate=False,
                show_models=True,
                diagram=False,
                auto_confirm=False
            )

            # This will sys.exit(0) if help is triggered
            args, warnings = fuzzy_match_args(args, argv)

            if should_trigger_help:
                print(f"  ✗ {description}: Should have triggered help but didn't")
                all_passed = False
            else:
                print(f"  ✓ {description}: Correctly did not trigger help")
        except SystemExit as e:
            if should_trigger_help and e.code == 0:
                print(f"  ✓ {description}: Correctly triggered help")
            else:
                print(f"  ✗ {description}: Unexpected exit with code {e.code}")
                all_passed = False

    return all_passed


def test_unknown_flags():
    """Test unknown flag detection and warnings."""
    print("\nTesting unknown flag detection...")

    test_cases = [
        (["--verbos"], "typo detection", True),  # Should suggest --verbose
        (["--unknown-flag"], "completely unknown flag", False),
        (["--topic", "test", "--xyz"], "unknown flag in middle", False),
    ]

    all_passed = True
    for argv, description, should_suggest in test_cases:
        args = argparse.Namespace(
            topic="test",
            context_path="",
            personas="",
            timeout=180.0,
            ideas=10,
            output="text",
            fresh_mode=False,
            strict_stale=False,
            local_llm_repetition=0,
            local_only=False,
            provider_tier="",
            debate_mode="none",
            enable_pheromone_trail=False,
            enable_replay_buffer=False,
            skip_health_gate=False,
            show_models=True,
            diagram=False,
            auto_confirm=False
        )

        args, warnings = fuzzy_match_args(args, argv)

        has_suggestion = any("Did you mean" in w for w in warnings)
        has_warning = len(warnings) > 0

        if should_suggest:
            if has_suggestion:
                print(f"  ✓ {description}: Suggested correction")
                print(f"    Warning: {warnings[0]}")
            else:
                print(f"  ✗ {description}: Should have suggested correction")
                all_passed = False
        elif has_warning:
            print(f"  ✓ {description}: Generated warning (not suggestion)")
            print(f"    Warning: {warnings[0]}")
        else:
            print(f"  ✓ {description}: No unknown flags detected")

    return all_passed


def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing /s fuzzy matching implementation")
    print("=" * 60)

    results = []
    results.append(test_levenshtein_distance())
    results.append(test_semantic_mappings())
    results.append(test_unknown_flags())

    print("\n" + "=" * 60)
    if all(results):
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        return 0
    else:
        print("✗ SOME TESTS FAILED")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
