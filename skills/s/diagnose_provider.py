#!/usr/bin/env python3
"""
Diagnostic script to trace LLM provider configuration during cognitive framework tests.

This will help us understand:
1. Which provider is actually being used
2. What environment variables are set
3. Provider registry state
"""

import json
import os
from pathlib import Path


def check_env_vars():
    """Check which API keys are configured."""
    print("\n1. Environment Variables:")
    print("-" * 40)

    api_keys = {
        "CHUTES_API_KEY": os.getenv("CHUTES_API_KEY"),
        "Z_AI_API_KEY": os.getenv("Z_AI_API_KEY"),
        "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
        "MISTRAL_API_KEY": os.getenv("MISTRAL_API_KEY"),
        "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY"),
    }

    for key, value in api_keys.items():
        status = "✓ SET" if value else "✗ NOT SET"
        # Show first 8 chars of key if set
        key_preview = f"{value[:8]}... ({len(value)} chars)" if value else "N/A"
        print(f"  {key}: {status}")
        if value:
            print(f"    → {key_preview}")


def check_provider_registry_state():
    """Check provider registry state file."""
    print("\n2. Provider Registry State:")
    print("-" * 40)

    # Check for state file
    state_file = Path.home() / ".csf_nip" / "provider_registry_state.json"

    if state_file.exists():
        print(f"  State file: {state_file}")
        try:
            with open(state_file) as f:
                state = json.load(f)

            print(f"  Providers tracked: {list(state.get('provider_states', {}).keys())}")

            for provider_id, provider_state in state.get('provider_states', {}).items():
                print(f"\n  {provider_id}:")
                print(f"    Available: {provider_state.get('available', 'N/A')}")
                print(f"    Healthy: {provider_state.get('healthy', 'N/A')}")
                print(f"    Failure Count: {provider_state.get('failure_count', 0)}")

                if provider_state.get('last_error'):
                    error = provider_state['last_error']
                    print(f"    Last Error: {error[:80]}...")

                if provider_state.get('backoff_until'):
                    print(f"    Backoff Until: {provider_state['backoff_until']}")

        except Exception as e:
            print(f"  ERROR reading state file: {e}")
    else:
        print(f"  No state file found at: {state_file}")
        print("  → Provider registry has not been initialized yet")


def check_llm_config():
    """Check LLM configuration from run_heavy.py."""
    print("\n3. LLM Configuration Analysis:")
    print("-" * 40)

    # Read base.py to see defaults
    base_file = Path(__file__).parent / "lib" / "agents" / "base.py"
    if base_file.exists():
        print(f"  Reading: {base_file}")

        content = base_file.read_text()

        # Extract default temperature
        if "temperature: float = 0.7" in content:
            print("  ✓ Default temperature: 0.7 (AgentLLMClient)")

        # Extract provider selection logic
        if '"chutes"' in content:
            print("  ✓ Chutes provider: First priority")

        if 'fallback to groq' in content.lower() or '"groq"' in content:
            print("  ✓ Groq provider: Fallback available")

    # Read expert.py to see ExpertAgent temperature
    expert_file = Path(__file__).parent / "lib" / "agents" / "expert.py"
    if expert_file.exists():
        print(f"\n  Reading: {expert_file}")

        content = expert_file.read_text()

        # Extract temperature used by ExpertAgent
        if "temperature=0.6" in content:
            print("  ✓ ExpertAgent temperature: 0.6")


def check_provider_detection():
    """Trace through provider detection logic."""
    print("\n4. Provider Detection Logic:")
    print("-" * 40)

    # Check which API keys are present
    has_chutes = bool(os.getenv("CHUTES_API_KEY"))
    has_groq = bool(os.getenv("GROQ_API_KEY"))

    print(f"  Chutes API key present: {has_chutes}")
    print(f"  Groq API key present: {has_groq}")

    if has_chutes:
        print("\n  → Expected provider: chutes")
        print("    (chutes is first in API_PROVIDERS list)")
    elif has_groq:
        print("\n  → Expected provider: groq")
        print("    (fallback when no other providers available)")
    else:
        print("\n  → WARNING: No API keys detected!")
        print("    → LLM calls will fail")

    # Check for Z_AI_API_KEY mapping
    zai_key = os.getenv("Z_AI_API_KEY")
    if zai_key and not has_chutes:
        print("\n  ⚠️  Z_AI_API_KEY is set but CHUTES_API_KEY is not")
        print("    → Z_AI_API_KEY may need to be aliased to CHUTES_API_KEY")
        print(f"    → Z_AI_API_KEY preview: {zai_key[:8]}...")


def main():
    """Run all diagnostics."""
    print("=" * 80)
    print("LLM Provider Configuration Diagnostic")
    print("=" * 80)

    check_env_vars()
    check_provider_registry_state()
    check_llm_config()
    check_provider_detection()

    print("\n" + "=" * 80)
    print("Diagnostic Complete")
    print("=" * 80)

    print("\nSUMMARY:")
    print("-" * 40)
    print("The root cause of 20% reliability is likely:")
    print("")
    print("1. **Empty LLM responses**: The retry logic improved lateral from 20% → 60%")
    print("   → This suggests the provider IS working but returns empty responses")
    print("")
    print("2. **Possible causes**:")
    print("   - Rate limiting (300 requests/day quota for chutes)")
    print("   - Model instability/free tier limitations")
    print("   - Timeout settings too aggressive (30s default)")
    print("   - Context window exhaustion")
    print("")
    print("3. **Next investigation steps**:")
    print("   - Check which model is actually being called")
    print("   - Monitor actual API calls during test runs")
    print("   - Test with increased timeout (60s → 90s)")
    print("   - Consider using groq fallback instead of chutes")


if __name__ == "__main__":
    main()
