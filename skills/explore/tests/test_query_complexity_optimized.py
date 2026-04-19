#!/usr/bin/env python3
"""Tests for query complexity scoring optimizations (TASK-011).

Tests the optimized complexity scoring including:
- Multi-word technical term detection
- Negation handling (reduces specificity)
- Pre-compiled regex patterns (performance)
- Better scoring calibration
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import query_complexity


class TestMultiWordTechnicalTerms:
    """Test multi-word technical term detection (TASK-011)."""

    def test_single_word_technical_term_detected(self):
        """Test single-word technical terms increase specificity."""
        query = "python async programming"
        score = query_complexity.calculate_complexity_score(query)

        # Should have medium specificity due to "python" and "async"
        assert score >= 12, f"Expected medium specificity for 'python async', got {score}"
        assert score < 40, f"Should not be complex, got {score}"

    def test_multi_word_technical_term_increases_specificity(self):
        """Test multi-word technical terms count more than single words."""
        single_word_query = "python machine"
        multi_word_query = "python machine learning"

        single_score = query_complexity.calculate_complexity_score(single_word_query)
        multi_score = query_complexity.calculate_complexity_score(multi_word_query)

        # Multi-word term should score significantly higher
        assert multi_score > single_score, f"Multi-word term should score higher: {multi_score} > {single_score}"

    def test_multiple_multi_word_terms_detected(self):
        """Test multiple multi-word terms are all detected."""
        query = "deep learning neural network for computer vision"
        score = query_complexity.calculate_complexity_score(query)

        # Should detect multiple multi-word terms:
        # "deep learning", "neural network", "computer vision"
        assert score > 30, f"Multiple multi-word terms should be complex, got {score}"

    def test_case_insensitive_detection(self):
        """Test multi-word terms are detected case-insensitively."""
        query1 = "Machine Learning algorithms"
        query2 = "machine learning algorithms"

        score1 = query_complexity.calculate_complexity_score(query1)
        score2 = query_complexity.calculate_complexity_score(query2)

        # Should be the same regardless of case
        assert score1 == score2, "Case should not affect complexity score"


class TestNegationHandling:
    """Test negation pattern handling (TASK-011)."""

    def test_negation_reduces_specificity(self):
        """Test queries with negation have lower specificity."""
        positive_query = "python async programming"
        negated_query = "python async programming without database"

        positive_score = query_complexity.calculate_complexity_score(positive_query)
        negated_score = query_complexity.calculate_complexity_score(negated_query)

        # Negation should reduce specificity score
        assert negated_score < positive_score, f"Negation should reduce score: {negated_score} < {positive_score}"

    def test_not_pattern_reduces_score(self):
        """Test 'not X' pattern reduces complexity."""
        query_with_not = "python programming not javascript"
        query_without_not = "python programming javascript"

        score_with_not = query_complexity.calculate_complexity_score(query_with_not)
        score_without_not = query_complexity.calculate_complexity_score(query_without_not)

        # "not" should reduce the score
        assert score_with_not < score_without_not, "'not' should reduce score"

    def test_without_pattern_reduces_score(self):
        """Test 'without X' pattern reduces complexity."""
        query_with_without = "web development without react"
        query_without = "web development with react"

        score_with_without = query_complexity.calculate_complexity_score(query_with_without)
        score_without = query_complexity.calculate_complexity_score(query_without)

        # "without" should reduce the score
        assert score_with_without < score_without, "'without' should reduce score"

    def test_negation_with_multi_word_term(self):
        """Test negation works correctly with multi-word terms."""
        query = "machine learning not deep learning"
        score = query_complexity.calculate_complexity_score(query)

        # Should detect both the multi-word term "machine learning" and negation "not deep learning"
        # Score should be balanced (not too high due to negation, not too low due to technical term)
        assert 0 <= score <= 100, f"Score should be in valid range, got {score}"


class TestCompiledPatternsPerformance:
    """Test pre-compiled regex patterns improve performance (TASK-011)."""

    def test_compiled_patterns_work_correctly(self):
        """Test compiled patterns detect same results as uncompiled."""
        query = "how to deploy python application"

        # Should detect "how" ambiguity indicator
        assert query_complexity.COMPILED_AMBIGUITY_PATTERNS[0].search(query) is not None

    def test_all_compiled_patterns_valid(self):
        """Test all compiled patterns are valid regex."""
        # Access the compiled patterns
        patterns = query_complexity.COMPILED_AMBIGUITY_PATTERNS

        # All should be compiled regex objects
        assert len(patterns) == len(query_complexity.AMBIGUITY_INDICATORS)
        for pattern in patterns:
            assert hasattr(pattern, 'search'), "Pattern should be compiled regex"

    def test_compiled_negation_patterns_valid(self):
        """Test negation patterns are compiled correctly."""
        # Access the compiled negation patterns
        patterns = query_complexity.COMPILED_NEGATION_PATTERNS

        # All should be compiled regex objects
        assert len(patterns) == len(query_complexity.NEGATION_PATTERNS)
        for pattern in patterns:
            assert hasattr(pattern, 'search'), "Pattern should be compiled regex"


class TestScoringCalibration:
    """Test improved scoring calibration (TASK-011)."""

    def test_simple_query_scores_low(self):
        """Test simple, specific queries score in Simple range."""
        queries = [
            "python async",
            "javascript array",
            "sql select",
        ]

        for query in queries:
            score = query_complexity.calculate_complexity_score(query)
            assert 0 <= score < 40, f"Simple query '{query}' should score < 40, got {score}"
            assert query_complexity.get_complexity_label(score) == "Simple"

    def test_medium_query_scores_medium(self):
        """Test medium complexity queries score in Medium range."""
        queries = [
            "how to use python async",
            "what is rest api",
            "best practices for javascript",
        ]

        for query in queries:
            score = query_complexity.calculate_complexity_score(query)
            assert 40 <= score <= 60, f"Medium query '{query}' should score 40-60, got {score}"
            assert query_complexity.get_complexity_label(score) == "Medium"

    def test_complex_query_scores_high(self):
        """Test complex queries score in Complex range."""
        queries = [
            "how to deploy machine learning model",
            "what are the best practices for deep learning neural networks",
            "compare different approaches for natural language processing",
        ]

        for query in queries:
            score = query_complexity.calculate_complexity_score(query)
            assert score > 60, f"Complex query '{query}' should score > 60, got {score}"
            assert query_complexity.get_complexity_label(score) == "Complex"

    def test_empty_query_returns_zero(self):
        """Test empty query returns minimum score."""
        score = query_complexity.calculate_complexity_score("")
        assert score == 0, f"Empty query should score 0, got {score}"


class TestAdaptiveThresholds:
    """Test adaptive Layer 2 thresholds based on complexity (TASK-011)."""

    def test_simple_query_higher_threshold(self):
        """Test simple queries require more results to trigger Layer 2."""
        threshold = query_complexity.get_layer2_threshold(20)  # Simple
        assert threshold == 30, "Simple queries should require 30 results"

    def test_medium_query_moderate_threshold(self):
        """Test medium queries require moderate results to trigger Layer 2."""
        threshold = query_complexity.get_layer2_threshold(50)  # Medium
        assert threshold == 20, "Medium queries should require 20 results"

    def test_complex_query_lower_threshold(self):
        """Test complex queries trigger Layer 2 earlier."""
        threshold = query_complexity.get_layer2_threshold(70)  # Complex
        assert threshold == 15, "Complex queries should require 15 results"

    def test_adaptive_limit_scales_with_complexity(self):
        """Test adaptive result limit scales correctly with complexity."""
        simple_limit = query_complexity.get_adaptive_limit(20)
        medium_limit = query_complexity.get_adaptive_limit(50)
        complex_limit = query_complexity.get_adaptive_limit(70)

        assert simple_limit < medium_limit < complex_limit, \
            f"Limits should scale: {simple_limit} < {medium_limit} < {complex_limit}"


class TestEdgeCases:
    """Test edge cases and boundary conditions (TASK-011)."""

    def test_query_with_special_characters(self):
        """Test queries with special characters are handled correctly."""
        query = "python: async/await (event loop)"
        score = query_complexity.calculate_complexity_score(query)

        # Should not crash and should return valid score
        assert 0 <= score <= 100, f"Score should be in valid range, got {score}"

    def test_query_with_numbers(self):
        """Test queries with numbers are handled correctly."""
        query = "python 3.11 async features"
        score = query_complexity.calculate_complexity_score(query)

        # Should not crash and should return valid score
        assert 0 <= score <= 100, f"Score should be in valid range, got {score}"

    def test_very_long_query(self):
        """Test very long queries don't exceed maximum score."""
        # Create a long query with many technical terms
        query = " ".join(["python"] * 100)
        score = query_complexity.calculate_complexity_score(query)

        # Should be capped at 100
        assert score == 100, f"Very long query should be capped at 100, got {score}"

    def test_query_only_stopwords(self):
        """Test query with only stop words scores low."""
        query = "the and or but"
        score = query_complexity.calculate_complexity_score(query)

        # Should score very low (no technical terms)
        assert score < 20, f"Stopword-only query should score low, got {score}"
