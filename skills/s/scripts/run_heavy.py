#!/usr/bin/env python3
"""
Deterministic heavy-mode runner for /s.

Provides:
- Real orchestrator execution (BrainstormOrchestrator)
- Structured output modes (json|markdown|text)
- Constitutional filtering of recommendations
- /q context + session activity topic inference
- Decision memo + follow-up command hints
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import profile config (available after _ensure_import_paths() sets up path)
# This import is delayed until needed to avoid import errors
_profile_config = None


def _get_profile_config():
    """Lazy load profile config module."""
    global _profile_config
    if _profile_config is None:
        from profiles import config

        _profile_config = config
    return _profile_config


# Import ProgressReporter for real-time progress reporting

DEFAULT_PERSONAS = ["innovator", "pragmatist", "critic", "expert", "synthesizer"]
ALLOWED_PERSONAS = set(DEFAULT_PERSONAS) | {"futurist"}


@dataclass
class ErrorResponse:
    """Standardized error response format for /s skill."""

    error: str
    message: str
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        result = {
            "error": self.error,
            "message": self.message,
        }
        if self.details:
            result.update(self.details)
        return result


def build_error_response(error_type: str, message: str, **details: Any) -> ErrorResponse:
    """
    Build a standardized error response.

    Args:
        error_type: Short error identifier (e.g., "unknown_personas", "invalid_tiers")
        message: Human-readable error message
        **details: Additional error-specific fields

    Returns:
        ErrorResponse object ready for JSON serialization
    """
    return ErrorResponse(error=error_type, message=message, details=details if details else None)


@dataclass
class TopicSelection:
    topic: str
    source: str
    confidence: float
    stale_context: bool = False
    stale_reason: str | None = None
    notes: list[str] | None = None


class InMemoryBrainstormMemory:
    """
    Minimal async memory adapter used by /s runner.

    Intentionally avoids disk/DB/CKS layers to keep heavy-mode execution
    deterministic and free of cache-related filesystem complexity.
    """

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    async def store(
        self,
        key: str,
        value: Any,
        layer: int = 1,
        propagate: bool = False,
    ) -> bool:
        self._store[key] = value
        return True


def _ensure_import_paths() -> None:
    # Insert in reverse so final priority is: P:/, P:/__csf, P:/__csf/src, P:/.claude/skills/s
    for candidate in ("P:/__csf/src", "P:/__csf", "P:/.claude/skills/s", "P:/"):
        if candidate not in sys.path:
            sys.path.insert(0, candidate)


def parse_personas(value: str | None) -> list[str]:
    """Parse personas from CSV string. Returns list of personas, does NOT validate."""
    if not value:
        return DEFAULT_PERSONAS.copy()
    parts = [p.strip().lower() for p in value.split(",") if p.strip()]
    if not parts:
        return DEFAULT_PERSONAS.copy()
    return parts


def _extract_work_summary(ctx: dict[str, Any]) -> str:
    if not isinstance(ctx, dict):
        return ""
    if "work_summary" in ctx:
        return str(ctx.get("work_summary", "")).strip()
    analysis = ctx.get("analysis", {})
    if isinstance(analysis, dict):
        return str(analysis.get("work_summary", "")).strip()
    return ""


def read_q_context_compat(wt_session: str) -> dict[str, Any] | None:
    """
    Normalize q_context across both known APIs:
    - read_context(session_id, check_stale=True) -> analysis dict with stale info
    - read_context() + check_staleness(context) -> raw context dict
    """
    _ensure_import_paths()
    try:
        import lib.q_context as qmod
    except Exception:
        return None

    read_context = getattr(qmod, "read_context", None)
    if read_context is None:
        return None

    try:
        sig = inspect.signature(read_context)
        params = set(sig.parameters.keys())
    except Exception:
        params = set()

    try:
        if "session_id" in params or "check_stale" in params:
            raw = read_context(wt_session, check_stale=True)
            if raw is None:
                return None
            work_summary = _extract_work_summary(raw)
            stale = raw.get("stale", {}) if isinstance(raw, dict) else {}
            return {
                "work_summary": work_summary,
                "stale": {
                    "is_stale": bool(stale.get("is_stale", False)),
                    "reason": stale.get("reason"),
                },
            }

        # Legacy form: read_context() only
        raw = read_context()
        if raw is None:
            return None
        is_stale = False
        reason = None
        check_staleness = getattr(qmod, "check_staleness", None)
        if callable(check_staleness):
            try:
                is_stale = bool(check_staleness(raw))
                if is_stale:
                    reason = "q_context check_staleness() returned True"
            except Exception:
                is_stale = False
        return {
            "work_summary": _extract_work_summary(raw),
            "stale": {"is_stale": is_stale, "reason": reason},
        }
    except Exception:
        return None


def _infer_topic_from_files(files: list[str]) -> str:
    if not files:
        return "No session activity found"
    tokens: list[str] = []
    for f in files[:12]:
        p = f.replace("\\", "/").strip("/")
        parts = [x for x in p.split("/") if x and x not in ("src", "__csf", ".claude")]
        if parts:
            tokens.append(parts[-2] if len(parts) >= 2 else parts[-1])
            stem = parts[-1].split(".")[0]
            if stem:
                tokens.append(stem)
    # Stable de-dup preserve order
    seen = set()
    ordered = []
    for t in tokens:
        t = t.replace("_", " ").replace("-", " ").strip()
        if t and t not in seen:
            seen.add(t)
            ordered.append(t)
    if not ordered:
        return "Recent session file edits"
    return f"Session focus: {'; '.join(ordered[:4])}"


def get_session_activity_compat(wt_session: str) -> dict[str, Any]:
    _ensure_import_paths()

    # Preferred if available in q_context module.
    try:
        import lib.q_context as qmod

        get_session_activity = getattr(qmod, "get_session_activity", None)
        if callable(get_session_activity):
            return get_session_activity(wt_session)
    except Exception:
        pass

    # Fallback to session activity tracker files.
    try:
        from src.modules.session_management.session_activity_tracker import (
            get_session_files,
        )

        sid = f"wt_{wt_session[:8]}" if wt_session else None
        files = get_session_files(session_id=sid, operation_filter=["edit", "write"])
        return {
            "terminal": wt_session[:8] + "..." if wt_session else "unknown",
            "topic": _infer_topic_from_files(files),
            "files_worked": files[:5],
            "domains": {},
        }
    except Exception:
        return {
            "terminal": "unknown",
            "topic": "No session activity found",
            "files_worked": [],
            "domains": {},
        }


def apply_constitutional_filter(
    ideas: list[dict[str, Any]],
    checker: Callable[[str], Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    allowed: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for idea in ideas:
        content = str(idea.get("content", ""))
        verdict = checker(content)
        violates = bool(getattr(verdict, "violates_constitution", False))
        if violates:
            rejected.append(
                {
                    "content": content,
                    "reason": getattr(verdict, "reason", None),
                    "alternative": getattr(verdict, "alternative", None),
                }
            )
        else:
            allowed.append(idea)
    return allowed, rejected


def choose_topic(
    explicit_topic: str | None,
    wt_session: str,
    q_reader: Callable[..., dict[str, Any] | None] | None = None,
    session_activity_reader: Callable[..., dict[str, Any]] | None = None,
    brainstorm_context_infer: Callable[[], str | None] | None = None,
) -> TopicSelection:
    notes: list[str] = []

    if explicit_topic and explicit_topic.strip():
        return TopicSelection(
            topic=explicit_topic.strip(),
            source="explicit",
            confidence=1.0,
            notes=notes,
        )

    q_data = q_reader(wt_session) if q_reader else None
    if q_data:
        stale = q_data.get("stale", {}) if isinstance(q_data, dict) else {}
        work_summary = str(q_data.get("work_summary", "")).strip()
        if stale.get("is_stale"):
            reason = str(stale.get("reason", "unknown"))
            notes.append(f"/q context is stale: {reason}")
            notes.append("Recommend running /q to refresh context.")
            if work_summary:
                return TopicSelection(
                    topic=work_summary,
                    source="q_context_stale",
                    confidence=0.65,
                    stale_context=True,
                    stale_reason=reason,
                    notes=notes,
                )
        elif work_summary:
            return TopicSelection(
                topic=work_summary,
                source="q_context",
                confidence=0.9,
                notes=notes,
            )

    if session_activity_reader:
        activity = session_activity_reader(wt_session)
        inferred = str(activity.get("topic", "")).strip()
        if inferred and "No session activity found" not in inferred:
            return TopicSelection(
                topic=inferred,
                source="session_activity",
                confidence=0.75,
                notes=notes,
            )

    if brainstorm_context_infer:
        inferred = brainstorm_context_infer()
        if inferred:
            return TopicSelection(
                topic=inferred.strip(),
                source="chat_context",
                confidence=0.6,
                notes=notes,
            )

    return TopicSelection(
        topic="General strategic brainstorming",
        source="fallback",
        confidence=0.4,
        notes=notes,
    )


def build_decision_memo(
    topic: str,
    allowed_ideas: list[dict[str, Any]],
    rejected_ideas: list[dict[str, Any]],
) -> dict[str, Any]:
    decision = (
        allowed_ideas[0]["content"]
        if allowed_ideas
        else "No constitutionally compliant recommendation."
    )
    alternatives = [i["content"] for i in allowed_ideas[1:3]]
    why_not = [r["reason"] for r in rejected_ideas[:2] if r.get("reason")]
    risks = []
    if rejected_ideas:
        risks.append("Some top ideas violated solo-dev constitutional constraints.")
    if not allowed_ideas:
        risks.append("No allowed ideas remained after constitutional filtering.")
    rollback = "Re-run /s --mode heavy --ideas 20 with narrower constraints and re-evaluate."
    return {
        "decision": decision,
        "alternatives": alternatives,
        "why_not": why_not,
        "risks": risks,
        "rollback": rollback,
        "topic": topic,
    }


def classify_result(allowed_ideas: list[dict[str, Any]], top_score: float) -> str:
    if not allowed_ideas:
        return "risky_or_blocked"
    if top_score >= 80:
        return "high_confidence_plan"
    return "exploratory"


def build_follow_up_hints(result_type: str, top_idea_text: str) -> list[str]:
    hints: list[str] = []
    idea_lower = top_idea_text.lower()

    if result_type == "high_confidence_plan":
        hints.extend(["/planning", "/nse"])
    elif result_type == "risky_or_blocked":
        hints.extend(["/r", "/design", "/nse"])
    else:
        hints.extend(["/planning", "/r"])

    if any(k in idea_lower for k in ("architecture", "system", "design", "module boundary")):
        if "/design" not in hints:
            hints.append("/design")
    if "/nse" not in hints:
        hints.append("/nse")

    out: list[str] = []
    for cmd in hints:
        if cmd not in out:
            out.append(cmd)
    return out


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Strategic Brainstorm Results: {payload['topic']}",
        "",
        f"- Session ID: `{payload['session_id']}`",
        f"- Topic source: `{payload['topic_source']}` ({payload['topic_confidence']:.2f})",
        f"- Result type: `{payload['result_type']}`",
    ]

    # Add context framing message
    if payload["topic_source"] in ("q_context", "session_activity", "chat_context"):
        lines.append(
            f"- **Context**: Applying strategic thinking to ongoing work based on {payload['topic_source']}"
        )

    lines.extend(
        [
            "",
            "## Top Ideas",
        ]
    )
    for i, idea in enumerate(payload["top_ideas"], 1):
        lines.append(f"{i}. [{idea['score']:.0f}/100] {idea['content']}")
    lines.extend(
        [
            "",
            "## Decision Memo",
            f"- Decision: {payload['decision_memo']['decision']}",
            f"- Alternatives: {', '.join(payload['decision_memo']['alternatives']) or 'None'}",
            f"- Why not: {', '.join(payload['decision_memo']['why_not']) or 'None'}",
            f"- Risks: {', '.join(payload['decision_memo']['risks']) or 'None'}",
            f"- Rollback: {payload['decision_memo']['rollback']}",
            "",
            "## Next Commands",
        ]
    )
    for cmd in payload["next_commands"]:
        lines.append(f"- {cmd}")
    return "\n".join(lines)


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"Strategic Brainstorm: {payload['topic']}",
        f"Session: {payload['session_id']}",
        f"Source: {payload['topic_source']} ({payload['topic_confidence']:.2f})",
        f"Type: {payload['result_type']}",
    ]

    # Add context framing
    if payload["topic_source"] in ("q_context", "session_activity", "chat_context"):
        lines.append(
            f"Context: Strategic analysis of ongoing work (from {payload['topic_source']})"
        )

    lines.extend(
        [
            "",
            "Top Ideas:",
        ]
    )
    for i, idea in enumerate(payload["top_ideas"], 1):
        lines.append(f"{i}. [{idea['score']:.0f}/100] {idea['content']}")
    lines.extend(
        [
            "",
            "Decision Memo:",
            f"Decision: {payload['decision_memo']['decision']}",
            f"Alternatives: {', '.join(payload['decision_memo']['alternatives']) or 'None'}",
            f"Risks: {', '.join(payload['decision_memo']['risks']) or 'None'}",
            f"Rollback: {payload['decision_memo']['rollback']}",
            "",
            "Next Commands: " + ", ".join(payload["next_commands"]),
        ]
    )
    return "\n".join(lines)


def render_mermaid_diagram(payload: dict[str, Any]) -> str:
    """Generate a Mermaid Mindmap diagram of the brainstorm results."""
    # Escape quotes for Mermaid
    topic = str(payload.get("topic", "Brainstorm")).replace('"', "'").replace("\n", " ")
    if len(topic) > 60:
        topic = topic[:57] + "..."

    lines = ["```mermaid", "mindmap", f"  root(({topic}))"]

    # Add top ideas as branches
    for idea in payload.get("top_ideas", [])[:5]:  # Limit to top 5 for clarity
        content = str(idea.get("content", "")).replace('"', "'").replace("\n", " ")
        if len(content) > 50:
            content = content[:47] + "..."
        lines.append(f"    {content}")

        # Add persona as sub-branch
        persona = idea.get("persona", "unknown")
        lines.append(f"      {persona}")

    # Add decision as a highlighted branch
    decision_memo = payload.get("decision_memo", {})
    decision = str(decision_memo.get("decision", "None")).replace('"', "'").replace("\n", " ")
    if len(decision) > 50:
        decision = decision[:47] + "..."
    lines.append("    ))Chosen Decision((")
    lines.append(f"      {decision}")

    lines.append("```")
    return "\n".join(lines)


def build_payload(
    topic_meta: TopicSelection,
    result: Any,
    allowed_ideas: list[dict[str, Any]],
    rejected_ideas: list[dict[str, Any]],
) -> dict[str, Any]:
    top_ideas = sorted(allowed_ideas, key=lambda x: float(x.get("score", 0)), reverse=True)[:7]
    top_score = float(top_ideas[0]["score"]) if top_ideas else 0.0
    result_type = classify_result(top_ideas, top_score)
    top_text = top_ideas[0]["content"] if top_ideas else ""
    decision_memo = build_decision_memo(topic_meta.topic, top_ideas, rejected_ideas)
    next_commands = build_follow_up_hints(result_type, top_text)

    return {
        "session_id": getattr(result, "session_id", ""),
        "topic": topic_meta.topic,
        "topic_source": topic_meta.source,
        "topic_confidence": topic_meta.confidence,
        "stale_context": topic_meta.stale_context,
        "stale_reason": topic_meta.stale_reason,
        "notes": topic_meta.notes or [],
        "metrics": getattr(result, "metadata", {}).get("metrics", {}),
        "top_ideas": top_ideas,
        "filtered_out": rejected_ideas,
        "result_type": result_type,
        "decision_memo": decision_memo,
        "next_commands": next_commands,
    }


async def check_provider_health_gate(
    min_healthy: int = 2,
    timeout: float = 10.0,
    show_models: bool = False,
) -> tuple[bool, list[str], str]:
    """
    Provider health gate - check providers are available before brainstorming.

    Args:
        min_healthy: Minimum number of healthy providers required (default: 2 for diversity)
        timeout: Health check timeout for API providers (default: 10s). CLI providers get 30s.

    Returns:
        Tuple of (passed, healthy_providers, message)
        - passed: True if enough healthy providers available
        - healthy_providers: List of healthy provider IDs
        - message: Status message for logging
    """
    from llm.providers import ProviderConfig, ProviderFactory, get_registry
    from llm.providers.health_monitor import HealthMonitor, HealthStatus

    # Get all registered providers
    registry = get_registry()
    available_providers = registry.get_providers()

    if not available_providers:
        return False, [], "❌ No providers detected in registry"

    # Create provider instances for health checking with adaptive timeouts
    provider_instances = []
    for provider_name in available_providers:
        try:
            # CLI providers need longer timeouts (300s vs 10s for API)
            is_cli = any(provider_name.endswith(suffix) for suffix in ["-cli", "cli"])
            provider_timeout = 300.0 if is_cli else timeout

            config = ProviderConfig(
                provider_type=provider_name,
                timeout=provider_timeout,
            )
            provider = ProviderFactory.create_provider(provider_name, config)
            provider_instances.append(provider)
        except Exception as e:
            # Provider failed to instantiate - consider it unhealthy
            print(
                f"[/s] ⚠️ Provider {provider_name} failed to instantiate: {e}",
                file=sys.stderr,
                flush=True,
            )
            continue

    if not provider_instances:
        return (
            False,
            [],
            f"❌ No providers could be instantiated (tried {len(available_providers)})",
        )

    # Run health checks
    monitor = HealthMonitor(providers=provider_instances)
    results = await monitor.check_all_providers()

    # Filter healthy providers
    healthy_providers = [
        provider_id
        for provider_id, result in results.items()
        if result.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)
    ]

    # Build enhanced status message
    total = len(results)
    healthy_count = len(healthy_providers)
    unhealthy_count = total - healthy_count

    status_lines = [
        "",
        "=" * 60,
        "[/s] Provider Health Check",
        "=" * 60,
        "",
    ]

    # Group by status (not tier)
    healthy_list = []
    unhealthy_list = []
    for provider_id, result in results.items():
        if result.status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED):
            healthy_list.append((provider_id, result))
        else:
            unhealthy_list.append((provider_id, result))

    # Display healthy providers
    if healthy_list:
        status_lines.append("  ✓ Healthy Providers:")
        for provider_id, result in healthy_list:
            emoji = "✓" if result.status == HealthStatus.HEALTHY else "⚠"
            status_text = result.status.value.upper()
            time_text = f"{result.response_time_ms:.0f}ms"

            # Show error if present
            error_text = ""
            if result.error:
                if "timeout" in result.error.lower():
                    error_text = " — TIMEOUT"
                elif "empty" in result.error.lower():
                    error_text = " — EMPTY RESPONSE"
                else:
                    error_text = f" — {result.error}"

            status_lines.append(
                f"    {emoji} {provider_id:<15} {status_text:<10} ({time_text}){error_text}"
            )

        status_lines.append("")

    # Display unhealthy providers
    if unhealthy_list:
        status_lines.append("  ✗ Unhealthy Providers:")
        for provider_id, result in unhealthy_list:
            status_text = result.status.value.upper()

            # Show error if present
            error_text = ""
            if result.error:
                if "timeout" in result.error.lower():
                    error_text = " — TIMEOUT"
                elif "empty" in result.error.lower():
                    error_text = " — EMPTY RESPONSE"
                else:
                    error_text = f" — {result.error}"

            status_lines.append(f"    ✗ {provider_id:<15} {status_text:<10}{error_text}")

        status_lines.append("")

    # Summary line
    status_lines.extend(
        [
            "-" * 60,
            f"Summary: {healthy_count} healthy, {unhealthy_count} unhealthy",
        ]
    )

    if healthy_count >= min_healthy:
        status_lines.append(f"✓ Using {healthy_count} providers for brainstorming")
    else:
        status_lines.append(
            f"✗ Need {min_healthy} healthy providers, only {healthy_count} available"
        )

    status_lines.append("=" * 60)

    message = "\n".join(status_lines)

    # Show models if requested (appends to existing formatted message)
    if show_models and healthy_providers:
        model_lines = [
            "",
            "[/s] Available Models (Healthy Providers Only):",
            "",
        ]
        for provider in provider_instances:
            provider_id = provider.config.provider_type
            if provider_id not in healthy_providers:
                continue  # Only show models for healthy providers

            # Try to get models from provider capability
            try:
                capability = provider._get_capability()
                models = capability.models if capability else []
                if models:
                    # Show first 3 models with "..." if more
                    display_models = models[:3]
                    if len(models) > 3:
                        display_models.append(f"... (+{len(models) - 3} more)")
                    model_lines.append(f"  {provider_id}: {', '.join(display_models)}")
                else:
                    model_lines.append(f"  {provider_id}: (auto-discover at runtime)")
            except Exception as e:
                model_lines.append(f"  {provider_id}: (unable to list models: {e})")

        message += "\n".join(model_lines)

    # Check if we have enough healthy providers
    if healthy_count < min_healthy:
        message += (
            f"\n\n✗ Failed: Need {min_healthy} healthy providers, only {healthy_count} available"
        )
        message += "\n  Suggestion: Use --local-only flag or --provider-tier T1 for best results"
        return False, healthy_providers, message

    # Success message already included in summary above
    return True, healthy_providers, message


async def run_heavy(
    topic_meta: TopicSelection,
    personas: list[str],
    timeout: float,
    num_ideas: int,
    use_mock: bool = False,  # Default to REAL agents, not mocks
    local_repetition: int = 2,  # Run N times with local LLM personas for diversity (default: 2 for quality)
    llm_config=None,  # Optional LLM config
    debate_mode: str = "fast",  # Debate mode: "none", "full", "fast" (default: fast for quality)
    enable_pheromone_trail: bool = False,  # Enable pheromone trails
    enable_replay_buffer: bool = False,  # Enable replay buffer
    enable_got: bool = True,  # Enable Graph-of-Thought analysis (default: True for quality)
    enable_tot: bool = True,  # Enable Tree-of-Thought analysis (default: True for quality)
    skip_health_gate: bool = False,  # Skip provider health check (for debugging)
    show_models: bool = False,  # Show which models each provider will use
    auto_confirm: bool = False,  # Skip confirmation prompt and auto-continue
    quiet: bool = False,  # Suppress progress reporting
) -> Any:
    _ensure_import_paths()
    from lib.orchestrator import BrainstormOrchestrator

    # Provider Health Gate - check before starting brainstorm
    healthy_providers = None  # Initialize for later use
    if not skip_health_gate and not use_mock:
        health_passed, healthy_providers, health_message = await check_provider_health_gate(
            min_healthy=2,
            timeout=10.0,
            show_models=show_models,
        )
        print(health_message, file=sys.stdout, flush=True)

        if not health_passed:
            # Build error response
            error_response = {
                "error": "provider_health_gate_failed",
                "message": f"Not enough healthy providers available ({len(healthy_providers)} < 2 required)",
                "healthy_providers": healthy_providers,
                "suggestion": "Try: /s 'your topic' --local-only (use local agents only) or check API keys",
            }
            raise ValueError(f"Provider health gate failed: {error_response['message']}")

        # Phase 0b: User approval gate - show eligible models and wait for confirmation
        if not auto_confirm:
            # Recreate provider instances to get model info
            from llm.providers import ProviderConfig, ProviderFactory

            approval_prompt = "\n" + "=" * 60 + "\n"
            approval_prompt += "[/s] PHASE 0: MODEL APPROVAL\n"
            approval_prompt += "=" * 60 + "\n\n"
            approval_prompt += f"Healthy providers ready: {', '.join(healthy_providers)}\n\n"
            approval_prompt += "Models to be used:\n"

            # Show models per healthy provider
            for provider_id in healthy_providers:
                try:
                    config = ProviderConfig(provider_type=provider_id, timeout=30.0)
                    provider_instance = ProviderFactory.create_provider(provider_id, config)
                    capability = provider_instance._get_capability()
                    models = capability.models if capability else []
                    if models:
                        model_lines = ", ".join(models[:5])
                        if len(models) > 5:
                            model_lines += f" (+{len(models) - 5} more)"
                        approval_prompt += f"  • {provider_id}: {model_lines}\n"
                    else:
                        approval_prompt += f"  • {provider_id}: (auto-discover at runtime)\n"
                except Exception:
                    approval_prompt += f"  • {provider_id}: (model list unavailable)\n"

            approval_prompt += "\n" + "-" * 60 + "\n"
            approval_prompt += "Proceed with these models? [y/n]: "
            print(approval_prompt, file=sys.stdout, flush=True)

            # Read user response
            try:
                response = sys.stdin.readline().strip().lower()
                if response not in ("y", "yes"):
                    print("\n[/s] Brainstorm cancelled by user.", file=sys.stdout, flush=True)
                    return {
                        "status": "cancelled",
                        "reason": "user_declined",
                        "healthy_providers": healthy_providers,
                    }
            except EOFError:
                # Non-interactive environment - auto-proceed
                print(
                    "[/s] Non-interactive mode detected, auto-proceeding...",
                    file=sys.stdout,
                    flush=True,
                )

    memory = InMemoryBrainstormMemory()

    # Configure debate mode
    debate_enabled = debate_mode != "none"

    # Initialize progress reporter with quiet mode support
    from progress_reporter import ProgressReporter

    progress_reporter = ProgressReporter(verbose=not quiet)
    progress_reporter.reset()

    # Use healthy providers from health gate (if available) to filter out unhealthy providers
    # This ensures round-robin provider selection only uses providers that passed health check
    providers_to_use = healthy_providers if not skip_health_gate and not use_mock else None

    orchestrator = BrainstormOrchestrator(
        memory=memory,
        enable_full_debate=debate_enabled,
        llm_config=llm_config,
        llm_providers=providers_to_use,  # Pass healthy providers for round-robin selection
        use_mock_agents=use_mock,
        enable_pheromone_trail=enable_pheromone_trail,
        enable_replay_buffer=enable_replay_buffer,
        enable_got=enable_got,
        enable_tot=enable_tot,
        on_phase_start=lambda phase, items=0: progress_reporter.phase_start(phase, items),
        on_persona_complete=lambda persona, count: progress_reporter.persona_complete(
            persona, count
        ),
        on_phase_complete=lambda phase, count: progress_reporter.phase_complete(phase, count),
    )

    # If local repetition requested, run multiple times with persona variations
    if local_repetition > 0:
        all_ideas = []
        print(
            f"[/s] Running {local_repetition} brainstorming iterations...",
            file=sys.stderr,
            flush=True,
        )
        for iteration in range(local_repetition):
            print(
                f"[/s]   Iteration {iteration + 1}/{local_repetition}...",
                file=sys.stderr,
                flush=True,
            )
            # Vary the seed prompt slightly for diversity
            varied_prompt = _add_persona_variation(topic_meta.topic, iteration)
            result = await orchestrator.brainstorm(
                prompt=varied_prompt,
                personas=personas,
                timeout=timeout,
                num_ideas=num_ideas,
                fresh_mode=True,  # Always use fresh mode for repetition
            )
            all_ideas.extend(getattr(result, "ideas", []))
        print(f"[/s]   Synthesizing {len(all_ideas)} ideas...", file=sys.stderr, flush=True)

        # Deduplicate and return merged result
        result = await orchestrator.brainstorm(
            prompt=topic_meta.topic,
            personas=["synthesizer"],  # Use synthesizer to merge
            timeout=60.0,
            num_ideas=num_ideas,
            fresh_mode=False,
        )
        # Merge all ideas into result
        result.ideas = all_ideas
        return result

    return await orchestrator.brainstorm(
        prompt=topic_meta.topic,
        personas=personas,
        timeout=timeout,
        num_ideas=num_ideas,
        fresh_mode=False,
    )


def _add_persona_variation(base_topic: str, iteration: int) -> str:
    """
    Add persona variation prompts to encourage diverse thinking.

    Variations rotate through:
    - First-principles thinking (break assumptions)
    - Lateral thinking (random entry points)
    - SCAMPER (Substitute, Combine, Adapt, etc.)
    """
    variations = [
        "\n\nAPPROACH CONSTRAINT: Use first-principles thinking. List 3 assumptions everyone makes about this problem. Then challenge each one with a counter-approach.",
        "\n\nAPPROACH CONSTRAINT: Use lateral thinking. Take this problem and apply it to a completely different domain (cooking, sports, nature). What does that analogy suggest?",
        "\n\nAPPROACH CONSTRAINT: Use SCAMPER. Answer these 3 questions: 1) What component could be removed? 2) What two things could be combined? 3) What if this was used for the opposite purpose?",
        "\n\nAPPROACH CONSTRAINT: Use reverse engineering. Fast-forward 2 years: this problem is solved. What does the solution look like? Now list the 3 steps that happened right before that success.",
        "\n\nAPPROACH CONSTRAINT: Use Six Thinking Hats. Give me 3 perspectives: 1) The skeptic's biggest worry, 2) The optimist's dream outcome, 3) The creative wildest idea.",
    ]
    variation = variations[iteration % len(variations)]
    return f"{base_topic}{variation}"


def result_ideas_to_dicts(result: Any) -> list[dict[str, Any]]:
    ideas = []
    for idea in getattr(result, "ideas", []):
        ideas.append(
            {
                "content": str(getattr(idea, "content", "")),
                "score": float(getattr(idea, "score", 0.0)),
                "persona": str(getattr(idea, "persona", "")),
                "reasoning_path": list(getattr(idea, "reasoning_path", []) or []),
            }
        )
    return ideas


def read_context_path(context_path: str) -> str:
    """Recursively read all files from a directory and format as context."""
    import pathlib

    # Path traversal protection: reject any path containing ".."
    if ".." in context_path:
        return ""

    root = pathlib.Path(context_path).resolve()
    if not root.exists():
        return ""
    if root.is_file():
        try:
            content = root.read_text(encoding="utf-8", errors="replace")
            return f"--- {root.name} ---\n{content}\n"
        except Exception:
            return ""

    # Count files and estimate size first for progress/warning
    files_to_read = []
    total_size = 0
    for fp in sorted(root.rglob("*")):
        if not fp.is_file():
            continue
        if fp.suffix in (
            ".pyc",
            ".pyo",
            ".so",
            ".dll",
            ".exe",
            ".bin",
            ".db",
            ".sqlite",
            ".whl",
            ".egg",
            ".tar",
            ".gz",
            ".zip",
        ):
            continue
        # Skip cache and build directories
        skip_dirs = {
            "venv",
            ".venv",
            "__pycache__",
            "node_modules",
            ".git",
            ".pytest_cache",
            ".mypy_cache",
            "dist",
            "build",
            ".tox",
            "coverage",
            "htmlcov",
            ".ruff_cache",
            ".vscode",
            ".idea",
            ".claude",
            "site-packages",
        }
        if any(part in skip_dirs for part in fp.parts):
            continue
        try:
            # Symlink traversal protection: resolve and verify stays within root
            resolved = fp.resolve()
            if not str(resolved).startswith(str(root)):
                continue
            total_size += fp.stat().st_size
            files_to_read.append(fp)
        except Exception:
            continue

    # Warn for large context
    size_mb = total_size / (1024 * 1024)
    if size_mb > 100 or len(files_to_read) > 50:
        print(
            f"[⚠️]  Large context: {len(files_to_read)} files, {size_mb:.0f}MB — this may take 60+ seconds...",
            file=sys.stderr,
            flush=True,
        )

    # Show progress
    print(
        f"[/s] Reading {len(files_to_read)} files from {context_path}...",
        file=sys.stderr,
        flush=True,
    )

    chunks: list[str] = []
    for i, fp in enumerate(files_to_read, 1):
        if i % 20 == 0 or i == len(files_to_read):  # Progress every 20 files
            print(f"[/s]   {i}/{len(files_to_read)} files read...", file=sys.stderr, flush=True)
        try:
            text = fp.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel = fp.relative_to(root)
        chunks.append(f"--- {rel} ---\n{text}")
    return "\n".join(chunks)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    # Check for list/help keywords BEFORE argparse processing
    # This handles: /s list (show models), /s help, /s --help, etc.
    # Use sys.argv[1:] when argv is None to capture command line args
    check_args = argv if argv is not None else sys.argv[1:]
    if check_args:
        # Handle "list" keyword - show available models (NOT flags/help)
        if any(arg.lower() == "list" for arg in check_args):
            from display import _display_free_models

            refresh = any(arg.lower() in ("refresh", "--refresh", "-r") for arg in check_args)
            markdown_output = _display_free_models(refresh=refresh)
            # Print markdown for response inclusion
            print(markdown_output)
            os._exit(0)  # Exit immediately after showing model list

        # Handle help keywords
        help_keywords = {"help", "--help", "-h", "options", "?"}
        for arg in check_args:
            if arg.lower() in help_keywords:
                _display_help_and_exit()

    parser = argparse.ArgumentParser(description="Run /s heavy mode deterministically.")
    parser.add_argument(
        "topic",
        nargs="?",
        default="",
        help="Topic for brainstorming. Special value 'list' shows available models. If omitted, infer from /q/session activity.",
    )
    parser.add_argument(
        "--topic", default="", help="Explicit topic. Overrides positional topic argument."
    )
    parser.add_argument(
        "--context-path",
        default="",
        help="Path to directory or file. All contents are included as context for the brainstorm.",
    )
    parser.add_argument("--personas", default="", help="Comma-separated personas.")
    parser.add_argument(
        "--profile",
        default="",
        choices=["fast", "normal", "deep"],
        help="Use a preset profile configuration (fast=quick, normal=standard, deep=thorough). "
        "Profile sets personas, debate mode, repetition, and timeout. Explicit flags override profile values.",
    )
    parser.add_argument(
        "--timeout", type=float, default=600.0
    )  # Increased from 180s for CLI providers (qwen-cli, gemini-cli)
    parser.add_argument("--ideas", type=int, default=10)
    parser.add_argument("--output", choices=["json", "markdown", "text"], default="text")
    parser.add_argument(
        "--fresh-mode",
        action="store_true",
        help="Generate ideas WITHOUT reading existing plans (prevents anchoring bias)",
    )
    parser.add_argument("--strict-stale", action="store_true", help="Fail if /q context is stale.")
    parser.add_argument(
        "--local-llm-repetition",
        type=int,
        default=2,
        help="Run brainstorming N times with different local LLM personas for diversity (free improvement)",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Use ONLY local LLM personas, skip external LLM providers",
    )
    parser.add_argument(
        "--debate-mode",
        choices=["none", "full", "fast"],
        default="fast",
        help="Debate mode: 'none' (single-pass Discuss), 'full' (3-round adversarial debate), 'fast' (default: abbreviated debate for quality)",
    )
    parser.add_argument(
        "--enable-pheromone-trail",
        action="store_true",
        help="[EXPERIMENTAL] Enable pheromone trails for learning from previous sessions",
    )
    parser.add_argument(
        "--enable-replay-buffer",
        action="store_true",
        help="[EXPERIMENTAL] Enable experience replay buffer for improved idea generation",
    )
    parser.add_argument(
        "--enable-got",
        action="store_true",
        default=True,
        help="Enable Graph-of-Thought analysis (node extraction, relationship detection, cycle analysis)",
    )
    parser.add_argument(
        "--enable-tot",
        action="store_true",
        default=True,
        help="Enable Tree-of-Thought analysis (outcome branching, likelihood scoring, scenario pruning)",
    )
    parser.add_argument(
        "--skip-health-gate",
        action="store_true",
        help="[DEBUGGING] Skip provider health check before brainstorming (not recommended)",
    )
    parser.add_argument(
        "--show-models",
        action="store_true",
        default=True,
        dest="show_models",
        help="[VISIBILITY] Show which models each provider will use (default: enabled)",
    )
    parser.add_argument(
        "--no-show-models",
        action="store_false",
        dest="show_models",
        help="[VISIBILITY] Hide provider models from health check output",
    )
    parser.add_argument(
        "--diagram",
        action="store_true",
        help="[OUTPUT] Include Mermaid diagram in output (for markdown/text formats)",
    )
    parser.add_argument(
        "--auto-confirm",
        action="store_true",
        help="[INTERACTIVE] Skip confirmation prompt and auto-continue with brainstorm",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="[OUTPUT] Suppress progress reporting (only show final results)",
    )
    # Use parse_known_args to allow fuzzy matching to handle unknown flags
    return parser.parse_known_args(argv)[0]


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def _display_help_and_exit() -> None:
    """Display help information and exit."""
    import sys

    print("\n" + "=" * 60)
    print(" /s - Strategy: Available Options")
    print("=" * 60)

    # Display profile presets first (TASK-005)
    print("\n### PROFILE PRESETS ###")
    print("  --profile fast    - Quick decisions (2 personas, no debate, 180s)")
    print("  --profile normal  - Standard use (4 personas, fast debate, 300s)")
    print("  --profile deep    - Complex analysis (6 personas, full debate, 600s)")
    print("\n  Profile details:")
    print("    fast    - personas: innovator,pragmatist | debate: none | repetition: 1")
    print(
        "    normal  - personas: innovator,pragmatist,critic,expert | debate: fast | repetition: 2"
    )
    print("    deep    - personas: all 6 | debate: full | repetition: 3")
    print("\n  Explicit flags (e.g., --personas) override profile values")

    print("\n### PERSONAS ###")
    print("  INNOVATOR    - Cynefin framework for complexity analysis")
    print("  PRAGMATIST   - Inversion thinking for failure prevention")
    print("  CRITIC       - Hanlon's Razor + Devil's Advocate")
    print("  EXPERT       - Chesterton's Fence for change validation")
    print("  FUTURIST     - Scenario planning and long-term implications")
    print("  SYNTHESIZER  - Cross-framework integration")

    print("\n### COGNITIVE TECHNIQUES ###")
    print(
        "  SCAMPER           - Substitute, Combine, Adapt, Modify, Put to use, Eliminate, Reverse"
    )
    print("  Lateral Thinking  - Challenge assumptions, random entry points")
    print("  Six Thinking Hats - Facts, feelings, caution, benefits, creativity, process")
    print("  First Principles  - Break down to fundamental truths")
    print("  Reverse Engineering - Work backwards from desired outcome")

    print("\n### CLI LOCAL TOOLS ###")
    print("  qwen-cli   - Qwen 3.5 Plus (1M context, multimodal)")
    print("  gemini-cli - Auto mode (Gemini 3, 1M context)")
    print("  vibe       - Devstral 2 (200K context)")
    print("  pi         - Multi-provider coding agent")

    print("\n### SUPPORTED FLAGS ###")
    print("  --profile PROFILE         Use preset: fast | normal | deep (see above)")
    print("  --recall                  Search previous brainstorm sessions")
    print("  --recall --persona NAME   Filter by persona (INNOVATOR/PRAGMATIST/CRITIC/EXPERT)")
    print("  --recall --min-impact N   Filter by impact score ≥ N (0.0–1.0)")
    print("  --context-path PATH       Prepend directory contents as project context")
    print("  --output FORMAT           json | markdown | text (default: markdown)")
    print("  --personas CSV            Comma-separated persona list")
    print("  --timeout N               Timeout in seconds (default: 300)")
    print("  --ideas N                 Target ideas to generate (default: 10)")
    print("  --fresh-mode              Prevent anchoring bias")
    print("  --local-llm-repetition N  Run brainstorm N times with variations")
    print("  --local-only              Skip external LLMs, use local only")
    print("  --debate-mode MODE        none | fast | full (default: fast)")
    print("  --enable-pheromone-trail  [EXPERIMENTAL] Learn from previous sessions")
    print("  --enable-replay-buffer    [EXPERIMENTAL] Improved idea generation")
    print("  --enable-got              Graph-of-Thought (default: ON)")
    print("  --enable-tot              Tree-of-Thought (default: ON)")
    sys.exit(0)


def fuzzy_match_args(
    args: argparse.Namespace, argv: list[str] | None
) -> tuple[argparse.Namespace, list[str]]:
    """
    Apply NLU-based fuzzy matching to command-line arguments.

    Handles:
    - Typo detection (Levenshtein distance ≤ 2)
    - Semantic intent mapping (--providers → --list)
    - Unknown flag warnings with graceful degradation
    """
    warnings = []

    # Valid flags recognized by argparse
    valid_flags = {
        "--topic",
        "--context-path",
        "--personas",
        "--timeout",
        "--ideas",
        "--output",
        "--fresh-mode",
        "--strict-stale",
        "--local-llm-repetition",
        "--local-only",
        "--provider-tier",
        "--debate-mode",
        "--enable-pheromone-trail",
        "--enable-replay-buffer",
        "--skip-health-gate",
        "--show-models",
        "--no-show-models",
        "--diagram",
        "--auto-confirm",
    }

    # Semantic intent mappings (equivalent flags)
    semantic_mappings = {
        "--help": "--list",  # "help" = show options
        "-h": "--list",  # "help" = show options
    }

    # Extract flags from argv (skip script name and topic values)
    parsed_argv = argv if argv else []
    unknown_flags = []
    help_requested = False

    i = 0
    while i < len(parsed_argv):
        arg = parsed_argv[i]

        # Check for help/list intent first
        if arg in semantic_mappings:
            help_requested = True
            warnings.append(f"Flag '{arg}' interpreted as request for usage information")
            i += 1
            continue

        # Check if it's a flag (starts with --)
        if arg.startswith("--"):
            flag_name = arg.split("=")[0]  # Handle --flag=value format

            if flag_name not in valid_flags:
                unknown_flags.append(flag_name)

                # Try to find close match (typo detection)
                suggestions = []
                for valid_flag in valid_flags:
                    distance = _levenshtein_distance(flag_name, valid_flag)
                    if distance <= 2 and distance > 0:
                        suggestions.append((valid_flag, distance))

                if suggestions:
                    # Sort by distance and suggest closest match
                    suggestions.sort(key=lambda x: x[1])
                    best_match = suggestions[0][0]
                    warnings.append(
                        f"Unknown flag '{flag_name}'. Did you mean '{best_match}'? "
                        f"(Continuing without this flag)"
                    )
                else:
                    warnings.append(f"Unknown flag '{flag_name}'. Continuing without it.")

        i += 1

    # If help was requested (via flag or topic keyword), display help and exit
    if help_requested:
        _display_help_and_exit()

    return args, warnings


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    args, warnings = fuzzy_match_args(args, argv)

    # Emit fuzzy matching warnings to stderr
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)

    # Apply profile configuration if --profile specified
    if hasattr(args, "profile") and args.profile:
        profile_config = _get_profile_config()
        try:
            profile = profile_config.profile_from_name(args.profile)

            # Check for conflicts between profile and explicit flags
            _, conflicts = profile_config.validate_profile_flags(args)
            for conflict in conflicts:
                print(f"WARNING: {conflict}", file=sys.stderr)

            # Apply profile settings (explicit flags take precedence)
            profile_config.apply_profile_to_args(args, profile)
        except ValueError as e:
            # Invalid profile name - show error and available profiles
            error_resp = build_error_response(
                error_type="invalid_profile",
                message=str(e),
                available_profiles=profile_config.get_available_profiles(),
            )
            print(json.dumps(error_resp.to_dict(), indent=2))
            return 1

    wt_session = os.environ.get("WT_SESSION", "")
    personas = parse_personas(args.personas)

    # Validate personas
    unknown = [p for p in personas if p not in ALLOWED_PERSONAS]
    if unknown:
        error_resp = build_error_response(
            error_type="unknown_personas",
            message=f"Unknown personas: {', '.join(unknown)}. Use: {', '.join(DEFAULT_PERSONAS)}",
            invalid=unknown,
            valid=list(ALLOWED_PERSONAS),
        )
        print(json.dumps(error_resp.to_dict(), indent=2))
        return 1

    _ensure_import_paths()
    from core.solo_dev_constitutional_filter import SoloDevConstitutionalFilter
    from lib.context_inference import (
        infer_brainstorm_topic_from_context,
    )

    # If --context-path provided, read all files and prepend to topic
    context_prefix = ""
    if args.context_path:
        context_prefix = read_context_path(args.context_path)
        if context_prefix:
            context_prefix = f"PROJECT CONTEXT (from {args.context_path}):\n{context_prefix}\n\nSTRATEGIC TOPIC:\n"

    effective_topic = f"{context_prefix}{args.topic}" if context_prefix else args.topic

    topic_meta = choose_topic(
        explicit_topic=effective_topic,
        wt_session=wt_session,
        q_reader=read_q_context_compat,
        session_activity_reader=get_session_activity_compat,
        brainstorm_context_infer=infer_brainstorm_topic_from_context,
    )

    if args.strict_stale and topic_meta.stale_context:
        error_resp = build_error_response(
            error_type="stale_context",
            message="The /q context is stale. Run /q to refresh context, then rerun /s.",
            reason=topic_meta.stale_reason,
            recommendation="Run /q to refresh context, then rerun /s.",
        )
        print(json.dumps(error_resp.to_dict(), indent=2))
        return 2

    # Mock mode removed - always use real LLM agents
    use_mock_effective = False
    # When local_only, default to 3 repetitions if not specified
    local_rep = (
        args.local_llm_repetition
        if args.local_llm_repetition > 0
        else (3 if args.local_only else 0)
    )

    result = asyncio.run(
        run_heavy(
            topic_meta=topic_meta,
            personas=personas,
            timeout=args.timeout,
            num_ideas=args.ideas,
            use_mock=use_mock_effective,
            local_repetition=local_rep,
            llm_config=None,
            debate_mode=args.debate_mode,
            enable_pheromone_trail=args.enable_pheromone_trail,
            enable_replay_buffer=args.enable_replay_buffer,
            enable_got=args.enable_got,
            enable_tot=args.enable_tot,
            skip_health_gate=args.skip_health_gate,
            show_models=args.show_models,
            auto_confirm=args.auto_confirm,
            quiet=args.quiet,
        )
    )

    filter_obj = SoloDevConstitutionalFilter()
    raw_ideas = result_ideas_to_dicts(result)
    allowed, rejected = apply_constitutional_filter(raw_ideas, filter_obj.check_action_item)
    payload = build_payload(topic_meta, result, allowed, rejected)

    if args.output == "json":
        print(json.dumps(payload, indent=2))
    elif args.output == "markdown":
        print(render_markdown(payload))
        if args.diagram:
            print("\n" + render_mermaid_diagram(payload))
    else:
        print(render_text(payload))
        if args.diagram:
            print("\n" + render_mermaid_diagram(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
