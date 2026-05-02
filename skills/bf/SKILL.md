---
name: bf
description: >
  Bifrost workbench — direct Python import of bf_agent library.
  Routes to bf_agent.run_simple() for stateless modes, run_compare() for fan-out,
  run_code() for multi-turn code agent with tool loop.
version: "2.0.0"
status: experimental
enforcement: advisory
category: routing
argument-hint: <mode> <model> <prompt...>
disable-model-invocation: true
triggers:
  - /bf
workflow_steps:
  - import bf_agent
  - call run_simple / run_compare / run_code
  - report result
---

You are a Bifrost workbench controller.

## bf_agent library

All work is done by importing and calling the bf_agent library:

```python
from bf_agent import run_simple, run_compare, run_code
```

No HTTP, no curl, no subprocess. Just Python in-process.

## bf_agent API

**run_simple(mode, prompt, model)** — stateless one-shot
- Modes: brainstorm, design, plan, review, explore
- Model: M27, GLM-5.1, DSv4-flash (default: DSv4-flash)
- Returns: {ok, mode, model, text, error, metrics{ttfb_ms, total_ms, status, error_type}}

**run_compare(prompt, models)** — parallel fan-out with LangGraph synthesis
- Models: list of model names, default [M27, GLM-5.1, DSv4-flash]
- Returns: {ok, mode, models, results[], synthesis, metrics{wall_time_ms, timed_out_models}}

**run_code(prompt, model, max_turns)** — multi-turn tool loop agent
- Model: M27, GLM-5.1, DSv4-flash (default: DSv4-flash)
- max_turns: optional override (default from BF_CODE_MAX_TURNS env, fallback 6)
- Returns: {ok, mode, model, answer, turns[], completed_via}
- Tool actions: read_file, list_dir, glob, write_file, final_answer
- Tool results fed back to model each turn until final_answer or max_turns

## Invocation

  /bf <mode> <model> <prompt...>

Argument semantics:
- `$0` = mode
- `$1` = model alias
- remaining text = task prompt

Defaults:
- If mode missing: `brainstorm`
- If model missing (non-compare): `M27`
- In compare mode, if models missing: `M27,GLM-5.1,DSv4-flash` (all three)

Modes:
- `brainstorm`: generate multiple ideas, directions, and variations
- `design`: focus on architecture, interfaces, contracts, tradeoffs
- `plan`: ordered steps with risks and checkpoints
- `review`: critique, find weaknesses, suggest improvements
- `explore`: open-ended investigation and hypothesis generation
- `code`: multi-turn tool loop — read files, write edits, final_answer
- `compare`: fan out across models in parallel, synthesize via LangGraph

Allowed model values:
  M27, GLM-5.1, DSv4-flash

## Implementation

### Simple modes (brainstorm/design/plan/review/explore)

```python
from bf_agent import run_simple

result = run_simple("$0", "<prompt>", model="$1")
print(result["text"] or f"ERROR: {result['error']}")
```

### Compare mode

```python
from bf_agent import run_compare

result = run_compare("<prompt>", models=["M27", "GLM-5.1", "DSv4-flash"])
for r in result["results"]:
    print(f"## {r['model']}\n{r['text']}\n")
print("## Synthesis\n" + result["synthesis"])
```

### Code mode

```python
from bf_agent import run_code

result = run_code("<prompt>", model="DSv4-flash")
print(result["answer"])
print(f"(completed via: {result['completed_via']}, turns: {len(result['turns'])})")
```

## Constraints

- BF_ALLOWED_ROOT defaults to P:/
- File reads limited to BF_FILE_CHAR_LIMIT (default 12000 chars)
- Directory listing capped at BF_DIR_ITEM_LIMIT (default 200 items)
- Glob capped at BF_GLOB_LIMIT (default 100 matches)
- Code agent max turns: BF_CODE_MAX_TURNS env or 6
- Timeout per model call: BF_TIMEOUT_MS env or 120000ms

## Examples

- /bf brainstorm M27 ideas for a repo-local memory system
- /bf design DSv4-flash plugin architecture for MCP-heavy workflows
- /bf plan GLM-5.1 migration from Python to TypeScript
- /bf review M27 this plugin architecture for brittleness
- /bf compare M27,GLM-5.1,DSv4-flash best architecture for multi-model planning in Claude Code
- /bf code DSv4-flash read P:/README.md and propose a refactor
- /bf explore GLM-5.1 what would a pre-mortem skill look like in Claude Code