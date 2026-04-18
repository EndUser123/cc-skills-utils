"""
Profile Configuration for /s Skill

Provides preset configurations that map to personas, debate mode, timeout,
and local repetition settings. This reduces cognitive load by offering
pre-configured options for common use cases.

Profiles:
- fast: 2 personas, no debate, 1 repetition, 180s timeout
- normal: 4 personas, fast debate, 2 repetitions, 300s timeout
- deep: 6 personas, full debate, 3 repetitions, 600s timeout
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Profile:
    """
    A profile preset for /s brainstorming configuration.

    Attributes:
        name: Profile name (fast, normal, deep)
        personas: List of persona names to use
        debate_mode: Debate mode (none, fast, full)
        local_repetition: Number of local LLM repetitions for diversity
        timeout: Session timeout in seconds
        description: Human-readable description
    """

    name: str
    personas: tuple[str, ...]
    debate_mode: Literal["none", "fast", "full"]
    local_repetition: int
    timeout: float
    description: str

    def to_dict(self) -> dict[str, any]:
        """Convert profile to dictionary for argparse."""
        return {
            "name": self.name,
            "personas": ",".join(self.personas),
            "debate_mode": self.debate_mode,
            "local_repetition": self.local_repetition,
            "timeout": self.timeout,
            "description": self.description,
        }


# Profile definitions
PROFILES: dict[str, Profile] = {
    "fast": Profile(
        name="fast",
        personas=("innovator", "pragmatist"),
        debate_mode="none",
        local_repetition=1,
        timeout=180.0,
        description="Quick decisions (2 personas, no debate, 180s timeout)",
    ),
    "normal": Profile(
        name="normal",
        personas=("innovator", "pragmatist", "critic", "expert"),
        debate_mode="fast",
        local_repetition=2,
        timeout=300.0,
        description="Standard use (4 personas, fast debate, 300s timeout)",
    ),
    "deep": Profile(
        name="deep",
        personas=("innovator", "pragmatist", "critic", "expert", "futurist", "synthesizer"),
        debate_mode="full",
        local_repetition=3,
        timeout=600.0,
        description="Complex analysis (6 personas, full debate, 600s timeout)",
    ),
}

# Default profile
DEFAULT_PROFILE = "normal"


def profile_from_name(name: str) -> Profile:
    """
    Get a profile by name.

    Args:
        name: Profile name (fast, normal, deep)

    Returns:
        Profile configuration

    Raises:
        ValueError: If profile name is not found
    """
    name_lower = name.lower()
    if name_lower not in PROFILES:
        available = ", ".join(PROFILES.keys())
        raise ValueError(f"Unknown profile '{name}'. Available profiles: {available}")
    return PROFILES[name_lower]


def get_available_profiles() -> list[str]:
    """Get list of available profile names."""
    return list(PROFILES.keys())


def validate_profile_flags(args) -> tuple[Profile | None, list[str]]:
    """
    Validate that profile doesn't conflict with explicit flags.

    Args:
        args: Parsed argparse namespace

    Returns:
        Tuple of (profile or None, list of conflict warnings)
    """
    if not hasattr(args, "profile") or not args.profile:
        return None, []

    profile = profile_from_name(args.profile)
    conflicts = []

    # Check for conflicting flags
    if hasattr(args, "personas") and args.personas:
        conflicts.append(
            f"--personas flag specified with --profile {args.profile} "
            "(flag will override profile personas)"
        )

    if hasattr(args, "debate_mode") and args.debate_mode != profile.debate_mode:
        conflicts.append(
            f"--debate-mode {args.debate_mode} specified with --profile {args.profile} "
            "(flag will override profile debate mode)"
        )

    if (
        hasattr(args, "local_llm_repetition")
        and args.local_llm_repetition != profile.local_repetition
    ):
        conflicts.append(
            f"--local-llm-repetition {args.local_llm_repetition} specified with --profile {args.profile} "
            "(flag will override profile repetition)"
        )

    if hasattr(args, "timeout") and args.timeout != profile.timeout:
        conflicts.append(
            f"--timeout {args.timeout} specified with --profile {args.profile} "
            "(flag will override profile timeout)"
        )

    return profile, conflicts


def apply_profile_to_args(args, profile: Profile) -> None:
    """
    Apply profile settings to args namespace (modifies in place).

    Only applies settings that weren't explicitly set by the user.
    Explicit flags (non-default values) take precedence over profile.

    Args:
        args: Argparse namespace to modify
        profile: Profile configuration to apply
    """
    # Only apply profile values if user hasn't explicitly set those flags
    # Check if the flag was explicitly provided (not default)

    # For personas: apply if --personas wasn't used
    if hasattr(args, "personas") and not args.personas:
        args.personas = ",".join(profile.personas)

    # For debate_mode: apply if --debate-mode wasn't used (default is "fast")
    if hasattr(args, "debate_mode") and args.debate_mode == "fast":
        args.debate_mode = profile.debate_mode

    # For local_repetition: apply if --local-llm-repetition is default (2)
    if hasattr(args, "local_llm_repetition") and args.local_llm_repetition == 2:
        args.local_llm_repetition = profile.local_repetition

    # For timeout: apply if --timeout is default (600.0 in run_heavy.py)
    if hasattr(args, "timeout") and args.timeout == 600.0:
        args.timeout = profile.timeout
