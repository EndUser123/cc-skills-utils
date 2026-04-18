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

DEFAULT_PERSONAS = ["innovator", "pragmatist", "critic", "expert", "synthesizer"]
ALLOWED_PERSONAS = set(DEFAULT_PERSONAS)


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
    # Insert in reverse so final priority is: P:/, P:/__csf, P:/__csf/src
    for candidate in ("P:/__csf/src", "P:/__csf", "P:/"):
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
        return {"terminal": "unknown", "topic": "No session activity found", "files_worked": [], "domains": {}}


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
    decision = allowed_ideas[0]["content"] if allowed_ideas else "No constitutionally compliant recommendation."
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
        hints.extend(["/r", "/arch", "/nse"])
    else:
        hints.extend(["/planning", "/r"])

    if any(k in idea_lower for k in ("architecture", "system", "design", "module boundary")):
        if "/arch" not in hints:
            hints.append("/arch")
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
    if payload['topic_source'] in ('q_context', 'session_activity', 'chat_context'):
        lines.append(f"- **Context**: Applying strategic thinking to ongoing work based on {payload['topic_source']}")

    lines.extend([
        "",
        "## Top Ideas",
    ])
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
    if payload['topic_source'] in ('q_context', 'session_activity', 'chat_context'):
        lines.append(f"Context: Strategic analysis of ongoing work (from {payload['topic_source']})")

    lines.extend([
        "",
        "Top Ideas:",
    ])
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


async def run_heavy(
    topic_meta: TopicSelection,
    personas: list[str],
    timeout: float,
    num_ideas: int,
    use_mock: bool = False,  # Default to REAL agents, not mocks
    local_repetition: int = 0,  # Run N times with local LLM personas for diversity
    llm_config=None,  # Optional LLM config for provider tier filtering
) -> Any:
    _ensure_import_paths()
    from commands.brainstorm.orchestrator import BrainstormOrchestrator

    memory = InMemoryBrainstormMemory()

    orchestrator = BrainstormOrchestrator(
        memory=memory,
        enable_full_debate=True,
        llm_config=llm_config,
        use_mock_agents=use_mock,
    )

    # If local repetition requested, run multiple times with persona variations
    if local_repetition > 0:
        all_ideas = []
        for iteration in range(local_repetition):
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
        "\n\nAPPROACH CONSTRAINT: Use first-principles thinking. Challenge fundamental assumptions. Break the problem down to basic truths and rebuild from there.",
        "\n\nAPPROACH CONSTRAINT: Use lateral thinking. Consider random entry points and unexpected connections. Avoid obvious solutions.",
        "\n\nAPPROACH CONSTRAINT: Use SCAMPER technique (Substitute, Combine, Adapt, Modify, Put to other uses, Eliminate, Reverse). Explore each dimension.",
        "\n\nAPPROACH CONSTRAINT: Use reverse engineering. Start from the ideal outcome and work backwards. What would need to be true?",
        "\n\nAPPROACH CONSTRAINT: Use Six Thinking Hats. Consider facts, feelings, caution, benefits, creativity, and process separately.",
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

    root = pathlib.Path(context_path)
    if not root.exists():
        return ""
    if root.is_file():
        try:
            content = root.read_text(encoding="utf-8", errors="replace")
            return f"--- {root.name} ---\n{content}\n"
        except Exception:
            return ""

    chunks: list[str] = []
    for fp in sorted(root.rglob("*")):
        if not fp.is_file():
            continue
        # Skip binary/large files
        if fp.suffix in (".pyc", ".pyo", ".so", ".dll", ".exe", ".bin", ".db", ".sqlite", ".whl", ".egg", ".tar", ".gz", ".zip"):
            continue
        try:
            text = fp.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel = fp.relative_to(root)
        chunks.append(f"--- {rel} ---\n{text}")
    return "\n".join(chunks)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run /s heavy mode deterministically.")
    parser.add_argument("--topic", default="", help="Explicit topic. If omitted, infer from /q/session activity.")
    parser.add_argument("--context-path", default="", help="Path to directory or file. All contents are included as context for the brainstorm.")
    parser.add_argument("--personas", default="", help="Comma-separated personas.")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--ideas", type=int, default=10)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--output", choices=["json", "markdown", "text"], default="text")
    parser.add_argument("--fresh-mode", action="store_true", help="Generate ideas WITHOUT reading existing plans (prevents anchoring bias)")
    parser.add_argument("--strict-stale", action="store_true", help="Fail if /q context is stale.")
    parser.add_argument("--local-llm-repetition", type=int, default=0, help="Run brainstorming N times with different local LLM personas for diversity (free improvement)")
    parser.add_argument("--local-only", action="store_true", help="Use ONLY local LLM personas, skip external LLM providers")
    parser.add_argument(
        "--provider-tier",
        default="",
        help="Filter providers by quality tier (e.g., 'T1,T2'). T1=best, T2=good, T3=experimental. Default: T1,T2,T3"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    wt_session = os.environ.get("WT_SESSION", "")
    personas = parse_personas(args.personas)

    # Validate personas
    unknown = [p for p in personas if p not in ALLOWED_PERSONAS]
    if unknown:
        print(
            json.dumps(
                {
                    "error": "unknown_personas",
                    "invalid": unknown,
                    "valid": list(ALLOWED_PERSONAS),
                    "message": f"Unknown personas: {', '.join(unknown)}. Use: {', '.join(DEFAULT_PERSONAS)}",
                },
                indent=2,
            )
        )
        return 1

    _ensure_import_paths()
    from commands.brainstorm.context_inference import (
        infer_brainstorm_topic_from_context,
    )
    from core.solo_dev_constitutional_filter import SoloDevConstitutionalFilter

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
        print(
            json.dumps(
                {
                    "error": "stale_context",
                    "reason": topic_meta.stale_reason,
                    "recommendation": "Run /q to refresh context, then rerun /s.",
                },
                indent=2,
            )
        )
        return 2

    # Handle local-only mode: use mock agents with repetition for diversity
    use_mock_effective = args.mock or args.local_only
    # When local_only, default to 3 repetitions if not specified
    local_rep = args.local_llm_repetition if args.local_llm_repetition > 0 else (3 if args.local_only else 0)

    # Handle provider tier filtering
    llm_config = None
    if args.provider_tier:
        from llm.providers.config import LLMConfig

        # Parse provider tiers (e.g., "T1,T2" -> ["T1", "T2"])
        allowed_tiers = [t.strip().upper() for t in args.provider_tier.split(",") if t.strip()]
        valid_tiers = {"T1", "T2", "T3"}
        invalid_tiers = [t for t in allowed_tiers if t not in valid_tiers]
        if invalid_tiers:
            print(
                json.dumps(
                    {
                        "error": "invalid_tiers",
                        "invalid": invalid_tiers,
                        "valid": list(valid_tiers),
                        "message": "Invalid tiers. Use T1, T2, or T3.",
                    },
                    indent=2,
                )
            )
            return 1

        llm_config = LLMConfig(allowed_tiers=allowed_tiers)

    result = asyncio.run(
        run_heavy(
            topic_meta=topic_meta,
            personas=personas,
            timeout=args.timeout,
            num_ideas=args.ideas,
            use_mock=use_mock_effective,
            local_repetition=local_rep,
            llm_config=llm_config,
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
    else:
        print(render_text(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
