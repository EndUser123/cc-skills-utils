# Inline Execution Code

This file contains the full Python execution code for the `/explore` skill. This code executes directly in the skill context (NOT as subprocess), enabling access to Claude Code's Agent tool for Layer 2 semantic filtering.

## Full Source

```python
#!/usr/bin/env python3
"""Universal search with three-layer filtering - inline skill execution.

This code block executes directly in the skill context (NOT as subprocess).
This enables access to Claude Code's Agent tool for Layer 2 semantic filtering.

The actual orchestration logic is in orchestration.py - this markdown is a thin
shim that imports and delegates to it. This allows the same code to be imported
by pytest for Tier 2/3 verification.
"""

import sys
from pathlib import Path

# Add skills/explore to path so orchestration module can be imported
skills_path = Path(__file__).parent.parent
sys.path.insert(0, str(skills_path))

from skills.explore.orchestration import execute_unified_search as _execute


def main(query: str, **kwargs) -> str:
    """
Main entry point for /explore skill execution.

This function is called by Claude Code when the /explore skill is invoked.
    It executes inline (NOT as subprocess), enabling Agent tool access.
    """
    import asyncio
    result = asyncio.run(_execute(query, **kwargs))
    return result
```
