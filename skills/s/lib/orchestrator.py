"""
Brainstorm Orchestrator - Multi-Phase Coordination System

This module implements the main orchestrator for the brainstorming system.
It coordinates multiple agents through a 3-phase workflow:
- Phase 1: Diverge - Parallel idea generation from multiple perspectives
- Phase 2: Discuss - Discussion and debate (MVP: basic evaluation)
- Phase 3: Converge - Rank, filter, and return top ideas

The orchestrator handles:
- Spawning and managing agents based on requested personas
- Parallel execution with proper error handling and timeouts
- Memory integration for persistent storage
- Quality metrics and execution tracking
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

# Setup sys.path for external LLM dependencies
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent.parent / "__csf" / "src"))
from llm.performance.model_tracker import (
    ModelPerformanceMetrics,
    ModelPerformanceTracker,
)
from llm.providers import LLMConfig

from .agents.base import Agent
from .convergence import (
    ConvergenceConfig,
    ConvergenceEngine,
    RankingStrategy,
)
from .debate.arena import DebateArena, DebateConfig
from .memory.brainstorm_memory import BrainstormMemory
from .models import (
    BrainstormContext,
    BrainstormResult,
    Evaluation,
    Idea,
)
from .pheromone import ExplorationGuidance, get_global_trail
from .replay import ReplayCandidate, get_global_buffer

logger = logging.getLogger(__name__)


class BrainstormOrchestrator:
    """
    Main orchestrator for multi-agent brainstorming sessions.

    Implements a 3-phase workflow (Diverge → Discuss → Converge) with
    parallel agent execution, timeout protection, and comprehensive metrics.

    Attributes:
        phase: Current workflow phase ("diverge" | "discuss" | "converge")
        agents: List of active agents for the current session
        memory: BrainstormMemory instance for persistent storage
        context: Current brainstorm context (if session is active)

    Example:
        ```python
        orchestrator = BrainstormOrchestrator()
        result = await orchestrator.brainstorm(
            prompt="Develop a sustainable transportation system",
            personas=["innovator", "pragmatist", "critic"],
            timeout=180.0
        )
        print(f"Generated {len(result.ideas)} ideas")
        for idea in result.top_ideas(5):
            print(f"- {idea.content} (Score: {idea.score})")
        ```

    """

    # Phase timeout defaults (seconds)
    # Generous timeouts to avoid cutting short good ideas
    # Increased timeouts for CLI providers (qwen-cli: 6s health, gemini-cli: 45s health)
    # CLI providers may take 60-90s per LLM call, so phases need more headroom
    DIVERGE_TIMEOUT = 600.0  # 10 minutes for parallel idea generation with CLI providers
    DISCUSS_TIMEOUT = 600.0  # 10 minutes for evaluation/debate
    CONVERGE_TIMEOUT = 180.0  # 3 minutes for ranking/filtering

    def __init__(
        self,
        memory: BrainstormMemory | None = None,
        enable_full_debate: bool = True,
        llm_config=None,
        llm_providers: list[str] | None = None,
        persona_providers: dict[str, str] | None = None,
        enable_performance_tracking: bool = True,
        enable_pheromone_trail: bool = False,
        pheromone_db_path: str | None = None,
        enable_replay_buffer: bool = False,
        replay_db_path: str | None = None,
        enable_got: bool = True,  # Graph-of-Thought analysis
        enable_tot: bool = True,  # Tree-of-Thought analysis
        use_mock_agents: bool = False,
        on_phase_start: callable | None = None,
        on_persona_complete: callable | None = None,
        on_phase_complete: callable | None = None,
    ):
        """
        Initialize the orchestrator.

        Args:
            memory: Optional BrainstormMemory instance. If None, creates a new one.
            enable_full_debate: Whether to use full adversarial debate in Phase 2 (default: True)
            llm_config: Optional LLMConfig for real LLM integration (default: None = use mock)
            enable_performance_tracking: Whether to track model performance (default: True)
            enable_pheromone_trail: Whether to enable pheromone trail for path learning (default: False)
            pheromone_db_path: Path to pheromone trail database (default: "data/brainstorm_pheromones.db")
            enable_replay_buffer: Whether to enable replay buffer for reusing successful ideas (default: False)
            replay_db_path: Path to replay buffer database (default: "data/brainstorm_replay.db")
            enable_got: Whether to enable Graph-of-Thought node analysis (default: True)
            enable_tot: Whether to enable Tree-of-Thought outcome branching (default: True)
            llm_providers: Optional list of provider names for round-robin assignment (default: None)
            persona_providers: Optional dict mapping persona names to provider names (default: None)
            use_mock_agents: Use _MockAgent instead of real LLM agents (default: False, for testing)

        """
        self.phase = "diverge"
        self.agents: list[Agent] = []
        self.memory = memory or BrainstormMemory()
        self.use_mock_agents = use_mock_agents
        self.context: BrainstormContext | None = None
        self.enable_full_debate = enable_full_debate
        self.llm_config = llm_config  # Store LLM config for agent creation
        self.llm_providers = llm_providers  # List for round-robin provider assignment
        self.persona_providers = persona_providers or {}  # Explicit persona → provider mapping
        self.enable_pheromone_trail = enable_pheromone_trail
        self.pheromone_trail = None
        self.pheromone_guidance: ExplorationGuidance | None = None
        self.enable_replay_buffer = enable_replay_buffer
        self.replay_buffer = None
        self.replay_candidates: list[ReplayCandidate] = []
        self.enable_got = enable_got  # Graph-of-Thought analysis
        self.enable_tot = enable_tot  # Tree-of-Thought analysis
        self.got_analysis = None  # Will store GoT results
        self.tot_branches = None  # Will store ToT results

        # Progress callbacks
        self.on_phase_start = on_phase_start
        self.on_persona_complete = on_persona_complete
        self.on_phase_complete = on_phase_complete

        # Initialize pheromone trail if enabled
        if enable_pheromone_trail:
            try:
                self.pheromone_trail = get_global_trail(db_path=pheromone_db_path)
                logger.info(f"Pheromone trail enabled: {pheromone_db_path}")
            except Exception as e:
                logger.warning(f"Could not initialize pheromone trail: {e}")
                self.enable_pheromone_trail = False

        # Initialize replay buffer if enabled
        if enable_replay_buffer:
            try:
                self.replay_buffer = get_global_buffer(db_path=replay_db_path)
                logger.info(f"Replay buffer enabled: {replay_db_path}")
            except Exception as e:
                logger.warning(f"Could not initialize replay buffer: {e}")
                self.enable_replay_buffer = False

        # Initialize performance tracker (skip in mock mode for performance)
        # FAIL FAST: Explicit check for mock mode - never default to mock
        is_mock_mode = use_mock_agents or (
            llm_config is not None and getattr(llm_config, "mock_mode", False)
        )

        self.enable_performance_tracking = enable_performance_tracking and not is_mock_mode
        self.performance_tracker: ModelPerformanceTracker | None = None
        if self.enable_performance_tracking:
            try:
                self.performance_tracker = ModelPerformanceTracker()
                logger.info("Performance tracking enabled")
            except Exception as e:
                logger.warning(f"Could not initialize performance tracker: {e}")
                self.performance_tracker = None
        elif is_mock_mode:
            logger.info("Mock mode detected - performance tracking disabled for speed")

        # Initialize debate arena if full debate is enabled
        self.debate_arena: DebateArena | None = None
        if self.enable_full_debate:
            self.debate_arena = DebateArena(
                config=DebateConfig(
                    num_rounds=3,
                    round_timeout=30.0,
                    judge_weight=0.6,
                    consensus_weight=0.4,
                    voting_strategy="weighted",
                    enable_refinement=True,
                )
            )

        # Metrics tracking
        self.metrics: dict[str, Any] = {
            "diverge_duration": 0.0,
            "discuss_duration": 0.0,
            "converge_duration": 0.0,
            "total_duration": 0.0,
            "ideas_generated": 0,
            "evaluations_performed": 0,
            "debates_conducted": 0,
            "agents_spawned": 0,
            "errors": [],
        }

        logger.info(
            f"BrainstormOrchestrator initialized "
            f"(full_debate={'enabled' if self.enable_full_debate else 'disabled'})"
        )

    def _get_provider_tier(self, provider: str) -> str:
        """
        Get the quality tier for a provider.

        Args:
            provider: Provider name (e.g., 'claude', 'openai', 'gemini', 'qwen-cli')

        Returns:
            Tier string (T1/T2/T3). Defaults to T3 for unknown providers.

        CLI tools inherit tier from their base provider:
        - gemini-cli: T2 (Gemini models)
        - qwen-cli: T2 (Qwen coder model - high quality)
        - vibe: T3 (Devstral - experimental)
        - opencode: T3 (multi-provider, variable quality)
        """
        provider_lower = provider.lower()

        # T1: Highest quality models
        if "claude" in provider_lower or "anthropic" in provider_lower:
            return "T1"

        # T2: Good quality models (including CLI tools with T2 base models)
        if "openai" in provider_lower or "gpt" in provider_lower:
            return "T2"
        if "gemini" in provider_lower or "google" in provider_lower:
            return "T2"
        # qwen-cli uses Qwen 3.5 Plus - a capable coder model, T2 tier
        if "qwen" in provider_lower:
            return "T2"

        # T3: Experimental or variable quality
        # groq, chutes, mistral, openrouter, vibe, opencode
        return "T3"

    def _is_provider_tier_allowed(self, provider: str) -> bool:
        """
        Check if a provider's tier is allowed by the LLM config.

        Args:
            provider: Provider name

        Returns:
            True if provider tier is in allowed_tiers list
        """
        if not self.llm_config:
            return True  # No config means no restrictions

        provider_tier = self._get_provider_tier(provider)
        allowed_tiers = getattr(self.llm_config, "allowed_tiers", ["T1", "T2", "T3"])

        return provider_tier in allowed_tiers

    def _filter_providers_by_tier(self) -> list[str]:
        """
        Filter the llm_providers list to only include providers with allowed tiers.

        Returns:
            Filtered list of provider names
        """
        if not self.llm_providers:
            return []

        filtered = []
        for provider in self.llm_providers:
            if self._is_provider_tier_allowed(provider):
                filtered.append(provider)
            else:
                tier = self._get_provider_tier(provider)
                logger.debug(
                    f"Provider '{provider}' (tier {tier}) filtered out by tier restrictions"
                )

        return filtered if filtered else self.llm_providers

    async def brainstorm(
        self,
        prompt: str,
        personas: list[str] | None = None,
        timeout: float = 180.0,
        num_ideas: int = 10,
        constraints: list[str] | None = None,
        goals: list[str] | None = None,
        fresh_mode: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> BrainstormResult:
        """
        Execute a complete brainstorming session through all 3 phases.

        Args:
            prompt: The main topic or problem to brainstorm about
            personas: List of persona names to use (default: ["innovator", "pragmatist", "critic"])
            timeout: Total timeout for the entire session in seconds (default: 180.0)
            num_ideas: Target number of ideas to generate (default: 10)
            constraints: Optional list of constraints or requirements
            goals: Optional list of specific goals to achieve
            fresh_mode: If True, agents must NOT read existing plans/solutions (prevents anchoring bias)
            metadata: Additional context or parameters

        Returns:
            BrainstormResult with all generated ideas and evaluations

        Raises:
            TimeoutError: If the session exceeds the specified timeout
            ValueError: If invalid parameters are provided
            Exception: For other errors during execution

        """
        # Validate input
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")

        if num_ideas < 1 or num_ideas > 100:
            raise ValueError("num_ideas must be between 1 and 100")

        # Create context
        self.context = BrainstormContext(
            topic=prompt.strip(),
            num_ideas=num_ideas,
            personas=personas or ["innovator", "pragmatist", "critic"],
            constraints=constraints or [],
            goals=goals or [],
            timeout_seconds=int(timeout),
            fresh_mode=fresh_mode,
            metadata=metadata or {},
        )

        # Initialize result
        session_id = str(uuid.uuid4())
        result = BrainstormResult(context=self.context, session_id=session_id)

        # Reset metrics
        self.metrics = {
            "diverge_duration": 0.0,
            "discuss_duration": 0.0,
            "converge_duration": 0.0,
            "total_duration": 0.0,
            "ideas_generated": 0,
            "evaluations_performed": 0,
            "agents_spawned": 0,
            "errors": [],
            "phase": "diverge",
        }

        start_time = time.time()

        try:
            logger.info(f"Starting brainstorm session {session_id}: {prompt[:50]}...")

            # Spawn agents
            await self._spawn_agents(self.context.personas)

            # Get pheromone guidance if enabled
            if self.enable_pheromone_trail and self.pheromone_trail:
                try:
                    self.pheromone_guidance = self.pheromone_trail.get_guidance(
                        topic=self.context.topic,
                        threshold=50.0,  # Only include nodes with meaningful strength
                        max_results=5,
                    )
                    logger.info(
                        f"Pheromone guidance: {len(self.pheromone_guidance.suggested_personas)} personas, "
                        f"confidence={self.pheromone_guidance.confidence:.2f}"
                    )
                    # Store guidance in result metadata
                    result.metadata["pheromone_guidance"] = self.pheromone_guidance.to_dict()
                except Exception as e:
                    logger.warning(f"Could not get pheromone guidance: {e}")

            # Get replay candidates if enabled
            if self.enable_replay_buffer and self.replay_buffer:
                try:
                    self.replay_candidates = self.replay_buffer.find_candidates(
                        topic=self.context.topic,
                        max_results=3,  # Get top 3 candidates
                        min_effectiveness=60.0,
                    )
                    logger.info(
                        f"Replay buffer: {len(self.replay_candidates)} candidates retrieved"
                    )
                    # Store candidates in result metadata
                    result.metadata["replay_candidates"] = [
                        {
                            "content": c.record.content[:100] + "...",
                            "effectiveness": c.record.effectiveness,
                            "reason": c.replay_reason,
                        }
                        for c in self.replay_candidates
                    ]
                except Exception as e:
                    logger.warning(f"Could not get replay candidates: {e}")

            # Phase 1: Diverge
            self.phase = "diverge"
            self.metrics["phase"] = "diverge"
            logger.info("Phase 1: Diverge - Generating ideas...")
            phase_start = time.time()
            if self.on_phase_start:
                self.on_phase_start("diverge", len(personas) if personas else 0)

            ideas = await self._phase_diverge(
                context=self.context,
                timeout=min(
                    self.DIVERGE_TIMEOUT, timeout * 0.6
                ),  # 60% for diverge (increased from 70% for discuss time)
            )

            self.metrics["diverge_duration"] = time.time() - phase_start
            self.metrics["ideas_generated"] = len(ideas)
            logger.info(f"Phase 1 complete: Generated {len(ideas)} ideas")
            if self.on_phase_complete:
                self.on_phase_complete("diverge", len(ideas))

            if not ideas:
                logger.warning("No ideas generated in Phase 1")
                result.metadata["warning"] = "No ideas generated during diverge phase"
                return result

            # Add ideas to result
            for idea in ideas:
                result.add_idea(idea)

            # Phase 2: Discuss
            self.phase = "discuss"
            self.metrics["phase"] = "discuss"
            logger.info("Phase 2: Discuss - Evaluating ideas...")
            phase_start = time.time()
            if self.on_phase_start:
                self.on_phase_start("discuss", len(ideas))

            evaluations = await self._phase_discuss(
                ideas=ideas,
                context=self.context,
                timeout=min(
                    self.DISCUSS_TIMEOUT, timeout * 0.35
                ),  # 35% for discuss (increased from 25%)
            )

            self.metrics["discuss_duration"] = time.time() - phase_start
            self.metrics["evaluations_performed"] = len(evaluations)
            logger.info(f"Phase 2 complete: Evaluated {len(evaluations)} ideas")
            if self.on_phase_complete:
                self.on_phase_complete("discuss", len(evaluations))

            # Add evaluations to result
            for evaluation in evaluations:
                result.add_evaluation(evaluation)

            # Phase 3: Converge
            self.phase = "converge"
            self.metrics["phase"] = "converge"
            logger.info("Phase 3: Converge - Ranking and filtering...")
            phase_start = time.time()
            if self.on_phase_start:
                self.on_phase_start("converge", len(evaluations))

            await self._phase_converge(
                result=result,
                timeout=min(self.CONVERGE_TIMEOUT, timeout * 0.05),  # 5% for converge (fast)
            )

            self.metrics["converge_duration"] = time.time() - phase_start
            logger.info("Phase 3 complete: Ideas ranked and filtered")
            if self.on_phase_complete:
                self.on_phase_complete("converge", len(result.ideas))

            # Deposit pheromones from successful session
            if self.enable_pheromone_trail and self.pheromone_trail:
                try:
                    deposit_summary = self.pheromone_trail.deposit_from_session(
                        session_id=session_id,
                        topic=self.context.topic,
                        ideas=result.ideas,
                        min_score=60.0,  # Only deposit for good ideas
                    )
                    logger.info(
                        f"Pheromone deposit: {deposit_summary['deposited']}/{deposit_summary['total_ideas']} ideas, "
                        f"strength={deposit_summary['total_strength']:.1f}"
                    )
                    result.metadata["pheromone_deposit"] = deposit_summary
                except Exception as e:
                    logger.warning(f"Could not deposit pheromones: {e}")

            # Store high-scoring ideas in replay buffer
            if self.enable_replay_buffer and self.replay_buffer:
                try:
                    replay_summary = self.replay_buffer.add_from_session(
                        session_id=session_id,
                        topic=self.context.topic,
                        ideas=result.ideas,
                        min_score=70.0,  # Only store top-tier ideas in replay buffer
                    )
                    logger.info(
                        f"Replay buffer: {replay_summary['added']}/{replay_summary['total_ideas']} ideas stored"
                    )
                    result.metadata["replay_buffer_update"] = replay_summary
                except Exception as e:
                    logger.warning(f"Could not update replay buffer: {e}")

            # Store in memory
            await self._store_result(session_id, result)

            # Track model performance
            if self.performance_tracker and self.llm_config and not self.llm_config.mock_mode:
                await self._track_model_performance(session_id, result)

        except TimeoutError as e:
            logger.error(f"Brainstorm session timed out: {e}")
            self.metrics["errors"].append(f"Timeout: {e!s}")
            raise TimeoutError(f"Brainstorm session exceeded timeout: {timeout}s") from e

        except Exception as e:
            logger.error(f"Error during brainstorm session: {e}", exc_info=True)
            self.metrics["errors"].append(str(e))
            result.metadata["error"] = str(e)
            raise

        finally:
            # Calculate total duration
            self.metrics["total_duration"] = time.time() - start_time
            result.metrics = self.metrics.copy()

            # Cleanup
            await self._cleanup()

            logger.info(
                f"Brainstorm session {session_id} complete: "
                f"{len(result.ideas)} ideas, {self.metrics['total_duration']:.2f}s"
            )

        return result

    async def _spawn_agents(self, personas: list[str]) -> None:
        """
        Spawn agents for the requested personas.

        Args:
            personas: List of persona names

        """
        self.agents.clear()

        # Use mock agents for testing (no API keys required)
        if self.use_mock_agents:
            for persona in personas:
                agent = _MockAgent(name=persona.title(), description=f"Mock {persona} agent")
                self.agents.append(agent)
            return

        # Import real agent classes
        from .agents.critic import CriticAgent
        from .agents.expert import ExpertAgent
        from .agents.futurist import FuturistAgent
        from .agents.innovator import InnovatorAgent
        from .agents.pragmatist import PragmatistAgent
        from .agents.synthesizer import SynthesizerAgent

        # Map persona names to agent classes
        agent_classes = {
            "expert": ExpertAgent,
            "critic": CriticAgent,
            "futurist": FuturistAgent,
            "innovator": InnovatorAgent,
            "pragmatist": PragmatistAgent,
            "synthesizer": SynthesizerAgent,
        }

        # Filter providers by tier if llm_config has tier restrictions
        available_providers = self._filter_providers_by_tier()

        # DEBUG: Log provider state for troubleshooting
        print(
            f"[DEBUG _spawn_agents] self.llm_providers = {self.llm_providers}",
            file=sys.stderr,
            flush=True,
        )
        print(
            f"[DEBUG _spawn_agents] available_providers = {available_providers}",
            file=sys.stderr,
            flush=True,
        )
        print(
            f"[DEBUG _spawn_agents] self.llm_config = {self.llm_config}",
            file=sys.stderr,
            flush=True,
        )

        # Create agents for requested personas
        for i, persona in enumerate(personas):
            persona_lower = persona.lower()
            if persona_lower in agent_classes:
                agent_class = agent_classes[persona_lower]

                # Determine provider for this agent
                # CRITICAL: Always pass preferred_providers to ensure agents use filtered/healthy providers
                # This prevents agents from selecting unhealthy providers from the registry
                agent_llm_config = self.llm_config

                if not self.use_mock_agents:
                    # Determine which providers list to use for this agent
                    providers_for_agent = None

                    # Check for explicit persona → provider mapping
                    if persona_lower in self.persona_providers:
                        provider = self.persona_providers[persona_lower]
                        # Verify provider tier is allowed
                        if self._is_provider_tier_allowed(provider):
                            providers_for_agent = [provider]
                            print(
                                f"[DEBUG] Persona '{persona}' -> explicit mapping to '{provider}'",
                                file=sys.stderr,
                                flush=True,
                            )
                            logger.debug(
                                f"Using provider '{provider}' for persona '{persona}' (explicit mapping)"
                            )
                        else:
                            logger.warning(
                                f"Provider '{provider}' for persona '{persona}' is not in allowed tiers, skipping"
                            )
                            continue
                    # Use tier-filtered providers if available
                    elif available_providers:
                        providers_for_agent = available_providers
                        provider_idx = i % len(available_providers)
                        print(
                            f"[DEBUG] Persona '{persona}' -> tier-filtered providers: {available_providers}",
                            file=sys.stderr,
                            flush=True,
                        )
                        logger.debug(
                            f"Using provider '{available_providers[provider_idx]}' for persona '{persona}' (round-robin [{provider_idx}], tier-filtered)"
                        )
                    # Use original llm_providers as fallback
                    elif self.llm_providers:
                        # Verify the selected provider tier is allowed
                        provider = self.llm_providers[i % len(self.llm_providers)]
                        if self._is_provider_tier_allowed(provider):
                            providers_for_agent = self.llm_providers
                            provider_idx = i % len(self.llm_providers)
                            print(
                                f"[DEBUG] Persona '{persona}' -> llm_providers fallback: {self.llm_providers}",
                                file=sys.stderr,
                                flush=True,
                            )
                            logger.debug(
                                f"Using provider '{provider}' for persona '{persona}' (round-robin [{provider_idx}])"
                            )
                        else:
                            print(
                                f"[DEBUG] Persona '{persona}' -> provider '{provider}' NOT allowed by tier",
                                file=sys.stderr,
                                flush=True,
                            )
                            logger.warning(
                                f"Provider '{provider}' is not in allowed tiers, skipping"
                            )
                            continue
                    else:
                        print(
                            f"[DEBUG] Persona '{persona}' -> NO providers available! persona_providers={self.persona_providers}, available={available_providers}, llm_providers={self.llm_providers}",
                            file=sys.stderr,
                            flush=True,
                        )

                    # Create or update LLMConfig with preferred_providers
                    if providers_for_agent:
                        print(
                            f"[DEBUG] Persona '{persona}' -> setting preferred_providers: {providers_for_agent}",
                            file=sys.stderr,
                            flush=True,
                        )
                        if agent_llm_config is None:
                            agent_llm_config = LLMConfig(preferred_providers=providers_for_agent)
                        else:
                            # Clone the config with preferred_providers added
                            agent_llm_config = LLMConfig(
                                allowed_tiers=agent_llm_config.allowed_tiers,
                                preferred_providers=providers_for_agent,
                                mock_mode=agent_llm_config.mock_mode,
                                timeout_seconds=agent_llm_config.timeout_seconds,
                            )

                # Pass llm_config to the agent
                agent = agent_class(llm_config=agent_llm_config)
                self.agents.append(agent)
            else:
                logger.warning(f"Unknown persona: {persona}, skipping")

        # Set total number of agents on each agent for idea distribution
        for agent in self.agents:
            if hasattr(agent, "_num_agents"):
                agent._num_agents = len(self.agents)

        self.metrics["agents_spawned"] = len(self.agents)
        logger.info(f"Spawned {len(self.agents)} agents: {', '.join(personas)}")

    async def _phase_diverge(
        self,
        context: BrainstormContext,
        timeout: float,
    ) -> list[Idea]:
        """
        Phase 1: Divergent Thinking - Generate ideas in parallel.

        Args:
            context: Brainstorm context
            timeout: Phase timeout in seconds

        Returns:
            List of generated ideas from all agents

        Note:
            Uses asyncio.wait() with FIRST_COMPLETED to collect results incrementally.
            This ensures completed ideas are captured even if timeout fires mid-execution.

        """
        ideas: list[Idea] = []
        # Create tasks from coroutines
        agent_tasks = [
            asyncio.create_task(self._run_agent_safely(agent, context)) for agent in self.agents
        ]
        remaining_tasks = set(agent_tasks)
        start_time = time.time()

        # Collect results incrementally until timeout or all complete
        while remaining_tasks:
            elapsed = time.time() - start_time
            remaining_timeout = timeout - elapsed

            if remaining_timeout <= 0:
                # Timeout reached - cancel remaining tasks
                for task in remaining_tasks:
                    task.cancel()
                logger.warning(
                    f"Cancelled {len(remaining_tasks)} pending agent tasks due to timeout"
                )
                break

            try:
                # Wait for at least one task to complete
                done, remaining_tasks = await asyncio.wait(
                    remaining_tasks,
                    timeout=remaining_timeout,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                # Collect results from completed tasks
                for task in done:
                    try:
                        result = task.result()
                        if isinstance(result, Exception):
                            logger.error(f"Agent failed: {result}")
                            self.metrics["errors"].append(str(result))
                        elif isinstance(result, list):
                            ideas.extend(result)
                            # Find agent index for callback
                            if task in agent_tasks:
                                idx = agent_tasks.index(task)
                                if self.on_persona_complete and idx < len(self.agents):
                                    persona_name = self.agents[idx].name
                                    self.on_persona_complete(persona_name, len(result))
                    except asyncio.CancelledError:
                        logger.warning("Agent task was cancelled")
                    except Exception as e:
                        logger.error(f"Agent task raised exception: {e}")
                        self.metrics["errors"].append(str(e))

            except Exception as e:
                logger.error(f"Unexpected error in diverge phase: {e}")
                break

        # Cancel any remaining tasks
        for task in remaining_tasks:
            task.cancel()

        completed_count = len(agent_tasks) - len(remaining_tasks)
        if len(remaining_tasks) > 0 or completed_count < len(agent_tasks):
            agent_names = [agent.name for agent in self.agents]
            logger.warning(
                f"Diverge phase: completed {completed_count}/{len(agent_tasks)} agents - "
                f"ideas collected: {len(ideas)}"
            )

        return ideas

    async def _phase_discuss(
        self,
        ideas: list[Idea],
        context: BrainstormContext,
        timeout: float,
    ) -> list[Evaluation]:
        """
        Phase 2: Discussion - Evaluate ideas through adversarial debate.

        Args:
            ideas: List of ideas to evaluate
            context: Brainstorm context
            timeout: Phase timeout in seconds

        Returns:
            List of evaluations for the ideas

        Note:
            If enable_full_debate is True, conducts full 3-round adversarial debate.
            Otherwise, falls back to basic evaluation.

        """
        evaluations: list[Evaluation] = []

        try:
            if self.enable_full_debate and self.debate_arena and len(self.agents) >= 2:
                # Use full adversarial debate framework
                logger.info("Phase 2: Conducting full adversarial debates...")

                debated_ideas = await asyncio.wait_for(
                    self.debate_arena.debate(
                        ideas=ideas, participants=self.agents, rounds=3, context=context
                    ),
                    timeout=timeout,
                )

                # Convert debated ideas to standard evaluations
                if debated_ideas:
                    for debated in debated_ideas:
                        evaluations.append(debated.to_evaluation())

                    self.metrics["debates_conducted"] = len(debated_ideas)
                    logger.info(f"Phase 2: Generated {len(evaluations)} evaluations from debates")
                else:
                    logger.warning(
                        "Phase 2: Debate returned no results, falling back to basic evaluation"
                    )
            elif self.enable_full_debate and len(self.agents) < 2:
                # Skip debate - need at least 2 participants
                logger.info(
                    f"Phase 2: Skipping debate (only {len(self.agents)} participant(s), "
                    f"need at least 2). Using basic evaluation..."
                )
                # Fall through to basic evaluation below

            if not evaluations:  # Only do basic evaluation if no debates conducted
                # Fallback to basic evaluation
                logger.info("Phase 2: Using basic evaluation (debate disabled)")

                # Create evaluation tasks for each idea
                tasks = [self._evaluate_idea_safely(idea, context) for idea in ideas]

                # Wait for all evaluations with timeout
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=timeout,
                )

                # Collect successful evaluations
                for result in results:
                    if isinstance(result, Exception):
                        logger.error(f"Evaluation failed: {result}")
                        self.metrics["errors"].append(str(result))
                    elif isinstance(result, Evaluation):
                        evaluations.append(result)

        except TimeoutError:
            logger.warning(
                f"Discuss phase timed out after {timeout}s - "
                f"ideas being evaluated: {len(ideas)}, "
                f"evaluations collected so far: {len(evaluations)}"
            )
            # Return whatever evaluations we have
            if not evaluations:
                raise

        # Graph-of-Thought analysis (enhancement)
        if self.enable_got:
            try:
                from ..got import GotEdgeAnalyzer, GotPlanner

                planner = GotPlanner()
                nodes = planner.extract_from_ideas(ideas)

                if nodes:
                    analyzer = GotEdgeAnalyzer()
                    edges = analyzer.analyze_relationships(nodes)
                    cycles = analyzer.detect_cycles()

                    self.got_analysis = {
                        "nodes": [
                            {"type": n.node_type, "content": n.content[:100]} for n in nodes[:20]
                        ],  # Limit for output
                        "edges": [
                            {
                                "from": e.source.node_type,
                                "to": e.target.node_type,
                                "relationship": e.relationship,
                            }
                            for e in edges[:10]
                        ],  # Limit for output
                        "cycles": len(cycles),
                        "summary": {
                            "total_nodes": len(nodes),
                            "total_edges": len(edges),
                            "cycles_detected": len(cycles),
                        },
                    }
                    logger.info(
                        f"GoT analysis: {len(nodes)} nodes, {len(edges)} edges, {len(cycles)} cycles"
                    )
            except ImportError:
                logger.warning("GoT modules not available, skipping analysis")
            except Exception as e:
                logger.warning(f"GoT analysis failed: {e}")

        return evaluations

    async def _phase_converge(
        self,
        result: BrainstormResult,
        timeout: float,
    ) -> None:
        """
        Phase 3: Advanced Convergence - Cluster, synthesize, and rank ideas.

        Uses the advanced convergence engine for:
        - Semantic clustering and deduplication
        - Idea synthesis from complementary ideas
        - Multi-criteria ranking with diversity assurance

        Args:
            result: BrainstormResult to update
            timeout: Phase timeout in seconds

        """
        try:
            # Create convergence config
            config = ConvergenceConfig(
                enable_clustering=True,
                enable_deduplication=True,
                enable_synthesis=len(result.ideas) > 5,  # Only synthesize if we have enough ideas
                similarity_threshold=0.75,
                complementarity_threshold=0.65,
                ranking_strategy=RankingStrategy.BALANCED,
                top_k=min(10, len(result.ideas)),  # Get top 10 or all if fewer
                diversity_threshold=0.3,
            )

            # Create convergence engine
            engine = ConvergenceEngine(config=config)

            # Run convergence pipeline
            converged_ideas, convergence_report = await engine.converge(
                ideas=result.ideas,
                evaluations=result.evaluations,
            )

            # Update result with converged ideas
            result.ideas.clear()

            for converged_idea in converged_ideas:
                # Update the idea score with the final convergence score
                converged_idea.idea.update_score(converged_idea.final_score)
                result.add_idea(converged_idea.idea)

                # Track synthesis metadata
                if converged_idea.is_synthesized:
                    if "synthesized_ideas" not in result.metadata:
                        result.metadata["synthesized_ideas"] = []
                    result.metadata["synthesized_ideas"].append(
                        {
                            "id": converged_idea.id,
                            "sources": converged_idea.synthesized_from,
                            "quality": converged_idea.synthesis_quality,
                        }
                    )

            # Store convergence report in metadata
            result.metadata["convergence_report"] = convergence_report.to_dict()

            # Tree-of-Thought analysis (enhancement)
            if self.enable_tot:
                try:
                    from ..tot import BranchGenerator

                    generator = BranchGenerator()
                    branches = generator.generate_for_ideas(result.ideas)
                    branches = generator.prune_unlikely(threshold=0.25)

                    if branches:
                        self.tot_branches = {
                            "total_branches": len(branches),
                            "by_type": {},
                            "by_likelihood": {},
                            "scenarios": [],
                        }

                        for branch in branches[:15]:  # Limit for output
                            self.tot_branches["scenarios"].append(
                                {
                                    "type": branch.branch_type,
                                    "likelihood": branch.likelihood,
                                    "description": branch.description[:150],
                                }
                            )
                            self.tot_branches["by_type"][branch.branch_type] = (
                                self.tot_branches["by_type"].get(branch.branch_type, 0) + 1
                            )
                            self.tot_branches["by_likelihood"][branch.likelihood] = (
                                self.tot_branches["by_likelihood"].get(branch.likelihood, 0) + 1
                            )

                        logger.info(
                            f"ToT analysis: {len(branches)} outcome scenarios "
                            f"({len(self.tot_branches['scenarios'])} shown)"
                        )
                except ImportError:
                    logger.warning("ToT modules not available, skipping analysis")
                except Exception as e:
                    logger.warning(f"ToT analysis failed: {e}")

            # Calculate quality metrics
            if result.ideas:
                avg_score = sum(idea.score for idea in result.ideas) / len(result.ideas)
                result.metadata["average_score"] = avg_score
                result.metadata["score_distribution"] = {
                    "min": min(idea.score for idea in result.ideas),
                    "max": max(idea.score for idea in result.ideas),
                    "median": sorted([idea.score for idea in result.ideas])[len(result.ideas) // 2],
                }

            logger.info(
                f"Advanced convergence complete: {len(result.ideas)} ideas, "
                f"{convergence_report.ideas_synthesized} synthesized, "
                f"{convergence_report.duplicates_removed} duplicates removed"
            )

        except Exception as e:
            logger.error(f"Error in advanced convergence: {e}")
            result.metadata["converge_error"] = str(e)

            # Fallback to basic convergence
            logger.info("Falling back to basic convergence...")
            for idea in result.ideas:
                evaluation = result.evaluations.get(idea.id)
                if evaluation:
                    idea.update_score(evaluation.overall_score)
                else:
                    idea.update_score(50.0)

            result.ideas.sort(key=lambda x: x.score, reverse=True)

    async def _run_agent_safely(
        self,
        agent: Agent,
        context: BrainstormContext,
    ) -> list[Idea]:
        """
        Run an agent with error handling.

        Args:
            agent: Agent to run
            context: Brainstorm context

        Returns:
            List of ideas generated by the agent

        Note:
            Catches and logs exceptions, returning empty list on failure.

        """
        try:
            ideas = await agent.generate_ideas(context)
            logger.debug(f"{agent.name} generated {len(ideas)} ideas")
            return ideas

        except Exception as e:
            logger.error(f"Error running agent {agent.name}: {e}", exc_info=True)
            return []

    async def _evaluate_idea_safely(
        self,
        idea: Idea,
        context: BrainstormContext,
    ) -> Evaluation:
        """
        Evaluate an idea with error handling.

        Args:
            idea: Idea to evaluate
            context: Brainstorm context

        Returns:
            Evaluation for the idea

        Note:
            For MVP, uses the first available agent for evaluation.
            Future versions will use multiple agents for consensus.

        """
        try:
            # Use the first available agent for evaluation (MVP approach)
            if self.agents:
                agent = self.agents[0]
                evaluation = await agent.evaluate_idea(idea)
                return evaluation

            # Fallback: Create a default evaluation
            return Evaluation.from_scores(
                idea_id=idea.id,
                novelty=50.0,
                feasibility=50.0,
                impact=50.0,
                evaluator="fallback",
            )

        except Exception as e:
            logger.error(f"Error evaluating idea {idea.id}: {e}", exc_info=True)
            # Return a default evaluation on error
            return Evaluation.from_scores(
                idea_id=idea.id,
                novelty=50.0,
                feasibility=50.0,
                impact=50.0,
                evaluator="error_fallback",
            )

    async def _store_result(self, session_id: str, result: BrainstormResult) -> None:
        """
        Store brainstorm result in memory.

        Args:
            session_id: Session identifier
            result: Result to store

        """
        try:
            # Store the full result
            key = f"session:{session_id}"
            await self.memory.store(
                key=key,
                value=result.model_dump(),
                layer=2,  # Store in L2 (disk cache)
                propagate=True,  # Also propagate to L3 if available
            )

            logger.debug(f"Stored result for session {session_id}")

        except Exception as e:
            logger.error(f"Failed to store result: {e}")

    async def _cleanup(self) -> None:
        """
        Cleanup after brainstorm session.

        Performs explicit cleanup of agent resources to prevent resource leaks
        across multiple brainstorm sessions. Agents are cleared to release LLM
        client connections and other resources they may hold.
        """
        self.phase = "idle"
        self.metrics["phase"] = "idle"

        # Explicitly clean up agent resources
        for agent in self.agents:
            try:
                # Check if agent has a cleanup method (for future extensibility)
                if hasattr(agent, "cleanup") and callable(agent.cleanup):
                    await agent.cleanup()
                    logger.debug(f"Cleaned up agent: {agent.name}")
            except Exception as e:
                logger.warning(f"Error cleaning up agent {agent.name}: {e}")

        # Clear agents list to release references
        self.agents.clear()
        logger.debug("All agents cleaned up and cleared")

    async def _track_model_performance(self, session_id: str, result: BrainstormResult) -> None:
        """
        Track model performance for a brainstorming session.

        Collects metrics about model usage and idea quality, then stores
        them in the performance tracker database for future model selection.

        Args:
            session_id: Session identifier
            result: Brainstorm result with ideas and evaluations

        """
        if not self.performance_tracker:
            return

        try:
            # Collect model usage from agents
            model_stats: dict[str, dict[str, Any]] = {}

            for agent in self.agents:
                # Get the agent's persona
                persona = agent.name

                # Try to get model usage info from the agent's LLM client
                if hasattr(agent, "llm_client"):
                    client = agent.llm_client

                    # Check if client has model usage tracking
                    if hasattr(client, "_model_usage") and client._model_usage:
                        # Aggregate usage by model
                        for usage in client._model_usage:
                            model = usage.get("model", "unknown")
                            provider = usage.get("provider", "unknown")

                            key = f"{provider}/{model}"
                            if key not in model_stats:
                                model_stats[key] = {
                                    "model_name": model,
                                    "provider": provider,
                                    "persona": persona,
                                    "latencies": [],
                                    "tokens": 0,
                                    "costs": 0.0,
                                    "idea_count": 0,
                                }

                            # Track metrics
                            if "latency_ms" in usage:
                                model_stats[key]["latencies"].append(usage["latency_ms"])
                            if "tokens_used" in usage:
                                model_stats[key]["tokens"] += usage["tokens_used"]
                            if "cost" in usage:
                                model_stats[key]["costs"] += usage["cost"]

                    # Clear model usage for next session
                    if hasattr(client, "_model_usage"):
                        client._model_usage.clear()

                # Count ideas generated by this agent
                agent_ideas = [idea for idea in result.ideas if idea.persona == persona]
                if model_stats:
                    # Update idea counts for all models this agent used
                    for stats in model_stats.values():
                        if stats["persona"] == persona:
                            stats["idea_count"] += len(agent_ideas)

            # If no model usage was tracked, fall back to session-level tracking
            if not model_stats and self.llm_config:
                # Use a generic entry based on session metrics
                model_stats["session"] = {
                    "model_name": "unknown",
                    "provider": "unknown",
                    "persona": "orchestrator",
                    "latencies": [],
                    "tokens": 0,
                    "costs": 0.0,
                    "idea_count": len(result.ideas),
                }

            # Calculate and record metrics for each model
            for _model_key, stats in model_stats.items():
                if stats["idea_count"] == 0:
                    continue

                # Calculate average latency
                avg_latency = (
                    sum(stats["latencies"]) / len(stats["latencies"]) if stats["latencies"] else 0.0
                )

                # Calculate idea quality scores
                ideas_by_model = [idea for idea in result.ideas if idea.persona == stats["persona"]]

                if not ideas_by_model:
                    continue

                # Get scores for ideas generated with this model/persona
                scores = []
                for idea in ideas_by_model:
                    # Use idea score if available
                    if idea.score > 0:
                        scores.append(idea.score)
                    # Otherwise use evaluation score if available
                    elif idea.id in result.evaluations:
                        eval_ = result.evaluations[idea.id]
                        scores.append(eval_.overall_score)

                avg_idea_score = sum(scores) / len(scores) if scores else 0.0
                top_idea_score = max(scores) if scores else 0.0

                # Create performance metrics
                metrics = ModelPerformanceMetrics(
                    model_name=stats["model_name"],
                    provider=stats["provider"],
                    session_id=session_id,
                    persona=stats["persona"],
                    ideas_generated=stats["idea_count"],
                    avg_idea_score=avg_idea_score,
                    top_idea_score=top_idea_score,
                    avg_latency_ms=avg_latency,
                    total_tokens=stats["tokens"],
                    total_cost=stats["costs"],
                    user_satisfaction=None,  # Could be added via user feedback later
                    timestamp=datetime.utcnow(),
                    metadata={
                        "total_ideas": len(result.ideas),
                        "total_evaluations": len(result.evaluations),
                        "session_duration": self.metrics.get("total_duration", 0.0),
                    },
                )

                # Record to database
                await self.performance_tracker.record_session(metrics)

                # Update model metadata in APIKeyManager (if available)
                if self.llm_config and hasattr(self, "agents") and self.agents:
                    try:
                        # Try to get API manager from first agent's client
                        if hasattr(self.agents[0], "llm_client"):
                            client = self.agents[0].llm_client
                            if hasattr(client, "_api_manager") and client._api_manager:
                                self.performance_tracker.update_model_info_in_provider(
                                    client._api_manager, stats["model_name"]
                                )
                    except Exception as e:
                        logger.warning(f"Could not update model metadata: {e}")

            logger.info(
                f"Recorded performance for {len(model_stats)} model(s) in session {session_id}"
            )

        except Exception as e:
            logger.warning(f"Error tracking model performance: {e}")

    def get_metrics(self) -> dict[str, Any]:
        """
        Get metrics from the last brainstorm session.

        Returns:
            Dictionary with execution metrics

        """
        return self.metrics.copy()

    def get_phase(self) -> str:
        """
        Get the current workflow phase.

        Returns:
            Current phase name ("diverge" | "discuss" | "converge" | "idle")

        """
        return self.phase


class _MockAgent(Agent):
    """
    Mock agent for MVP testing.

    Generates placeholder ideas and evaluations.
    This is a temporary implementation until real persona agents are created.
    Does NOT require LLM client or API keys.

    Attributes:
        _num_agents: Total number of agents (set by orchestrator)

    """

    def __init__(self, name: str | None = None, description: str | None = None):
        """Initialize mock agent WITHOUT LLM client (for testing)."""
        # Skip Agent.__init__ which requires API keys
        self.name = name or self.__class__.__name__
        self.description = description or "Mock agent for testing"
        self.llm_client = None  # Mock agents don't use LLM
        self.system_prompt = f"You are {self.name}, a mock testing agent."
        self._num_agents = 1  # Default, will be updated by orchestrator

    async def generate_ideas(self, context: BrainstormContext) -> list[Idea]:
        """Generate mock ideas based on the topic."""
        ideas = []
        # Calculate ideas per agent (div evenly among all agents)
        num_to_generate = max(1, context.num_ideas // self._num_agents)

        for i in range(num_to_generate):
            idea = Idea(
                content=f"[{self.name}] Idea {i + 1} for: {context.topic[:50]}...",
                persona=self.name,
                reasoning_path=[
                    f"Analyzed topic: {context.topic[:30]}...",
                    f"Applied {self.name} perspective",
                    f"Generated solution option {i + 1}",
                ],
                score=50.0,  # Will be updated during evaluation
                metadata={
                    "agent": self.name,
                    "context_topic": context.topic,
                },
            )
            ideas.append(idea)

        return ideas

    async def evaluate_idea(self, idea: Idea) -> Evaluation:
        """Generate mock evaluation for an idea."""
        # Generate pseudo-random scores based on idea ID
        import hashlib

        hash_val = int(hashlib.md5(idea.id.encode()).hexdigest(), 16)
        novelty = 40.0 + (hash_val % 50)  # 40-90
        feasibility = 40.0 + ((hash_val // 10) % 50)  # 40-90
        impact = 40.0 + ((hash_val // 100) % 50)  # 40-90

        return Evaluation.from_scores(
            idea_id=idea.id,
            novelty=novelty,
            feasibility=feasibility,
            impact=impact,
            arguments_pro=[
                f"Strong potential in {self.name} perspective",
                "Aligns with core objectives",
            ],
            arguments_con=[
                f"May face challenges from {self.name} viewpoint",
                "Requires further validation",
            ],
            evaluator=self.name,
        )


__all__ = ["BrainstormOrchestrator"]
