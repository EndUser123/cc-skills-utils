# Evidence Contract

> Reference for gitbatch evidence file format, naming, and summary generation

## Evidence File Format

Each package writes a JSON file to the evidence directory:

```json
{
  "package": "<pkg_name>",
  "skill": "<skill_name>",
  "status": "PASS|FAIL|SKIP",
  "timestamp": "<ISO8601>",
  "summary": "<one-line summary>",
  "details": {
    // Skill-specific content
  },
  "themes": [
    // For failures: categorized root causes
  ]
}
```

## Skill-Specific Evidence Fields

### `/p` (Code Maturation Pipeline)

```json
{
  "status": "PASS",
  "summary": "235 tests collected, 16 failed",
  "details": {
    "tests_collected": 235,
    "tests_passed": 219,
    "tests_failed": 16,
    "pre_existing_failures": 14,
    "new_failures": 2
  },
  "themes": [
    {"name": "workflow_steps schema mismatch", "count": 2, "packages": ["skill-guard", "search-research"]}
  ]
}
```

### `/gitready` (Skill Readiness)

```json
{
  "status": "FAIL",
  "summary": "Missing pointers: P1.md, PHASE-3.md",
  "details": {
    "missing_pointers": ["P1.md", "PHASE-3.md"],
    "documentation_gaps": []
  },
  "themes": [
    {"name": "Incomplete pointer files", "count": 1, "packages": ["some-skill"]}
  ]
}
```

## Evidence File Naming

- **Format:** `<package_name>.json`
- **Location:** `P:\\\\\\packages/gitbatch/.evidence/batch_<timestamp>/`
- **Latest symlink:** `P:\\\\\\packages/gitbatch/.evidence/latest` -> `batch_<timestamp>/`

## Summary Generation

After all packages are processed, gitbatch reads all evidence JSON files and generates a skill-adaptive summary:

1. **Counts** packages by status (passed/failed/skipped)
2. **Groups** failures by theme (not individual tests)
3. **Formats** output using skill-specific template
4. **Persists** summary alongside evidence files
