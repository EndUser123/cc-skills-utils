#!/usr/bin/env python3
"""Unified CLI model discovery system.

This module provides dynamic model discovery for CLI tools that support
model listing commands, and fallback to known model lists for tools
that don't have native --list-models functionality.
"""

import json
import subprocess
from pathlib import Path
from typing import Any

# Cache settings
CACHE_DIR = Path.home() / ".cache" / "ai-cli"
CLI_CACHE_FILE = CACHE_DIR / "cli_models.json"
CACHE_TTL_HOURS = 24


def get_cached_cli_models() -> dict[str, Any] | None:
    """Get cached CLI models data if available and fresh."""
    if not CLI_CACHE_FILE.exists():
        return None

    import time

    cache_age = time.time() - CLI_CACHE_FILE.stat().st_mtime
    max_age_seconds = CACHE_TTL_HOURS * 3600

    if cache_age > max_age_seconds:
        return None

    try:
        return json.loads(CLI_CACHE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save_cli_models_to_cache(data: dict[str, Any]) -> None:
    """Save CLI models data to cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CLI_CACHE_FILE.write_text(json.dumps(data, indent=2))


def get_opencode_models() -> list[dict[str, Any]]:
    """Fetch models from opencode CLI using subprocess."""
    import shutil

    # Find opencode executable
    opencode_path = shutil.which("opencode")
    if not opencode_path:
        return []

    result = subprocess.run(
        [opencode_path, "models", "--verbose"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        return []

    lines = result.stdout.strip().split("\n")
    models = []
    current_model_id = None
    json_lines = []
    brace_count = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if json_lines:
            json_lines.append(line)
            brace_count += line.count("{") - line.count("}")

            if brace_count == 0:
                try:
                    json_text = "\n".join(json_lines)
                    model_data = json.loads(json_text)

                    context = model_data.get("limit", {}).get("context", 0)
                    cost_in = model_data.get("cost", {}).get("input", -1)
                    cost_out = model_data.get("cost", {}).get("output", -1)

                    models.append(
                        {
                            "id": current_model_id,
                            "name": model_data.get("name", "Unknown"),
                            "provider": "opencode",
                            "is_free": cost_in == 0 and cost_out == 0,
                            "prompt_price": cost_in,
                            "completion_price": cost_out,
                            "context_length": context,
                        }
                    )
                except (json.JSONDecodeError, KeyError):
                    pass

                json_lines = []
                brace_count = 0
                current_model_id = None
        elif line.startswith("{"):
            json_lines.append(line)
            brace_count = line.count("{") - line.count("}")
        else:
            current_model_id = line

    return models


def get_gemini_models() -> list[dict[str, Any]]:
    """Get known Gemini CLI models.

    Note: gemini CLI doesn't have a --list-models command.
    These are the default models known to be available.

    Based on gemini-cli source code and documentation:
    - gemini-2.5-flash (default, fastest)
    - gemini-2.5-pro (advanced reasoning)

    Free tier: 60 requests/min and 1,000 requests/day with OAuth.
    """
    return [
        {
            "id": "gemini-2.5-flash",
            "name": "Gemini 2.5 Flash",
            "provider": "gemini-cli",
            "is_free": True,
            "prompt_price": 0.0,
            "completion_price": 0.0,
            "context_length": 1048576,
            "description": "Fastest Gemini 2.5 model (1M context, free: 60 req/min, 1000 req/day)",
        },
        {
            "id": "gemini-2.5-pro",
            "name": "Gemini 2.5 Pro",
            "provider": "gemini-cli",
            "is_free": True,
            "prompt_price": 0.0,
            "completion_price": 0.0,
            "context_length": 1000000,
            "description": "Advanced Gemini 2.5 model (1M context, free: 60 req/min, 1000 req/day)",
        },
    ]


def get_vibe_models() -> list[dict[str, Any]]:
    """Get known Vibe CLI models.

    Note: vibe CLI doesn't have a --list-models command.
    These are the default Mistral models known to be available.

    Based on Mistral AI announcement (Devstral 2 and Vibe CLI):
    - Devstral 2 (123B) - next-generation coding model
    - Devstral Small 2 (24B) - laptop-friendly

    Vibe CLI is free and open-source (Apache 2.0 license).
    """
    return [
        {
            "id": "devstral-2",
            "name": "Devstral 2 (123B)",
            "provider": "vibe",
            "is_free": True,
            "prompt_price": 0.0,
            "completion_price": 0.0,
            "context_length": 256000,
            "description": "Next-generation coding model (256k context, open-source)",
        },
        {
            "id": "devstral-small-2",
            "name": "Devstral Small 2 (24B)",
            "provider": "vibe",
            "is_free": True,
            "prompt_price": 0.0,
            "completion_price": 0.0,
            "context_length": 256000,
            "description": "Laptop-friendly coding model (256k context, open-source)",
        },
    ]


def get_qwen_models() -> list[dict[str, Any]]:
    """Get known Qwen CLI models.

    Note: qwen CLI doesn't have a --list-models command.
    These are the default Qwen models known to be available.

    Based on qwen-code CLI documentation:
    - Qwen3.5-Plus (latest, optimized for qwen-code)
    - Qwen3-Coder (code-specialized, open-source)

    Free tier: 1,000 requests/day with Qwen OAuth.
    """
    return [
        {
            "id": "qwen-plus-latest",
            "name": "Qwen 3.5 Plus",
            "provider": "qwen",
            "is_free": True,
            "prompt_price": 0.0,
            "completion_price": 0.0,
            "context_length": 1000000,
            "description": "Latest Qwen model (1M context, free: 1000 req/day with OAuth)",
        },
        {
            "id": "qwen3-coder",
            "name": "Qwen 3 Coder",
            "provider": "qwen",
            "is_free": True,
            "prompt_price": 0.0,
            "completion_price": 0.0,
            "context_length": 1000000,
            "description": "Code-specialized model (1M context, open-source)",
        },
    ]


def discover_cli_models(
    force_refresh: bool = False,
    tools: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Discover models from all CLI tools.

    Args:
        force_refresh: Force cache refresh
        tools: List of tools to discover (default: all available)

    Returns:
        Dictionary mapping tool names to their model lists
    """
    # Check cache first
    if not force_refresh:
        cached = get_cached_cli_models()
        if cached is not None:
            return cached

    # Default to all tools if not specified
    if tools is None:
        tools = ["opencode", "gemini", "vibe", "qwen"]

    results = {}

    # opencode - has dynamic discovery
    if "opencode" in tools:
        try:
            results["opencode"] = get_opencode_models()
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            results["opencode"] = []

    # gemini - use known models (no --list-models)
    if "gemini" in tools:
        results["gemini"] = get_gemini_models()

    # vibe - use known models (no --list-models)
    if "vibe" in tools:
        results["vibe"] = get_vibe_models()

    # qwen - use known models (no --list-models)
    if "qwen" in tools:
        results["qwen"] = get_qwen_models()

    # Save to cache
    save_cli_models_to_cache(results)

    return results


def format_cli_models_for_display(
    models: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Format CLI models for display in /s output.

    Returns:
        List of CLI tool entries with model details
    """
    display_data = []

    for tool_name, tool_models in models.items():
        if not tool_models:
            continue

        # Count free vs paid
        free_count = sum(1 for m in tool_models if m.get("is_free", False))

        display_data.append(
            {
                "name": f"{tool_name} CLI",
                "cost": "FREE"
                if free_count == len(tool_models)
                else f"FREEMIUM ({free_count}/{len(tool_models)} free)",
                "notes": f"{len(tool_models)} models available",
                "models": tool_models,
            }
        )

    return display_data


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Discover CLI tool models")
    parser.add_argument("--refresh", action="store_true", help="Force cache refresh")
    parser.add_argument(
        "--tools",
        nargs="+",
        help="Tools to discover",
        default=["opencode", "gemini", "vibe", "qwen"],
    )
    parser.add_argument("--json", action="store_true", help="Output JSON")

    args = parser.parse_args()

    models = discover_cli_models(force_refresh=args.refresh, tools=args.tools)

    if args.json:
        print(json.dumps(models, indent=2))
    else:
        for tool, tool_models in models.items():
            print(f"\n{tool}:")
            for m in tool_models:
                free_tag = "FREE" if m.get("is_free") else f"${m.get('prompt_price', 0):.4f}"
                print(f"  {free_tag:8} {m.get('context_length', 0):>10,} ctx  {m.get('id')}")
