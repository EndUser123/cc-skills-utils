#!/usr/bin/env python3
"""
Brainstorm CLI Command - Multi-Agent Ideation System

This CLI provides a command-line interface for the multi-agent brainstorming system.
It coordinates multiple AI personas through a 3-phase workflow (Diverge, Discuss, Converge)
to generate and evaluate ideas on any topic.

Usage Examples:
    # Basic usage
    python brainstorm_cmd.py "ideas for improving team productivity"

    # With specific personas
    python brainstorm_cmd.py "design a coffee shop" \
        --personas Expert Innovator Pragmatist \
        --num-ideas 15

    # Save results to file
    python brainstorm_cmd.py "API security best practices" \
        --output json \
        --save results.json

    # Verbose mode with custom timeout
    python brainstorm_cmd.py "refactor legacy codebase" \
        --verbose \
        --timeout 300 \
        --num-ideas 20
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from enum import Enum
from pathlib import Path

import click

# Setup sys.path for external LLM dependencies
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "__csf" / "src"))
sys.path.insert(0, str(Path(__file__).parent))

# Import brainstorming components
try:
    from llm.providers import LLMConfig

    from lib import BrainstormOrchestrator, BrainstormResult
    BRAINSTORM_AVAILABLE = True
except ImportError as e:
    BRAINSTORM_AVAILABLE = False
    IMPORT_ERROR = str(e)


class OutputFormat(Enum):
    """Output format options."""

    TEXT = "text"
    JSON = "json"
    MARKDOWN = "markdown"


# Available personas
AVAILABLE_PERSONAS = [
    "Expert",
    "Innovator",
    "Pragmatist",
    "Critic",
    "Synthesizer",
]


def validate_personas(ctx: click.Context, param: click.Option, value: tuple) -> list[str]:
    """
    Validate that requested personas are available.

    Args:
        ctx: Click context
        param: Click option parameter
        value: Tuple of persona names from command line

    Returns:
        List of validated persona names

    Raises:
        click.BadParameter: If invalid personas are provided

    """
    if not value:
        return AVAILABLE_PERSONAS.copy()

    personas = list(value)
    invalid = [p for p in personas if p not in AVAILABLE_PERSONAS]

    if invalid:
        available_str = ", ".join(AVAILABLE_PERSONAS)
        raise click.BadParameter(
            f"Invalid personas: {', '.join(invalid)}. Available: {available_str}"
        )

    return personas


def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable format.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string (e.g., "2m 34s", "45s")

    """
    if seconds >= 60:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    return f"{int(seconds)}s"


def format_score_bar(score: float, width: int = 20) -> str:
    """
    Create a visual bar for scores.

    Args:
        score: Score value (0-100)
        width: Width of the bar in characters

    Returns:
        Visual bar string

    """
    filled = int((score / 100) * width)
    empty = width - filled
    bar = "█" * filled + "░" * empty
    return f"[{bar}] {score:.1f}/100"


def output_text(result: BrainstormResult, verbose: bool = False) -> None:
    """
    Output results in plain text format.

    Args:
        result: Brainstorm result to output
        verbose: Whether to show verbose output

    """
    click.echo("\n" + "=" * 80)
    click.echo(f"BRAINSTORM RESULTS: {result.context.topic}")
    click.echo("=" * 80)

    # Session info
    click.echo(f"\nSession ID: {result.session_id}")
    click.echo(f"Timestamp: {result.timestamp.isoformat()}")
    click.echo(f"Total Ideas Generated: {result.total_ideas}")

    # Metrics
    if "metrics" in result.metadata:
        metrics = result.metadata["metrics"]
        click.echo("\nExecution Metrics:")
        click.echo(f"  Total Duration: {format_duration(metrics.get('total_duration', 0))}")
        click.echo(f"  Diverge Phase: {format_duration(metrics.get('diverge_duration', 0))}")
        click.echo(f"  Discuss Phase: {format_duration(metrics.get('discuss_duration', 0))}")
        click.echo(f"  Converge Phase: {format_duration(metrics.get('converge_duration', 0))}")
        click.echo(f"  Agents Spawned: {metrics.get('agents_spawned', 0)}")

    # Quality metrics
    if "average_score" in result.metadata:
        click.echo("\nQuality Metrics:")
        click.echo(f"  Average Score: {result.metadata['average_score']:.1f}")
        if "score_distribution" in result.metadata:
            dist = result.metadata["score_distribution"]
            click.echo(f"  Score Range: {dist['min']:.1f} - {dist['max']:.1f}")
            click.echo(f"  Median Score: {dist['median']:.1f}")

    # Top ideas
    click.echo(f"\n{'=' * 80}")
    click.echo("TOP IDEAS")
    click.echo("=" * 80)

    top_n = 10 if verbose else 5
    for i, idea in enumerate(result.top_ideas(top_n), 1):
        click.echo(f"\n{i}. {idea.content[:100]}...")
        click.echo(f"   Persona: {idea.persona}")
        click.echo(f"   Score: {format_score_bar(idea.score)}")

        # Show evaluation if available
        if idea.id in result.evaluations:
            eval = result.evaluations[idea.id]
            click.echo(f"   Novelty:    {format_score_bar(eval.novelty_score)}")
            click.echo(f"   Feasibility: {format_score_bar(eval.feasibility_score)}")
            click.echo(f"   Impact:     {format_score_bar(eval.impact_score)}")

        # Show reasoning in verbose mode
        if verbose and idea.reasoning_path:
            click.echo("   Reasoning:")
            for step in idea.reasoning_path:
                click.echo(f"     - {step}")

    # Personas used
    click.echo(f"\n{'=' * 80}")
    click.echo("PERSONAS USED")
    click.echo("=" * 80)
    for persona in result.context.personas:
        count = len(result.get_ideas_by_persona(persona))
        click.echo(f"  {persona}: {count} ideas")


def output_json(result: BrainstormResult, output_file: Path | None = None) -> None:
    """
    Output results in JSON format.

    Args:
        result: Brainstorm result to output
        output_file: Optional file path to save output

    """
    data = result.model_dump(mode="json")

    json_str = json.dumps(data, indent=2, default=str)

    if output_file:
        output_file.write_text(json_str, encoding="utf-8")
        click.echo(f"Results saved to: {output_file}")
    else:
        click.echo(json_str)


def output_markdown(result: BrainstormResult, output_file: Path | None = None) -> str:
    """
    Output results in Markdown format.

    Args:
        result: Brainstorm result to output
        output_file: Optional file path to save output

    Returns:
        Markdown string

    """
    lines = []

    # Header
    lines.append(f"# Brainstorm Results: {result.context.topic}")
    lines.append("")
    lines.append(f"**Session ID:** `{result.session_id}`  ")
    lines.append(f"**Timestamp:** {result.timestamp.isoformat()}  ")
    lines.append(f"**Total Ideas:** {result.total_ideas}  ")
    lines.append("")

    # Metrics
    if "metrics" in result.metadata:
        metrics = result.metadata["metrics"]
        lines.append("## Execution Metrics")
        lines.append("")
        lines.append(f"- **Total Duration:** {format_duration(metrics.get('total_duration', 0))}  ")
        lines.append(f"- **Diverge Phase:** {format_duration(metrics.get('diverge_duration', 0))}  ")
        lines.append(f"- **Discuss Phase:** {format_duration(metrics.get('discuss_duration', 0))}  ")
        lines.append(f"- **Converge Phase:** {format_duration(metrics.get('converge_duration', 0))}  ")
        lines.append(f"- **Agents Spawned:** {metrics.get('agents_spawned', 0)}  ")
        lines.append("")

    # Quality Metrics
    if "average_score" in result.metadata:
        lines.append("## Quality Metrics")
        lines.append("")
        lines.append(f"- **Average Score:** {result.metadata['average_score']:.1f}/100  ")
        if "score_distribution" in result.metadata:
            dist = result.metadata["score_distribution"]
            lines.append(f"- **Score Range:** {dist['min']:.1f} - {dist['max']:.1f}  ")
            lines.append(f"- **Median Score:** {dist['median']:.1f}  ")
        lines.append("")

    # Top Ideas
    lines.append("## Top Ideas")
    lines.append("")

    for i, idea in enumerate(result.top_ideas(10), 1):
        lines.append(f"### {i}. {idea.content}")
        lines.append("")
        lines.append(f"- **Persona:** {idea.persona}  ")
        lines.append(f"- **Score:** {idea.score:.1f}/100  ")

        if idea.id in result.evaluations:
            eval = result.evaluations[idea.id]
            lines.append(f"- **Novelty:** {eval.novelty_score:.1f}/100  ")
            lines.append(f"- **Feasibility:** {eval.feasibility_score:.1f}/100  ")
            lines.append(f"- **Impact:** {eval.impact_score:.1f}/100  ")

            if eval.arguments_pro:
                lines.append("- **Strengths:**")
                for arg in eval.arguments_pro[:3]:
                    lines.append(f"  - {arg}")

            if eval.arguments_con:
                lines.append("- **Weaknesses:**")
                for arg in eval.arguments_con[:3]:
                    lines.append(f"  - {arg}")

        if idea.reasoning_path:
            lines.append("- **Reasoning Path:**")
            for step in idea.reasoning_path:
                lines.append(f"  1. {step}")

        lines.append("")

    # Personas Summary
    lines.append("## Personas Summary")
    lines.append("")
    for persona in result.context.personas:
        count = len(result.get_ideas_by_persona(persona))
        lines.append(f"- **{persona}:** {count} ideas  ")
    lines.append("")

    markdown = "\n".join(lines)

    if output_file:
        output_file.write_text(markdown, encoding="utf-8")
        click.echo(f"Results saved to: {output_file}")
    else:
        click.echo(markdown)

    return markdown


def save_result(result: BrainstormResult, filepath: Path, format_type: str) -> None:
    """
    Save result to file in specified format.

    Args:
        result: Brainstorm result to save
        filepath: Path to save file
        format_type: Output format (text/json/markdown)

    """
    filepath = Path(filepath)

    # Ensure directory exists
    filepath.parent.mkdir(parents=True, exist_ok=True)

    if format_type == "json":
        output_json(result, filepath)
    elif format_type == "markdown":
        output_markdown(result, filepath)
    else:
        # Default to text
        import io
        from contextlib import redirect_stdout

        f = io.StringIO()
        with redirect_stdout(f):
            output_text(result, verbose=True)

        filepath.write_text(f.getvalue(), encoding="utf-8")
        click.echo(f"Results saved to: {filepath}")


def show_progress(phase: str, message: str = "") -> None:
    """
    Show progress update.

    Args:
        phase: Current phase name
        message: Optional progress message

    """
    if message:
        click.echo(f"  [{phase}] {message}")
    else:
        click.echo(f"[{phase}]")


# CLI Command
@click.command()
@click.argument("prompt", required=False)
@click.option(
    "--personas",
    "-p",
    multiple=True,
    callback=validate_personas,
    help="Personas to use (default: all). Available: " + ", ".join(AVAILABLE_PERSONAS),
)
@click.option(
    "--num-ideas",
    "-n",
    default=10,
    type=click.IntRange(1, 100),
    help="Number of ideas to generate (default: 10, max: 100)",
)
@click.option(
    "--timeout",
    "-t",
    default=180,
    type=click.IntRange(30, 600),
    help="Maximum execution time in seconds (default: 180, min: 30, max: 600)",
)
@click.option(
    "--output",
    "-o",
    type=click.Choice(["text", "json", "markdown"], case_sensitive=False),
    default="text",
    help="Output format (default: text)",
)
@click.option(
    "--save",
    "-s",
    type=click.Path(),
    help="Save results to file",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed progress and output",
)
@click.option(
    "--list-personas",
    is_flag=True,
    help="List available personas and exit",
)
@click.option(
    "--real-llm",
    is_flag=True,
    help="Use real LLM providers instead of mock mode (requires API keys)",
)
@click.option(
    "--pheromone-trail",
    is_flag=True,
    help="Enable pheromone trail to learn from successful exploration paths",
)
@click.option(
    "--pheromone-db",
    default=None,
    type=click.Path(),
    help="Path to pheromone trail database (default: data/brainstorm_pheromones.db)",
)
@click.option(
    "--replay-buffer",
    is_flag=True,
    help="Enable replay buffer to reuse successful ideas from previous sessions",
)
@click.option(
    "--replay-db",
    default=None,
    type=click.Path(),
    help="Path to replay buffer database (default: data/brainstorm_replay.db)",
)
@click.option(
    "--persona-memory",
    "--pm",
    is_flag=True,
    help="Store brainstorm results to persona memory for cross-system search",
)
@click.option(
    "--top-only",
    is_flag=True,
    help="When using --persona-memory, only store top 5 ideas as permanent",
)
def main(
    prompt: str | None,
    personas: list[str],
    num_ideas: int,
    timeout: int,
    output: str,
    save: str | None,
    verbose: bool,
    list_personas: bool,
    real_llm: bool,
    pheromone_trail: bool,
    pheromone_db: str,
    replay_buffer: bool,
    replay_db: str,
    persona_memory: bool,
    top_only: bool,
) -> None:
    """
    Brainstorm ideas using multi-agent collaboration.

    PROMPT: The topic or problem to brainstorm about

    Example usage:

        \b
        # Basic usage
        brainstorm "ideas for improving team productivity"

        \b
        # With specific personas and more ideas
        brainstorm "design a coffee shop" --personas Expert Innovator Pragmatist --num-ideas 15

        \b
        # Save results as JSON
        brainstorm "API security best practices" --output json --save results.json

        \b
        # Verbose mode with custom timeout
        brainstorm "refactor legacy codebase" --verbose --timeout 300 --num-ideas 20

        \b
        # Use real LLM providers
        brainstorm "AI safety research" --real-llm --personas Expert Critic
    """
    # Check availability
    if not BRAINSTORM_AVAILABLE:
        click.echo("Error: Brainstorming system not available.", err=True)
        if IMPORT_ERROR:
            click.echo(f"Import error: {IMPORT_ERROR}", err=True)
        click.echo("Please ensure the brainstorm module is properly installed.", err=True)
        sys.exit(1)

    # List personas if requested
    if list_personas:
        click.echo("Available Personas:")
        for persona in AVAILABLE_PERSONAS:
            click.echo(f"  - {persona}")
        sys.exit(0)

    # Validate prompt
    if not prompt or not prompt.strip():
        click.echo("Error: Prompt cannot be empty.", err=True)
        click.echo('Usage: python brainstorm_cmd.py "your prompt here"', err=True)
        click.echo("   or: python brainstorm_cmd.py --help", err=True)
        sys.exit(1)

    # Display configuration in verbose mode
    if verbose:
        click.echo("\n" + "=" * 80)
        click.echo("BRAINSTORM CONFIGURATION")
        click.echo("=" * 80)
        click.echo(f"Prompt: {prompt}")
        click.echo(f"Personas: {', '.join(personas)}")
        click.echo(f"Target Ideas: {num_ideas}")
        click.echo(f"Timeout: {timeout}s")
        click.echo(f"Output Format: {output}")
        if save:
            click.echo(f"Save File: {save}")
        if pheromone_trail:
            click.echo(f"Pheromone Trail: enabled ({pheromone_db})")
        if replay_buffer:
            click.echo(f"Replay Buffer: enabled ({replay_db})")
        click.echo("=" * 80 + "\n")

    # Initialize orchestrator
    if verbose:
        click.echo("Initializing brainstorm orchestrator...")

    # Configure LLM mode
    llm_config = None
    if real_llm:
        if verbose:
            click.echo("Enabling real LLM mode...")
        llm_config = LLMConfig(mock_mode=False)
    elif verbose:
        click.echo("Using mock mode (use --real-llm for actual AI calls)")

    # Configure learning systems
    if pheromone_trail and verbose:
        click.echo("Enabling pheromone trail...")
    if replay_buffer and verbose:
        click.echo("Enabling replay buffer...")

    orchestrator = BrainstormOrchestrator(
        llm_config=llm_config,
        enable_pheromone_trail=pheromone_trail,
        pheromone_db_path=pheromone_db,
        enable_replay_buffer=replay_buffer,
        replay_db_path=replay_db,
    )
    start_time = time.time()

    try:
        # Run brainstorming session
        click.echo(f"Starting brainstorm session on: {prompt[:100]}...\n")

        result = asyncio.run(
            orchestrator.brainstorm(
                prompt=prompt,
                personas=personas,
                timeout=float(timeout),
                num_ideas=num_ideas,
            )
        )

        elapsed = time.time() - start_time

        # Show completion summary
        click.echo(f"\n✓ Brainstorm completed in {format_duration(elapsed)}")
        click.echo(f"  Generated {result.total_ideas} ideas")
        click.echo(f"  Performed {result.total_evaluations} evaluations")

        # Calculate quality score
        if result.total_ideas > 0 and "average_score" in result.metadata:
            avg_score = result.metadata["average_score"]
            click.echo(f"  Average quality score: {avg_score:.1f}/100")

        # Output results
        click.echo("\n")

        if output == "json":
            output_json(result, Path(save) if save else None)
        elif output == "markdown":
            output_markdown(result, Path(save) if save else None)
        else:
            output_text(result, verbose=verbose)

        # Save to file if requested and not already done
        if save and output != "json" and output != "markdown":
            save_result(result, Path(save), output)

        # Store to persona memory if requested
        if persona_memory:
            try:
                from brainstorm.memory.persona_store import (
                    store_brainstorm_result,
                    store_top_ideas,
                )

                if top_only:
                    stored = store_top_ideas(result, n=5, retention_tag="permanent")
                    click.echo(f"✓ Stored top {stored} ideas to persona memory (permanent)")
                else:
                    stored = store_brainstorm_result(result, retention_tag="90day")
                    click.echo(f"✓ Stored {stored} ideas to persona memory (90day retention)")
            except Exception as e:
                click.echo(f"Warning: Could not store to persona memory: {e}", err=True)

        # Exit with success
        sys.exit(0)

    except KeyboardInterrupt:
        click.echo("\n\nInterrupted by user.", err=True)
        sys.exit(130)

    except TimeoutError:
        click.echo(f"\n\nError: Brainstorm session timed out after {timeout}s", err=True)
        click.echo("Try increasing the timeout with --timeout or reducing --num-ideas", err=True)
        sys.exit(1)

    except ValueError as e:
        click.echo(f"\n\nError: {e}", err=True)
        sys.exit(1)

    except Exception as e:
        click.echo(f"\n\nUnexpected error: {e}", err=True)
        if verbose:
            import traceback
            click.echo(traceback.format_exc(), err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
