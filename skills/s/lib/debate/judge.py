"""
Judge Agent for Multi-Agent Debate Evaluation

The Judge agent is responsible for evaluating debate rounds and
providing comprehensive assessments of idea quality based on
the adversarial discussion.
"""
from __future__ import annotations

import logging

from ..agents.base import Agent
from ..models import Evaluation, Idea
from ..reasoning.chain_of_thought import ChainOfThoughtStrategy
from .models import (
    DebatedIdea,
    DebateEvaluation,
    DebateRound,
    RoundContribution,
    RoundEvaluation,
)

logger = logging.getLogger(__name__)


class JudgeAgent(Agent):
    """
    Judge Agent for evaluating multi-agent debates.

    The Judge agent assesses:
    - Quality of arguments in each round
    - Persuasiveness and evidence quality
    - Overall debate quality
    - Consensus strength among agents
    - Final verdict and recommendation

    The Judge is impartial and evaluates based on reasoning quality,
    evidence strength, and logical consistency rather than taking sides.

    Attributes:
        reasoning_strategy: Chain-of-Thought strategy for evaluation
        evaluation_criteria: Standard criteria for judging debates

    Example:
        ```python
        judge = JudgeAgent()
        debated_idea = await judge.evaluate_debate(
            idea=original_idea,
            pros=[pro_arg1, pro_arg2],
            cons=[con_arg1, con_arg2],
            rebuttals=[rebuttal1]
        )
        print(f"Judge Score: {debated_idea.judge_score}")
        print(f"Recommendation: {debated_idea.recommendation}")
        ```

    """

    def __init__(self):
        """Initialize the Judge agent."""
        super().__init__(
            name="Judge",
            description="Impartial evaluator of multi-agent debates"
        )

        # System prompt for Judge persona
        self.system_prompt = """You are an impartial Judge evaluating debates between multiple AI agents.

Your role is to:
- Assess the quality of arguments in each round
- Evaluate evidence and reasoning quality
- Identify strengths and weaknesses on all sides
- Determine which side made the strongest case
- Provide a fair, balanced verdict

Your evaluation criteria:
1. Quality: Are arguments well-structured and logical?
2. Persuasiveness: How compelling are the arguments?
3. Evidence: Is there good support for claims?
4. Consistency: Do arguments hold together logically?
5. Balance: Are both sides given fair consideration?

You are neutral and objective. You do not favor any particular side.
Your verdict is based solely on the quality of reasoning and evidence."""

        # Initialize reasoning strategy
        self.reasoning_strategy = ChainOfThoughtStrategy(
            timeout=45.0,
            max_thoughts=8,
            temperature=0.4  # Low temperature for consistent, fair judgment
        )

        # Standard evaluation criteria
        self.evaluation_criteria = {
            "quality": "Logical structure, clarity, and coherence",
            "persuasiveness": "Compelling nature of arguments",
            "evidence": "Quality and relevance of supporting evidence",
            "consistency": "Internal logical consistency",
            "originality": "Novelty and creativity of arguments",
        }

    async def evaluate_round(
        self,
        contributions: list[RoundContribution],
        round_type: DebateRound
    ) -> RoundEvaluation:
        """
        Evaluate a single debate round.

        Assesses the quality, persuasiveness, and evidence quality
        of all contributions in a specific round.

        Args:
            contributions: All contributions in this round
            round_type: Which round (PRO, CON, or REBUTTAL)

        Returns:
            RoundEvaluation with scores and qualitative feedback

        Example:
            ```python
            round_eval = await judge.evaluate_round(
                contributions=pro_contributions,
                round_type=DebateRound.PRO
            )
            print(f"Quality: {round_eval.quality_score}")
            print(f"Strengths: {round_eval.strengths}")
            ```

        """
        # Build evaluation prompt
        prompt = self._build_round_evaluation_prompt(contributions, round_type)

        try:
            # Use Chain-of-Thought reasoning for evaluation
            thought_process = await self.reasoning_strategy.reason(
                prompt=prompt,
                context={
                    "round_type": round_type.value,
                    "num_contributions": len(contributions),
                    "evaluation_criteria": self.evaluation_criteria,
                    "judge_mode": True
                }
            )

            # Parse evaluation from reasoning
            evaluation = self._parse_round_evaluation(
                round_type=round_type,
                thought_process=thought_process,
                contributions=contributions
            )

            logger.debug(
                f"Judge evaluated {round_type.value} round: "
                f"quality={evaluation.quality_score:.1f}"
            )

            return evaluation

        except Exception as e:
            logger.error(f"Error evaluating round {round_type.value}: {e}")

            # Fallback evaluation
            return RoundEvaluation(
                round=round_type,
                quality_score=60.0,
                persuasiveness_score=60.0,
                evidence_score=60.0,
                strengths=["Arguments were presented"],
                weaknesses=["Limited analysis due to error"],
                judge_notes=f"Evaluation error: {e!s}"
            )

    async def generate_ideas(self, context) -> list:
        """
        Judge agents don't generate ideas.

        This is a placeholder implementation to satisfy the Agent interface.
        """
        return []

    async def evaluate_idea(self, idea: Idea) -> Evaluation:
        """
        Evaluate an idea from a judge's perspective.

        Provides a balanced, impartial evaluation of the idea's merit.

        Args:
            idea: The idea to evaluate

        Returns:
            Evaluation with balanced scores and objective arguments

        """
        # Build evaluation prompt
        eval_prompt = f"""Evaluate the following idea impartially:

Idea: {idea.content}
Generated by: {idea.persona}

Provide a balanced assessment considering:
1. Novelty: How unique is this idea?
2. Feasibility: How practical is implementation?
3. Impact: What positive outcomes could result?

Provide scores (0-100) for each dimension and list strengths and weaknesses.
"""

        try:
            # Use reasoning to evaluate
            thought_process = await self.reasoning_strategy.reason(
                prompt=eval_prompt,
                context={
                    "idea_id": idea.id,
                    "evaluation_mode": True,
                    "persona": "judge"
                }
            )

            # Parse evaluation from reasoning
            evaluation = await self._parse_evaluation_from_reasoning(
                idea_id=idea.id,
                thought_process=thought_process
            )

            return evaluation

        except Exception:
            # Fallback evaluation on error
            return Evaluation.from_scores(
                idea_id=idea.id,
                novelty=70.0,  # Judge takes middle ground
                feasibility=70.0,
                impact=70.0,
                arguments_pro=[
                    "Balanced approach",
                    "Reasonable proposal",
                    "Considered multiple factors"
                ],
                arguments_con=[
                    "May require further validation",
                    "Unintended consequences possible"
                ],
                evaluator=f"{self.name}_fallback"
            )

    async def evaluate_debate(
        self,
        idea: Idea,
        pros: list[str],
        cons: list[str],
        rebuttals: list[str],
        round_evaluations: list[RoundEvaluation] | None = None
    ) -> DebatedIdea:
        """
        Evaluate a complete debate and produce final verdict.

        Synthesizes all rounds of the debate into a comprehensive
        evaluation with final scores and recommendation.

        Args:
            idea: The original idea being debated
            pros: Pro arguments supporting the idea
            cons: Con arguments opposing the idea
            rebuttals: Rebuttal arguments countering the cons
            round_evaluations: Optional pre-computed round evaluations

        Returns:
            DebatedIdea with comprehensive evaluation and verdict

        Example:
            ```python
            debated_idea = await judge.evaluate_debate(
                idea=original_idea,
                pros=["It's innovative", "It's scalable"],
                cons=["It's expensive", "It's risky"],
                rebuttals=["The cost is justified by long-term savings"]
            )
            print(f"Verdict: {debated_idea.debate_evaluation.final_verdict}")
            print(f"Recommendation: {debated_idea.recommendation}")
            ```

        """
        # Build comprehensive evaluation prompt
        prompt = self._build_debate_evaluation_prompt(idea, pros, cons, rebuttals)

        try:
            # Use reasoning for comprehensive evaluation
            thought_process = await self.reasoning_strategy.reason(
                prompt=prompt,
                context={
                    "idea_id": idea.id,
                    "num_pros": len(pros),
                    "num_cons": len(cons),
                    "num_rebuttals": len(rebuttals),
                    "judge_mode": True,
                    "final_verdict": True
                }
            )

            # Parse comprehensive evaluation
            evaluation = self._parse_debate_evaluation(
                idea_id=idea.id,
                thought_process=thought_process,
                round_evaluations=round_evaluations or []
            )

            # Create debated idea
            debated_idea = DebatedIdea(
                original=idea,
                pro_arguments=pros,
                con_arguments=cons,
                rebuttals=rebuttals,
                round_evaluations=round_evaluations or [],
                debate_evaluation=evaluation,
                judge_score=evaluation.overall_quality_score,
                recommendation=evaluation.recommendation
            )

            logger.info(
                f"Judge evaluated debate for idea {idea.id}: "
                f"score={debated_idea.judge_score:.1f}, "
                f"recommendation={debated_idea.recommendation}"
            )

            return debated_idea

        except Exception as e:
            logger.error(f"Error evaluating debate for idea {idea.id}: {e}")

            # Fallback: Create minimal debated idea
            return DebatedIdea(
                original=idea,
                pro_arguments=pros,
                con_arguments=cons,
                rebuttals=rebuttals,
                judge_score=50.0,
                recommendation="revise",
                debate_metadata={"error": str(e)}
            )

    def _build_round_evaluation_prompt(
        self,
        contributions: list[RoundContribution],
        round_type: DebateRound
    ) -> str:
        """Build prompt for evaluating a single round."""
        prompt = f"""Evaluate the following {round_type.value.upper()} arguments from a debate:

Round: {round_type.value.upper()}
Number of arguments: {len(contributions)}

Arguments:
"""

        for i, contrib in enumerate(contributions, 1):
            prompt += f"\n{i}. Agent: {contrib.agent_name}\n"
            prompt += f"Argument: {contrib.argument}\n"
            if contrib.reasoning_path:
                prompt += f"Reasoning: {' -> '.join(contrib.reasoning_path[-3:])}\n"
            prompt += "\n"

        prompt += f"""
Evaluate these {round_type.value.upper()} arguments on:

1. Quality (0-100):
   - Logical structure and coherence
   - Clarity and precision
   - Depth of analysis

2. Persuasiveness (0-100):
   - Compelling nature of arguments
   - Emotional resonance (if appropriate)
   - Rhetorical effectiveness

3. Evidence (0-100):
   - Quality of supporting evidence
   - Relevance of examples
   - Strength of reasoning

Provide:
- A quality score (0-100)
- A persuasiveness score (0-100)
- An evidence score (0-100)
- 2-3 specific strengths
- 1-2 weaknesses or gaps
- Brief judge notes

Be fair and objective in your assessment."""

        return prompt

    def _build_debate_evaluation_prompt(
        self,
        idea: Idea,
        pros: list[str],
        cons: list[str],
        rebuttals: list[str]
    ) -> str:
        """Build prompt for comprehensive debate evaluation."""
        prompt = f"""You are the Judge evaluating a complete debate on the following idea:

IDEA: {idea.content}
Generated by: {idea.persona}

=== PRO ARGUMENTS (Supporting the idea) ===
"""

        for i, pro in enumerate(pros, 1):
            prompt += f"\nPro {i}: {pro}\n"

        prompt += "\n=== CON ARGUMENTS (Opposing the idea) ===\n"
        for i, con in enumerate(cons, 1):
            prompt += f"\nCon {i}: {con}\n"

        prompt += "\n=== REBUTTALS (Counter-arguments to Cons) ===\n"
        for i, rebuttal in enumerate(rebuttals, 1):
            prompt += f"\nRebuttal {i}: {rebuttal}\n"

        prompt += """
=== JUDGE'S EVALUATION ===

Evaluate this debate comprehensively:

1. Overall Quality (0-100):
   - Which side made stronger arguments?
   - Was the debate substantive and insightful?
   - Did both sides present their cases well?

2. Consensus Strength (0-100):
   - Is there clear agreement or disagreement?
   - How divisive is this idea?
   - Can the agents find common ground?

3. Winner Round:
   - Which round had the strongest arguments? (PRO/CON/REBUTTAL)

4. Final Verdict:
   - Summarize the debate in 2-3 sentences
   - State which side prevailed

5. Confidence (0-100):
   - How confident are you in this verdict?
   - Was the debate conclusive or ambiguous?

6. Recommendation (accept/reject/revise):
   - accept: The idea is strong and should be pursued
   - reject: The idea has fatal flaws and should be abandoned
   - revise: The idea has merit but needs refinement

Provide your complete evaluation."""

        return prompt

    def _parse_round_evaluation(
        self,
        round_type: DebateRound,
        thought_process,
        contributions: list[RoundContribution]
    ) -> RoundEvaluation:
        """Parse round evaluation from thought process."""
        # For MVP, extract scores from reasoning metadata
        # In production, would parse actual LLM output

        # Placeholder: Generate pseudo-random scores based on contributions
        import hashlib
        content = " ".join([c.argument for c in contributions])
        hash_val = int(hashlib.md5(content.encode()).hexdigest(), 16)

        quality = 50.0 + (hash_val % 40)  # 50-90
        persuasiveness = 50.0 + ((hash_val // 10) % 40)  # 50-90
        evidence = 50.0 + ((hash_val // 100) % 40)  # 50-90

        # Generate strengths based on round type
        if round_type == DebateRound.PRO:
            strengths = [
                "Clear identification of benefits",
                "Logical progression of arguments",
                "Strong supporting rationale"
            ]
        elif round_type == DebateRound.CON:
            strengths = [
                "Thorough risk analysis",
                "Identification of potential issues",
                "Critical examination of assumptions"
            ]
        else:  # REBUTTAL
            strengths = [
                "Effective counter-arguments",
                "Addressed key concerns",
                "Defended core proposal"
            ]

        weaknesses = [
            "Could provide more specific examples",
            "Some arguments could be strengthened"
        ]

        return RoundEvaluation(
            round=round_type,
            quality_score=quality,
            persuasiveness_score=persuasiveness,
            evidence_score=evidence,
            strengths=strengths,
            weaknesses=weaknesses,
            judge_notes=f"Evaluated {len(contributions)} {round_type.value} arguments"
        )

    def _parse_debate_evaluation(
        self,
        idea_id: str,
        thought_process,
        round_evaluations: list[RoundEvaluation]
    ) -> DebateEvaluation:
        """Parse comprehensive debate evaluation from thought process."""
        # For MVP, generate evaluation based on round evaluations
        # In production, would parse actual LLM output

        if not round_evaluations:
            # No round evaluations, create defaults
            round_evaluations = [
                RoundEvaluation(
                    round=DebateRound.PRO,
                    quality_score=70.0,
                    persuasiveness_score=70.0,
                    evidence_score=70.0,
                    strengths=["Supportive arguments"],
                    weaknesses=["Generic analysis"]
                ),
                RoundEvaluation(
                    round=DebateRound.CON,
                    quality_score=65.0,
                    persuasiveness_score=65.0,
                    evidence_score=65.0,
                    strengths=["Critical analysis"],
                    weaknesses=["Could be more specific"]
                ),
                RoundEvaluation(
                    round=DebateRound.REBUTTAL,
                    quality_score=68.0,
                    persuasiveness_score=68.0,
                    evidence_score=68.0,
                    strengths=["Counter-arguments provided"],
                    weaknesses=["Limited depth"]
                ),
            ]

        # Calculate overall quality as average of round averages
        round_avgs = [r.average_score for r in round_evaluations]
        overall_quality = sum(round_avgs) / len(round_avgs)

        # Determine winner round (highest average)
        winner_idx = round_avgs.index(max(round_avgs))
        winner_round = round_evaluations[winner_idx].round

        # Generate verdict
        if overall_quality >= 75:
            verdict = "The idea demonstrates strong merit with robust supporting arguments and manageable concerns."
            recommendation = "accept"
            consensus = 80.0
        elif overall_quality >= 60:
            verdict = "The idea shows promise but requires refinement to address identified weaknesses."
            recommendation = "revise"
            consensus = 65.0
        else:
            verdict = "The idea has significant flaws that outweigh its potential benefits."
            recommendation = "reject"
            consensus = 40.0

        return DebateEvaluation(
            idea_id=idea_id,
            round_evaluations=round_evaluations,
            overall_quality_score=overall_quality,
            consensus_strength=consensus,
            winner_round=winner_round,
            final_verdict=verdict,
            confidence_score=70.0,  # Moderate confidence for MVP
            recommendation=recommendation
        )

    async def _parse_evaluation_from_reasoning(
        self,
        idea_id: str,
        thought_process
    ) -> Evaluation:
        """
        Parse evaluation from reasoning output.

        Args:
            idea_id: ID of the idea being evaluated
            thought_process: Thought process from evaluation reasoning

        Returns:
            Evaluation with parsed scores and arguments

        """
        # For MVP, provide balanced evaluation
        # In production, would parse actual LLM output for scores

        return Evaluation.from_scores(
            idea_id=idea_id,
            novelty=70.0,  # Judge takes middle ground
            feasibility=70.0,
            impact=70.0,
            arguments_pro=[
                "Well-reasoned approach",
                "Considered multiple perspectives",
                "Logical structure"
            ],
            arguments_con=[
                "Could benefit from more evidence",
                "Some aspects need clarification"
            ],
            evaluator=self.name
        )


__all__ = [
    "DebateEvaluation",
    "JudgeAgent",
    "RoundEvaluation",
]
