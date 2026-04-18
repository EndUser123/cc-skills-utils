#!/usr/bin/env python3
"""
Display functions for /s skill.

Uses shared model enumerator from CSF to fetch models dynamically
from provider APIs with caching. No hardcoded model data.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.table import Table

# Add CSF src to path for shared model enumerator
CSF_SRC = Path(__file__).parent.parent.parent.parent.parent / "__csf" / "src"
if CSF_SRC.exists():
    sys.path.insert(0, str(CSF_SRC))

# Import leaderboard types from the same directory
import importlib.util  # noqa: E402
import sys  # noqa: E402

from src.core.config.api_keys import APIKeyManager  # noqa: E402
from src.llm.providers.utils.model_enumerator import (  # noqa: E402
    ModelInfo,
    enumerate_chutes_models,
    enumerate_gemini_models,
    enumerate_groq_models,
    enumerate_nvidia_models,
    enumerate_openrouter_models,
    enumerate_zai_models,
)

_leaderboard_path = Path(__file__).parent / "leaderboard_registry.py"
spec = importlib.util.spec_from_file_location("leaderboard_registry", _leaderboard_path)
if spec and spec.loader:
    _leaderboard_module = importlib.util.module_from_spec(spec)
    sys.modules["leaderboard_registry"] = _leaderboard_module
    spec.loader.exec_module(_leaderboard_module)
    LeaderboardEntry = _leaderboard_module.LeaderboardEntry
else:
    # Fallback if import fails
    LeaderboardEntry = None  # type: ignore

console = Console()

# Cache configuration
MODELS_CACHE_PATH = Path.home() / ".claude" / "llm-api-models.json"
CACHE_EXPIRY_HOURS = 12

# Leaderboard registry (optional - may not exist in all environments)
_leaderboard_registry = None
try:
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(
        "leaderboard_registry", Path(__file__).parent / "leaderboard_registry.py"
    )
    if spec and spec.loader:
        _leaderboard_registry = importlib.util.module_from_spec(spec)
        sys.modules["leaderboard_registry"] = _leaderboard_registry
        spec.loader.exec_module(_leaderboard_registry)
except Exception:
    pass  # Leaderboard optional


@dataclass
class CachedModels:
    """Cached model data with timestamp."""

    models_by_provider: dict[str, list[ModelInfo]] = field(default_factory=dict)
    timestamp: float = 0.0

    def is_fresh(self) -> bool:
        """Check if cache is still fresh."""
        import time

        return time.time() - self.timestamp < (CACHE_EXPIRY_HOURS * 3600)


_cache: CachedModels | None = None


def _load_cache(allow_stale: bool = False) -> CachedModels | None:
    """Load models from cache.

    Args:
        allow_stale: If True, returns cache even if expired.
    """
    global _cache

    if _cache and (allow_stale or _cache.is_fresh()):
        return _cache

    if not MODELS_CACHE_PATH.exists():
        return None

    try:
        import json
        import time

        with open(MODELS_CACHE_PATH) as f:
            data = json.load(f)

        # Read timestamp from JSON metadata for timezone consistency (UTC)
        metadata = data.get("_metadata", {})
        cache_time = metadata.get("timestamp")
        if cache_time is None:
            # Fallback to st_mtime for old cache files without metadata
            cache_time = MODELS_CACHE_PATH.stat().st_mtime

        cache_age_hours = (time.time() - cache_time) / 3600

        if not allow_stale and cache_age_hours >= CACHE_EXPIRY_HOURS:
            return None

        # Reconstruct ModelInfo objects (exclude metadata from model data)
        models_by_provider = {}
        for provider, models_data in data.items():
            if provider == "_metadata":
                continue  # Skip metadata field
            models_by_provider[provider] = [
                ModelInfo(
                    id=m["id"],
                    name=m["name"],
                    provider=m["provider"],
                    is_free=m.get("is_free", False),
                    prompt_price=m.get("prompt_price", 0.0),
                    completion_price=m.get("completion_price", 0.0),
                    context_length=m.get("context_length", 0),
                    description=m.get("description", ""),
                )
                for m in models_data
            ]

        _cache = CachedModels(models_by_provider=models_by_provider, timestamp=cache_time)
        return _cache

    except Exception as e:
        console.print(f"[dim]Failed to load cache: {e}[/dim]")
        return None


def _save_cache(models_by_provider: dict[str, list[ModelInfo]]) -> None:
    """Save models to cache."""
    global _cache

    try:
        import json
        import time

        MODELS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Convert to JSON-serializable format
        data = {}
        for provider, models in models_by_provider.items():
            data[provider] = [
                {
                    "id": m.id,
                    "name": m.name,
                    "provider": m.provider,
                    "is_free": m.is_free,
                    "prompt_price": m.prompt_price,
                    "completion_price": m.completion_price,
                    "context_length": m.context_length,
                    "description": m.description,
                }
                for m in models
            ]

        # Include timestamp in JSON for timezone consistency (UTC)
        data["_metadata"] = {
            "timestamp": time.time(),
            "version": "1.0",
        }

        with open(MODELS_CACHE_PATH, "w") as f:
            json.dump(data, f, indent=2)

        _cache = CachedModels(models_by_provider=models_by_provider, timestamp=time.time())

    except Exception as e:
        console.print(f"[dim]Failed to save cache: {e}[/dim]")


async def _fetch_models(refresh: bool = False) -> tuple[dict[str, list[ModelInfo]], float]:
    """Fetch models from provider APIs.

    Args:
        refresh: Force refresh by bypassing cache

    Returns:
        Tuple of (models_by_provider, timestamp)
    """
    # Try cache first (skip if refresh=True)
    if not refresh:
        cached = _load_cache()
        if cached:
            console.print(f"[dim]Using cached models ({CACHE_EXPIRY_HOURS}h expiry)[/dim]\n")
            return cached.models_by_provider, cached.timestamp

    console.print("[dim]Fetching models from providers...[/dim]\n")

    api_manager = APIKeyManager()
    results = {}

    # Helper to fetch from a provider
    async def fetch_provider(
        provider_name: str,
        enumerator_func,
    ) -> None:
        config = api_manager.get_provider(provider_name)
        if not config or not config.api_key:
            return

        try:
            models = await enumerator_func(config.api_key)
            results[provider_name] = models
        except Exception as e:
            console.print(f"[dim]Error fetching {provider_name}: {e}[/dim]")

    # Fetch from all providers in parallel with timeout protection
    fetch_time = 0.0
    try:
        import time

        fetch_time = time.time()
        await asyncio.wait_for(
            asyncio.gather(
                fetch_provider("openrouter", enumerate_openrouter_models),
                fetch_provider("chutes", enumerate_chutes_models),
                fetch_provider("gemini", enumerate_gemini_models),
                fetch_provider("groq", enumerate_groq_models),
                fetch_provider("nvidia", enumerate_nvidia_models),
                fetch_provider("zai", enumerate_zai_models),
            ),
            timeout=30.0,  # 30 second timeout for all provider fetches
        )
    except TimeoutError:
        console.print("[yellow]Warning: Provider API fetch timed out after 30 seconds[/yellow]")
        console.print("[dim]Falling back to stale cache if available[/dim]\n")

    # If fetch failed or timed out, fallback to stale cache
    if not results:
        cached = _load_cache(allow_stale=True)
        if cached:
            return cached.models_by_provider, cached.timestamp
        return {}, 0.0

    # Save to cache if we got fresh results
    if results:
        _save_cache(results)

    return results, fetch_time


# Known paid providers (pay-per-token, not free/subscription)
PAID_PROVIDERS = {
    "anthropic",
    "openai",
    "open",
}

# Known free/subscription providers
FREE_PROVIDERS = {
    "groq",
    "chutes",
    "openrouter",
    "nvidia",
    "qwen",
    "google",
    "deepseek",
    "meta-llama",
    "mistralai",
    "mistral",
}


def _is_free_or_subscription(model: ModelInfo) -> bool:
    """Check if a model is free or subscription-based (not pay-per-token).

    Includes:
    - Models marked as free
    - Models with zero pricing
    - Providers that offer free tiers: groq, chutes, openrouter
    - Specific free/subscription model providers: qwen, google (gemini), deepseek, meta-llama, mistralai

    Excludes paid providers: anthropic, openai
    """
    # First check: exclude known paid providers
    if model.provider.lower() in PAID_PROVIDERS:
        return False

    # Direct free flag
    if model.is_free:
        return True

    # Zero pricing indicates free
    if model.prompt_price == 0 and model.completion_price == 0:
        return True

    # Providers with free tiers
    free_tier_providers = {"groq", "chutes", "openrouter"}
    if model.provider.lower() in free_tier_providers:
        return True

    # Free/subscription model providers
    free_model_providers = {"qwen", "google", "deepseek", "meta-llama", "mistralai", "mistral"}
    if model.provider.lower() in free_model_providers:
        return True

    return False


def _get_cost_category(model: ModelInfo) -> str:
    """Determine cost category for a model."""
    if _is_free_or_subscription(model):
        return "FREE"
    return "PAID"


def _get_leaderboard_ranking(
    model: ModelInfo,
    leaderboard_data: dict[str, list],
) -> str:
    """Get leaderboard ranking string for a model.

    Returns formatted string like "C:85 R:78" for Coding/Reasoning scores.
    """
    if _leaderboard_registry is None:
        return ""

    # Build model_id in provider format
    model_id = f"{model.provider}/{model.id}"

    scores = []
    for category_key, label in [
        ("coding", "C"),
        ("reasoning", "R"),
        ("general", "G"),
        ("math", "M"),
    ]:
        entries = leaderboard_data.get(category_key, [])
        for entry in entries:
            if entry.model_id == model_id or entry.model_id == model.id:
                scores.append(f"{label}:{entry.score:.0f}")
                break

    return " ".join(scores) if scores else ""


def _print_api_table(
    tier_name: str,
    models: list[ModelInfo],
    leaderboard_data: dict[str, list] | None = None,
) -> None:
    """Print API models in a Rich table format."""
    console.print(f"\n[bold]{tier_name}[/bold]")

    if not models:
        console.print("  [dim]None[/dim]")
        return

    table = Table(show_header=True, header_style="bold cyan", box=None)
    table.add_column("Model", style="white", width=30)
    table.add_column("Provider", style="yellow", width=25)
    table.add_column("Cost", style="green", width=8)
    table.add_column("Score", style="magenta", width=8)
    table.add_column("Notes", style="dim", width=45)

    for model in models:
        cost = _get_cost_category(model)
        # Get the score for this model from leaderboard data
        score = ""
        if leaderboard_data:
            model_id = f"{model.provider}/{model.id}"
            for entries in leaderboard_data.values():
                for entry in entries:
                    if entry.model_id == model_id or entry.model_id == model.id:
                        score = f"{entry.score:.0f}"
                        break
                if score:
                    break

        table.add_row(
            model.name,
            model.provider,
            cost,
            score,
            model.description[:45] if model.description else "",
        )

    console.print(table)


def _print_category_table(
    category_name: str,
    category_key: str,
    leaderboard_data: dict[str, list[LeaderboardEntry]],
    model_info_map: dict[str, ModelInfo],
    api_provider_map: dict[str, str],
    limit: int = 6,
    available_providers: set[str] | None = None,
) -> str:
    """Print top models for a specific category.

    Args:
        available_providers: Set of provider names with configured API keys

    Returns:
        Markdown formatted table for response inclusion
    """
    entries = leaderboard_data.get(category_key, [])

    # Filter to free/subscription models only
    free_entries = []
    for entry in entries:
        # Get model info
        model_info = model_info_map.get(entry.model_id)
        if not model_info:
            # Try to find by model ID without provider prefix
            if "/" in entry.model_id:
                model_id = entry.model_id.split("/")[-1]
                model_info = model_info_map.get(model_id)

        # Skip if not found or not free/subscription
        if not model_info:
            continue
        if not _is_free_or_subscription(model_info):
            continue

        free_entries.append((entry, model_info))

    # Sort by score (descending) and limit
    free_entries.sort(key=lambda x: x[0].score, reverse=True)
    free_entries = free_entries[:limit]

    console.print(f"\n[bold cyan]{category_name}[/bold cyan]")

    # Build markdown table
    md_lines = [f"\n{category_name}"]
    md_lines.append("| Model | API Host | Cost | Score | Benchmark |")
    md_lines.append("|-------|----------|------|-------|-----------|")

    if not free_entries:
        console.print("  [dim]None[/dim]")
        md_lines.append("| *None* | | | | |")
        console.print("")  # Empty line after category
        return "\n".join(md_lines) + "\n"

    table = Table(show_header=True, header_style="bold cyan", box=None)
    table.add_column("Model", style="white", width=35)
    table.add_column("API Host", style="yellow", width=25)
    table.add_column("Cost", style="green", width=8)
    table.add_column("Score", style="magenta", width=8)
    table.add_column("Benchmark", style="dim", width=30)

    for entry, model_info in free_entries:
        cost = _get_cost_category(model_info)
        # Use leaderboard entry info for notes, not provider description
        benchmark = f"{entry.benchmark}"
        if len(benchmark) > 28:
            benchmark = benchmark[:25] + "..."

        # Get API hosting provider (where to use API keys)
        api_provider = api_provider_map.get(entry.model_id, model_info.provider)

        # Check if provider API key is configured
        if (
            available_providers is not None
            and api_provider
            and api_provider.lower() not in available_providers
        ):
            api_provider_display = f"{api_provider} (needs key)"
        else:
            api_provider_display = api_provider or "unknown"

        table.add_row(
            model_info.name,
            api_provider_display,
            cost,
            f"{entry.score:.0f}",
            benchmark,
        )

        # Add markdown row
        md_lines.append(
            f"| {model_info.name} | {api_provider_display} | {cost} | {entry.score:.0f} | {benchmark} |"
        )

    console.print(table)
    console.print("")  # Empty line after category
    return "\n".join(md_lines) + "\n"


def _print_cli_table(cli_tools: list[dict]) -> str:
    """Print CLI tools in a Rich table format.

    If a tool has a 'models' key, displays individual models.
    Otherwise, displays the tool as a single entry.

    Returns:
        Markdown formatted table for response inclusion
    """
    console.print("\n[bold]CLI LOCAL TOOLS[/bold]")

    # Build markdown table
    md_lines = ["\nCLI LOCAL TOOLS"]
    md_lines.append("| Tool | Cost | Context | Notes |")
    md_lines.append("|------|------|---------|-------|")

    if not cli_tools:
        console.print("  [dim]None[/dim]")
        md_lines.append("| *None* | | | |")
        console.print("")  # Empty line after CLI section
        return "\n".join(md_lines) + "\n"

    table = Table(show_header=True, header_style="bold cyan", box=None)
    table.add_column("Model", style="white", width=35)
    table.add_column("Cost", style="green", width=12)
    table.add_column("Context", style="cyan", width=12)
    table.add_column("Notes", style="dim", width=45)

    for tool in cli_tools:
        # If tool has detailed models, show each one
        if "models" in tool and tool["models"]:
            models = tool["models"]
            # Show tool name as a header for its models
            tool_name = tool["name"]
            table.add_row(
                f"[bold]{tool_name}[/bold]",
                tool["cost"],
                "",
                f"{len(models)} models available",
            )
            # Add markdown header row for tool with models
            md_lines.append(
                f"| **{tool_name}** | {tool['cost']} | | {len(models)} models available |"
            )

            # Show individual models
            for model in models[:5]:  # Limit to 5 models per tool
                model_id = model.get("id", "unknown")
                context = model.get("context_length", 0)
                is_free = model.get("is_free", False)
                cost_tag = "FREE" if is_free else f"${model.get('prompt_price', 0):.4f}"

                # Format context for display
                if context >= 1000000:
                    context_str = f"{context // 1000000}M"
                elif context >= 1000:
                    context_str = f"{context // 1000}K"
                else:
                    context_str = str(context)

                table.add_row(
                    f"  └─ {model_id}",
                    cost_tag,
                    f"{context_str} ctx",
                    model.get("description", ""),
                )

                # Add markdown row for individual model
                md_lines.append(
                    f"| └─ {model_id} | {cost_tag} | {context_str} ctx | {model.get('description', '')} |"
                )

            # Show "and N more" if there are additional models
            if len(models) > 5:
                table.add_row(
                    f"  └─ [dim]... and {len(models) - 5} more[/dim]",
                    "",
                    "",
                    f"Use 'cli_models.py --tools {tool_name.split()[0].lower()}' for full list",
                )
                md_lines.append(
                    f"| └─ ... and {len(models) - 5} more | | | See: `cli_models.py --tools {tool_name.split()[0].lower()}` |"
                )
        else:
            # Static tool entry (no detailed models)
            table.add_row(
                tool["name"],
                tool["cost"],
                "",
                tool["notes"],
            )
            md_lines.append(f"| {tool['name']} | {tool['cost']} | | {tool['notes']} |")

    console.print(table)
    console.print("")  # Empty line after CLI section
    return "\n".join(md_lines) + "\n"


def _display_summary(models_by_provider: dict[str, list[ModelInfo]]) -> None:
    """Display summary of free and subscription models."""
    all_models = []
    for models in models_by_provider.values():
        all_models.extend(models)

    free_models = [m for m in all_models if _is_free_or_subscription(m)]
    paid_models = [m for m in all_models if not _is_free_or_subscription(m)]

    print("\n" + "-" * 70)
    print(" SUMMARY")
    print("-" * 70)

    print(f"\n### Free Models ({len(free_models)}) ###")
    if free_models:
        for model in free_models[:20]:  # Limit output
            print(f"  ✅ {model.name} ({model.provider})")
        if len(free_models) > 20:
            print(f"  ... and {len(free_models) - 20} more")
    else:
        print("  None")

    print(f"\n### Paid Models ({len(paid_models)}) ###")
    if paid_models:
        for model in paid_models[:10]:  # Limit output
            print(f"  💰 {model.name} ({model.provider})")
        if len(paid_models) > 10:
            print(f"  ... and {len(paid_models) - 10} more")
    else:
        print("  None")

    print("\n" + "=" * 70)


async def _display_free_models_async(refresh: bool = False) -> str:
    """Display free and subscription models from all providers.

    Uses leaderboard data as the source of truth for which models to show.
    Leaderboard data is cached for 7 days.

    Args:
        refresh: Force refresh of leaderboard cache (ignores 7-day expiry)

    Returns:
        Markdown formatted tables for response inclusion
    """
    # Collect markdown output for response inclusion
    markdown_lines: list[str] = []

    console.print(
        "\n[bold cyan]╔════════════════════════════════════════════════════════════════════╗[/bold cyan]"
    )
    console.print(
        "[bold cyan]║[/bold cyan] [bold white]/s - Available Models (Dynamic)[/bold white]                                     [bold cyan]║[/bold cyan]"
    )
    console.print(
        "[bold cyan]╚════════════════════════════════════════════════════════════════════╝[/bold cyan]"
    )

    # Fetch leaderboard data from JSON file (single source of truth)
    leaderboard_data = {}
    if _leaderboard_registry is not None:
        try:
            leaderboard_data = _leaderboard_registry.fetch_leaderboard_data()
        except FileNotFoundError as e:
            console.print(f"[yellow]Leaderboard data file not found: {e}[/yellow]")
            console.print("[dim]Update leaderboard_data.json with fresh arena.ai data[/dim]\n")
        except Exception as e:
            console.print(f"[dim]Leaderboard fetch failed: {e}[/dim]")

    if not leaderboard_data:
        console.print(
            "[yellow]No leaderboard data available. Run with --refresh to fetch.[/yellow]"
        )
        sys.exit(0)

    # Build a set of all model IDs from leaderboard data
    leaderboard_model_ids = set()
    for category_entries in leaderboard_data.values():
        for entry in category_entries:
            leaderboard_model_ids.add(entry.model_id)
            # Also add the model ID without provider prefix
            if "/" in entry.model_id:
                leaderboard_model_ids.add(entry.model_id.split("/")[-1])

    # Optionally fetch model details from providers (12-hour cache) for pricing/description
    models_by_provider, _ = await _fetch_models(refresh=refresh)

    # Create a mapping of model_id -> ModelInfo for quick lookup
    model_info_map = {}
    for _, models in models_by_provider.items():
        for model in models:
            model_id = f"{model.provider}/{model.id}"
            model_info_map[model_id] = model
            model_info_map[model.id] = model  # Also map without provider prefix

    # Build display models from leaderboard data (deduplicated by model_id)
    display_models_map = {}  # model_id -> (provider, ModelInfo)
    invalid_model_ids = []  # Track models not in provider data

    for _, entries in leaderboard_data.items():
        for entry in entries:
            # Skip if we already have this model
            if entry.model_id in display_models_map:
                continue

            # Get model details if available, otherwise create a basic ModelInfo
            model_info = model_info_map.get(entry.model_id)
            if model_info:
                # Use the fetched model details
                provider = model_info.provider
                display_models_map[entry.model_id] = (provider, model_info)
            else:
                # Track models without provider data (validation failure)
                invalid_model_ids.append(entry.model_id)

                # Create a basic ModelInfo from leaderboard entry
                parts = entry.model_id.split("/", 1)
                provider = parts[0] if len(parts) > 1 else "unknown"
                model_id = parts[1] if len(parts) > 1 else entry.model_id

                # Skip paid providers entirely
                if provider.lower() in PAID_PROVIDERS:
                    continue

                # Create a basic ModelInfo (with warning indicator)
                from src.llm.providers.utils.model_enumerator import ModelInfo

                display_models_map[entry.model_id] = (
                    provider,
                    ModelInfo(
                        id=model_id,
                        name=entry.model_id,
                        provider=provider,
                        is_free=True,  # Free providers only
                        prompt_price=0.0,
                        completion_price=0.0,
                        context_length=0,
                        description=f"Elo: {entry.score:.0f} on {entry.benchmark} [unverified]",
                    ),
                )

    # Show validation warning if models were skipped
    if invalid_model_ids:
        console.print(
            f"[yellow]Warning: {len(invalid_model_ids)} models not in provider data:[/yellow]"
        )
        # Show up to 5 invalid model IDs
        for model_id in invalid_model_ids[:5]:
            console.print(f"  [dim]- {model_id}[/dim]")
        if len(invalid_model_ids) > 5:
            console.print(f"  [dim]... and {len(invalid_model_ids) - 5} more[/dim]")
        console.print("[dim]These models may not be available through configured API keys.[/dim]\n")

    # Build model_info_map from display_models_map for category display
    # Track which API provider each model came from
    model_info_for_categories = {}
    # API Host vs Model Creator distinction:
    # - api_provider_map[model_id] -> API hosting provider (openrouter, chutes, groq)
    #   This tells users which API key to use for accessing the model
    # - model.provider -> Model creator (Google, DeepSeek, Meta, etc.)
    #   This identifies the company that created the model
    # Example: gemini-2.5-flash (created by Google) hosted via chutes
    api_provider_map = {}  # model_id -> API provider (openrouter, chutes, groq)

    for provider_name, models in models_by_provider.items():
        for model in models:
            model_id = f"{model.provider}/{model.id}"
            api_provider_map[model_id] = provider_name
            api_provider_map[model.id] = provider_name

    # Include all free/subscription models from leaderboard data
    for model_id, (_, model_info) in display_models_map.items():
        if _is_free_or_subscription(model_info):
            model_info_for_categories[model_id] = model_info

    # Get available API providers (providers with configured API keys)
    # Start with providers we successfully fetched models from
    available_providers: set[str] = set(models_by_provider.keys())

    # Also check for other common providers that might have keys but no models fetched
    api_manager = APIKeyManager()
    extra_providers = [
        "openrouter",
        "chutes",
        "gemini",
        "groq",
        "nvidia",
        "zai",
        "openai",
        "anthropic",
        "google",
        "mistral",
        "deepseek",
    ]
    for provider_name in extra_providers:
        if provider_name not in available_providers:
            config = api_manager.get_provider(provider_name)
            if config and config.api_key:
                available_providers.add(provider_name)

    # Display top 6 models per category
    markdown_lines.append(
        _print_category_table(
            "REASONING (Top 6)",
            "reasoning",
            leaderboard_data,
            model_info_for_categories,
            api_provider_map,
            limit=6,
            available_providers=available_providers,
        )
    )
    markdown_lines.append(
        _print_category_table(
            "CODING (Top 6)",
            "coding",
            leaderboard_data,
            model_info_for_categories,
            api_provider_map,
            limit=6,
            available_providers=available_providers,
        )
    )
    markdown_lines.append(
        _print_category_table(
            "GENERAL (Top 6)",
            "general",
            leaderboard_data,
            model_info_for_categories,
            api_provider_map,
            limit=6,
            available_providers=available_providers,
        )
    )
    markdown_lines.append(
        _print_category_table(
            "MATH (Top 6)",
            "math",
            leaderboard_data,
            model_info_for_categories,
            api_provider_map,
            limit=6,
            available_providers=available_providers,
        )
    )

    # Display CLI tools with dynamic model discovery
    try:
        # Import CLI model discovery module
        import cli_models

        # Discover CLI models (uses cache by default)
        discovered_models = cli_models.discover_cli_models(force_refresh=refresh)

        # Format for display
        cli_tools = cli_models.format_cli_models_for_display(discovered_models)

        # Add static fallback for tools without discovery
        if not any("codex" in tool["name"].lower() for tool in cli_tools):
            cli_tools.append(
                {"name": "codex-cli", "cost": "FREE", "notes": "Python-focused CLI tool"}
            )

        markdown_lines.append(_print_cli_table(cli_tools))
    except Exception as e:
        # Fallback to static list on error
        console.print(f"[dim]CLI model discovery failed: {e}[/dim]")
        cli_tools = [
            {"name": "qwen-code CLI", "cost": "FREE", "notes": "CLI tool for Qwen models"},
            {"name": "gemini-cli", "cost": "FREE", "notes": "CLI tool for Gemini models"},
            {"name": "codex-cli", "cost": "FREE", "notes": "Python-focused CLI tool"},
            {
                "name": "vibe (Mistral)",
                "cost": "FREEMIUM",
                "notes": "Mistral-powered CLI, Python tasks",
            },
            {"name": "opencode-ai CLI", "cost": "FREEMIUM", "notes": "Multi-provider meta-tool"},
        ]
        markdown_lines.append(_print_cli_table(cli_tools))

    # Summary section
    console.print(
        f"\n[dim]Total models with leaderboard data: {len(model_info_for_categories)}[/dim]"
    )

    # Calculate and display data freshness timestamps
    import time
    from datetime import datetime

    # Get model cache timestamp
    model_cache_time = None
    if MODELS_CACHE_PATH.exists():
        model_cache_time = MODELS_CACHE_PATH.stat().st_mtime

    # Get leaderboard cache timestamp
    leaderboard_cache_time = None
    if _leaderboard_registry is not None:
        try:
            leaderboard_cache_time = (
                _leaderboard_registry._cache.timestamp if _leaderboard_registry._cache else None
            )
        except AttributeError:
            pass

    # Format timestamps for display
    def format_timestamp(ts: float | None) -> str:
        if ts is None:
            return "Unknown"
        dt = datetime.fromtimestamp(ts)
        age_hours = (time.time() - ts) / 3600
        if age_hours < 1:
            age_str = f"{int(age_hours * 60)}m ago"
        elif age_hours < 24:
            age_str = f"{int(age_hours)}h ago"
        else:
            age_str = f"{int(age_hours / 24)}d ago"
        return f"{dt.strftime('%Y-%m-%d %H:%M')} ({age_str})"

    model_cache_str = format_timestamp(model_cache_time)
    leaderboard_cache_str = format_timestamp(leaderboard_cache_time)

    console.print(f"[dim]Leaderboard data: {leaderboard_cache_str}[/dim]")
    console.print(f"[dim]Provider models: {model_cache_str}[/dim]")
    console.print(
        f"[dim]Cache expiry: Leaderboard 7 days | Models {CACHE_EXPIRY_HOURS} hours[/dim]"
    )

    # Cache conflict detection
    if model_cache_time and leaderboard_cache_time:
        # Check if provider cache is significantly newer than leaderboard cache
        age_diff_hours = (model_cache_time - leaderboard_cache_time) / 3600
        if age_diff_hours > 24:  # Provider cache more than 1 day newer
            console.print(
                f"[yellow]Warning: Provider cache is {int(age_diff_hours)}h newer than leaderboard cache[/yellow]"
            )
            console.print("[dim]Run '/s list --refresh' to sync both caches[/dim]\n")
        elif age_diff_hours < -24:  # Leaderboard cache more than 1 day newer
            console.print(
                f"[yellow]Warning: Leaderboard cache is {int(-age_diff_hours)}h newer than provider cache[/yellow]"
            )
            console.print("[dim]Run '/s list --refresh' to sync both caches[/dim]\n")

    # Add metadata section to markdown
    markdown_lines.append("\n### Data Freshness")
    markdown_lines.append(f"- **Leaderboard data**: {leaderboard_cache_str}")
    markdown_lines.append(f"- **Provider models**: {model_cache_str}")
    markdown_lines.append(
        f"- **Cache expiry**: Leaderboard 7 days | Models {CACHE_EXPIRY_HOURS} hours"
    )

    # Return all markdown for response inclusion
    return "\n".join(markdown_lines)


def _display_free_models(refresh: bool = False) -> str:
    """Sync wrapper for async model display.

    Args:
        refresh: Force refresh of both model and leaderboard caches

    Returns:
        Markdown formatted tables for response inclusion
    """
    return asyncio.run(_display_free_models_async(refresh=refresh))


__all__ = ["_display_free_models"]
