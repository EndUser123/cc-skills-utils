"""
Tests for Idea model confidence fields.

RED PHASE: These tests verify the new confidence and confidence_rationale fields.
Tests will FAIL until the fields are added to the Idea model.
"""

import pytest
from lib.models import Idea
from pydantic import ValidationError


class TestIdeaConfidenceFields:
    """Test suite for Idea model confidence-related fields."""

    def test_idea_has_confidence_field(self):
        """Verify Idea model has confidence field with correct type."""
        idea = Idea(content="Test idea with confidence", persona="TestPractitioner", confidence=0.8)
        assert hasattr(idea, "confidence")
        assert isinstance(idea.confidence, float)
        assert idea.confidence == 0.8

    def test_idea_has_confidence_rationale_field(self):
        """Verify Idea model has confidence_rationale field with correct type."""
        idea = Idea(
            content="Test idea with rationale",
            persona="TestPractitioner",
            confidence=0.7,
            confidence_rationale="High specificity and clear relevance",
        )
        assert hasattr(idea, "confidence_rationale")
        assert isinstance(idea.confidence_rationale, str)
        assert idea.confidence_rationale == "High specificity and clear relevance"

    def test_confidence_default_value(self):
        """Verify confidence defaults to 0.5 when not provided."""
        idea = Idea(content="Test idea without confidence text", persona="TestPractitioner")
        assert idea.confidence == 0.5

    def test_confidence_rationale_default_value(self):
        """Verify confidence_rationale defaults to empty string when not provided."""
        idea = Idea(content="Test idea without rationale text", persona="TestPractitioner")
        assert idea.confidence_rationale == ""

    def test_confidence_minimum_boundary(self):
        """Verify confidence enforces minimum value of 0.0."""
        with pytest.raises(ValidationError) as exc_info:
            Idea(
                content="Invalid confidence below minimum text",
                persona="TestPractitioner",
                confidence=-0.1,
            )
        assert "confidence" in str(exc_info.value).lower()

    def test_confidence_maximum_boundary(self):
        """Verify confidence enforces maximum value of 1.0."""
        with pytest.raises(ValidationError) as exc_info:
            Idea(
                content="Invalid confidence above maximum text",
                persona="TestPractitioner",
                confidence=1.1,
            )
        assert "confidence" in str(exc_info.value).lower()

    def test_confidence_zero_boundary_accepted(self):
        """Verify confidence=0.0 is accepted (boundary case)."""
        idea = Idea(content="Zero confidence idea text", persona="TestPractitioner", confidence=0.0)
        assert idea.confidence == 0.0

    def test_confidence_one_boundary_accepted(self):
        """Verify confidence=1.0 is accepted (boundary case)."""
        idea = Idea(
            content="Perfect confidence idea text", persona="TestPractitioner", confidence=1.0
        )
        assert idea.confidence == 1.0

    def test_confidence_type_validation_float_string(self):
        """Verify confidence rejects string values (type validation)."""
        with pytest.raises(ValidationError):
            Idea(
                content="Invalid confidence type",
                persona="TestPractitioner",
                confidence="high",  # type: ignore
            )

    def test_confidence_rationale_type_validation(self):
        """Verify confidence_rationale rejects non-string values."""
        with pytest.raises(ValidationError):
            Idea(
                content="Invalid rationale type",
                persona="TestPractitioner",
                confidence_rationale=123,  # type: ignore
            )

    def test_backward_compatibility_without_confidence_fields(self):
        """Verify old code creating Ideas without confidence fields still works."""
        idea = Idea(content="Legacy idea creation", persona="TestPractitioner", score=75.0)
        assert idea.content == "Legacy idea creation"
        assert idea.confidence == 0.5  # Should use default
        assert idea.confidence_rationale == ""  # Should use default

    def test_confidence_rationale_accepts_long_text(self):
        """Verify confidence_rationale can accept longer explanatory text."""
        long_rationale = (
            "This idea has high confidence because: "
            "1. It directly addresses the user's question about X. "
            "2. It is based on established patterns from similar problems. "
            "3. It has been validated against multiple test cases."
        )
        idea = Idea(
            content="Well-justified idea", persona="TestExpert", confidence_rationale=long_rationale
        )
        assert idea.confidence_rationale == long_rationale

    def test_full_idea_with_all_confidence_fields(self):
        """Verify Idea works correctly with all confidence fields populated."""
        idea = Idea(
            content="Complete idea with confidence",
            persona="TestInnovator",
            reasoning_path=["step1", "step2"],
            score=85.0,
            confidence=0.92,
            confidence_rationale="Novel approach with strong supporting evidence",
            next_action="Validate with user",
            estimated_minutes=30,
        )
        assert idea.content == "Complete idea with confidence"
        assert idea.confidence == 0.92
        assert idea.confidence_rationale == "Novel approach with strong supporting evidence"
        assert idea.score == 85.0
