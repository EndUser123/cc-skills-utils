#!/usr/bin/env python3
"""Test empty response validation in AgentLLMClient.generate()"""

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Add paths for imports
lib_path = Path(__file__).parent
sys.path.insert(0, str(lib_path.parent))
sys.path.insert(0, str(lib_path.parent.parent.parent.parent.parent / "__csf" / "src"))

# Mock the llm.providers module BEFORE importing
mock_llm = MagicMock()
mock_providers = MagicMock()
mock_base = MagicMock()

sys.modules["llm"] = mock_llm
sys.modules["llm.providers"] = mock_providers
sys.modules["llm.providers.base"] = mock_base

# Create a mock ProviderResponse
@dataclass
class MockProviderResponse:
    content: str
    model_used: str = "test-model"

# Set up the mock ProviderResponse BEFORE importing
sys.modules["llm.providers.base"].ProviderResponse = MockProviderResponse

# Mock other required modules
sys.modules["llm.providers.LLMConfig"] = MagicMock()
sys.modules["llm.providers.ProviderConfig"] = MagicMock()
sys.modules["llm.providers.ProviderFactory"] = MagicMock()

# Import after mocking
from lib.agents.base import AgentLLMClient


async def test_empty_response_object():
    """Test that None response object raises ValueError"""
    print("\n🧪 Test 1: Empty response object (None)")

    # Create a mock provider that returns None
    mock_provider = MagicMock()
    mock_provider.generate_response = AsyncMock(return_value=None)
    mock_provider.__class__.__name__ = "TestProvider"

    client = AgentLLMClient()

    # Mock _get_provider to return our mock
    client._get_provider = AsyncMock(return_value=mock_provider)

    try:
        response = await client.generate(prompt="test prompt")
        print("❌ FAIL: Should have raised ValueError for None response")
        return False
    except ValueError as e:
        error_msg = str(e)
        print("✅ PASS: Raised ValueError as expected")
        print(f"   Error message: {error_msg}")

        # Verify error message contains provider name
        if "TestProvider" in error_msg and "None" in error_msg:
            print("✅ PASS: Error message includes provider name and 'None'")
            return True
        else:
            print("❌ FAIL: Error message missing provider name or 'None'")
            return False
    except Exception as e:
        print(f"❌ FAIL: Raised unexpected exception: {type(e).__name__}: {e}")
        return False


async def test_empty_response_content():
    """Test that response with empty content raises ValueError"""
    print("\n🧪 Test 2: Empty response content (whitespace)")

    # Create a mock provider that returns empty content
    mock_provider = MagicMock()
    mock_provider.__class__.__name__ = "GroqProvider"

    # Test 2a: Completely empty content
    print("\n  Test 2a: Empty string content")
    empty_response = MockProviderResponse(content="")
    mock_provider.generate_response = AsyncMock(return_value=empty_response)

    client = AgentLLMClient()
    client._get_provider = AsyncMock(return_value=mock_provider)

    try:
        response = await client.generate(prompt="test prompt")
        print("  ❌ FAIL: Should have raised ValueError for empty content")
        return False
    except ValueError as e:
        error_msg = str(e)
        print("  ✅ PASS: Raised ValueError as expected")
        print(f"     Error message: {error_msg}")

        if "GroqProvider" in error_msg and ("empty" in error_msg.lower() or "whitespace" in error_msg.lower()):
            print("  ✅ PASS: Error message includes provider name and 'empty/whitespace'")
        else:
            print("  ❌ FAIL: Error message missing expected details")
            return False

    # Test 2b: Whitespace-only content
    print("\n  Test 2b: Whitespace-only content")
    whitespace_response = MockProviderResponse(content="   \n\t  ")
    mock_provider.generate_response = AsyncMock(return_value=whitespace_response)

    try:
        response = await client.generate(prompt="test prompt")
        print("  ❌ FAIL: Should have raised ValueError for whitespace content")
        return False
    except ValueError:
        print("  ✅ PASS: Raised ValueError for whitespace")
        return True
    except Exception as e:
        print(f"  ❌ FAIL: Raised unexpected exception: {type(e).__name__}: {e}")
        return False


async def test_valid_response():
    """Test that valid response passes through"""
    print("\n🧪 Test 3: Valid response")

    # Create a mock provider that returns valid content
    mock_provider = MagicMock()
    mock_provider.__class__.__name__ = "ChutesProvider"
    valid_response = MockProviderResponse(content="This is a valid idea")
    mock_provider.generate_response = AsyncMock(return_value=valid_response)

    client = AgentLLMClient()
    client._get_provider = AsyncMock(return_value=mock_provider)

    try:
        response = await client.generate(prompt="test prompt")
        if response.content == "This is a valid idea":
            print("✅ PASS: Valid response returned correctly")
            return True
        else:
            print(f"❌ FAIL: Unexpected content: {response.content}")
            return False
    except Exception as e:
        print(f"❌ FAIL: Raised unexpected exception: {type(e).__name__}: {e}")
        return False


async def main():
    """Run all tests"""
    print("=" * 70)
    print("Testing Empty Response Validation in AgentLLMClient.generate()")
    print("=" * 70)

    results = []

    # Run all tests
    results.append(await test_empty_response_object())
    results.append(await test_empty_response_content())
    results.append(await test_valid_response())

    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("✅ All tests passed!")
        return 0
    else:
        print(f"❌ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
