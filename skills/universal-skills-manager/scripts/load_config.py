#!/usr/bin/env python3
"""
Config Loader for Universal Skills Manager

Loads config.json and exports environment variables for use in skill workflows.
This script should be sourced at the start of skill workflows:

    # In bash:
    eval $(python3 scripts/load_config.py)

    # Or for direct use in Python:
    import load_config; load_config.load()

Exports:
    SKILLSMP_API_KEY - API key for SkillsMP services
"""

import json
import os
import sys
from pathlib import Path


def load_config():
    """Load config.json and return environment variables as a dict."""
    # Determine script directory and skill root
    script_dir = Path(__file__).parent
    skill_dir = script_dir.parent
    config_file = skill_dir / "config.json"

    # Check if config exists
    if not config_file.exists():
        print(f"# ⚠️  Config file not found: {config_file}", file=sys.stderr)
        print("#    API features will be limited to public endpoints only.", file=sys.stderr)
        return {}

    # Load config
    try:
        with open(config_file) as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"# ⚠️  Error loading config: {e}", file=sys.stderr)
        return {}

    # Extract API key
    api_key = config.get("skillsmp_api_key", "")

    if not api_key:
        print("# ⚠️  No skillsmp_api_key found in config.json", file=sys.stderr)
        print("#    API features will be limited to public endpoints only.", file=sys.stderr)
        return {}

    # Verbose output
    if os.environ.get("USM_VERBOSE", "false") == "true":
        print(f"# ✅ Config loaded: SKILLSMP_API_KEY set (length: {len(api_key)})", file=sys.stderr)

    # Return environment variables as bash-exportable format
    return {
        "SKILLSMP_API_KEY": api_key,
    }


def main():
    """Main entry point - outputs bash export statements."""
    env_vars = load_config()

    if not env_vars:
        return 0  # Don't fail - allow skill to work with public features

    # Output bash export statements
    for key, value in env_vars.items():
        # Escape value for shell
        escaped_value = value.replace("'", "'\\''")
        print(f"export {key}='{escaped_value}'")

    return 0


if __name__ == "__main__":
    sys.exit(main())
