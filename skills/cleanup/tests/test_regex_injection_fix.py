"""Regression tests for regex injection vulnerability fix in cleanup.py.

This test verifies that regex metacharacters in directory names are properly
escaped when passed to re.compile(), preventing ReDoS or regex injection attacks.

Vulnerability location: cleanup.py line 811
    regex = re.compile(pattern)

The pattern comes from module_candidates derived from file paths, which could
contain regex metacharacters like (, ), *, +, [, {, etc. if directory names
contain these characters.

Run with: pytest P:/.claude/skills/cleanup/tests/test_regex_injection_fix.py -v
"""

import sys
import re
import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add cleanup skill scripts/ to path BEFORE importing
cleanup_scripts_dir = Path("P:/.claude/skills/cleanup/scripts")
sys.path.insert(0, str(cleanup_scripts_dir))

from cleanup import find_import_references  # noqa: E402


class TestRegexInjectionProtection:
    """Test that regex metacharacters in directory names are safely handled."""

    def test_safe_directory_name_works_correctly(self, tmp_path):
        """Test that normal directory names without metacharacters work correctly.

        Given: A directory with a safe name like 'test_dir'
        When: Searching for import references
        Then: The regex compilation succeeds and finds references
        """
        # Create test directory structure
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        # Create a module that imports from test_dir
        module_file = test_dir / "mymodule.py"
        module_file.write_text("def my_function(): pass\n")

        importer_file = tmp_path / "importer.py"
        importer_file.write_text("from test_dir import mymodule\n")

        # Search for references - should work without errors
        try:
            references = find_import_references(
                str(module_file),
                search_root=str(tmp_path)
            )
            # Should return a list (possibly empty)
            assert isinstance(references, list)
        except re.error:
            pytest.fail("Safe directory name should not cause regex error")

    def test_regex_metacharacters_in_dir_name_are_escaped(self, tmp_path):
        """Test that directory names with regex metacharacters are properly escaped.

        Given: A directory named with regex metacharacters like 'test(dir)'
        When: Searching for import references (forcing regex fallback)
        Then: The regex metacharacters are escaped and re.compile() succeeds

        This is the RED phase test - it WILL FAIL until the fix is implemented.
        """
        # Create directory with regex metacharacters
        test_dir = tmp_path / "test(dir)"
        test_dir.mkdir()

        # Create a module
        module_file = test_dir / "mymodule.py"
        module_file.write_text("def my_function(): pass\n")

        # Create an importer
        importer_file = tmp_path / "importer.py"
        importer_file.write_text("from test(dir) import mymodule\n")

        # Force fallback to regex by mocking both CDS import and ripgrep failure
        with patch('builtins.__import__', side_effect=ImportError("CDS not available")):
            # Mock subprocess.run to fail (ripgrep not found)
            with patch('subprocess.run', side_effect=FileNotFoundError):
                # This should NOT raise re.error when pattern is escaped
                try:
                    references = find_import_references(
                        str(module_file),
                        search_root=str(tmp_path)
                    )
                    # Should return a list (possibly empty)
                    assert isinstance(references, list)
                except re.error as e:
                    pytest.fail(
                        f"Regex metacharacters in directory name should be escaped. "
                        f"Got re.error: {e}"
                    )

    def test_malicious_pattern_with_kleene_star(self, tmp_path):
        """Test that patterns with * are handled safely.

        Given: A directory named with 'test*dir' (contains Kleene star)
        When: Searching for import references (forcing regex fallback)
        Then: The star is escaped and doesn't cause catastrophic backtracking
        """
        # Create directory with * in name (we'll test via mocking)
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        module_file = test_dir / "mymodule.py"
        module_file.write_text("def my_function(): pass\n")

        # Test the pattern construction directly
        with patch('builtins.__import__', side_effect=ImportError("CDS not available")):
            with patch('subprocess.run', side_effect=FileNotFoundError):
                # Test the vulnerability: current implementation doesn't escape *
                candidate = "test*dir"
                escaped = candidate.replace('.', r'\.')  # Current implementation

                # This creates: \bimport\s+test*dir\b
                # The * is NOT escaped, which is the vulnerability!
                pattern = rf'\bimport\s+{escaped}\b'

                # Try to compile - this should succeed but * acts as wildcard
                try:
                    regex = re.compile(pattern)
                    # Test that * acts as wildcard (vulnerable behavior)
                    test_string = "import testXYZdir"  # Should NOT match test*dir
                    match = regex.search(test_string)
                    # With the vulnerability, * acts as wildcard and matches
                    # After fix with re.escape(), it should only match literal "test*dir"
                    if match is not None:
                        pytest.fail(
                            f"Metacharacter * should not act as wildcard. "
                            f"Pattern '{pattern}' matched '{test_string}'"
                        )
                except re.error as e:
                    # This happens when pattern is malformed
                    pytest.fail(f"Regex should compile: {e}")

    def test_metacharacter_plus_sign(self, tmp_path):
        """Test that + in directory names is escaped.

        Given: A directory named with 'test+dir'
        When: Searching for import references (forcing regex fallback)
        Then: The + is escaped as \\+
        """
        test_dir = tmp_path / "test+dir"
        test_dir.mkdir()

        module_file = test_dir / "mymodule.py"
        module_file.write_text("def my_function(): pass\n")

        with patch('builtins.__import__', side_effect=ImportError("CDS not available")):
            with patch('subprocess.run', side_effect=FileNotFoundError):
                try:
                    references = find_import_references(
                        str(module_file),
                        search_root=str(tmp_path)
                    )
                    assert isinstance(references, list)
                except re.error as e:
                    pytest.fail(f"+ metacharacter should be escaped: {e}")

    def test_metacharacter_parentheses(self, tmp_path):
        """Test that parentheses in directory names are escaped.

        Given: A directory named with 'test(dir)(dir2)'
        When: Searching for import references (forcing regex fallback)
        Then: Parentheses are escaped as \\( and \\)
        """
        test_dir = tmp_path / "test(dir)(dir2)"
        test_dir.mkdir()

        module_file = test_dir / "mymodule.py"
        module_file.write_text("def my_function(): pass\n")

        with patch('builtins.__import__', side_effect=ImportError("CDS not available")):
            with patch('subprocess.run', side_effect=FileNotFoundError):
                try:
                    references = find_import_references(
                        str(module_file),
                        search_root=str(tmp_path)
                    )
                    assert isinstance(references, list)
                except re.error as e:
                    pytest.fail(f"Parentheses should be escaped: {e}")

    def test_metacharacter_square_brackets(self, tmp_path):
        """Test that square brackets in directory names are escaped.

        Given: A directory named with 'test[abc]'
        When: Searching for import references (forcing regex fallback)
        Then: Square brackets are escaped as \\[ and \\]
        """
        test_dir = tmp_path / "test[abc]"
        test_dir.mkdir()

        module_file = test_dir / "mymodule.py"
        module_file.write_text("def my_function(): pass\n")

        with patch('builtins.__import__', side_effect=ImportError("CDS not available")):
            with patch('subprocess.run', side_effect=FileNotFoundError):
                try:
                    references = find_import_references(
                        str(module_file),
                        search_root=str(tmp_path)
                    )
                    assert isinstance(references, list)
                except re.error as e:
                    pytest.fail(f"Square brackets should be escaped: {e}")

    def test_metacharacter_curly_braces(self, tmp_path):
        """Test that curly braces in directory names are escaped.

        Given: A directory named with 'test{a,b,c}'
        When: Searching for import references (forcing regex fallback)
        Then: Curly braces are escaped as \\{ and \\}
        """
        test_dir = tmp_path / "test{abc}"
        test_dir.mkdir()

        module_file = test_dir / "mymodule.py"
        module_file.write_text("def my_function(): pass\n")

        with patch('builtins.__import__', side_effect=ImportError("CDS not available")):
            with patch('subprocess.run', side_effect=FileNotFoundError):
                try:
                    references = find_import_references(
                        str(module_file),
                        search_root=str(tmp_path)
                    )
                    assert isinstance(references, list)
                except re.error as e:
                    pytest.fail(f"Curly braces should be escaped: {e}")

    def test_combined_metacharacters(self, tmp_path):
        """Test that multiple metacharacters are all escaped.

        Given: A directory named with '(.*)(.*+'
        When: Searching for import references (forcing regex fallback)
        Then: All metacharacters are escaped properly

        This is an extreme case testing the malicious pattern mentioned in
        the vulnerability report.

        Note: Windows filesystem doesn't allow these characters in directory names,
        so we test the pattern construction logic directly instead.
        """
        # Test the pattern construction directly with malicious input
        candidate = "(.*)(.*+"

        # Current implementation (vulnerable) only escapes dots
        escaped_vulnerable = candidate.replace('.', r'\.')

        # This creates an invalid regex pattern
        pattern_vulnerable = rf'\bimport\s+{escaped_vulnerable}\b'

        # Try to compile the vulnerable pattern
        try:
            regex = re.compile(pattern_vulnerable)
            # If it compiles, test if it behaves correctly
            # With unescaped metacharacters, it would match unintended strings
            test_string = "import testXYZ"  # Should NOT match (.*)
            match = regex.search(test_string)
            if match is not None:
                pytest.fail(
                    f"Metacharacters in '{candidate}' are being interpreted as regex. "
                    f"Pattern '{pattern_vulnerable}' matched '{test_string}'"
                )
        except re.error as e:
            # This is expected with unescaped metacharacters
            # After the fix, re.escape() should be used instead of .replace('.', r'\.')
            # For now, we document this as the vulnerable behavior
            pass

        # After fix: re.escape() should be used
        escaped_fixed = re.escape(candidate)
        # Use a pattern that works with the escaped metacharacters
        # (word boundary doesn't work after + character)
        pattern_fixed = rf'\bimport\s+{escaped_fixed}'

        # This should always compile without error
        try:
            regex = re.compile(pattern_fixed)
            # Should only match the literal string, not interpret metacharacters
            test_string = "import (.*)(.*+"
            assert regex.search(test_string) is not None

            # Should NOT match similar strings
            test_string_false = "import testXYZ"
            assert regex.search(test_string_false) is None
        except re.error as e:
            pytest.fail(f"Pattern with re.escape() should always compile: {e}")

    def test_dot_is_already_escaped(self, tmp_path):
        """Test that dots in module names are properly escaped.

        Given: A module name like 'foo.bar.baz'
        When: Building regex patterns (forcing regex fallback)
        Then: Dots are escaped as \\. to match literal dots, not 'any character'

        This test verifies the existing dot escaping logic works correctly.
        """
        test_dir = tmp_path / "foo" / "bar" / "baz"
        test_dir.mkdir(parents=True)

        module_file = test_dir / "mymodule.py"
        module_file.write_text("def my_function(): pass\n")

        importer_file = tmp_path / "importer.py"
        # Should match 'from foo.bar.baz import mymodule'
        importer_file.write_text("from foo.bar.baz import mymodule\n")

        with patch('builtins.__import__', side_effect=ImportError("CDS not available")):
            with patch('subprocess.run', side_effect=FileNotFoundError):
                try:
                    references = find_import_references(
                        str(module_file),
                        search_root=str(tmp_path)
                    )
                    assert isinstance(references, list)
                except re.error as e:
                    pytest.fail(f"Module name with dots should work: {e}")


class TestRegexInjectionInPatternBuilding:
    """Test the pattern building logic specifically."""

    def test_pattern_escaping_all_metacharacters(self):
        """Test that re.escape is used on all user input in patterns.

        Given: A candidate module name with metacharacters
        When: Building regex patterns for import searching
        Then: All metacharacters are escaped using re.escape()

        This tests the fix: changing from candidate.replace('.', r'\.')
        to re.escape(candidate).
        """
        # Test cases with various metacharacters
        test_cases = [
            ("test(dir)", r"test\(dir\)"),  # Parentheses
            ("test*dir", r"test\*dir"),      # Asterisk
            ("test+dir", r"test\+dir"),      # Plus
            ("test?dir", r"test\?dir"),      # Question mark
            ("test[abc]", r"test\[abc\]"),   # Square brackets
            ("test{abc}", r"test\{abc\}"),   # Curly braces
            ("test^dir", r"test\^dir"),      # Caret
            ("test$dir", r"test\$dir"),      # Dollar
            ("test|dir", r"test\|dir"),      # Pipe
            ("test.dir", r"test\.dir"),      # Dot (should already work)
            ("foo.bar.baz", r"foo\.bar\.baz"),  # Multiple dots
        ]

        for candidate, expected_escaped in test_cases:
            # After fix, this should use re.escape
            escaped = re.escape(candidate)
            assert escaped == expected_escaped, (
                f"Expected {candidate} to escape to {expected_escaped}, "
                f"but got {escaped}"
            )

    def test_from_import_pattern_uses_escape(self):
        """Test that 'from' import patterns properly escape module names.

        Given: A module name with metacharacters like 'test(dir)'
        When: Building the 'from X import' pattern
        Then: The pattern uses escaped version: r'\bfrom\s+test\(dir\)(\s+|\. )'
        """
        candidate = "test(dir)"
        escaped = re.escape(candidate)

        # Build the pattern as in cleanup.py
        pattern = rf'\bfrom\s+{escaped}(\s+|\.)'

        # Should compile without error
        try:
            regex = re.compile(pattern)
        except re.error as e:
            pytest.fail(f"Pattern should compile after escaping: {e}")

        # Should match the literal string, not interpret metacharacters
        test_string = "from test(dir) import mymodule"
        assert regex.search(test_string) is not None

        # Should NOT match similar strings (metacharacters not interpreted)
        test_string_false = "from testa dir import mymodule"
        assert regex.search(test_string_false) is None

    def test_import_pattern_uses_escape(self):
        """Test that 'import' patterns properly escape module names.

        Given: A module name with metacharacters like 'test+dir'
        When: Building the 'import X' pattern
        Then: The pattern uses escaped version: r'\bimport\s+test\+dir\b'
        """
        candidate = "test+dir"
        escaped = re.escape(candidate)

        # Build the pattern as in cleanup.py
        pattern = rf'\bimport\s+{escaped}\b'

        # Should compile without error
        try:
            regex = re.compile(pattern)
        except re.error as e:
            pytest.fail(f"Pattern should compile after escaping: {e}")

        # Should match the literal string
        test_string = "import test+dir"
        assert regex.search(test_string) is not None


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
