"""
Debate Arena - Multi-Agent Debate Orchestration

The DebateArena orchestrates adversarial debates between multiple agents,
following a structured 3-round format to stress-test ideas through
argumentation and counter-argumentation.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from ..agents.base import Agent
from ..models import BrainstormContext, Idea
from .judge import JudgeAgent
from .models import (
    DebateConfig,
    DebatedIdea,
    DebateRound,
    RoundContribution,
)
from .voting import VotingMechanism, VotingStrategy

logger = logging.getLogger(__name__)


class DebateArena:
    """
    Orchestrates multi-agent adversarial debates.

    The DebateArena manages the 3-round debate process:
    1. Round 1 (PRO): Expert agent presents supporting arguments
    2. Round 2 (CON): Critic agent presents opposing arguments
    3. Round 3 (REBUTTAL): Innovator agent provides counter-arguments

    After all rounds, the Judge evaluates the debate and agents
    vote to reach consensus.

    Attributes:
        config: Configuration for debate behavior
        judge: Judge agent for evaluating debates
        voting: Voting mechanism for consensus

    Example:
        ```python
        arena = DebateArena(config=DebateConfig())
        debated_ideas = await arena.debate(
            ideas=[idea1, idea2, idea3],
            participants=[expert, critic, innovator],
            rounds=3
        )
        for debated in debated_ideas:
            print(f"Score: {debated.final_score}")
            print(f"Recommendation: {debated.recommendation}")
        ```

    """

    def __init__(
        self,
        config: DebateConfig | None = None,
        judge: JudgeAgent | None = None,
        voting: VotingMechanism | None = None
    ):
        """
        Initialize the DebateArena.

        Args:
            config: Optional debate configuration
            judge: Optional Judge agent (creates default if None)
            voting: Optional voting mechanism (creates default if None)

        """
        self.config = config or DebateConfig()
        self.judge = judge or JudgeAgent()
        self.voting = voting or VotingMechanism(
            strategy=VotingStrategy(self.config.voting_strategy)
        )

        logger.info(
            f"DebateArena initialized with {self.config.num_rounds} rounds, "
            f"strategy={self.config.voting_strategy}"
        )

    async def debate(
        self,
        ideas: list[Idea],
        participants: list[Agent],
        rounds: int = 3,
        context: BrainstormContext | None = None
    ) -> list[DebatedIdea]:
        """
        Execute full debate process for multiple ideas.

        Runs the complete 3-round debate for each idea, including
        argument generation, judge evaluation, and consensus voting.

        Args:
            ideas: List of ideas to debate
            participants: List of agent participants
            rounds: Number of debate rounds (default: 3)
            context: Optional brainstorm context

        Returns:
            List of DebatedIdea with full debate results

        Raises:
            ValueError: If invalid parameters provided
            asyncio.TimeoutError: If debate exceeds timeout

        Example:
            ```python
            debated_ideas = await arena.debate(
                ideas=[idea1, idea2],
                participants=[expert, critic, innovator],
                rounds=3
            )
            ```

        """
        if not ideas:
            raise ValueError("Cannot debate empty ideas list")

        if not participants:
            raise ValueError("Cannot debate without participants")

        if len(participants) < 2:
            raise ValueError("Need at least 2 participants for debate")

        # Adjust rounds if needed
        rounds = min(rounds, self.config.num_rounds)

        logger.info(
            f"Starting debate for {len(ideas)} ideas with "
            f"{len(participants)} participants over {rounds} rounds"
        )

        # Track start time
        start_time = datetime.utcnow()

        # Debate each idea
        debated_ideas: list[DebatedIdea] = []

        for i, idea in enumerate(ideas):
            try:
                logger.info(f"Debating idea {i+1}/{len(ideas)}: {idea.id}")

                # Debate single idea
                debated = await self.debate_single_idea(
                    idea=idea,
                    participants=participants,
                    rounds=rounds,
                    context=context
                )

                debated_ideas.append(debated)

                logger.info(
                    f"Idea {i+1} debate complete: "
                    f"score={debated.final_score:.1f}, "
                    f"recommendation={debated.recommendation}"
                )

            except Exception as e:
                logger.error(f"Error debating idea {idea.id}: {e}")
                # Continue with other ideas
                continue

        # Log completion
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.info(
            f"Debate complete: {len(debated_ideas)}/{len(ideas)} ideas "
            f"debated in {duration:.1f}s"
        )

        return debated_ideas

    async def debate_single_idea(
        self,
        idea: Idea,
        participants: list[Agent],
        rounds: int,
        context: BrainstormContext | None = None
    ) -> DebatedIdea:
        """
        Debate a single idea through all rounds.

        Args:
            idea: The idea to debate
            participants: List of participating agents
            rounds: Number of debate rounds
            context: Optional brainstorm context

        Returns:
            DebatedIdea with complete debate results

        """
        # Store all contributions
        all_contributions: list[RoundContribution] = []

        # Execute debate rounds
        pro_arguments: list[str] = []
        con_arguments: list[str] = []
        rebuttals: list[str] = []

        # Round 1: PRO (Expert supports idea)
        if rounds >= 1:
            logger.debug(f"Round 1 (PRO) for idea {idea.id}")
            pro_contributions = await self._conduct_round(
                idea=idea,
                participants=participants,
                round_type=DebateRound.PRO,
                context=context
            )
            all_contributions.extend(pro_contributions)
            pro_arguments = [c.argument for c in pro_contributions]

        # Round 2: CON (Critic challenges idea)
        if rounds >= 2:
            logger.debug(f"Round 2 (CON) for idea {idea.id}")
            con_contributions = await self._conduct_round(
                idea=idea,
                participants=participants,
                round_type=DebateRound.CON,
                context=context
            )
            all_contributions.extend(con_contributions)
            con_arguments = [c.argument for c in con_contributions]

        # Round 3: REBUTTAL (Innovator provides counter-arguments)
        if rounds >= 3:
            logger.debug(f"Round 3 (REBUTTAL) for idea {idea.id}")
            rebuttal_contributions = await self._conduct_round(
                idea=idea,
                participants=participants,
                round_type=DebateRound.REBUTTAL,
                context=context
            )
            all_contributions.extend(rebuttal_contributions)
            rebuttals = [c.argument for c in rebuttal_contributions]

        # Evaluate each round
        round_evaluations = []
        for round_type in [DebateRound.PRO, DebateRound.CON, DebateRound.REBUTTAL]:
            round_contribs = [c for c in all_contributions if c.round == round_type]
            if round_contribs:
                try:
                    eval_task = asyncio.wait_for(
                        self.judge.evaluate_round(round_contribs, round_type),
                        timeout=self.config.round_timeout
                    )
                    round_eval = await eval_task
                    round_evaluations.append(round_eval)
                except TimeoutError:
                    logger.warning(f"Round {round_type.value} evaluation timed out")
                except Exception as e:
                    logger.error(f"Error evaluating round {round_type.value}: {e}")

        # Judge evaluates complete debate
        try:
            debated_idea = await asyncio.wait_for(
                self.judge.evaluate_debate(
                    idea=idea,
                    pros=pro_arguments,
                    cons=con_arguments,
                    rebuttals=rebuttals,
                    round_evaluations=round_evaluations
                ),
                timeout=self.config.round_timeout * 2
            )
        except TimeoutError:
            logger.warning(f"Judge evaluation timed out for idea {idea.id}")
            # Create minimal debated idea
            debated_idea = DebatedIdea(
                original=idea,
                pro_arguments=pro_arguments,
                con_arguments=con_arguments,
                rebuttals=rebuttals,
                contributions=all_contributions,
                round_evaluations=round_evaluations,
                judge_score=50.0,
                recommendation="revise"
            )
        except Exception as e:
            logger.error(f"Error in judge evaluation: {e}")
            debated_idea = DebatedIdea(
                original=idea,
                pro_arguments=pro_arguments,
                con_arguments=con_arguments,
                rebuttals=rebuttals,
                contributions=all_contributions,
                round_evaluations=round_evaluations,
                judge_score=50.0,
                recommendation="revise",
                debate_metadata={"error": str(e)}
            )

        # Add contributions to debated idea
        debated_idea.contributions = all_contributions
        debated_idea.round_evaluations = round_evaluations

        # Conduct consensus vote
        try:
            consensus_result = await asyncio.wait_for(
                self.voting.vote_on_idea(
                    debated_idea=debated_idea,
                    agents=participants,
                    round_contributions=all_contributions
                ),
                timeout=self.config.round_timeout
            )
            debated_idea.consensus_score = consensus_result.consensus_score
            debated_idea.debate_metadata["consensus_result"] = consensus_result.model_dump()

        except TimeoutError:
            logger.warning(f"Consensus voting timed out for idea {idea.id}")
        except Exception as e:
            logger.error(f"Error in consensus voting: {e}")

        # Calculate final score
        debated_idea.calculate_final_score(
            judge_weight=self.config.judge_weight,
            consensus_weight=self.config.consensus_weight
        )

        # Apply quality-based refinement if enabled
        if self.config.enable_refinement:
            debated_idea = self._refine_score_based_on_quality(debated_idea)

        return debated_idea

    async def _conduct_round(
        self,
        idea: Idea,
        participants: list[Agent],
        round_type: DebateRound,
        context: BrainstormContext | None = None
    ) -> list[RoundContribution]:
        """
        Conduct a single debate round.

        Args:
            idea: The idea being debated
            participants: List of participating agents
            round_type: Which round to conduct
            context: Optional brainstorm context

        Returns:
            List of RoundContribution from this round

        """
        contributions: list[RoundContribution] = []

        # Select agents for this round based on round type
        round_agents = self._select_agents_for_round(
            participants=participants,
            round_type=round_type
        )

        # Generate contributions from each agent
        tasks = [
            self._generate_contribution(agent, idea, round_type, context)
            for agent in round_agents
        ]

        # Run in parallel with timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self.config.round_timeout
            )

            # Collect successful contributions
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Agent contribution failed: {result}")
                elif isinstance(result, RoundContribution):
                    contributions.append(result)

        except TimeoutError:
            logger.warning(f"Round {round_type.value} timed out")
            # Return whatever contributions we have

        return contributions

    def _select_agents_for_round(
        self,
        participants: list[Agent],
        round_type: DebateRound
    ) -> list[Agent]:
        """
        Select which agents participate in a given round.

        Args:
            participants: All available agents
            round_type: Which round

        Returns:
            List of agents for this round

        """
        selected = []

        for agent in participants:
            agent_name = getattr(agent, "name", agent.__class__.__name__)

            # Select based on round type
            if round_type == DebateRound.PRO:
                # Expert and Pragmatist support
                if agent_name in ["Expert", "Pragmatist"]:
                    selected.append(agent)

            elif round_type == DebateRound.CON:
                # Critic challenges
                if agent_name in ["Critic"]:
                    selected.append(agent)

            elif round_type == DebateRound.REBUTTAL:
                # Innovator and Synthesizer provide counter-arguments
                if agent_name in ["Innovator", "Synthesizer"]:
                    selected.append(agent)

        # Fallback: if no agents selected, use all
        if not selected:
            selected = participants

        return selected

    async def _generate_contribution(
        self,
        agent: Agent,
        idea: Idea,
        round_type: DebateRound,
        context: BrainstormContext | None = None
    ) -> RoundContribution:
        """
        Generate a single agent's contribution for a round.

        Args:
            agent: The agent to generate contribution from
            idea: The idea being debated
            round_type: Which round
            context: Optional brainstorm context

        Returns:
            RoundContribution with argument and reasoning

        Note:
            For MVP, generates simulated contributions.
            In production, would call agent's debate method.

        """
        agent_name = getattr(agent, "name", agent.__class__.__name__)

        # Generate argument based on round type
        if round_type == DebateRound.PRO:
            argument = self._generate_pro_argument(agent_name, idea)
        elif round_type == DebateRound.CON:
            argument = self._generate_con_argument(agent_name, idea)
        else:  # REBUTTAL
            argument = self._generate_rebuttal(agent_name, idea)

        # Generate reasoning path
        reasoning_path = [
            f"Analyzed idea from {agent_name} perspective",
            f"Considered {round_type.value} arguments",
            "Formulated position based on domain knowledge",
            "Constructed final argument"
        ]

        return RoundContribution(
            agent_name=agent_name,
            round=round_type,
            argument=argument,
            reasoning_path=reasoning_path,
            timestamp=datetime.utcnow(),
            metadata={
                "agent_type": agent_name,
                "idea_id": idea.id
            }
        )

    def _generate_pro_argument(self, agent_name: str, idea: Idea) -> str:
        """Generate a pro argument for the idea."""
        templates = [
            f"{idea.content} demonstrates significant potential for positive impact. "
            f"The approach is grounded in established principles and offers practical benefits. "
            f"From a {agent_name} perspective, this idea addresses core needs effectively.",

            f"The proposed solution of {idea.content[:50]}... shows strong merit. "
            f"It leverages proven methodologies and has a clear path to implementation. "
            f"The benefits outweigh the costs, making it a viable option.",

            f"This idea deserves support because it tackles the problem systematically. "
            f"The {agent_name} framework validates its approach, and evidence suggests "
            f"it will deliver meaningful results."
        ]
        import hashlib
        idx = int(hashlib.md5(idea.id.encode()).hexdigest(), 16) % len(templates)
        return templates[idx]

    def _generate_con_argument(self, agent_name: str, idea: Idea) -> str:
        """Generate a con argument against the idea."""
        templates = [
            f"While {idea.content} has merit, there are significant concerns. "
            f"The implementation risks are substantial, and the resource requirements "
            f"may be underestimated. From a {agent_name} perspective, we must identify "
            f"potential failure modes before proceeding.",

            f"This proposal faces serious challenges. The assumptions about feasibility "
            f"are optimistic, and there are unresolved questions about scalability. "
            f"A {agent_name} analysis reveals multiple points of failure that need "
            f"careful consideration.",

            f"The idea of {idea.content[:50]}... requires critical examination. "
            f"There are gaps in the reasoning, and the proposed approach may not "
            f"withstand real-world conditions. We must address these concerns before "
            f"moving forward."
        ]
        import hashlib
        idx = int(hashlib.md5(idea.id.encode()).hexdigest(), 16) % len(templates)
        return templates[idx]

    def _generate_rebuttal(self, agent_name: str, idea: Idea) -> str:
        """Generate a rebuttal argument."""
        templates = [
            f"The criticisms raised can be addressed through careful planning. "
            f"{idea.content} incorporates risk mitigation strategies, and the concerns "
            f"about feasibility are manageable with the right approach. "
            f"From an {agent_name} viewpoint, the innovation justifies the effort.",

            "While the concerns are valid, they are not insurmountable. "
            "This proposal has built-in safeguards and contingency plans. "
            "The potential upside significantly outweighs the risks when properly managed.",

            f"The objections raised underestimate the adaptability of this solution. "
            f"By {agent_name} principles, we can iterate and refine as we implement, "
            f"addressing challenges as they arise while maintaining the core vision."
        ]
        import hashlib
        idx = int(hashlib.md5(idea.id.encode()).hexdigest(), 16) % len(templates)
        return templates[idx]

    def _refine_score_based_on_quality(self, debated_idea: DebatedIdea) -> DebatedIdea:
        """
        Refine the final score based on debate quality.

        If debate quality is below threshold, reduce score.
        If debate quality is high, maintain or boost score.

        Args:
            debated_idea: The debated idea to refine

        Returns:
            DebatedIdea with refined score

        """
        quality_threshold = self.config.quality_threshold
        current_score = debated_idea.final_score

        # Check debate quality from round evaluations
        if debated_idea.round_evaluations:
            avg_quality = sum(
                r.quality_score for r in debated_idea.round_evaluations
            ) / len(debated_idea.round_evaluations)

            if avg_quality < quality_threshold:
                # Reduce score due to poor debate quality
                penalty = (quality_threshold - avg_quality) * 0.5
                debated_idea.final_score = max(0, current_score - penalty)
                debated_idea.debate_metadata["quality_penalty"] = penalty
                logger.debug(
                    f"Applied quality penalty of {penalty:.1f} to idea {debated_idea.id}"
                )
            elif avg_quality > 80:
                # Boost score for exceptional debate quality
                bonus = (avg_quality - 80) * 0.2
                debated_idea.final_score = min(100, current_score + bonus)
                debated_idea.debate_metadata["quality_bonus"] = bonus
                logger.debug(
                    f"Applied quality bonus of {bonus:.1f} to idea {debated_idea.id}"
                )

        return debated_idea


__all__ = [
    "DebateArena",
    "DebateConfig",
]
