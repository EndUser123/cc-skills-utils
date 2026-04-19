#!/usr/bin/env python3
"""Performance regression test for cleanup.py O(n²) violation mapping.

This test CAPTURES CURRENT BEHAVIOR of the performance issue in
analyze_source_code_problems() where violations are filtered repeatedly
for each source file, creating O(N*M) complexity.

Issue: Lines 1452, 1465, 1487, 1499 in cleanup.py filter the entire
violations list for EACH source_file, causing quadratic performance.

The test patches is_related_violation to count how many times it's called,
demonstrating that the current implementation calls it O(N*M) times
where N = number of violations and M = number of source files.

Run with: pytest tests/test_performance_fix.py -v
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add cleanup skill scripts/ to path BEFORE importing
cleanup_scripts_dir = Path("P:/.claude/skills/cleanup/scripts")
sys.path.insert(0, str(cleanup_scripts_dir))

from cleanup import (  # noqa: E402
    analyze_source_code_problems,
)
from cleanup import (
    is_related_violation as original_is_related_violation,
)


class TestViolationMappingPerformance:
    """Test that violation mapping maintains O(n) or O(n log n) complexity."""

    @pytest.fixture
    def large_violations_set(self):
        """Generate a large set of violations for performance testing.

        Creates 150 violations across 3 different types to simulate
        real-world workload that triggers the O(n²) issue.

        Returns:
            List of 150 violation dictionaries
        """
        violations = []

        # Generate 50 coverage violations
        for i in range(50):
            violations.append({
                'path': f'P:/project{i % 5}/htmlcov/index.html',
                'rule': 'TEST_OUTPUT_IN_WORKSPACE',
                'severity': 'low'
            })

        # Generate 50 test evidence violations
        for i in range(50):
            violations.append({
                'path': f'P:/project{i % 5}/tdd_evidence/test_{i}.json',
                'rule': 'TEST_OUTPUT_IN_WORKSPACE',
                'severity': 'low'
            })

        # Generate 50 placeholder violations
        for i in range(50):
            violations.append({
                'path': f'P:/fake_{i % 3}',
                'rule': 'HEURISTIC_PLACEHOLDER',
                'severity': 'low'
            })

        return violations

    @pytest.fixture
    def mock_source_finders(self):
        """Mock the source finder functions to return predictable data.

        Returns 10 source files for each violation type to create
        the N*M scenario where N=35 source files and M=150 violations.
        """
        mock_data = {}

        # Mock coverage sources (10 files)
        mock_data['find_coverage_sources'] = {
            f'P:/project{i}/tests/test_coverage.py': ['line 42: coverage output']
            for i in range(10)
        }

        # Mock test evidence sources (10 files)
        mock_data['find_test_evidence_sources'] = {
            f'P:/project{i}/tests/test_evidence.py': ['line 10: evidence output']
            for i in range(10)
        }

        # Mock placeholder sources (10 files)
        mock_data['find_placeholder_dir_sources'] = {
            f'P:/project{i}/setup.py': [f'line {i}: creates fake dir']
            for i in range(10)
        }

        # Mock root path sources (5 files)
        mock_data['find_root_path_construction_sources'] = {
            f'P:/project{i}/config.py': ['line 5: P:/ path construction']
            for i in range(5)
        }

        return mock_data

    def test_counts_is_related_violation_calls(self, large_violations_set, mock_source_finders):
        """Test that demonstrates O(n²) complexity by counting is_related_violation calls.

        Given: 150 violations and 35 source files
        When: analyze_source_code_problems processes the data
        Then: is_related_violation should NOT be called 150*35=5250 times (O(n*m))

        Current implementation filters all violations for each source file:
        - Line 1452: filters coverage_violations (50) for each of 10 sources = 500 calls
        - Line 1465: filters test_evidence_violations (50) for each of 10 sources = 500 calls
        - Line 1487: filters placeholder_violations (50) for each of 10 sources = 500 calls
        - Line 1499: filters all violations (150) for each of 5 sources = 750 calls
        Total: ~2250 calls (O(n*m) where n=150, m=35)

        Optimized version should group violations first, reducing calls to O(n).
        """
        call_count = 0

        def counting_is_related_violation(violation, source_file):
            nonlocal call_count
            call_count += 1
            return original_is_related_violation(violation, source_file)

        with patch('cleanup.find_coverage_sources') as mock_cov, \
             patch('cleanup.find_test_evidence_sources') as mock_ev, \
             patch('cleanup.find_placeholder_dir_sources') as mock_ph, \
             patch('cleanup.find_root_path_construction_sources') as mock_root, \
             patch('cleanup.is_related_violation', side_effect=counting_is_related_violation):

            # Setup mocks
            mock_cov.return_value = mock_source_finders['find_coverage_sources']
            mock_ev.return_value = mock_source_finders['find_test_evidence_sources']
            mock_ph.return_value = mock_source_finders['find_placeholder_dir_sources']
            mock_root.return_value = mock_source_finders['find_root_path_construction_sources']

            # Run the function
            result = analyze_source_code_problems(large_violations_set, search_root="P:/")

            # Verify results are correct
            assert result['total_violations'] == 150
            assert 'source_problems' in result
            assert 'violation_map' in result

            # The test FAILS if call count is too high (O(n*m) behavior)
            # With 150 violations and 35 source files, O(n*m) = ~5250 calls
            # But due to filtering by violation type, actual is ~2250 calls
            # Optimized version should be closer to O(n) = ~150 calls

            print(f"\nis_related_violation called {call_count} times")
            print(f"Violations: {len(large_violations_set)}")
            print(f"Source files: {sum(len(d) for d in mock_source_finders.values())}")
            print("Expected O(n*m): ~2250 calls")
            print("Expected O(n) after fix: ~150 calls")

            # This assertion will FAIL with current O(n²) implementation
            # It will PASS after optimization to O(n)
            assert call_count < 500, (
                f"O(n²) complexity detected: is_related_violation called {call_count} times. "
                f"This indicates violations are being filtered for each source file. "
                f"Expected < 500 calls for O(n) complexity, got {call_count} calls (O(n*m))."
            )

    def test_violation_mapping_correctness(self, large_violations_set, mock_source_finders):
        """Test that violation mapping produces correct results after optimization.

        Given: 150 violations with known relationships to source files
        When: analyze_source_code_problems maps violations to sources
        Then: Each violation should map to correct source files based on is_related_violation

        This ensures any performance optimization maintains correctness.
        """
        with patch('cleanup.find_coverage_sources') as mock_cov, \
             patch('cleanup.find_test_evidence_sources') as mock_ev, \
             patch('cleanup.find_placeholder_dir_sources') as mock_ph, \
             patch('cleanup.find_root_path_construction_sources') as mock_root:

            # Setup mocks
            mock_cov.return_value = mock_source_finders['find_coverage_sources']
            mock_ev.return_value = mock_source_finders['find_test_evidence_sources']
            mock_ph.return_value = mock_source_finders['find_placeholder_dir_sources']
            mock_root.return_value = mock_source_finders['find_root_path_construction_sources']

            result = analyze_source_code_problems(large_violations_set, search_root="P:/")

            # Verify all violations are accounted for
            assert result['total_violations'] == 150

            # Verify violation map structure
            violation_map = result['violation_map']
            assert isinstance(violation_map, dict)

            # Check that mapped violations use correct relatedness logic
            for problem in result['source_problems']:
                source_file = problem['source_file']
                for violation_path in problem['violations']:
                    # Verify that is_related_violation would return True for this pair
                    violation = next(v for v in large_violations_set if v['path'] == violation_path)
                    assert original_is_related_violation(violation, source_file), (
                        f"Violation {violation_path} incorrectly mapped to {source_file}"
                    )

    def test_small_dataset_baseline(self, mock_source_finders):
        """Establish baseline behavior with small dataset.

        Given: 10 violations across 3 types
        When: analyze_source_code_problems processes the data
        Then: Should work correctly regardless of optimization

        This provides a baseline for comparison.
        """
        # Create small dataset (10 violations)
        small_violations = [
            {'path': 'P:/project0/htmlcov/index.html', 'rule': 'TEST_OUTPUT_IN_WORKSPACE'},
            {'path': 'P:/project0/tdd_evidence/test.json', 'rule': 'TEST_OUTPUT_IN_WORKSPACE'},
            {'path': 'P:/fake_0', 'rule': 'HEURISTIC_PLACEHOLDER'},
            {'path': 'P:/project1/htmlcov/index.html', 'rule': 'TEST_OUTPUT_IN_WORKSPACE'},
            {'path': 'P:/project1/tdd_evidence/test.json', 'rule': 'TEST_OUTPUT_IN_WORKSPACE'},
            {'path': 'P:/fake_1', 'rule': 'HEURISTIC_PLACEHOLDER'},
            {'path': 'P:/project2/htmlcov/index.html', 'rule': 'TEST_OUTPUT_IN_WORKSPACE'},
            {'path': 'P:/project2/tdd_evidence/test.json', 'rule': 'TEST_OUTPUT_IN_WORKSPACE'},
            {'path': 'P:/fake_2', 'rule': 'HEURISTIC_PLACEHOLDER'},
            {'path': 'P:/project3/htmlcov/index.html', 'rule': 'TEST_OUTPUT_IN_WORKSPACE'},
        ]

        with patch('cleanup.find_coverage_sources') as mock_cov, \
             patch('cleanup.find_test_evidence_sources') as mock_ev, \
             patch('cleanup.find_placeholder_dir_sources') as mock_ph, \
             patch('cleanup.find_root_path_construction_sources') as mock_root:

            # Setup mocks with smaller datasets
            mock_cov.return_value = {
                'P:/project0/tests/test_coverage.py': ['line 42'],
                'P:/project1/tests/test_coverage.py': ['line 42'],
            }
            mock_ev.return_value = {
                'P:/project0/tests/test_evidence.py': ['line 10'],
                'P:/project1/tests/test_evidence.py': ['line 10'],
            }
            mock_ph.return_value = {
                'P:/project0/setup.py': ['line 1'],
                'P:/project1/setup.py': ['line 1'],
            }
            mock_root.return_value = {}

            result = analyze_source_code_problems(small_violations, search_root="P:/")

            assert result['total_violations'] == 10
            assert 'source_problems' in result
            assert 'violation_map' in result


class TestDemonstrateComplexityIssue:
    """Tests that clearly demonstrate the O(n²) complexity problem."""

    def test_demonstrate_quadratic_filtering(self):
        """Demonstrate the quadratic filtering issue with a simple example.

        Given: 100 violations and 10 source files
        When: Current implementation filters violations for each source
        Then: Results in 100 * 10 = 1000 comparisons (O(n*m))

        This test shows WHY the current approach is slow.
        """
        violations = [
            {'path': f'P:/project{i}/htmlcov/index.html', 'rule': 'TEST_OUTPUT'}
            for i in range(100)
        ]

        source_files = [
            f'P:/project{i}/tests/test.py'
            for i in range(10)
        ]

        comparison_count = 0

        def count_comparison(v, sf):
            nonlocal comparison_count
            comparison_count += 1
            return original_is_related_violation(v, sf)

        # Simulate current O(n*m) approach
        for source_file in source_files:
            # This is what lines 1452, 1465, 1487, 1499 do
            related = [v for v in violations if count_comparison(v, source_file)]
            _ = related  # Suppress unused

        # Current approach: 100 violations * 10 sources = 1000 comparisons
        print(f"\nCurrent approach: {comparison_count} comparisons")
        print(f"Violations: {len(violations)}, Sources: {len(source_files)}")
        print(f"Complexity: O(n*m) = {len(violations) * len(source_files)}")

        assert comparison_count == 1000, "Should demonstrate O(n*m) complexity"

    def test_demonstrate_linear_grouping(self):
        """Demonstrate the optimized O(n) grouping approach.

        Given: 100 violations and 10 source files in same projects
        When: Optimized implementation groups violations by module first
        Then: Results in ~100 comparisons (O(n))

        This test shows what the optimized version SHOULD do.
        """
        from collections import defaultdict

        # Create violations in 10 projects (10 per project)
        violations = []
        for proj_num in range(10):
            for i in range(10):
                violations.append({
                    'path': f'P:/project{proj_num}/htmlcov/file{i}.html',
                    'rule': 'TEST_OUTPUT'
                })

        # Sources in the same 10 projects
        source_files = [
            f'P:/project{i}/tests/test.py'
            for i in range(10)
        ]

        comparison_count = 0

        def count_comparison(v, sf):
            nonlocal comparison_count
            comparison_count += 1
            return original_is_related_violation(v, sf)

        # Optimized approach: group violations by module first
        violation_groups = defaultdict(list)
        for v in violations:
            path_obj = Path(v['path'])
            try:
                rel_path = path_obj.relative_to('P:/')
                if len(rel_path.parts) >= 2:
                    module_key = '/'.join(rel_path.parts[:2])
                    violation_groups[module_key].append(v)
            except Exception:
                pass

        # Now map sources to pre-computed groups (no comparisons needed!)
        mapped_count = 0
        for source_file in source_files:
            source_path = Path(source_file)
            try:
                rel_source = source_path.relative_to('P:/')
                if len(rel_source.parts) >= 2:
                    module_key = '/'.join(rel_source.parts[:2])
                    # For matching projects, this should find violations
                    # project0/tests matches project0/htmlcov (same first 2 parts: project0)
                    # Actually they're different: project0/tests vs project0/htmlcov
                    # So we need to match by just the project name
                    project_key = rel_source.parts[0]  # Just "project0", "project1", etc.
                    # Find all violation groups that start with this project
                    for vgroup_key in violation_groups:
                        if vgroup_key.startswith(project_key + '/'):
                            related = violation_groups[vgroup_key]
                            mapped_count += len(related)
            except Exception:
                pass

        # Optimized approach: 0 comparisons needed (just dict lookups)
        print(f"\nOptimized approach: {comparison_count} comparisons")
        print(f"Violations mapped: {mapped_count}")
        print(f"Complexity: O(n) = {len(violations)}")
        print(f"Module groups: {list(violation_groups.keys())[:5]}...")

        assert comparison_count == 0, "Optimized approach should not need comparisons"

        # Should map all 100 violations (10 per project * 10 projects)
        assert mapped_count == 100, f"Should map 100 violations, got {mapped_count}"
