#!/usr/bin/env python3
"""
Tests for semantic commit message generation in git sync.

These tests verify that the git sync script can generate semantic
commit messages based on changed files, rather than using generic
"wip: auto-commit before sync" messages.

Run with: pytest tests/test_sync_semantic_commits.py -v
"""

import pytest
from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock, patch


class TestSemanticCommitMessageGeneration:
    """Tests for semantic commit message generation functionality."""

    @pytest.fixture
    def sync_module(self):
        """Import the sync_utils module for testing."""
        # Add parent directory to path for imports
        parent_dir = Path(__file__).parent.parent
        sys.path.insert(0, str(parent_dir))

        # Import sync_utils module (contains generate_commit_message)
        import sync_utils
        return sync_utils

    def test_generate_commit_message_function_exists(self, sync_module):
        """
        Test that generate_commit_message function exists.

        Given: The sync module is imported
        When: We check for the generate_commit_message function
        Then: The function should exist
        """
        assert hasattr(sync_module, 'generate_commit_message'), \
            "sync module must have generate_commit_message function"

    def test_generate_commit_message_extracts_changed_files(self, sync_module):
        """
        Test that generate_commit_message can extract changed files from git status.

        Given: Git status shows changed files
        When: generate_commit_message is called with the status
        Then: It should parse and return the changed file list
        """
        # Mock the run function to return sample git status
        with patch.object(sync_module, 'run') as mock_run:
            # Simulate git diff --name-only output
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=".claude/settings.json\nsrc/main.py\n",
                stderr=""
            )

            result = sync_module.generate_commit_message()

            # The function should have called run to get changed files
            mock_run.assert_called()
            assert result is not None

    def test_generate_commit_message_produces_semantic_format(self, sync_module):
        """
        Test that generate_commit_message produces semantic commit format.

        Given: Changed files include settings and Python code
        When: generate_commit_message is called
        Then: Result should match semantic format: type(scope): subject
        """
        with patch.object(sync_module, 'run') as mock_run:
            # Simulate changed files
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=".claude/settings.json\nsrc/main.py\n",
                stderr=""
            )

            result = sync_module.generate_commit_message()

            # Check semantic format: type(scope): subject
            # Matches patterns like "feat(config): update settings"
            # or "fix(src): resolve bug in main"
            import re
            semantic_pattern = r'^[a-z]+\([^)]+\): .+$'
            assert re.match(semantic_pattern, result), \
                f"Commit message '{result}' must match semantic format 'type(scope): subject'"

    def test_generate_commit_message_not_generic_wip(self, sync_module):
        """
        Test that generate_commit_message does NOT return generic "wip: auto-commit before sync".

        Given: Any set of changed files
        When: generate_commit_message is called
        Then: Result should NOT be the generic "wip: auto-commit before sync" message
        """
        with patch.object(sync_module, 'run') as mock_run:
            # Simulate changed files
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=".claude/settings.json\n",
                stderr=""
            )

            result = sync_module.generate_commit_message()

            generic_message = "wip: auto-commit before sync"
            assert result != generic_message, \
                f"Commit message must NOT be generic '{generic_message}'"
            assert generic_message not in result.lower(), \
                f"Commit message should not contain generic wip pattern"

    def test_generate_commit_message_infers_type_from_files(self, sync_module):
        """
        Test that generate_commit_message infers commit type from file changes.

        Given: Changed files include specific extensions
        When: generate_commit_message is called
        Then: Commit type should reflect the nature of changes

        Examples:
        - .py files -> feat, fix, refactor
        - .md files -> docs
        - test files -> test
        - .json/.yaml -> config
        """
        with patch.object(sync_module, 'run') as mock_run:
            # Test with .md files (docs type)
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="README.md\nCLAUDE.md\n",
                stderr=""
            )

            result = sync_module.generate_commit_message()

            # Should infer docs type from .md files
            assert result.startswith("docs(") or "docs" in result.lower(), \
                f".md files should generate 'docs' type commit, got: {result}"

    def test_generate_commit_message_with_python_files(self, sync_module):
        """
        Test that generate_commit message generates appropriate type for Python files.

        Given: Changed files include .py files
        When: generate_commit_message is called
        Then: Commit type should be one of: feat, fix, refactor
        """
        with patch.object(sync_module, 'run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="src/main.py\ntest/test_main.py\n",
                stderr=""
            )

            result = sync_module.generate_commit_message()

            # Python files should generate meaningful commit types
            valid_types = ['feat(', 'fix(', 'refactor(', 'test(', 'chore(']
            assert any(result.startswith(t) for t in valid_types), \
                f"Python files should generate specific commit type, got: {result}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
