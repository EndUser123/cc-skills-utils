#!/usr/bin/env python3
"""Test import reference detection with real files."""

import sys
from pathlib import Path

# Add cleanup skill scripts/ to path BEFORE importing (cleanup.py moved to scripts/)
cleanup_scripts_dir = Path("P:/.claude/skills/cleanup/scripts")
sys.path.insert(0, str(cleanup_scripts_dir))

# Now we can import from cleanup module in scripts/
from cleanup import find_import_references  # noqa: E402

# Test 1: A file that should be imported - unified_semantic_daemon.py
test_file = "P:/__csf/src/daemons/unified_semantic_daemon.py"
print(f"Testing: {test_file}")
print("="*60)

references = find_import_references(test_file, search_root="P:/__csf")

print(f"Found {len(references)} import references:")
for ref in references[:10]:  # Show first 10
    print(f"  - {ref}")

if len(references) > 10:
    print(f"  ... and {len(references) - 10} more")

print()

# Test 2: A file with submodule imports - let's try path_validator.py
test_file2 = "P:/.claude/hooks/path_validator.py"
print(f"Testing: {test_file2}")
print("="*60)

references2 = find_import_references(test_file2, search_root="P:/")

print(f"Found {len(references2)} import references:")
for ref in references2[:10]:
    print(f"  - {ref}")

if len(references2) > 10:
    print(f"  ... and {len(references2) - 10} more")

print()
print("VERIFICATION:")
print("- If unified_semantic_daemon.py shows 0 references, submodule detection failed")
print("- If path_validator.py shows 0 references, basic detection failed")
