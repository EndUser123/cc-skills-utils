#!/usr/bin/env python3
"""
data_safety_vcs.py - Data Safety VCS Reference

Executable wrapper for the /data-safety-vcs skill.
Returns proper dict format for StopRouter.
"""

import json
import sys
from pathlib import Path

def main():
    """Return data-safety-vcs guidance as dict format."""
    skill_file = Path(__file__).parent / "SKILL.md"

    result = {
        "statusLine": "📋 Data Safety VCS loaded",
        "internalPrompt": skill_file.read_text(encoding='utf-8') if skill_file.exists() else "# Data Safety VCS not found"
    }

    print(json.dumps(result))


if __name__ == "__main__":
    main()
