#!/usr/bin/env python3
"""
Test what providers the provider registry actually detects.
"""
import sys
from pathlib import Path

# Setup sys.path for external LLM dependencies
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "__csf" / "src"))

from llm.providers import get_registry


def main():
    print("=" * 80)
    print("Provider Registry Detection Test")
    print("=" * 80)

    # Get registry
    registry = get_registry(refresh=True)

    # Get detected providers
    providers = registry.get_providers()

    print(f"\nDetected providers: {providers}")

    print(f"\nAPI providers: {registry._api_providers}")
    print(f"CLI providers: {registry._cli_providers}")

    # Get provider states
    print("\nProvider States:")
    for provider_id, state in registry._provider_states.items():
        print(f"\n  {provider_id}:")
        print(f"    Available: {state.available}")
        print(f"    Healthy: {state.healthy}")
        print(f"    Provider Type: {state.provider_type}")

    # Get summary
    summary = registry.get_summary()
    print("\nRegistry Summary:")
    print(f"  Total detected: {summary['total_detected']}")
    print(f"  API providers: {summary['api_providers']}")
    print(f"  CLI providers: {summary['cli_providers']}")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
