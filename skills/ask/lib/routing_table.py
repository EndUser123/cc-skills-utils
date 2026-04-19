"""Intent pattern → command routing table for /ask.

Extracted and codified from references/intent-routing-table.md.
Each entry: (regex_pattern, command, priority)
Priority: explicit > implicit (higher wins for ties).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Command = str


@dataclass(frozen=True)
class RouteEntry:
    pattern: re.Pattern[str]
    command: Command
    priority: int = 0  # higher = more explicit intent


# ── Explicit command mentions ──────────────────────────────────────────────────
EXPLICIT_PATTERNS: list[RouteEntry] = [
    RouteEntry(re.compile(r'^/?design(?:\s|$)', re.IGNORECASE), "/design", 10),
    RouteEntry(re.compile(r'^/?rca(?:\s|$)', re.IGNORECASE), "/rca", 10),
    RouteEntry(re.compile(r'^/?debug(?:\s|$)', re.IGNORECASE), "/debug", 10),
    RouteEntry(re.compile(r'^/?research(?:\s|$)', re.IGNORECASE), "/research", 10),
    RouteEntry(re.compile(r'^/?doc(?:ument)?(?:\s|$)', re.IGNORECASE), "/doc", 10),
    RouteEntry(re.compile(r'^/?analy(?:ze|sis)(?:\s|$)', re.IGNORECASE), "/analyze", 10),
    RouteEntry(re.compile(r'^/?breakdown(?:\s|$)', re.IGNORECASE), "/breakdown", 10),
    RouteEntry(re.compile(r'^/?cwo(?:\s|$)', re.IGNORECASE), "/cwo", 10),
    RouteEntry(re.compile(r'^/?truth(?:\s|$)', re.IGNORECASE), "/truth", 10),
    RouteEntry(re.compile(r'^/?search(?:\s|$)', re.IGNORECASE), "/search", 10),
    RouteEntry(re.compile(r'^/?discover(?:\s|$)', re.IGNORECASE), "/discover", 10),
    RouteEntry(re.compile(r'^/?verify(?:\s|$)', re.IGNORECASE), "/verify", 10),
    RouteEntry(re.compile(r'^/?llm-debate(?:\s|$)', re.IGNORECASE), "/llm-debate", 10),
    RouteEntry(re.compile(r'^/?build(?:\s|$)', re.IGNORECASE), "/build", 10),
    RouteEntry(re.compile(r'^/?evolve(?:\s|$)', re.IGNORECASE), "/evolve", 10),
    RouteEntry(re.compile(r'^/?qa(?:\s|$)', re.IGNORECASE), "/qa", 10),
    RouteEntry(re.compile(r'^/?test(?:\s|$)', re.IGNORECASE), "/test", 10),
    RouteEntry(re.compile(r'^/?tdd(?:\s|$)', re.IGNORECASE), "/tdd", 10),
    RouteEntry(re.compile(r'^/?plan(?:\s|$)', re.IGNORECASE), "/planning", 10),
    RouteEntry(re.compile(r'^/?adf(?:\s|$)', re.IGNORECASE), "/adf", 10),
]

# ── Intent-based (implicit) patterns ─────────────────────────────────────────
INTENT_PATTERNS: list[RouteEntry] = [
    # Architecture
    RouteEntry(
        re.compile(
            r'(?:how\s+(?:should\s+|do\s+|would\s+))?'
            r'(?:i\s+)?design'
            r'|architecture\s+decision'
            r'|how\s+(?:should\s+i\s+)?structure'
            r'|what.*architecture'
            r'|which.*pattern',
            re.IGNORECASE,
        ),
        "/design",
        5,
    ),
    # RCA / debugging
    RouteEntry(
        re.compile(
            r'(?:why\s+(?:does\s+|is\s+|did\s+|has\s+))'
            r'|root\s+cause'
            r'|stuck\s+on'
            r'|debug\s+this'
            r'|keep[s]?\s+(?:failing|breaking|error)',
            re.IGNORECASE,
        ),
        "/rca",
        5,
    ),
    # Truth verification
    RouteEntry(
        re.compile(
            r'did\s+i\s+actually'
            r'|prove\s+it'
            r'|verify\s+(?:my|the)\s+claim'
            r'|check\s+(?:my)\s+(?:work|claims)',
            re.IGNORECASE,
        ),
        "/truth",
        5,
    ),
    # Should I extract / is X justified
    RouteEntry(
        re.compile(
            r'should\s+i\s+extract'
            r'|is\s+creating\s+\w+\s+justified'
            r'|new\s+module'
            r'|extract\s+(?:this|that)',
            re.IGNORECASE,
        ),
        "/adf",
        5,
    ),
    # Planning / breakdown
    RouteEntry(
        re.compile(
            r'plan\s+project'
            r'|break\s+down'
            r'|help\s+me\s+plan'
            r'|how\s+to\s+start'
            r'|task\s+breakdown',
            re.IGNORECASE,
        ),
        "/breakdown",
        5,
    ),
    # Research / learn
    RouteEntry(
        re.compile(
            r'research\s+\w+'
            r'|learn\s+about'
            r'|how\s+does\s+\w+\s+work'
            r'|what\s+is\s+\w+\s+and\s+how\s+(?:does\s+)?it\s+work',
            re.IGNORECASE,
        ),
        "/research",
        5,
    ),
    # Analyze quality
    RouteEntry(
        re.compile(
            r'analy(?:ze|sis)'
            r'|code\s+quality'
            r'|improve\s+this\s+code'
            r'|review\s+code',
            re.IGNORECASE,
        ),
        "/analyze",
        5,
    ),
    # Discover patterns
    RouteEntry(
        re.compile(
            r'discover\s+'
            r'|what\s+exists'
            r'|find\s+patterns',
            re.IGNORECASE,
        ),
        "/discover",
        5,
    ),
    # Search chat
    RouteEntry(
        re.compile(
            r'what\s+did\s+(?:we|i|you)\s+discuss'
            r'|search\s+(?:my\s+)?chat'
            r'|what\s+(?:was|were)\s+(?:we|i)\s+(?:discuss|talking)',
            re.IGNORECASE,
        ),
        "/search",
        5,
    ),
    # Workflow orchestration
    RouteEntry(
        re.compile(
            r'complex\s+project'
            r'|orchestrat'
            r'|multi-step\s+workflow',
            re.IGNORECASE,
        ),
        "/cwo",
        5,
    ),
    # Documentation
    RouteEntry(
        re.compile(
            r'document(?:ation)?\s+(?:this|that|the)'
            r'|write\s+docs?'
            r'|ingest\s+docs?',
            re.IGNORECASE,
        ),
        "/doc",
        5,
    ),
    # Build / implement
    RouteEntry(
        re.compile(
            r'build\s+(?:a\s+)?(?:new\s+)?feature'
            r'|implement\s+'
            r'|add\s+(?:a\s+)?feature',
            re.IGNORECASE,
        ),
        "/build",
        5,
    ),
    # Evolve / modernize
    RouteEntry(
        re.compile(
            r'moderni[sz]e'
            r'|upgrade\s+\w+'
            r'|tech\s+debt'
            r'|refactor',
            re.IGNORECASE,
        ),
        "/evolve",
        5,
    ),
    # QA / test
    RouteEntry(
        re.compile(
            r'qa(?:\s|$|\W)'
            r'|certif(?:y|ication)'
            r'|end.?to.?end\s+test'
            r'|e2e\s+test',
            re.IGNORECASE,
        ),
        "/qa",
        5,
    ),
    # LLM debate / multiple perspectives
    RouteEntry(
        re.compile(
            r'multiple\s+perspectives?'
            r'|debate'
            r'|llm\s+debate',
            re.IGNORECASE,
        ),
        "/llm-debate",
        5,
    ),
    # Challenge assumptions
    RouteEntry(
        re.compile(
            r'challenge\s+assumptions?'
            r'|critical\s+analysis'
            r'|challenge\s+mode',
            re.IGNORECASE,
        ),
        "/design --challenge",
        5,
    ),
]

# ── Combined lookup ────────────────────────────────────────────────────────────
ALL_PATTERNS = EXPLICIT_PATTERNS + INTENT_PATTERNS


def route(input_text: str) -> Command | None:
    """Match user input against all patterns. Returns first match by priority desc."""
    if not input_text or not input_text.strip():
        return None

    best: Command | None = None
    best_priority = -1

    for entry in ALL_PATTERNS:
        if entry.pattern.search(input_text):
            if entry.priority > best_priority:
                best = entry.command
                best_priority = entry.priority

    return best
