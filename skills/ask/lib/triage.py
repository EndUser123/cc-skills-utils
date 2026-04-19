"""Reversibility triage for /ask routing decisions.

Codified from SKILL.md STEP 0 reversibility table.
Returns (score, path) tuples.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

TriagePath = Literal["FAST", "STANDARD", "CAREFUL"]


@dataclass(frozen=True)
class TriageResult:
    reversibility: float
    dependency_count: int
    path: TriagePath
    reasoning: str


# ── Keyword scoring helpers ────────────────────────────────────────────────────

_IRREVERSIBLE = re.compile(
    r"\b(deploy|destroy|delete|drope?d?|remove?|drop\s+\w+|rm\s+-rf|"
    r"truncate|publish|release\s+to\s+prod|"
    r"grant\s+.*admin|make\s+public|"
    r"irreversible|undo?\s+impossible|"
    r"destroy\s+\w+|delete\s+\w+|remove\s+\w+|"
    r"change\s+(?:the\s+)?schema|schema\s+change)\b",
    re.IGNORECASE,
)
_MODERATE = re.compile(
    r"\b(plan|refactor|restructure|"
    r"migrate|backfill|reindex|"
    r"create\s+file|new\s+feature|implement|"
    r"extract\s+module|split\s+service|"
    r"break\s+cache|change\s+schema|"
    r"modify\s+api|update\s+migration)\b",
    re.IGNORECASE,
)
_TRIVIAL = re.compile(
    r"\b(help|status|list|show|"
    r"what\s+(?:can|does)|how\s+do|"
    r"explain|describe|find|search|"
    r"check|verify|simple|query|"
    r"read-only|view|browse)\b",
    re.IGNORECASE,
)

# Explicit dependency keywords
_DEPENDENCY_KEYWORDS = re.compile(
    r"\b(because|since|depends|after|before|"
    r"follow(?:s|ing)?\s+on|in\s+order\s+to|"
    r"which\s+implies?|requires?|needs?)\b",
    re.IGNORECASE,
)


def _score_reversibility(text: str) -> float:
    if _IRREVERSIBLE.search(text):
        return 2.0
    if _MODERATE.search(text):
        return 1.5
    if _TRIVIAL.search(text):
        return 1.0
    return 1.25  # default: trivial


def _count_dependencies(text: str) -> int:
    matches = _DEPENDENCY_KEYWORDS.findall(text)
    return len(matches)


def triage(request: str) -> TriageResult:
    """Assess complexity and select the appropriate cognitive path.

    Args:
        request: Raw user request text.

    Returns:
        TriageResult with reversibility score, dependency count, and chosen path.
    """
    rev_score = _score_reversibility(request)
    dep_count = _count_dependencies(request)

    if rev_score >= 1.75:
        path: TriagePath = "CAREFUL"
        reasoning = "Irreversible or high-stakes action detected"
    elif dep_count >= 5:
        path = "CAREFUL"
        reasoning = f"5+ dependencies ({dep_count}), decompose before routing"
    elif rev_score >= 1.25:
        path = "STANDARD"
        reasoning = "Moderate complexity, context exploration recommended"
    elif dep_count >= 2:
        path = "STANDARD"
        reasoning = f"Multiple dependencies ({dep_count}), confirm understanding first"
    else:
        path = "FAST"
        reasoning = "Trivial request, direct routing"

    return TriageResult(
        reversibility=rev_score,
        dependency_count=dep_count,
        path=path,
        reasoning=reasoning,
    )
