# Suggested Commands

The following commands are useful for developing and testing the `/s` skill.

## Running the /s Skill
The main entry point for the skill is `scripts/run_heavy.py`.

```powershell
# Run with a specific topic
python scripts/run_heavy.py --topic "architecture options for auth migration"

# Run with a topic and project context
python scripts/run_heavy.py --topic "package/handoff" --context-path packages/handoff

# Run with custom personas
python scripts/run_heavy.py --topic "strategy topic" --personas "innovator,critic"

# Use only top-tier providers (claude/anthropic)
python scripts/run_heavy.py --topic "strategy topic" --provider-tier T1

# Full 3-round adversarial debate
python scripts/run_heavy.py --topic "strategy topic" --debate-mode full
```

## Testing
The project uses `pytest` for testing.

```powershell
# Run all tests
pytest tests/

# Run a specific test file
pytest tests/test_timeout.py

# Run tests with benchmarks
pytest tests/ --benchmark-only
```

## Linting and Formatting
The project uses `ruff` for linting and formatting.

```powershell
# Check for linting errors
ruff check .

# Fix fixable linting errors
ruff check . --fix

# Check formatting
ruff format . --check

# Format all files
ruff format .
```

## Utility Commands (Windows)
```powershell
# List files
dir /b
ls (if using PowerShell/Git Bash)

# Search for patterns
grep -r "pattern" . (if using Git Bash)
findstr /s /i "pattern" * (Windows native)
```
