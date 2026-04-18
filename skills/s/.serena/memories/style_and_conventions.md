# Style and Conventions

This project follows a 'Director Model' where the human is the director/architect and the AI is the primary developer.

## General Principles
- **Quality priority**: Thoroughness > speed. "Does it work correctly?" > "How fast can we ship?".
- **Constitutional Context**: Strategies should guide and assist AI agents, not replace user direction.
- **Functional verification**: Importing and testing code is essential.
- **LLM generation with guardrails**: DSLs, validation, and verification cycles are appropriate.

## Code Style
- **Python**: Use Python 3.12+ (latest features preferred).
- **Type Hints**: Use strong typing (e.g. `from __future__ import annotations`, `Callable`, `dataclass`, `Any`).
- **Docstrings**: Use Google-style docstrings for functions and classes.
- **Asynchronous I/O**: Use `asyncio` for non-blocking operations, especially when calling LLMs or doing file I/O.
- **Deterministic output**: Strive for reproducible results where possible.

## Testing
- **Co-location**: Tests should be co-located with their paired code in the proper directory (e.g. `tests/` for skill logic).
- **Test creation**: Agents are expected to create tests, scenarios, and verification code for new features.
- **Integration flows**: Use YAML-defined workflows (if applicable) and integration tests to verify complete paths.
- **Risk-aware testing**: Test what changed based on impact analysis.

## Forbidden Patterns
- **Autonomous execution**: Avoid background autonomous execution without user oversight.
- **Self-healing systems**: Do not implement code that modifies itself without human approval.
- **Complex frameworks**: Avoid "Enterprise" patterns where simple solutions suffice.
- **Lock-free multi-terminal coordination**: Keep terminal sessions independent.
