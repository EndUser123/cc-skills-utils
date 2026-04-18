"""
Unit tests for /s skill profile system.

Tests the Profile dataclass and helper functions.
"""

import sys
from dataclasses import FrozenInstanceError  # noqa: E402 (needed below)
from pathlib import Path

import pytest

# Add scripts directory to path for local imports
scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

from profiles.config import (  # noqa: E402
    DEFAULT_PROFILE,
    PROFILES,
    Profile,
    apply_profile_to_args,
    get_available_profiles,
    profile_from_name,
    validate_profile_flags,
)


class TestProfileDataclass:
    """Test Profile dataclass functionality."""

    def test_profile_creation(self):
        """Test creating a Profile instance."""
        profile = Profile(
            name="test",
            personas=("innovator", "pragmatist"),
            debate_mode="none",
            local_repetition=1,
            timeout=180.0,
            description="Test profile",
        )
        assert profile.name == "test"
        assert profile.personas == ("innovator", "pragmatist")
        assert profile.debate_mode == "none"
        assert profile.local_repetition == 1
        assert profile.timeout == 180.0
        assert profile.description == "Test profile"

    def test_profile_to_dict(self):
        """Test Profile.to_dict() method."""
        profile = Profile(
            name="test",
            personas=("innovator", "pragmatist"),
            debate_mode="none",
            local_repetition=1,
            timeout=180.0,
            description="Test profile",
        )
        result = profile.to_dict()
        assert result["name"] == "test"
        assert result["personas"] == "innovator,pragmatist"
        assert result["debate_mode"] == "none"
        assert result["local_repetition"] == 1
        assert result["timeout"] == 180.0
        assert result["description"] == "Test profile"

    def test_profile_immutability(self):
        """Test that Profile is frozen (immutable)."""
        profile = Profile(
            name="test",
            personas=("innovator",),
            debate_mode="none",
            local_repetition=1,
            timeout=180.0,
            description="Test",
        )
        with pytest.raises(FrozenInstanceError):
            profile.name = "modified"


class TestProfileDefinitions:
    """Test predefined profile configurations."""

    def test_fast_profile(self):
        """Test fast profile has correct settings."""
        profile = PROFILES["fast"]
        assert profile.name == "fast"
        assert profile.personas == ("innovator", "pragmatist")
        assert profile.debate_mode == "none"
        assert profile.local_repetition == 1
        assert profile.timeout == 180.0
        assert "Quick decisions" in profile.description

    def test_normal_profile(self):
        """Test normal profile has correct settings."""
        profile = PROFILES["normal"]
        assert profile.name == "normal"
        assert profile.personas == ("innovator", "pragmatist", "critic", "expert")
        assert profile.debate_mode == "fast"
        assert profile.local_repetition == 2
        assert profile.timeout == 300.0
        assert "Standard use" in profile.description

    def test_deep_profile(self):
        """Test deep profile has correct settings."""
        profile = PROFILES["deep"]
        assert profile.name == "deep"
        assert set(profile.personas) == {
            "innovator",
            "pragmatist",
            "critic",
            "expert",
            "futurist",
            "synthesizer",
        }
        assert profile.debate_mode == "full"
        assert profile.local_repetition == 3
        assert profile.timeout == 600.0
        assert "Complex analysis" in profile.description

    def test_default_profile(self):
        """Test DEFAULT_PROFILE constant."""
        assert DEFAULT_PROFILE == "normal"
        assert DEFAULT_PROFILE in PROFILES


class TestProfileFromName:
    """Test profile_from_name() function."""

    def test_valid_name_lowercase(self):
        """Test getting profile with lowercase name."""
        profile = profile_from_name("fast")
        assert profile.name == "fast"

    def test_valid_name_uppercase(self):
        """Test getting profile with uppercase name (case-insensitive)."""
        profile = profile_from_name("FAST")
        assert profile.name == "fast"

    def test_valid_name_mixed_case(self):
        """Test getting profile with mixed case name."""
        profile = profile_from_name("NoRmAl")
        assert profile.name == "normal"

    def test_invalid_name_raises_error(self):
        """Test that invalid profile name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown profile 'invalid'"):
            profile_from_name("invalid")


class TestGetAvailableProfiles:
    """Test get_available_profiles() function."""

    def test_returns_list(self):
        """Test that get_available_profiles returns a list."""
        profiles = get_available_profiles()
        assert isinstance(profiles, list)

    def test_contains_expected_profiles(self):
        """Test that all expected profiles are in the list."""
        profiles = get_available_profiles()
        assert "fast" in profiles
        assert "normal" in profiles
        assert "deep" in profiles


class TestValidateProfileFlags:
    """Test validate_profile_flags() function."""

    def test_no_profile_returns_none(self):
        """Test when no profile specified."""
        args = MockNamespace(personas="", debate_mode="fast", local_llm_repetition=2, timeout=600.0)
        profile, conflicts = validate_profile_flags(args)
        assert profile is None
        assert conflicts == []

    def test_no_conflicts(self):
        """Test when profile has no conflicting flags."""
        args = MockNamespace(
            profile="fast", personas="", debate_mode="none", local_llm_repetition=1, timeout=180.0
        )
        profile, conflicts = validate_profile_flags(args)
        assert profile.name == "fast"
        assert conflicts == []

    def test_personas_conflict(self):
        """Test conflict when --personas specified with profile."""
        args = MockNamespace(
            profile="fast",
            personas="critic,expert",
            debate_mode="none",
            local_llm_repetition=1,
            timeout=180.0,
        )
        profile, conflicts = validate_profile_flags(args)
        assert len(conflicts) == 1
        assert "--personas" in conflicts[0]

    def test_debate_mode_conflict(self):
        """Test conflict when --debate-mode differs from profile."""
        args = MockNamespace(
            profile="fast",
            personas="",
            debate_mode="full",
            local_llm_repetition=1,
            timeout=180.0,
        )
        profile, conflicts = validate_profile_flags(args)
        assert len(conflicts) == 1
        assert "--debate-mode" in conflicts[0]

    def test_local_repetition_conflict(self):
        """Test conflict when --local-llm-repetition differs from profile."""
        args = MockNamespace(
            profile="fast",
            personas="",
            debate_mode="none",
            local_llm_repetition=3,
            timeout=180.0,
        )
        profile, conflicts = validate_profile_flags(args)
        assert len(conflicts) == 1
        assert "--local-llm-repetition" in conflicts[0]

    def test_timeout_conflict(self):
        """Test conflict when --timeout differs from profile."""
        args = MockNamespace(
            profile="fast",
            personas="",
            debate_mode="none",
            local_llm_repetition=1,
            timeout=600.0,
        )
        profile, conflicts = validate_profile_flags(args)
        assert len(conflicts) == 1
        assert "--timeout" in conflicts[0]


class TestApplyProfileToArgs:
    """Test apply_profile_to_args() function."""

    def test_applies_personas_when_empty(self):
        """Test applies profile personas when --personas is empty."""
        args = MockNamespace(personas="", debate_mode="fast", local_llm_repetition=2, timeout=600.0)
        profile = PROFILES["fast"]
        apply_profile_to_args(args, profile)
        assert args.personas == "innovator,pragmatist"

    def test_keeps_explicit_personas(self):
        """Test keeps explicit --personas value."""
        args = MockNamespace(
            personas="critic,expert", debate_mode="fast", local_llm_repetition=2, timeout=600.0
        )
        profile = PROFILES["fast"]
        apply_profile_to_args(args, profile)
        assert args.personas == "critic,expert"  # Unchanged

    def test_applies_debate_mode_when_default(self):
        """Test applies profile debate_mode when --debate-mode is default."""
        args = MockNamespace(personas="", debate_mode="fast", local_llm_repetition=2, timeout=600.0)
        profile = PROFILES["deep"]
        apply_profile_to_args(args, profile)
        assert args.debate_mode == "full"

    def test_keeps_explicit_debate_mode(self):
        """Test keeps explicit --debate-mode value."""
        args = MockNamespace(personas="", debate_mode="none", local_llm_repetition=2, timeout=600.0)
        profile = PROFILES["deep"]
        apply_profile_to_args(args, profile)
        assert args.debate_mode == "none"  # Unchanged

    def test_applies_local_repetition_when_default(self):
        """Test applies profile local_repetition when --local-llm-repetition is default."""
        args = MockNamespace(personas="", debate_mode="fast", local_llm_repetition=2, timeout=600.0)
        profile = PROFILES["fast"]
        apply_profile_to_args(args, profile)
        assert args.local_llm_repetition == 1

    def test_keeps_explicit_local_repetition(self):
        """Test keeps explicit --local-llm-repetition value."""
        args = MockNamespace(personas="", debate_mode="fast", local_llm_repetition=5, timeout=600.0)
        profile = PROFILES["fast"]
        apply_profile_to_args(args, profile)
        assert args.local_llm_repetition == 5  # Unchanged

    def test_applies_timeout_when_default(self):
        """Test applies profile timeout when --timeout is default."""
        args = MockNamespace(personas="", debate_mode="fast", local_llm_repetition=2, timeout=600.0)
        profile = PROFILES["normal"]
        apply_profile_to_args(args, profile)
        assert args.timeout == 300.0

    def test_keeps_explicit_timeout(self):
        """Test keeps explicit --timeout value."""
        args = MockNamespace(personas="", debate_mode="fast", local_llm_repetition=2, timeout=900.0)
        profile = PROFILES["normal"]
        apply_profile_to_args(args, profile)
        assert args.timeout == 900.0  # Unchanged


class MockNamespace:
    """Mock argparse.Namespace for testing."""

    def __init__(self, **kwargs):
        # Set defaults
        self.profile = kwargs.get("profile", None)
        self.personas = kwargs.get("personas", "")
        self.debate_mode = kwargs.get("debate_mode", "fast")
        self.local_llm_repetition = kwargs.get("local_llm_repetition", 2)
        self.timeout = kwargs.get("timeout", 600.0)
