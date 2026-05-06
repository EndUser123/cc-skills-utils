# Subagent Result Envelope Pattern for gitbatch

> Standardize how subagents return results to avoid token streaming through orchestrator
> Source: Adapted from `/skill-ship` subagent-result-envelope.md

## Purpose

When gitbatch v0.5 executes `Skill()` calls, the orchestrator receives full skill output (~500-2000 tokens per package). With 8 packages, this means ~4000-16000 tokens of skill output flowing through the orchestrator context.

The Result Envelope pattern ensures agents write results to disk and return only a small summary.

## The Problem (v0.5)

```
Orchestrator executes Skill() for package 1
  → Skill output streams back: 800 tokens
Orchestrator executes Skill() for package 2
  → Skill output streams back: 1200 tokens
...
Total: ~8000 tokens through orchestrator
```

## The Solution (v0.6)

```
Agent executes Skill() for package 1
  → Saves results to file
  → Returns envelope: {"status": "done", "artifact": "...", "summary": "..."}
Agent executes Skill() for package 2
  → Saves results to file
  → Returns envelope: {"status": "done", "artifact": "...", "summary": "..."}
...
Total: ~300 tokens through orchestrator (8 envelopes × ~40 tokens)
```

## Result Envelope Schema

```json
{
  "status": "done | blocked | error",
  "artifact": "P:/packages/gitbatch/.evidence/batch_<ts>/<pkg>.json",
  "summary": "≤200 characters — what happened, key metrics",
  "metrics": {
    "bytes_written": 2048,
    "skill_output_lines": 150
  }
}
```

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | enum | Yes | `done`: completed successfully, `blocked`: needs user input, `error`: failed |
| `artifact` | string | Yes | Path to full output file (relative to project root) |
| `summary` | string | Yes | 1-3 sentence summary, max 200 chars |
| `metrics` | object | No | Optional metrics for observability |

## Implementation for gitbatch

### For Subagents

Each subagent spawned by gitbatch should:

1. Invoke the target skill via `Skill()` tool
2. Save skill results to the evidence file
3. Return a result envelope instead of letting full output stream back

```python
# Pseudocode for subagent
def execute_package_skill(pkg: str, skill: str, evidence_file: str) -> dict:
    # Run the skill
    result = skill_invoke(skill, target=pkg)

    # Write to evidence file (persists through compaction)
    write_json(evidence_file, {
        "package": pkg,
        "skill": skill,
        "status": extract_status(result),
        "summary": extract_summary(result),
        "details": extract_details(result)
    })

    # Return envelope (not full result)
    return {
        "status": "done",
        "artifact": evidence_file,
        "summary": f"{pkg}: {extract_summary(result)}",
        "metrics": {"bytes_written": filesize(evidence_file)}
    }
```

### For Orchestrator (gitbatch SKILL.md execution)

The orchestrator reads envelopes and generates summary:

```python
# Pseudocode for orchestrator
envelopes = []
for pkg in packages:
    agent = spawn_agent(f"gitbatch-{pkg}")
    envelope = agent.execute(execute_package_skill, pkg=pkg, skill=skill, evidence_file=evidence_file)
    envelopes.append(envelope)

# Generate summary from evidence files
summary = generate_skill_adaptive_summary(envelopes, evidence_dir)
```

## Benefits

| Metric | v0.5 (Legacy) | v0.6 (Agent-Based) |
|--------|---------------|-------------------|
| Tokens through orchestrator | ~8000 (8 packages) | ~320 (8 envelopes) |
| Compaction immunity | Partial (evidence files) | Full |
| Debugging | Full output in context | Read evidence files |
| Complexity | Simple | Moderate |

## Integration Points

### With Evidence Contract

The envelope's `artifact` field points to the evidence file, which follows the existing Evidence Contract format.

### With Skill-Adaptive Summary

The orchestrator reads evidence files to generate the skill-adaptive summary, just as in v0.5.

## Examples

### /p Skill Execution

```
Envelope 1: {"status": "done", "artifact": ".../debugRCA.json", "summary": "debugRCA: 553 passed, 5 failed", "metrics": {"bytes_written": 4096}}
Envelope 2: {"status": "done", "artifact": ".../gitready.json", "summary": "gitready: 120 passed, 1 skipped", "metrics": {"bytes_written": 2048}}
...
```

### Error Handling

```
Envelope 1: {"status": "error", "artifact": ".../search-research.json", "summary": "search-research: hung (infinite loop detected)", "metrics": {}}
```

---
**Source**: Adapted from `/skill-ship` subagent-result-envelope.md
**Related**: `../SKILL.md` (gitbatch v0.6 execution flow)
