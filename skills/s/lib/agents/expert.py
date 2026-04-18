"""
Expert Agent - Domain Knowledge Specialist
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..models import BrainstormContext, Evaluation, Idea
from .base import Agent


class ExpertAgent(Agent):
    _api_log_file = Path(__file__).parent.parent.parent / "api_responses_log.jsonl"

    def __init__(self, llm_config=None):
        super().__init__(
            name="Expert",
            description="Domain knowledge expert with evidence-based reasoning",
            llm_config=llm_config,
        )

    def _log_api_response(
        self, response, idea_num: int, attempt: int, success: bool, error: str | None = None
    ):
        """Log detailed API response information for debugging.

        Args:
            response: ProviderResponse object
            idea_num: Which idea number this is (1-indexed)
            attempt: Which attempt number (1-indexed)
            success: Whether the idea was successfully generated
            error: Error message if any
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": self.name,
            "idea_number": idea_num,
            "attempt": attempt,
            "success": success,
            "response": {
                "content": response.content if response.content else "",
                "content_length": len(response.content) if response.content else 0,
                "model_used": response.model_used,
                "success": response.success,
                "response_time": response.response_time,
                "token_usage": {
                    "input": response.token_usage.input_tokens,
                    "output": response.token_usage.output_tokens,
                    "total": response.token_usage.total_tokens,
                }
                if response.token_usage
                else None,
                "error_message": response.error_message,
                "metadata": response.metadata or {},
            },
            "error": error,
        }

        # Append to log file
        try:
            with open(self._api_log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            print(f"ExpertAgent: Failed to write API log: {e}")

        # Also print summary to console
        status = "✓ SUCCESS" if success else "✗ FAILED"
        print(f"ExpertAgent API Response [{status}] Idea #{idea_num} Attempt {attempt}:")
        print(f"  Model: {response.model_used}")
        print(f"  Content length: {len(response.content) if response.content else 0} chars")
        print(f"  Response time: {response.response_time:.2f}s")
        if response.token_usage:
            print(
                f"  Tokens: {response.token_usage.input_tokens} in → {response.token_usage.output_tokens} out"
            )
        if response.error_message:
            print(f"  Error: {response.error_message}")
        if response.metadata:
            # Check for HTTP status code in metadata
            if "http_status" in response.metadata:
                print(f"  HTTP Status: {response.metadata['http_status']}")
        if not success and error:
            print(f"  Failure reason: {error}")

    def _get_default_system_prompt(self) -> str:
        return """You are a domain expert with deep knowledge in relevant fields."""

    async def generate_ideas(self, context: BrainstormContext) -> list[Idea]:
        """
        Generate ideas in PARALLEL for faster response.

        Note: Uses parallel LLM calls to avoid timeout issues with slow CLI providers.
        """
        import asyncio

        # Calculate number of ideas - respect the input parameter
        num_ideas = max(1, min(3, context.num_ideas))

        async def generate_single_idea(idx: int) -> Idea | None:
            prompt = f"As a domain expert, generate a well-researched idea for: Topic: {context.topic}. This is expert idea #{idx + 1}. Use evidence-based reasoning."
            prompt += self._get_fresh_mode_warning(context)

            # Retry logic: attempt up to 3 times to generate a valid idea
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    response = await self.llm_client.generate(
                        prompt=prompt,
                        system_prompt=self.system_prompt,
                        temperature=0.6,
                        max_tokens=800,
                        persona=self.name,
                    )

                    # Log this API response attempt
                    is_valid = bool(response.content and len(response.content.strip()) >= 10)
                    self._log_api_response(
                        response,
                        idea_num=idx + 1,
                        attempt=attempt + 1,
                        success=is_valid,
                        error=None if is_valid else "Content too short or empty",
                    )

                    # Validate response before creating Idea
                    if not is_valid:
                        if attempt < max_attempts - 1:
                            print(
                                f"ExpertAgent: Empty/short response (attempt {attempt + 1}/{max_attempts}), retrying..."
                            )
                            continue
                        else:
                            print(
                                f"ExpertAgent: Empty/short response after {max_attempts} attempts, skipping idea #{idx + 1}"
                            )
                            return None

                    return Idea(
                        content=response.content,
                        persona=self.name,
                        reasoning_path=[f"Generated via {response.model_used}"],
                        score=70.0,
                        metadata={"provider": response.model_used},
                    )

                except Exception as e:
                    last_error = str(e)
                    # Create a dummy response object for logging when exception occurs
                    from llm.providers.base import ProviderResponse, TokenUsage

                    dummy_response = ProviderResponse(
                        content="",
                        success=False,
                        token_usage=TokenUsage(),
                        response_time=0.0,
                        model_used="unknown",
                        error_message=last_error,
                    )

                    self._log_api_response(
                        dummy_response,
                        idea_num=idx + 1,
                        attempt=attempt + 1,
                        success=False,
                        error=last_error,
                    )

                    if attempt < max_attempts - 1:
                        print(
                            f"ExpertAgent error (attempt {attempt + 1}/{max_attempts}): {e}, retrying..."
                        )
                    else:
                        print(f"ExpertAgent error after {max_attempts} attempts: {e}")
                        return None

            return None

        # Generate all ideas in PARALLEL
        tasks = [generate_single_idea(i) for i in range(num_ideas)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out None and exceptions
        ideas = [r for r in results if isinstance(r, Idea)]
        return ideas

    async def evaluate_idea(self, idea: Idea) -> Evaluation:
        """Evaluate idea using LLM with expert lens (evidence-based, practical)."""
        prompt = f"""Evaluate this idea from an expert perspective:

IDEA: {idea.content}
PERSONA: {idea.persona}

Provide your evaluation as JSON:
{{
    "novelty": <0-100, how novel is this idea>,
    "feasibility": <0-100, how implementable is this>,
    "impact": <0-100, what impact would this have>,
    "arguments_pro": ["specific reason 1", "specific reason 2"],
    "arguments_con": ["concern 1", "concern 2"]
}}

Expert perspective: Prioritize evidence-based approaches, proven methodologies, and practical implementation."""
        return await self._evaluate_with_llm(idea, prompt)


__all__ = ["ExpertAgent"]
