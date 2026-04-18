"""
Tests for Agent._compute_idea_confidence() method.

GREEN PHASE: These tests verify the confidence computation method with mocked LLM calls.
"""

from unittest.mock import AsyncMock, Mock

import pytest
from lib.agents.base import Agent
from lib.models import Idea


class DummyAgent(Agent):
    """Minimal concrete Agent for testing _compute_idea_confidence."""

    async def generate_ideas(self, context):
        return []

    async def evaluate_idea(self, idea):
        from ..models import Evaluation

        return Evaluation.from_scores(
            idea_id=idea.id, novelty=50.0, feasibility=50.0, impact=50.0, evaluator="dummy"
        )


class TestAgentConfidenceComputation:
    """Test suite for Agent._compute_idea_confidence() method."""

    @pytest.mark.asyncio
    async def test_agent_has_compute_idea_confidence_method(self):
        """Verify Agent class has _compute_idea_confidence method."""
        agent = DummyAgent(name="TestAgent")
        idea = Idea(content="Test idea for confidence computation", persona="TestPractitioner")

        # Mock the LLM response
        mock_response = Mock()
        mock_response.content = (
            '{"confidence": 0.8, "rationale": "High specificity and clear relevance"}'
        )
        agent.llm_client.generate = AsyncMock(return_value=mock_response)

        # Call the method to verify it returns proper tuple
        confidence, rationale = await agent._compute_idea_confidence(idea)
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0
        assert isinstance(rationale, str)

    @pytest.mark.asyncio
    async def test_confidence_returns_clamped_value(self):
        """Verify confidence is always clamped between 0.0 and 1.0."""
        agent = DummyAgent(name="TestAgent")

        # Test with valid confidence
        idea = Idea(
            content="A well-specified, feasible idea with clear relevance", persona="TestExpert"
        )
        mock_response = Mock()
        mock_response.content = '{"confidence": 0.75, "rationale": "Good idea structure"}'
        agent.llm_client.generate = AsyncMock(return_value=mock_response)

        confidence, rationale = await agent._compute_idea_confidence(idea)
        assert 0.0 <= confidence <= 1.0
        assert confidence == 0.75

    @pytest.mark.asyncio
    async def test_confidence_clamps_invalid_values(self):
        """Verify confidence values are clamped to valid range."""
        agent = DummyAgent(name="TestAgent")
        idea = Idea(content="Test idea for clamping", persona="TestPractitioner")

        # Test clamping of value > 1.0
        mock_response = Mock()
        mock_response.content = '{"confidence": 1.5, "rationale": "Too high"}'
        agent.llm_client.generate = AsyncMock(return_value=mock_response)

        confidence, rationale = await agent._compute_idea_confidence(idea)
        assert confidence == 1.0  # Clamped to max

        # Test clamping of value < 0.0
        mock_response.content = '{"confidence": -0.5, "rationale": "Too low"}'
        confidence, rationale = await agent._compute_idea_confidence(idea)
        assert confidence == 0.0  # Clamped to min

    @pytest.mark.asyncio
    async def test_confidence_rationale_is_string(self):
        """Verify confidence_rationale is returned as string."""
        agent = DummyAgent(name="TestAgent")
        idea = Idea(content="Test idea for rationale", persona="TestPractitioner")

        mock_response = Mock()
        mock_response.content = '{"confidence": 0.7, "rationale": "Clear reasoning path"}'
        agent.llm_client.generate = AsyncMock(return_value=mock_response)

        confidence, rationale = await agent._compute_idea_confidence(idea)
        assert isinstance(rationale, str)
        assert rationale == "Clear reasoning path"

    @pytest.mark.asyncio
    async def test_confidence_computation_uses_idea_content(self):
        """Verify confidence computation considers idea content."""
        agent = DummyAgent(name="TestAgent")

        # Mock different responses for different ideas
        mock_response1 = Mock()
        mock_response1.content = '{"confidence": 0.5, "rationale": "Vague idea"}'
        mock_response2 = Mock()
        mock_response2.content = '{"confidence": 0.9, "rationale": "Specific idea"}'

        call_count = 0

        async def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_response1
            else:
                return mock_response2

        agent.llm_client.generate = mock_generate

        idea1 = Idea(content="Vague, unclear idea without specifics", persona="TestPractitioner")
        idea2 = Idea(
            content="Specific, well-defined idea with clear implementation path",
            persona="TestExpert",
        )
        confidence1, rationale1 = await agent._compute_idea_confidence(idea1)
        confidence2, rationale2 = await agent._compute_idea_confidence(idea2)

        # Different ideas got different confidence scores
        assert confidence1 == 0.5
        assert confidence2 == 0.9
        assert rationale1 == "Vague idea"
        assert rationale2 == "Specific idea"

    @pytest.mark.asyncio
    async def test_confidence_fallback_on_llm_error(self):
        """Verify fallback behavior when LLM call fails."""
        agent = DummyAgent(name="TestAgent")
        idea = Idea(content="Test idea for fallback", persona="TestPractitioner")

        # Mock LLM error
        agent.llm_client.generate = AsyncMock(side_effect=Exception("LLM API error"))

        confidence, rationale = await agent._compute_idea_confidence(idea)
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0
        assert confidence == 0.5  # Fallback confidence
        assert "LLM error" in rationale or "fallback" in rationale.lower()

    @pytest.mark.asyncio
    async def test_confidence_accepts_various_ideas(self):
        """Verify confidence computation works with different idea types."""
        agent = DummyAgent(name="TestAgent")

        # Mock responses for various ideas
        mock_response = Mock()
        mock_response.content = '{"confidence": 0.75, "rationale": "Valid idea"}'
        agent.llm_client.generate = AsyncMock(return_value=mock_response)

        ideas = [
            Idea(content="Very short idea with enough chars", persona="TestPractitioner"),
            Idea(content="A" * 500, persona="TestExpert"),  # Very long idea
            Idea(content="Idea with special chars: @#$%^&*()", persona="TestInnovator"),
        ]
        for idea in ideas:
            confidence, rationale = await agent._compute_idea_confidence(idea)
            assert isinstance(confidence, float)
            assert 0.0 <= confidence <= 1.0
            assert isinstance(rationale, str)

    @pytest.mark.asyncio
    async def test_confidence_rationale_not_empty(self):
        """Verify confidence_rationale is never empty (at minimum has fallback text)."""
        agent = DummyAgent(name="TestAgent")
        idea = Idea(content="Test idea for rationale check", persona="TestPractitioner")

        mock_response = Mock()
        mock_response.content = '{"confidence": 0.8, "rationale": "Well-justified confidence"}'
        agent.llm_client.generate = AsyncMock(return_value=mock_response)

        confidence, rationale = await agent._compute_idea_confidence(idea)
        assert rationale  # Should not be empty string
        assert len(rationale) > 0

    @pytest.mark.asyncio
    async def test_parse_confidence_json_parsing(self):
        """Verify JSON parsing of confidence response."""
        agent = DummyAgent(name="TestAgent")
        idea = Idea(content="Test JSON parsing", persona="TestPractitioner")

        # Test proper JSON response
        mock_response = Mock()
        mock_response.content = '{"confidence": 0.85, "rationale": "Strong evidence"}'
        agent.llm_client.generate = AsyncMock(return_value=mock_response)

        confidence, rationale = await agent._compute_idea_confidence(idea)
        assert confidence == 0.85
        assert rationale == "Strong evidence"

    @pytest.mark.asyncio
    async def test_parse_confidence_regex_fallback(self):
        """Verify regex fallback when JSON parsing fails."""
        agent = DummyAgent(name="TestAgent")
        idea = Idea(content="Test regex fallback", persona="TestPractitioner")

        # Test malformed response (no JSON)
        mock_response = Mock()
        mock_response.content = "Confidence: 0.65 because the idea is good"
        agent.llm_client.generate = AsyncMock(return_value=mock_response)

        confidence, rationale = await agent._compute_idea_confidence(idea)
        assert confidence == 0.65  # Extracted via regex

    @pytest.mark.asyncio
    async def test_parse_confidence_rationale_extraction(self):
        """Verify rationale extraction from various patterns."""
        agent = DummyAgent(name="TestAgent")
        idea = Idea(content="Test rationale patterns", persona="TestPractitioner")

        # Test rationale pattern extraction
        mock_response = Mock()
        mock_response.content = "confidence: 0.7\nrationale: This is the explanation text"
        agent.llm_client.generate = AsyncMock(return_value=mock_response)

        confidence, rationale = await agent._compute_idea_confidence(idea)
        assert confidence == 0.7
        assert "This is the explanation text" in rationale
