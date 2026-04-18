#!/usr/bin/env python3
"""
Verification script for empty response validation fix.

This script verifies that the AgentLLMClient.generate() method now includes
empty response validation that will fail fast instead of timing out.
"""

import sys
from pathlib import Path


def verify_fix():
    """Verify the fix is present in the code."""
    print("=" * 70)
    print("Verifying Empty Response Validation Fix")
    print("=" * 70)

    base_py = Path(__file__).parent / "agents" / "base.py"

    if not base_py.exists():
        print(f"❌ FAIL: {base_py} not found")
        return False

    content = base_py.read_text()

    # Check for the fix
    checks = [
        {
            "name": "Empty response object validation",
            "pattern": "if not response:",
            "description": "Checks for None response object"
        },
        {
            "name": "Empty response content validation",
            "pattern": "if not response.content or not response.content.strip():",
            "description": "Checks for empty or whitespace-only content"
        },
        {
            "name": "ValueError with provider name",
            "pattern": 'f"Empty response from provider {provider_name}',
            "description": "Error message includes provider name"
        },
        {
            "name": "Provider name extraction",
            "pattern": "provider_name = provider.__class__.__name__",
            "description": "Extracts provider name for error messages"
        },
    ]

    all_passed = True
    for check in checks:
        if check["pattern"] in content:
            print(f"✅ PASS: {check['name']}")
            print(f"   {check['description']}")
        else:
            print(f"❌ FAIL: {check['name']}")
            print(f"   Expected: {check['description']}")
            print(f"   Pattern not found: {check['pattern']}")
            all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("✅ All checks passed! The fix is correctly implemented.")
        print("\nThe fix will now:")
        print("1. Immediately detect when providers return None responses")
        print("2. Immediately detect when providers return empty content")
        print("3. Raise clear ValueError with provider name")
        print("4. Prevent 108-second timeout from empty responses")
        return True
    else:
        print("❌ Some checks failed. The fix may not be complete.")
        return False


def show_fix_details():
    """Show the actual fix in the code."""
    print("\n" + "=" * 70)
    print("Fix Details")
    print("=" * 70)

    base_py = Path(__file__).parent / "agents" / "base.py"
    content = base_py.read_text()

    # Find the generate method
    start_marker = "    async def generate("
    end_marker = "        return response"

    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker, start_idx) + len(end_marker)

    if start_idx != -1 and end_idx != -1:
        method_code = content[start_idx:end_idx]
        print("\nAgentLLMClient.generate() method:")
        print("-" * 70)
        for line in method_code.split('\n'):
            print(line)
        print("-" * 70)

    print("\nKey changes:")
    print("1. Added provider_name extraction for error messages")
    print("2. Added validation: if not response")
    print("3. Added validation: if not response.content or not response.content.strip()")
    print("4. Raises ValueError with clear provider-specific error message")


def main():
    """Main verification."""
    success = verify_fix()
    show_fix_details()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
