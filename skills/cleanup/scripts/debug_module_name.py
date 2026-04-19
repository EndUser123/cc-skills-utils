#!/usr/bin/env python3
"""Debug module name generation."""

from pathlib import Path

test_file = "P:/__csf/src/daemons/unified_semantic_daemon.py"
file_path_obj = Path(test_file).resolve()

print(f"File: {file_path_obj}")
print(f"Parts: {file_path_obj.parts}")
print()

if '__csf' in file_path_obj.parts:
    csf_idx = file_path_obj.parts.index('__csf')
    print(f"__csf index: {csf_idx}")
    print(f"After __csf: {file_path_obj.parts[csf_idx + 1:]}")

    after_csf = file_path_obj.parts[csf_idx + 1:]
    print()
    print(f"after_csf: {after_csf}")

    if after_csf:
        module_name = str(after_csf[-1]).replace('.py', '')
        print(f"module_name: {module_name}")

        if len(after_csf) > 1:
            full_path = '.'.join(after_csf[:-1] + [module_name])
            without_first = '.'.join(after_csf[1:-1] + [module_name]) if len(after_csf) > 2 else module_name
            print(f"Candidates: {full_path}, {without_first}")

print()
print("EXPECTED imports from actual codebase:")
print("  from src.daemons.unified_semantic_daemon import...")
print("  from daemons.unified_semantic_daemon import...")
