#!/usr/bin/env python3
"""
API Helper for Universal Skills Manager

Auto-loads config.json on module import, eliminating the need for manual
Step 0 execution. This module provides self-contained API key management.

Usage:
    import sys
    sys.path.insert(0, 'path/to/universal-skills-manager/scripts')
    import api_helper

    key = api_helper.get_api_key()
    if key:
        # Use authenticated endpoints
    else:
        # Fall back to public endpoints

Location: .claude/skills/universal-skills-manager/scripts/api_helper.py
"""

import os
from pathlib import Path

# Track if we've already loaded to avoid redundant reads
_LOADED = False


def _auto_load_config():
    """
    Load config.json once on module import.

    This function runs automatically when the module is imported,
    setting SKILLSMP_API_KEY in os.environ if config.json exists.
    """
    global _LOADED

    if _LOADED:
        return  # Already loaded

    try:
        # Determine script directory and skill root
        script_dir = Path(__file__).parent
        skill_dir = script_dir.parent
        config_file = skill_dir / "config.json"

        # Check if config exists
        if not config_file.exists():
            return  # Silent fail - public endpoints only

        # Load config
        import json

        with open(config_file) as f:
            config = json.load(f)

        # Extract API key
        api_key = config.get("skillsmp_api_key", "")
        if not api_key:
            return  # No key configured

        # Export to environment (persists for session)
        os.environ["SKILLSMP_API_KEY"] = api_key

    except (OSError, json.JSONDecodeError):
        # Silent fail - allow public endpoints
        pass
    finally:
        _LOADED = True


# Auto-load on module import
_auto_load_config()


def get_api_key():
    """
    Get SkillsMP API key.

    Returns:
        str: API key if configured, None otherwise

    Example:
        >>> import api_helper
        >>> key = api_helper.get_api_key()
        >>> if key:
        ...     print(f"API key configured: {key[:10]}...")
        ... else:
        ...     print("Using public endpoints only")
    """
    return os.environ.get("SKILLSMP_API_KEY")


def is_configured():
    """
    Check if SkillsMP API key is configured.

    Returns:
        bool: True if API key is available, False otherwise

    Example:
        >>> import api_helper
        >>> if api_helper.is_configured():
        ...     print("SkillsMP search available")
        ... else:
        ...     print("Using SkillHub/ClawHub (no key required)")
    """
    return bool(get_api_key())


# Main block for testing
if __name__ == "__main__":
    key = get_api_key()
    if key:
        print(f"✅ SKILLSMP_API_KEY configured (length: {len(key)})")
    else:
        print("⚠️  SKILLSMP_API_KEY not configured - public endpoints only")
