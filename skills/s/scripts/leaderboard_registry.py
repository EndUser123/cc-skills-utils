#!/usr/bin/env python3
"""
Leaderboard Registry for LLM Model Performance Tracking.

Loads model performance data from a JSON data file (single source of truth).
No HTTP scraping, no hardcoded fallback data - fail fast if JSON file is missing.

JSON data file location: P:/.claude/skills/s/data/leaderboard_data.json
Update the JSON file manually with fresh arena.ai data.

Scores are raw Elo ratings (1400-1600 range), not normalized percentages.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

# Path to JSON data file (single source of truth)
LEADERBOARD_DATA_PATH = Path(__file__).parent.parent / "data" / "leaderboard_data.json"


# ============================================================================
# Task Categories
# ============================================================================


class TaskCategory(StrEnum):
    """Task categories for model evaluation."""

    REASONING = "reasoning"
    CODING = "coding"
    GENERAL = "general"
    MATH = "math"
    AGENTIC_CODING = "agentics"  # SWE-Bench, Aider-style


# ============================================================================
# Leaderboard Entries
# ============================================================================


@dataclass(frozen=True, slots=True)
class LeaderboardEntry:
    """A single model's performance on a leaderboard."""

    model_id: str  # Provider-format model ID (e.g., "google/gemma-3-27b-it:free")
    score: float  # Raw Elo score (1400-1600 range for arena.ai)
    rank: int  # Position on this leaderboard
    benchmark: str  # Source benchmark name
    last_updated: str  # ISO timestamp

    def __post_init__(self):
        if self.rank < 1:
            raise ValueError(f"Rank must be >= 1, got {self.rank}")
        # Elo scores are typically 1000-2000 range
        # arena.ai coding scores are 1400-1600
        if not (1000 <= self.score <= 2000):
            raise ValueError(f"Score must be in Elo range (1000-2000), got {self.score}")


# ============================================================================
# Model ID Normalization
# ============================================================================

# Map leaderboard model names to provider-format model IDs
# This handles naming variations across platforms
_MODEL_ID_ALIASES: dict[str, str] = {
    # Google / Gemini (2026 models)
    "gemini-3-pro": "google/gemini-3-pro",
    "gemini-3-flash": "google/gemini-3-flash",
    "gemini-3-flash-thinking-minimal": "google/gemini-3-flash-thinking-minimal",
    "gemini-2.5-pro": "google/gemini-2.5-pro",
    "gemini-2.5-flash": "google/gemini-2.5-flash",
    "gemini-2.0-flash-exp": "google/gemini-2.0-flash-exp",
    "gemma-3-27b-it": "google/gemma-3-27b-it:free",
    "gemma-3-27b-it:free": "google/gemma-3-27b-it:free",
    "gemma-3-4b-it:free": "google/gemma-3-4b-it:free",
    "gemma-3-12b-it:free": "google/gemma-3-12b-it:free",
    # xAI / Grok (2026 models)
    "grok-4.1-fast": "xai/grok-4.1-fast",
    "grok-4": "xai/grok-4",
    # OpenAI (2026 models)
    "gpt-5.4-high": "openai/gpt-5.4-high",
    "gpt-5.4-medium": "openai/gpt-5.4-medium",
    "gpt-5.3-codex": "openai/gpt-5.3-codex",
    "gpt-5.2": "openai/gpt-5.2",
    "gpt-5.1-high": "openai/gpt-5.1-high",
    "gpt-5.1": "openai/gpt-5.1",
    "gpt-5.1-medium": "openai/gpt-5.1-medium",
    "gpt-5-medium": "openai/gpt-5-medium",
    "gpt-5-chat": "openai/gpt-5-chat",
    # Anthropic (2026 models)
    "claude-opus-4-6": "anthropic/claude-opus-4-6",
    "claude-opus-4-6-thinking": "anthropic/claude-opus-4-6-thinking",
    "claude-sonnet-4-6": "anthropic/claude-sonnet-4-6",
    "claude-opus-4-5-20251101-thinking-32k": "anthropic/claude-opus-4-5-20251101-thinking-32k",
    "claude-opus-4-5-20251101": "anthropic/claude-opus-4-5-20251101",
    "claude-sonnet-4-5-20250929-thinking-32k": "anthropic/claude-sonnet-4-5-20250929-thinking-32k",
    "claude-opus-4-5-20251101-thinking-32k": "anthropic/claude-opus-4-5-20251101-thinking-32k",
    "claude-opus-4-5-20251101": "anthropic/claude-opus-4-5-20251101",
    "claude-sonnet-4-5-20250929-thinking-32k": "anthropic/claude-sonnet-4-5-20250929-thinking-32k",
    # Meta / Llama
    "llama-3.1-405b": "meta-llama/llama-3.1-405b-instruct",
    "llama-3.3-70b": "meta-llama/llama-3.3-70b-versatile",
    # Qwen
    "qwen2.5-72b-instruct": "qwen/qwen2.5-72b-instruct",
    "qwen2.5-coder-32b-instruct": "qwen/qwen2.5-coder-32b-instruct",
    # DeepSeek
    "deepseek-r1": "deepseek/deepseek-r1",
    "deepseek-v3": "deepseek/deepseek-v3",
    # Mistral
    "mistral-large": "mistral/mistral-large",
    "mistral-small": "mistral/mistral-small",
    # Zhipu AI
    "glm-5": "zhipu/glm-5",
    "glm-4.7": "zhipu/glm-4.7",
    # MiniMax
    "m2.7": "minimax/m2.7",
    "m2.5": "minimax/m2.5",
    "m2.1-preview": "minimax/m2.1-preview",
    # Aliases for zai provider (z.ai)
    "zhipu/glm-4.7z.ai": "zhipu/glm-4.7",
    "zhipu/glm-5z.ai": "zhipu/glm-5",
    # Moonshot
    "kimi-k2.5-thinking": "moonshot/kimi-k2.5-thinking",
    "kimi-k2.5-instant": "moonshot/kimi-k2.5-instant",
    # Xiaomi
    "mimo-v2-pro": "xiaomi/mimo-v2-pro",
}


def normalize_model_id(raw_name: str) -> str:
    """Normalize a model name from a leaderboard to provider format.

    Args:
        raw_name: Model name from leaderboard (may have variations)

    Returns:
        Provider-format model ID (e.g., "google/gemma-3-27b-it:free")

    Examples:
        >>> normalize_model_id("gemini-3-pro")
        "google/gemini-3-pro"
        >>> normalize_model_id("google/gemini-3-pro")
        "google/gemini-3-pro"
    """
    # Direct lookup first
    if raw_name in _MODEL_ID_ALIASES:
        return _MODEL_ID_ALIASES[raw_name]

    # Try prefix matching for provider/ patterns
    if "/" in raw_name:
        # Already in provider/model format
        return raw_name

    # Try to infer provider from model name prefix
    if raw_name.startswith("gpt-"):
        return f"openai/{raw_name}"
    elif raw_name.startswith("claude-"):
        return f"anthropic/{raw_name}"
    elif raw_name.startswith("llama-"):
        return f"meta-llama/{raw_name}"
    elif raw_name.startswith("qwen"):
        return f"qwen/{raw_name}"
    elif raw_name.startswith("gemini"):
        return f"google/{raw_name}"
    elif raw_name.startswith("deepseek"):
        return f"deepseek/{raw_name}"
    elif raw_name.startswith("grok"):
        return f"xai/{raw_name}"
    elif raw_name.startswith("glm"):
        return f"zhipu/{raw_name}"
    elif raw_name.startswith("mistral"):
        return f"mistral/{raw_name}"
    elif raw_name.startswith("m2.") or raw_name.startswith("mimo"):
        return f"minimax/{raw_name}"
    elif raw_name.startswith("kimi"):
        return f"moonshot/{raw_name}"

    # Default: return as-is
    return raw_name


# ============================================================================
# Leaderboard Data Loader (JSON file - single source of truth)
# ============================================================================


def _load_from_json() -> dict[str, list[LeaderboardEntry]]:
    """Load leaderboard data from JSON file.

    Returns:
        Dictionary mapping task categories to leaderboard entries

    Raises:
        FileNotFoundError: If JSON data file doesn't exist
        ValueError: If JSON data is invalid
    """
    if not LEADERBOARD_DATA_PATH.exists():
        raise FileNotFoundError(
            f"Leaderboard data file not found: {LEADERBOARD_DATA_PATH}\n"
            f"Please ensure the JSON file exists at this location.\n"
            f"This file is the single source of truth for leaderboard data.\n"
            f"Update it manually with fresh arena.ai data."
        )

    try:
        with open(LEADERBOARD_DATA_PATH) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in leaderboard data file: {e}")

    # Validate required fields
    if "source" not in data:
        raise ValueError("JSON data missing 'source' field")
    if data["source"] != "arena.ai":
        raise ValueError(f"Unexpected data source: {data.get('source')}. Expected 'arena.ai'")

    # Parse entries by category
    results: dict[str, list[LeaderboardEntry]] = {}

    # Map JSON category keys to TaskCategory enum values
    category_mapping = {
        "coding": TaskCategory.CODING,
        "general": TaskCategory.GENERAL,
        "reasoning": TaskCategory.REASONING,
        # "math" is in JSON but we use reasoning as proxy
    }

    for json_key, task_category in category_mapping.items():
        if json_key not in data:
            continue

        entries = []
        for item in data[json_key]:
            try:
                # Normalize model ID
                model_id = normalize_model_id(item["model_id"])

                entry = LeaderboardEntry(
                    model_id=model_id,
                    score=float(item["score"]),
                    rank=int(item["rank"]),
                    benchmark=str(item["benchmark"]),
                    last_updated=str(data.get("last_updated", "unknown")),
                )
                entries.append(entry)
            except (KeyError, ValueError) as e:
                # Skip invalid entries but continue processing
                logger.warning("Skipping invalid entry %s: %s", item, e)

        results[task_category] = entries

    # For math category, use reasoning data (LMArena proxy)
    if TaskCategory.REASONING in results:
        # Create math entries from reasoning data with adjusted benchmark name
        math_entries = []
        for entry in results[TaskCategory.REASONING]:
            math_entries.append(
                LeaderboardEntry(
                    model_id=entry.model_id,
                    score=entry.score,
                    rank=entry.rank,
                    benchmark="MATH/GSM8K (LMArena Proxy)",
                    last_updated=entry.last_updated,
                )
            )
        results[TaskCategory.MATH] = math_entries

    # For agentic coding, use coding data (same arena.ai benchmark)
    if TaskCategory.CODING in results:
        results[TaskCategory.AGENTIC_CODING] = results[TaskCategory.CODING]

    return results


# ============================================================================
# Public API
# ============================================================================


def fetch_leaderboard_data() -> dict[str, list[LeaderboardEntry]]:
    """Fetch all leaderboard data from JSON file.

    The JSON file is the single source of truth and is always reloaded.
    No caching of the JSON file content - fail fast if file is missing.

    Returns:
        Dictionary mapping task categories to leaderboard entries
    """
    # Load from JSON file (always fresh - no caching of JSON file content)
    try:
        entries = _load_from_json()
    except (FileNotFoundError, ValueError) as e:
        # Fail fast - no fallback data
        logger.error("Failed to load leaderboard data: %s", e)
        raise

    return entries


def get_leaderboard_for_task(
    task: TaskCategory,
) -> list[LeaderboardEntry]:
    """Get leaderboard entries for a specific task.

    Args:
        task: Task category (reasoning, coding, general, etc.)

    Returns:
        List of leaderboard entries, sorted by score (best first)
    """
    # Fetch fresh data from JSON file
    results = fetch_leaderboard_data()
    return results.get(task, [])


def rank_models_by_task(
    available_models: list[str],
    task: TaskCategory,
    top_n: int = 10,
) -> list[tuple[str, float, int]]:
    """Rank available models by leaderboard performance.

    Args:
        available_models: List of provider-format model IDs (e.g., from API)
        task: Task category to rank by
        top_n: Return top N models

    Returns:
        List of (model_id, score, rank) tuples
    """
    leaderboard = get_leaderboard_for_task(task)

    # Build lookup dict for O(1) access
    scores_by_model = {entry.model_id: entry.score for entry in leaderboard}

    # Score available models
    scored_models = []
    for model_id in available_models:
        score = scores_by_model.get(model_id, 0.0)
        if score > 0:  # Only include models with leaderboard data
            scored_models.append((model_id, score))

    # Sort by score descending
    scored_models.sort(key=lambda x: x[1], reverse=True)

    # Assign ranks and limit to top_n
    results = []
    for i, (model_id, score) in enumerate(scored_models[:top_n], 1):
        results.append((model_id, score, i))

    return results


# ============================================================================
# CLI Helpers
# ============================================================================


def print_leaderboard_summary(task: TaskCategory) -> None:
    """Print a summary of leaderboard data for a task category.

    Args:
        task: Task category to display
    """
    entries = get_leaderboard_for_task(task)

    if not entries:
        print(f"No leaderboard data available for {task.value}")
        return

    print(f"\n{'=' * 70}")
    print(f" {task.value.upper()} LEADERBOARD TOP 10")
    print("=" * 70)

    for entry in entries[:10]:
        # Display raw Elo score, not percentage
        print(f"{entry.rank:3}. {entry.model_id:50} {entry.score:6.0f}  ({entry.benchmark})")

    print("=" * 70)


if __name__ == "__main__":
    # Test fetching
    print("Testing leaderboard fetch from JSON...")
    try:
        results = fetch_leaderboard_data()

        for category, entries in results.items():
            print(f"\n{category}: {len(entries)} entries")
            for entry in entries[:5]:
                print(f"  {entry.rank}. {entry.model_id}: {entry.score:.0f} Elo")
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")
        print("\nPlease ensure leaderboard_data.json exists at:")
        print(f"  {LEADERBOARD_DATA_PATH}")
