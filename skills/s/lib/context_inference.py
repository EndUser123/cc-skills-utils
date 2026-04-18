"""
Chat Context Inference for Brainstorm System

Analyzes recent chat history to infer brainstorm topics when user
doesn't provide an explicit topic.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


def infer_brainstorm_topic_from_context(
    limit: int = 20,
    lookback_minutes: int = 30
) -> str | None:
    """Infer a brainstorm topic from recent chat context."""
    try:
        recent = _get_recent_chat_messages(limit=limit, lookback_minutes=lookback_minutes)
        if not recent:
            return None
        topic_keywords = _extract_topic_keywords(recent)
        if not topic_keywords:
            return None
        ranked = _rank_keywords(topic_keywords, recent)
        if not ranked:
            return None
        top_keyword = ranked[0]
        topic = _format_brainstorm_topic(top_keyword, ranked[:3])
        return topic
    except Exception as e:
        logger.warning(f"Could not infer topic from context: {e}")
        return None


def _get_recent_chat_messages(limit: int = 20, lookback_minutes: int = 30) -> list[dict]:
    """Get recent chat messages from the current session transcript."""
    messages = []
    try:
        transcript_path = os.environ.get("CLAUDE_SESSION_TRANSCRIPT")
        if not transcript_path:
            projects_dir = Path.home() / ".claude" / "projects"
            if not projects_dir.exists():
                return []
            jsonl_files = list(projects_dir.rglob("*.jsonl"))
            if not jsonl_files:
                return []
            jsonl_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            transcript_path = str(jsonl_files[0])
        transcript_file = Path(transcript_path)
        if not transcript_file.exists():
            return []
        cutoff_time = datetime.utcnow() - timedelta(minutes=lookback_minutes)
        with open(transcript_file, encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry.get("role") in ["user", "assistant"]:
                        timestamp_str = entry.get("timestamp", "")
                        if timestamp_str:
                            try:
                                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                                if timestamp < cutoff_time:
                                    continue
                            except:
                                pass
                        messages.append(entry)
                        if len(messages) >= limit:
                            break
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        logger.warning(f"Could not read chat transcript: {e}")
    return messages


def _extract_topic_keywords(messages: list[dict]) -> list[str]:
    """Extract potential topic keywords from messages."""
    keywords = []
    problem_patterns = [
        r"how to (\w+(?:\s+\w+){0,4})",
        r"ways? to (\w+(?:\s+\w+){0,4})",
        r"improve (\w+(?:\s+\w+){0,3})",
        r"fix (\w+(?:\s+\w+){0,3})",
        r"problem with (\w+)",
        r"issue with (\w+)",
        r"(\w+) (?:debug|error|failure|bug)",
        r"add (\w+(?:\s+\w+){0,3})",
        r"enhance (\w+(?:\s+\w+){0,3})",
        r"optimize (\w+(?:\s+\w+){0,3})",
    ]
    for msg in messages:
        content = msg.get("message", msg.get("content", ""))
        if not content:
            continue
        for pattern in problem_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            keywords.extend([m.strip() for m in matches if len(m.strip()) > 3])
        if "?" in content:
            question_parts = content.split("?")
            for part in question_parts[:2]:
                words = re.findall(r"\b[a-z]{4,}\b", part.lower())
                keywords.extend(words[-3:])
        brainstorm_patterns = [
            r"brainstorm (.+?)(?:\.|\?|$)",
            r"ideas? for (.+?)(?:\.|\?|$)",
            r"suggest (.+?)(?:\.|\?|$)",
        ]
        for pattern in brainstorm_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            keywords.extend([m.strip() for m in matches if len(m.strip()) > 3])
    return [k for k in keywords if len(k) > 3]


def _rank_keywords(keywords: list[str], messages: list[dict]) -> list:
    """Rank keywords by frequency and recency."""
    from collections import Counter
    freq = Counter(keywords)
    now = datetime.utcnow()
    for msg in messages:
        msg_time = msg.get("timestamp", "")
        if msg_time:
            try:
                msg_time = datetime.fromisoformat(msg_time.replace("Z", "+00:00"))
                age_minutes = (now - msg_time).total_seconds() / 60 if msg_time < now else 0
                recency_boost = 1.0 / (1.0 + age_minutes / 10.0)
                content = msg.get("message", msg.get("content", "")).lower()
                for keyword in set(keywords):
                    if keyword.lower() in content:
                        freq[keyword] = freq.get(keyword, 0) + int(recency_boost * 2)
            except:
                pass
    return freq.most_common(10)


def _format_brainstorm_topic(top_keyword: tuple, related: list) -> str:
    """Format keywords into a brainstorm topic prompt."""
    primary = top_keyword[0]
    related_words = [r[0] for r in related if r[0].lower() != primary.lower()]
    if related_words:
        context = " ".join(related_words[:2])
        return f"Ways to improve or innovate: {primary} (context: {context})"
    return f"Ways to improve or innovate: {primary}"


def get_recent_context_summary() -> str:
    """Get a summary of recent chat context for brainstorm topic inference."""
    topic = infer_brainstorm_topic_from_context()
    if topic:
        return f"Recent discussion suggests brainstorming: {topic}"
    return "No clear topic inferred from recent context."


__all__ = [
    "get_recent_context_summary",
    "infer_brainstorm_topic_from_context",
]
