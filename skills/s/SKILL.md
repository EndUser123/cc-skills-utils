---
id: s
name: s
description: Exploratory strategy with multi-persona brainstorming, GoT+ToT enhancement, and outcome scenario analysis
version: 2.8.0
status: stable
category: strategy
output_template: Template 1 (Strict Analysis Format)
extends:
  - PART C (Truthfulness) - Honest strategic assessment
  - PART P (Testing Workflow) - Options validation before implementation
triggers:
  - /s
  - "strategic analysis"
  - "brainstorm options"
  - "multi-option tradeoff"
aliases:
  - /s
suggest:
  - /r
follow_up_offer:
  - /design
workflow_steps:
  - step_parse_args: Extract topic and flags from user prompt; handle --help/--list/unknown flags
  - step_resolve_context: Check if topic is a filesystem path; set --context-path if so
  - step_run_script: Execute run_heavy.py with resolved args
  - step_display_results: Present ranked ideas, decision memo, and next-step hints
---

# /s - Strategy

## Purpose

General-purpose strategic thinking engine for any situation requiring multi-perspective analysis.

- Uses real `BrainstormOrchestrator` execution (`from lib.orchestrator import BrainstormOrchestrator`)
- Produces ranked options, tradeoffs, decision memo, and next-step hints
- **Multi-terminal friendly**: Works across concurrent sessions without coordination
- **No TTL, no stale data issues**: Generates fresh ideas each run, immune to context staleness
- Deterministic checks are intentionally out of scope; run `/r` first
- Owns exploratory cognitive checks from DUF decomposition (red-team, bias mirror, value-reveal)
- Uses multiple ideation techniques per persona:
  - **SCAMPER**: Substitute, Combine, Adapt, Modify, Put to other uses, Eliminate, Reverse
  - **Lateral Thinking**: Challenge assumptions, random entry points
  - **Six Thinking Hats**: Multiple perspectives (facts, feelings, caution, benefits, creativity, process)
  - **First Principles**: Break down to fundamental truths
  - **Reverse Engineering**: Work backwards from desired outcome

**Core principle**: `/s` applies fresh strategic thinking to the topic you provide. Use it to generate options, analyze tradeoffs, and explore strategic alternatives for any decision or plan.

## Constitutional Context

Director Model (human director + AI agent). Strategies guide AI agents under user direction. LLM-generated code with guardrails = appropriate. Autonomous background services = not appropriate. See `CLAUDE.md` for full context.

## Scope Boundary

- `/r`: deterministic remember + refine (what did we forget, predictable improvements, deterministic pre-mortem, plan validation)
- `/s`: exploratory multi-persona strategy (high-upside options, adversarial tradeoffs, and uncertainty handling)

## Usage

### Provide Your Topic Directly

`/s` works best when you provide a clear topic or question.

**Examples:**
```bash
/s "architecture options for auth migration"
/s "strategy for reducing technical debt"
/s "product roadmap for next 6 months"
```

### What /s Does With Your Topic

1. **Diverge**: Multiple personas generate diverse options (innovator, pragmatist, critic, expert)
2. **Discuss**: Options are ranked and filtered through constitutional constraints
3. **Converge**: Produces decision memo with tradeoffs and next steps

**Output:**
- Ranked ideas with scores
- Decision memo (chosen alternative, why others were rejected)
- Next command hints (/planning, /design)

### Recall and Prior Context

When `--recall` is used, `/s` queries CHS/CKS and includes only a few top-ranked snippets from prior sessions — not full transcripts. For any fact about current code or plans that matters for the strategy, confirm with a small targeted `Read` of the current artifact rather than trusting recalled history alone. Recall narrows what to look at; grounded reads verify it is still current.

### Anti-Anchoring vs Context Awareness

- Avoid anchoring on **solutions** (don't read existing implementation docs before brainstorming)
- Use conversation **context** (detect from `/q` and session activity what you're working on)
- Correct flow: `/q` (work summary) then `/s` (auto-detects context, applies strategic thinking)
- `/s` does NOT read existing implementation docs, ignore your conversation, or generate generic advice

## Decomposition Ownership

`/s` owns exploratory parts of removed skills:
- from `/opt`: multi-option optimization strategy, high-upside alternatives, adversarial tradeoffs
- from `/oops`: independent perspective escalation for recurring failure patterns
- from `/opts`: exploratory opportunity expansion beyond deterministic quick scans
- from `/value`: exploratory value-creation options and upside hypotheses
- from `/value-maximization`: expansion of high-upside alternatives when deterministic pass marks exclusions
- from `/analysis-profile`: exploratory architecture alternatives for performance tradeoffs
- from `/analysis-logs`: exploratory failure-hypothesis expansion when deterministic checks are inconclusive

`/s` does not own deterministic triage (`/r`), command standards validation (`/val` decomposition), verification tiers (`/verify` decomposition), or promotion execution gates (`/p*`).

## Execution

### Flag Handling (MANDATORY — resolve before running script)

Parse the user's args before doing anything else:

| Input | Action |
|---|---|
| `/s "topic"` | Run script with `--topic "topic"` |
| `/s "topic" --recall` | Run script with `--topic "topic" --recall` |
| `/s --list` or `/s --help` or `/s -h` | Display the **Supported Flags** section below, then stop. Do NOT run the script. |
| `/s "topic" --unknown-flag` | Strip the unknown flag, warn the user, run with the remaining args |
| `/s` (no args) | Use fallback context resolution (see below) |

**Supported Flags** (show this when `--list` or `--help` is requested):
```
--recall                  Search previous brainstorm sessions on similar topics; includes only top-ranked snippets from prior sessions, not full transcripts
--recall --persona NAME   Filter recall by persona (INNOVATOR/PRAGMATIST/CRITIC/EXPERT)
--recall --min-impact N   Filter recall to sessions with impact score ≥ N (0.0–1.0)
--context-path PATH       Prepend directory contents as project context
--output FORMAT           Output format: json | markdown | text (default: markdown)
--personas CSV            Comma-separated persona list to activate
--profile PROFILE          Use preset configuration (fast|normal|deep) - sets personas, debate mode, repetition, timeout
--timeout N               Script timeout in seconds (default: 300)
--ideas N                 Target number of ideas to generate (default: 10)
--fresh-mode              Prevent anchoring bias by skipping existing docs
--local-llm-repetition N  Run brainstorm N times with different cognitive variations
--local-only              Skip external LLMs, use local agents only
--debate-mode MODE        Adversarial debate: none | fast | full (default: none)
--enable-pheromone-trail  [EXPERIMENTAL] Learn from previous sessions
--enable-replay-buffer    [EXPERIMENTAL] Improved idea generation via replay
--quiet                   [OUTPUT] Suppress progress reporting (only show final results)
```

### Context Resolution (MANDATORY)

Before running the script, check if the topic refers to a filesystem path:

1. If the topic matches or resembles a path in the repo (e.g. `package/handoff`, `packages/design`, `skills/s`), pass it via `--context-path`
2. **`--context-path` behavior**: Reads all file contents from the specified path and prepends them to the topic as project context
3. If the topic is not a path (e.g. "auth migration strategy"), omit `--context-path`

**You have project context. The external LLM does not. Always pass `--context-path` when the topic refers to something in this repo.**

**Example:**
```bash
# Topic is a path - include directory contents as context
/s "package/handoff" --context-path packages/handoff

# Topic is abstract - no context path needed
/s "auth migration strategy"
```

Run:

```bash
python P:/.claude/skills/s/scripts/run_heavy.py \
  --topic "{{USER_PROMPT}}" \
  --context-path "{{RESOLVED_PATH_OR_OMIT}}" \
  --personas "{{PERSONAS_CSV_OR_EMPTY}}" \
  --timeout "{{TIMEOUT_OR_300}}" \
  --ideas "{{IDEAS_OR_10}}" \
  --output "{{json|markdown|text}}" \
  {{--fresh-mode to prevent anchoring bias}} \
  {{--local-llm-repetition N for free diversity (N=2-3 recommended)}} \
  {{--local-only to skip external LLMs and use local only}} \
  {{--debate-mode {none,full,fast} for adversarial debate}} \
  {{--enable-pheromone-trail [EXPERIMENTAL]}} \
  {{--enable-replay-buffer [EXPERIMENTAL]}} \
  {{--quiet to suppress progress reporting}}
```

**Provider and model details**: See `references/providers-and-models.md` for provider tiers, API host vs model creator, `/s list` output format, and provider classification source of truth.

**Debate, profiles, advanced features**: See `references/profiles-and-debate.md` for profile presets (fast/normal/deep), debate modes, local LLM repetition, confidence-based turn taking, and experimental features.

## Phases and Personas

- **Diverge:** Innovator (Cynefin), Pragmatist (Inversion)
- **Discuss:** Critic (Hanlon + Devil's Advocate), Expert (Chesterton's Fence)
- **Converge:** Synthesizer (cross-framework integration)

## Output Requirements

Heavy output must include:
- `session_id` (unique per invocation, no cross-terminal coordination needed)
- scored recommendations (e.g. `[85/100]`)
- `metrics` (phase timings, agents spawned)
- `value_map` (top opportunities, expected upside, confidence)
- constitutional filtering results (`filtered_out`)
- decision memo (`decision`, `alternatives`, `why_not`, `risks`, `rollback`)
- next command hints

**Multi-terminal guarantees:**
- Each `/s` invocation is independent — no shared state, no coordination required
- Ideas are generated fresh each time — no caching, no staleness concerns
- Safe to run `/s` in multiple terminals simultaneously
- No TTL — strategies don't expire, ideas remain valid regardless of when generated

## When to Use /s

Use after `/q` or `/r` for plans, architecture discussions, and multi-perspective analysis. Do NOT use for deterministic checks (`/r`), implementation verification (`/p`), or documentation lookups (`/search`).

**Recommended workflow:** `/q` (context) -> `/r` (deterministic checks) -> `/s` (strategy) -> `/p` (implementation)

## Output Routing Note

`/s` output is large by design (5 personas × scored recommendations). When used inside a larger multi-step workflow, route the output through disk rather than inlining it:

- **Write output to disk** — use `--output markdown` and capture the session file written to `.claude/state/`. Reference the file path in subsequent prompts rather than pasting the full output inline.
- **Don't chain inline** — passing `/s` output directly as context into another step will overflow the orchestrator window. Run `/s`, note the session file path, reference it by path in the next step.
- **One `/s` per phase** — if you need strategic input at multiple points in a workflow, run `/s` at phase boundaries and reset context between phases using the handoff system.

## Deprecations

- `/llm-brainstorm` -> `/s`
- `/llm-debate` -> `/s`
- `/strat` removed

## Advanced Features

See `references/strategy-advanced.md` for:
- Graph-of-Thought (GoT) integration features
- Tree-of-Thought (ToT) integration features
- Persona Memory Recall (Optional)
- Argument Fuzzy Matching (NLU-Based)
- Fallback Behavior (DEPRECATED)
- Combined GoT + ToT integration

## Version

**Version:** 2.8.0 (2026-03-28)

**Changes from v2.7.0:**
- Moved provider/model details to `references/providers-and-models.md`
- Moved debate/profiles/advanced features to `references/profiles-and-debate.md`
- Condensed constitutional context, anti-anchoring, removed duplicate Usage section
- Reduced from 537 to ~250 lines

## Reference Files

| File | Contents |
|------|----------|
| `references/strategy-advanced.md` | GoT/ToT integration, persona memory recall, argument fuzzy matching, fallback behavior |
| `references/providers-and-models.md` | Provider tiers, API host vs model creator, `/s list` output, provider classification source of truth |
| `references/profiles-and-debate.md` | Profile presets (fast/normal/deep), debate modes, local LLM repetition, confidence-based turn taking |
