"""
Base Agent Class for Brainstorm System

This module defines the abstract base class that all brainstorming agents must implement.
The Agent interface provides a contract for generating ideas and evaluating them.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

# Setup sys.path for external LLM dependencies
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent.parent / "__csf" / "src"))
from llm.providers import LLMConfig, ProviderConfig, ProviderFactory
from llm.providers.base import ProviderResponse

from ..models import BrainstormContext, Evaluation, Idea

# Module-level round-robin state for provider rotation
_provider_rotation_index = 0
_provider_rotation_lock = asyncio.Lock()

# P0-6: Exponential backoff configuration for rate limiting
_MAX_RETRIES = 3
_INITIAL_BACKOFF = 1.0  # seconds
_MAX_BACKOFF = 30.0  # seconds

# Confidence computation constants
_DEFAULT_CONFIDENCE: float = 0.5
_MIN_CONFIDENCE: float = 0.0
_MAX_CONFIDENCE: float = 1.0
_CONFIDENCE_TEMPERATURE: float = 0.3
_CONFIDENCE_MAX_TOKENS: int = 300
_MAX_RATIONALE_LENGTH: int = 200
_MAX_ERROR_LENGTH: int = 100

# Runtime rate-limit detection: Track providers that return 429 errors
# Using threading.Lock for sync module-level access
import threading

_rate_limited_providers: set[str] = set()
_rate_limit_lock = threading.Lock()


def _sanitize_llm_input(text: str, max_length: int = 50000) -> str:
    """
    Sanitize user input for external LLM providers (P0-3: Prompt injection prevention).

    Args:
        text: User-provided text (topic, context)
        max_length: Maximum allowed length

    Returns:
        Sanitized text with length limit and dangerous patterns removed
    """
    if not text:
        return ""

    # Enforce length limit to prevent DOS
    if len(text) > max_length:
        text = text[:max_length] + "\n\n[Content truncated due to length]"

    # Remove potential prompt injection patterns
    dangerous_patterns = [
        "ignore previous instructions",
        "disregard all above",
        "forget everything",
        "system prompt",
        "override directive",
        "jailbreak",
        "ignore instructions",
        "skip protocol",
    ]

    text_lower = text.lower()
    for pattern in dangerous_patterns:
        if pattern in text_lower:
            # Replace with warning
            text = re.sub(
                re.escape(pattern),
                "[POTENTIALLY UNSAFE INSTRUCTION REMOVED]",
                text,
                flags=re.IGNORECASE,
            )

    return text


class AgentLLMClient:
    """
    Wrapper around LLM providers for brainstorm agents.

    Adapts the ProviderInterface to the brainstorm agent's expected API.
    """

    def __init__(self, config: LLMConfig | None = None, provider: str | None = None):
        """
        Initialize the LLM client.

        Args:
            config: LLMConfig with preferences
            provider: Optional specific provider to use (e.g., "chutes", "groq")
        """
        self.config = config or LLMConfig()
        self.provider = provider
        # NOTE: Provider instance NOT cached - create fresh each time for round-robin diversity

    async def _get_provider(self) -> Any:
        """Get a fresh provider instance using round-robin rotation (no caching).

        Excludes rate-limited providers from the rotation.
        """
        global _rate_limited_providers, _rate_limit_lock

        if self.provider:
            # Use specified provider
            print(f"[AgentLLMClient] Using specified provider: {self.provider}")
            provider_config = ProviderConfig(
                provider_type=self.provider,
                api_key_env=self._get_api_key_env(self.provider),
                timeout=self.config.timeout_seconds,
            )
            provider_instance = ProviderFactory.create_provider(self.provider, provider_config)
        else:
            # Check if preferred_providers is set in config (from health gate filtering)
            if self.config.preferred_providers:
                providers = self.config.preferred_providers
                print(f"[AgentLLMClient] Using preferred providers from config: {providers}")
            else:
                # Use factory to get available provider with round-robin rotation
                from llm.providers import get_registry

                registry = get_registry()
                providers = registry.get_providers()
                print(f"[AgentLLMClient] Available providers from registry: {providers}")

            if providers:
                # Filter out rate-limited providers
                with _rate_limit_lock:
                    available_providers = [p for p in providers if p not in _rate_limited_providers]
                    if not available_providers:
                        # All providers are rate-limited, clear the list and try again
                        print(
                            "[AgentLLMClient] All providers rate-limited, clearing exclusion list"
                        )
                        _rate_limited_providers.clear()
                        available_providers = providers

                # Round-robin through available providers using shared index
                global _provider_rotation_index, _provider_rotation_lock
                async with _provider_rotation_lock:
                    provider_name = available_providers[
                        _provider_rotation_index % len(available_providers)
                    ]
                    _provider_rotation_index += 1
                print(
                    f"[AgentLLMClient] Round-robin selected provider: {provider_name} (index {_provider_rotation_index - 1})"
                )
                provider_config = ProviderConfig(
                    provider_type=provider_name,
                    api_key_env=self._get_api_key_env(provider_name),
                    timeout=self.config.timeout_seconds,
                )
                provider_instance = ProviderFactory.create_provider(provider_name, provider_config)
                print(
                    f"[AgentLLMClient] Created provider instance: {provider_instance.__class__.__name__}"
                )

            else:
                # Fallback to groq (has API key)
                print("[AgentLLMClient] No providers detected, falling back to groq")
                provider_config = ProviderConfig(
                    provider_type="groq",
                    api_key_env="GROQ_API_KEY",  # pragma: allowlist secret
                    timeout=self.config.timeout_seconds if self.config.timeout_seconds else 300,
                )
                provider_instance = ProviderFactory.create_provider("groq", provider_config)
        return provider_instance

    def _mark_rate_limited(self, provider_name: str) -> None:
        """Mark a provider as rate-limited after consecutive 429 errors."""
        global _rate_limited_providers, _rate_limit_lock
        with _rate_limit_lock:
            _rate_limited_providers.add(provider_name)
        print(
            f"[AgentLLMClient] Provider {provider_name} marked as rate-limited",
            file=sys.stderr,
            flush=True,
        )

    def _clear_rate_limit(self, provider_name: str) -> None:
        """Clear rate limit flag for a provider (call after successful response)."""
        global _rate_limited_providers, _rate_limit_lock
        with _rate_limit_lock:
            _rate_limited_providers.discard(provider_name)
        print(
            f"[AgentLLMClient] Provider {provider_name} cleared from rate-limited list",
            file=sys.stderr,
            flush=True,
        )
        print(f"[AgentLLMClient] Provider {provider_name} cleared from rate-limited list")

    @classmethod
    def mark_rate_limited(cls, provider_name: str) -> None:
        """Mark a provider as rate-limited to exclude from round-robin.

        Args:
            provider_name: Name of the provider that returned 429 rate limit error
        """
        global _rate_limited_providers, _rate_limit_lock
        _rate_limited_providers.add(provider_name)
        print(f"[AgentLLMClient] Marked provider as rate-limited: {provider_name}")

    def _get_api_key_env(self, provider: str) -> str:
        """Get the API key environment variable name for a provider."""
        env_map = {
            "chutes": "CHUTES_API_KEY",  # Chutes provider uses CHUTES_API_KEY
            "groq": "GROQ_API_KEY",
            "mistral": "MISTRAL_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
        }
        return env_map.get(provider.lower(), f"{provider.upper()}_API_KEY")

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        **kwargs,
    ) -> ProviderResponse:
        """
        Generate a response from the LLM with empty response validation.

        P0-3 FIX: Sanitizes input prompts to prevent prompt injection attacks.
        P0-6 FIX: Implements exponential backoff for rate limiting.
        """
        # P0-3: Sanitize input prompts to prevent prompt injection
        prompt = _sanitize_llm_input(prompt, max_length=50000)
        if system_prompt:
            system_prompt = _sanitize_llm_input(system_prompt, max_length=10000)

        provider = await self._get_provider()
        provider_name = provider.__class__.__name__

        # P0-6: Exponential backoff retry logic for rate limiting
        for attempt in range(_MAX_RETRIES):
            try:
                response = await provider.generate_response(
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system_prompt=system_prompt,
                    **kwargs,
                )

                # Validate response is not empty (fast-fail to avoid timeout)
                if not response:
                    if attempt < _MAX_RETRIES - 1:
                        # Retry with backoff
                        backoff = min(_INITIAL_BACKOFF * (2**attempt), _MAX_BACKOFF)
                        print(
                            f"[AgentLLMClient] Empty response from {provider_name}, "
                            f"retrying in {backoff:.1f}s... (attempt {attempt + 1}/{_MAX_RETRIES})",
                            file=sys.stderr,
                            flush=True,
                        )
                        await asyncio.sleep(backoff)
                        continue
                    raise ValueError(
                        f"Empty response from provider {provider_name}: "
                        f"Response object is None. Provider may be down or API key invalid."
                    )

                if not response.content or not response.content.strip():
                    if attempt < _MAX_RETRIES - 1:
                        # Retry with backoff
                        backoff = min(_INITIAL_BACKOFF * (2**attempt), _MAX_BACKOFF)
                        print(
                            f"[AgentLLMClient] Empty content from {provider_name}, "
                            f"retrying in {backoff:.1f}s... (attempt {attempt + 1}/{_MAX_RETRIES})",
                            file=sys.stderr,
                            flush=True,
                        )
                        await asyncio.sleep(backoff)
                        continue
                    raise ValueError(
                        f"Empty response content from provider {provider_name}: "
                        f"Response.content is empty or whitespace. Provider may be rate-limited or API error."
                    )

                return response

            except Exception as e:
                # Check if this is a rate limit error or transient error
                error_msg = str(e).lower()
                is_transient = any(
                    term in error_msg
                    for term in ["rate limit", "429", "timeout", "connection", "temporary"]
                )

                if is_transient and attempt < _MAX_RETRIES - 1:
                    backoff = min(_INITIAL_BACKOFF * (2**attempt), _MAX_BACKOFF)
                    print(
                        f"[AgentLLMClient] Transient error from {provider_name}: {e}, "
                        f"retrying in {backoff:.1f}s... (attempt {attempt + 1}/{_MAX_RETRIES})",
                        file=sys.stderr,
                        flush=True,
                    )
                    await asyncio.sleep(backoff)
                    continue

                # Re-raise if not transient or out of retries
                raise

        # This should never be reached - all retry paths should either return or raise
        raise RuntimeError(
            f"Unexpected state: exhausted {_MAX_RETRIES} retries without response or error from {provider_name}"
        )


class Agent(ABC):
    """
    Abstract base class for all brainstorming agents.

    Each agent represents a specific persona or thinking style that approaches
    idea generation and evaluation from a unique perspective.
    """

    def __init__(
        self,
        name: str | None = None,
        description: str | None = None,
        llm_config: LLMConfig | None = None,
    ):
        """Initialize the agent with LLM client."""
        self.name = name or self.__class__.__name__
        self.description = description or f"Agent implementing {self.name} persona"
        # DEBUG: Log what config is being passed
        import sys

        print(
            f"[DEBUG Agent.__init__] name={self.name}, llm_config={llm_config}, "
            f"preferred_providers={llm_config.preferred_providers if llm_config else None}",
            file=sys.stderr,
            flush=True,
        )
        self.llm_client = AgentLLMClient(llm_config)
        self.system_prompt = self._get_default_system_prompt()

    def _get_default_system_prompt(self) -> str:
        """Get the default system prompt for this agent."""
        return f"You are {self.name}, an AI assistant helping with brainstorming."

    def _get_fresh_mode_warning(self, context: BrainstormContext) -> str:
        """
        Get fresh_mode warning if enabled.

        When fresh_mode is True, agents must NOT read existing plans or solutions
        to prevent anchoring bias.

        Args:
            context: The brainstorming context

        Returns:
            Warning string to inject into prompts, or empty string if fresh_mode is disabled
        """
        if not context.fresh_mode:
            return ""

        return (
            "\n\nCRITICAL CONSTRAINT - FRESH MODE: "
            "You MUST generate ideas from first principles WITHOUT reading any existing "
            "plans, solutions, or implementation documents. "
            "Do NOT look at what has already been decided or implemented. "
            "Think independently and explore ALL options, including those that might "
            "contradict existing approaches. Your goal is to generate fresh, unbiased ideas."
        )

    @abstractmethod
    async def generate_ideas(self, context: BrainstormContext) -> list[Idea]:
        """Generate ideas based on the provided context."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement generate_ideas()")

    @abstractmethod
    async def evaluate_idea(self, idea: Idea) -> Evaluation:
        """Evaluate a single idea from the agent's perspective."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement evaluate_idea()")

    async def generate_and_evaluate(
        self, context: BrainstormContext
    ) -> list[tuple[Idea, Evaluation]]:
        """Generate ideas and evaluate them in a single call."""
        ideas = await self.generate_ideas(context)
        results = []
        for idea in ideas:
            evaluation = await self.evaluate_idea(idea)
            results.append((idea, evaluation))
        return results

    def _parse_evaluation_from_llm_response(self, response: str, idea_id: str) -> Evaluation:
        """Parse evaluation scores and arguments from LLM response.

        The LLM should respond with JSON containing:
        - novelty: score 0-100
        - feasibility: score 0-100
        - impact: score 0-100
        - arguments_pro: list of strings
        - arguments_con: list of strings

        If JSON parsing fails, falls back to regex extraction.
        """
        # Try JSON first
        try:
            # Look for JSON block in response
            json_match = re.search(r'\{[^}]*"novelty"[^}]*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                return Evaluation.from_scores(
                    idea_id=idea_id,
                    novelty=float(data.get("novelty", 50)),
                    feasibility=float(data.get("feasibility", 50)),
                    impact=float(data.get("impact", 50)),
                    arguments_pro=data.get("arguments_pro", []),
                    arguments_con=data.get("arguments_con", []),
                    evaluator=self.name,
                )
        except (json.JSONDecodeError, ValueError, KeyError):
            pass

        # Fallback: regex extraction
        novelty = self._extract_score(response, r"novelty[:\s]+(\d+)")
        feasibility = self._extract_score(response, r"feasibility[:\s]+(\d+)")
        impact = self._extract_score(response, r"impact[:\s]+(\d+)")

        # Extract pro/con arguments
        pros = self._extract_arguments(
            response, r"pro[:\s]*(.+?)(?=con:|$)", ["Practical aspects identified"]
        )
        cons = self._extract_arguments(
            response, r"con[:\s]*(.+?)(?=pro:|$)", ["Potential concerns noted"]
        )

        return Evaluation.from_scores(
            idea_id=idea_id,
            novelty=novelty,
            feasibility=feasibility,
            impact=impact,
            arguments_pro=pros,
            arguments_con=cons,
            evaluator=self.name,
        )

    def _extract_score(self, text: str, pattern: str) -> float:
        """Extract a score from text using regex pattern."""
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                score = float(match.group(1))
                return max(0, min(100, score))  # Clamp to 0-100
            except (ValueError, IndexError):
                pass
        return 50.0  # Default fallback

    def _extract_arguments(self, text: str, pattern: str, defaults: list[str]) -> list[str]:
        """Extract argument list from text using regex pattern."""
        matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
        if matches:
            # Clean up matches and return up to 3
            cleaned = [m.strip()[:100] for m in matches if m.strip()]
            return cleaned[:3]
        return defaults

    async def _evaluate_with_llm(self, idea: Idea, evaluation_prompt: str) -> Evaluation:
        """Common evaluation logic using LLM."""
        try:
            response = await self.llm_client.generate(
                prompt=evaluation_prompt,
                system_prompt=self.system_prompt,
                temperature=0.3,  # Lower temperature for consistent evaluation
                max_tokens=600,
                persona=self.name,
            )
            return self._parse_evaluation_from_llm_response(response.content, idea.id)
        except Exception as e:
            # Fallback to default evaluation on error
            return Evaluation.from_scores(
                idea_id=idea.id,
                novelty=50.0,
                feasibility=50.0,
                impact=50.0,
                arguments_pro=[f"Evaluation attempted: {self.name}"],
                arguments_con=[f"Evaluation error: {str(e)[:50]}"],
                evaluator=f"{self.name}_fallback",
            )

    async def _compute_idea_confidence(self, idea: Idea) -> tuple[float, str]:
        """
        Compute agent's confidence in an idea for turn-based coordination.

        Confidence is computed based on four dimensions:
        - Specificity: How well-defined and concrete the idea is
        - Consistency: How internally coherent the reasoning is
        - Relevance: How directly the idea addresses the topic
        - Uniqueness: How novel or differentiated the idea is

        Args:
            idea: The idea to evaluate confidence for

        Returns:
            Tuple of (confidence: float, rationale: str)
            - confidence: Value between 0.0 and 1.0
            - rationale: Human-readable explanation for the confidence score
        """
        # Prompt for confidence evaluation
        confidence_prompt = f"""Evaluate your confidence in this idea on a scale of 0.0 to 1.0.

IDEA:
Content: {idea.content}
Persona: {idea.persona}
Reasoning Path: {idea.reasoning_path if idea.reasoning_path else "Not provided"}

Rate your confidence based on:
1. SPECIFICITY: Is the idea concrete and actionable, or vague and abstract?
2. CONSISTENCE: Is the reasoning internally coherent and logical?
3. RELEVANCE: How directly does this address the core problem/topic?
4. UNIQUENESS: Does this offer a distinct perspective or is it redundant?

Respond in JSON format:
{{
  "confidence": <float between 0.0 and 1.0>,
  "rationale": "<brief explanation of the score based on the 4 dimensions>"
}}
"""

        try:
            response = await self.llm_client.generate(
                prompt=confidence_prompt,
                system_prompt=self.system_prompt,
                temperature=_CONFIDENCE_TEMPERATURE,
                max_tokens=_CONFIDENCE_MAX_TOKENS,
            )

            # Parse confidence from LLM response
            confidence, rationale = self._parse_confidence_from_response(response.content, idea.id)

            # Clamp confidence to valid range
            confidence = max(_MIN_CONFIDENCE, min(_MAX_CONFIDENCE, confidence))

            return confidence, rationale

        except Exception as e:
            # Fallback on error
            fallback_rationale = (
                f"LLM error during confidence computation: {str(e)[:_MAX_ERROR_LENGTH]}. "
                f"Using fallback confidence of {_DEFAULT_CONFIDENCE}."
            )
            return _DEFAULT_CONFIDENCE, fallback_rationale

    def _parse_confidence_from_response(self, response: str, idea_id: str) -> tuple[float, str]:
        """
        Parse confidence score and rationale from LLM response.

        Args:
            response: LLM response text
            idea_id: Idea ID for logging (unused in parsing but kept for interface)

        Returns:
            Tuple of (confidence: float, rationale: str)
        """
        # Try JSON first
        try:
            json_match = re.search(r'\{[^}]*"confidence"[^}]*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                confidence = float(data.get("confidence", _DEFAULT_CONFIDENCE))
                rationale = data.get("rationale", "No rationale provided")
                return confidence, rationale
        except (json.JSONDecodeError, ValueError, KeyError):
            pass

        # Fallback: regex extraction for confidence
        confidence_match = re.search(r"confidence[:\s]+([0-9]*\.?[0-9]+)", response, re.IGNORECASE)
        if confidence_match:
            try:
                confidence = float(confidence_match.group(1))
            except ValueError:
                confidence = _DEFAULT_CONFIDENCE
        else:
            confidence = _DEFAULT_CONFIDENCE

        # Extract rationale from common patterns
        rationale_patterns = [
            r"rationale[:\s]+(.+?)(?=\n\n|confidence:|$)",
            r"because[:\s]+(.+?)(?=\n\n|confidence:|$)",
            r"explanation[:\s]+(.+?)(?=\n\n|confidence:|$)",
        ]

        rationale = "Confidence computed from LLM analysis"
        for pattern in rationale_patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                rationale = match.group(1).strip()[:_MAX_RATIONALE_LENGTH]
                break

        return confidence, rationale

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"

    def __str__(self) -> str:
        return f"{self.name}: {self.description}"


__all__ = ["Agent"]
