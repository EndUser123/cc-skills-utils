"""Tests for ask/lib/triage.py."""

import pytest

from ask.lib.triage import triage, TriageResult, TriagePath


class TestReversibilityScoring:
    """Tests for keyword-based reversibility scoring."""

    @pytest.mark.parametrize(
        "input_text,expected_min",
        [
            # Trivial (1.0): config, feature flags, simple edits
            ("update the config", 1.0),
            ("change the timeout", 1.0),
            ("add a log level", 1.0),
            ("enable the feature flag", 1.0),
            # Moderate (1.25-1.5): refactors, process changes
            ("extract a function", 1.25),
            ("rename the variable", 1.25),
            ("refactor the method", 1.25),
            ("add error handling", 1.25),
            # Irreversible (2.0): schema/data migrations, infrastructure
            ("delete a column", 2.0),
            ("drop the table", 2.0),
            ("remove the index", 2.0),
            ("change the schema", 2.0),
        ],
    )
    def test_reversibility_scoring(self, input_text: str, expected_min: float) -> None:
        result = triage(input_text)
        assert result.reversibility >= expected_min, f"{input_text!r} scored {result.reversibility}, expected >= {expected_min}"

    def test_delete_triggers_careful(self) -> None:
        result = triage("delete the user table")
        assert result.path == TriagePath.CAREFUL

    def test_refactor_triggers_standard(self) -> None:
        result = triage("extract this into a helper function")
        assert result.path == TriagePath.STANDARD


class TestDependencyCounting:
    """Tests for dependency counting in triage."""

    def test_no_dependencies(self) -> None:
        result = triage("update config")
        assert result.dependency_count == 0

    def test_single_dependency(self) -> None:
        result = triage("refactor the auth module")
        assert result.dependency_count >= 1

    def test_multiple_dependencies(self) -> None:
        result = triage("extract a function from the core module that is used by the API layer")
        assert result.dependency_count >= 2


class TestPathSelection:
    """Tests for path selection based on reversibility score."""

    @pytest.mark.parametrize(
        "input_text,expected_path",
        [
            # FAST: reversibility <= 1.25
            ("update the config", TriagePath.FAST),
            ("change a timeout", TriagePath.FAST),
            ("add a log level", TriagePath.FAST),
            # STANDARD: 1.25 < reversibility <= 1.75
            ("extract a function", TriagePath.STANDARD),
            ("rename a variable", TriagePath.STANDARD),
            ("add error handling", TriagePath.STANDARD),
            ("refactor this method", TriagePath.STANDARD),
            # CAREFUL: reversibility > 1.75
            ("delete the table", TriagePath.CAREFUL),
            ("drop the index", TriagePath.CAREFUL),
            ("change the schema", TriagePath.CAREFUL),
            ("remove the column", TriagePath.CAREFUL),
        ],
    )
    def test_path_selection(self, input_text: str, expected_path: TriagePath) -> None:
        result = triage(input_text)
        assert result.path == expected_path, f"{input_text!r} → {result.path}, expected {expected_path}"


class TestReasoningField:
    """Tests for the reasoning field in TriageResult."""

    def test_reasoning_is_populated(self) -> None:
        result = triage("extract a function from the auth module")
        assert len(result.reasoning) > 0

    def test_reasoning_contains_keywords(self) -> None:
        result = triage("delete the old table")
        assert any(
            keyword in result.reasoning.lower()
            for keyword in ["delete", "drop", "remove", "irrevers"]
        )


class TestEdgeCases:
    """Tests for edge cases in triage."""

    def test_empty_string(self) -> None:
        result = triage("")
        assert result.reversibility >= 1.0

    def test_whitespace_only(self) -> None:
        result = triage("   ")
        assert result.reversibility >= 1.0

    def test_unknown_intent_defaults_fast(self) -> None:
        result = triage("please do something")
        assert result.path == TriagePath.FAST

    def test_careful_path_includes_options(self) -> None:
        result = triage("delete all user records")
        assert result.path == TriagePath.CAREFUL
        assert result.reversibility >= 1.75