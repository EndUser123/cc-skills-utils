#!/usr/bin/env python3
"""Debug test to see what parse_known_args returns."""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))

def test_parse_known_args():
    """Test what parse_known_args actually returns."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default="")
    parser.add_argument("--verbose", action="store_true")

    # Test with typo
    args, unknown = parser.parse_known_args(["--verbos"])

    print(f"args: {args}")
    print(f"unknown: {unknown}")
    print(f"args has 'verbos': {hasattr(args, 'verbos')}")
    print(f"args has 'verbose': {hasattr(args, 'verbose')}")
    print(f"args.verbose value: {args.verbose if hasattr(args, 'verbose') else 'N/A'}")

if __name__ == "__main__":
    test_parse_known_args()
