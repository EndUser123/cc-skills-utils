"""
Profile configuration package for /s skill.

Exports Profile dataclass and helper functions.
"""

from .config import (
    DEFAULT_PROFILE,
    PROFILES,
    Profile,
    apply_profile_to_args,
    get_available_profiles,
    profile_from_name,
    validate_profile_flags,
)

__all__ = [
    "Profile",
    "PROFILES",
    "DEFAULT_PROFILE",
    "profile_from_name",
    "get_available_profiles",
    "validate_profile_flags",
    "apply_profile_to_args",
]
