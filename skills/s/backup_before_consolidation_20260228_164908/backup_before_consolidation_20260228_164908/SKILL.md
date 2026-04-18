---
name: s
description: Strategy skill (orchestrator-backed Diverge→Discuss→Converge). Owns exploratory DUF decomposition; deterministic remember/refine moved to /r.
category: strategy
triggers:
  - /s
  - "strategic analysis"
  - "brainstorm options"
  - "multi-option tradeoff"
aliases:
  - /s
suggest:
  - /r
  - /q
  - /nse
  - /arch
---

# /s - Strategy

## Purpose

General-purpose strategic thinking engine for any situation requiring multi-perspective analysis.

- Uses real `BrainstormOrchestrator` execution
- Produces ranked options, tradeoffs, decision memo, and next-step hints
- **Context-aware**: Detects conversation focus and applies strategic thinking to ongoing work
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

**Core principle**: `/s` applies fresh strategic thinking to the current context. It works for plans, solutions, or anything needing multi-perspective analysis. It detects conversation focus from `/q` context, session activity, or chat history.

## Constitutional Context (CSF)

**This project uses Director Model: Human director + AI agent implementation.**

**Workflow:**
- **User role**: Technical architect/director — provides requirements, reviews work, guides direction
- **AI role**: Primary developer — writes code, tests, documentation under user direction
- **Quality priority**: Thoroughness > speed. "Does it work correctly?" > "How fast can we ship?"

**What this means for strategy:**
- Strategies should **guide and assist AI agents**, not replace user direction
- **Functional verification matters** — importing and testing code is essential
- **LLM generation with guardrails** — DSLs, validation, verification cycles are appropriate
- **Quality gates** — thorough testing, integration flows, and performance baselines

### ✅ Appropriate for This Project

- **LLM-generated tests**: Agents create tests, scenarios, and verification code
- **Quality-first tooling**: Thorough checks over fast checks
- **Integration flows**: YAML-defined workflows that test complete paths
- **Risk-aware testing**: Test what changed based on impact analysis
- **DSLs for LLMs**: Constrained formats that prevent hallucination
- **Performance baselines**: Quality gates for critical paths
- **Heavy automation**: Under user direction, not autonomous

### ❌ Not Appropriate (Enterprise Anti-Patterns)

- **Background autonomous execution**: Services running without user oversight/trigger
- **Self-healing systems**: Code that modifies itself without human approval
- **Real-time monitoring dashboards**: Always-running metrics services
- **Team approval gates**: Consensus processes for single-director workflow
- **Lock-free multi-terminal coordination**: Enterprise concurrency patterns
- **Enterprise patterns**: Complex frameworks when simple solutions suffice

**Key distinction**: LLM-generated code under user direction = ✅. Autonomous background services = ❌.

## Scope Boundary

- `/r`: deterministic remember + refine (what did we forget, predictable improvements, deterministic pre-mortem, plan validation)
- `/s`: exploratory multi-persona strategy (high-upside options, adversarial tradeoffs, and uncertainty handling)

## Context-Aware Strategic Thinking

`/s` automatically detects conversation context and applies strategic thinking to ongoing work. It does NOT need an explicit topic when you're mid-conversation.

### How Context Inference Works

When you invoke `/s` without arguments, it follows this inference chain:

1. **`q_context`** (confidence 0.9): If you've run `/q`, uses the strategic work summary
2. **`session_activity`** (confidence 0.75): Infers from recent file edits in the session
3. **`chat_context`** (confidence 0.6): Analyzes recent conversation for the focus
4. **`fallback`** (confidence 0.4): "General strategic brainstorming"

This means `/s` automatically applies strategic thinking to:
- Plans you're developing
- Solutions you're implementing
- Architecture discussions
- Any strategic question about the work

### Anti-Anchoring vs Context Awareness

There's an important distinction:

- ✅ **Avoid anchoring on SOLUTIONS**: Don't read existing implementation docs before brainstorming — that filters out better alternatives
- ✅ **USE conversation CONTEXT**: Detect what you're working on from `/q` and session activity — that's the input to strategic thinking, not a constraint

**Example correct flow:**
```
# You're working on a consolidation plan for /p
/q  # Generates work summary about /p consolidation
/s  # AUTOMATICALLY detects context, applies strategic thinking to the /p plan
```

**What `/s` does:**
- Reads `/q` work summary → detects you're working on /p consolidation
- Applies multi-persona strategic thinking to improve the plan
- Generates alternatives, tradeoffs, and decision memo

**What `/s` does NOT do:**
- Read existing `/p` implementation docs → would anchor on current solution
- Ignore your conversation → would ask "what topic?"
- Generate generic advice → applies strategic thinking to YOUR work

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

### Context Resolution (MANDATORY)

Before running the script, resolve the user's topic to a filesystem path:

1. If the topic matches or resembles a path in the repo (e.g. `package/handoff`, `packages/arch`, `skills/s`), resolve it to the actual directory path
2. Pass the resolved path via `--context-path` so the external LLM receives all file contents from that directory
3. If the topic is not a path (e.g. "auth migration strategy"), omit `--context-path`

**You have project context. The external LLM does not. Always pass `--context-path` when the topic refers to something in this repo.**

Run:

```bash
python P:/.claude/skills/s/scripts/run_heavy.py \
  --topic "{{USER_PROMPT}}" \
  --context-path "{{RESOLVED_PATH_OR_OMIT}}" \
  --personas "{{PERSONAS_CSV_OR_EMPTY}}" \
  --timeout "{{TIMEOUT_OR_180}}" \
  --ideas "{{IDEAS_OR_10}}" \
  --output "{{json|markdown|text}}" \
  {{--fresh-mode to prevent anchoring bias}} \
  {{--local-llm-repetition N for free diversity (N=2-3 recommended)}} \
  {{--local-only to skip external LLMs and use local only}} \
  {{--provider-tier T1,T2 to filter by quality tier}} \
  {{--mock if requested}}
```

**Local LLM Repetition (Free Diversity Improvement):**

`--local-llm-repetition N` runs the brainstorm N times with different cognitive approach variations:
- **First-principles thinking**: Challenge fundamental assumptions
- **Lateral thinking**: Consider random entry points and unexpected connections
- **SCAMPER**: Substitute, Combine, Adapt, Modify, Put to other uses, Eliminate, Reverse
- **Reverse engineering**: Start from ideal outcome and work backwards
- **Six Thinking Hats**: Facts, feelings, caution, benefits, creativity, process

This is **free** compared to external LLMs — you get 2-3x the idea diversity without additional API costs.

**Local-Only Mode:**

`--local-only` skips external LLM providers entirely and uses only local agents with prompt variations. Useful for:
- Faster brainstorming without external API calls
- Privacy-sensitive topics
- Testing without API quota usage

**Provider Tier Filtering:**

`--provider-tier T1,T2` filters external LLM providers by quality tier to avoid lower-quality models. Tiers are:
- **T1 (Best)**: claude, anthropic - Highest quality reasoning
- **T2 (Good)**: openai, gpt, gemini, google - Strong performance
- **T3 (Experimental)**: All other providers - Variable quality

**Examples:**
```bash
# Use only top-tier providers (claude/anthropic)
/s "strategy topic" --provider-tier T1

# Use high-quality providers (T1 + T2)
/s "strategy topic" --provider-tier T1,T2

# Default allows all tiers
/s "strategy topic"  # Equivalent to --provider-tier T1,T2,T3
```

This prevents "stupid LLMs" by filtering out experimental/lower-quality providers from your brainstorm.

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

## Usage

```bash
# Mid-conversation: /s detects context automatically
/q                      # Generate work summary
/s                      # Automatically applies strategic thinking to ongoing work

# Explicit topic:
/s "architecture options for auth migration"

# Output variants:
/s "service boundary redesign" --output json

# Multi-terminal: /s works reliably across concurrent sessions
# No TTL: Ideas stay valid regardless of when generated
# No stale data: Every run produces fresh strategic thinking
```

### When to Use /s

✅ **Appropriate:**
- Mid-conversation, after `/q` or `/r`
- For plans being developed
- For solutions being implemented
- For architecture discussions
- For any strategic question about ongoing work
- When you need multi-perspective analysis

❌ **Not appropriate:**
- Deterministic checks and validation (use `/r`)
- Implementation verification (use `/p`)
- Quick facts from documentation (use `/search`)

### Recommended Workflow

```bash
# Typical strategic analysis flow:
/q           # What are we working on? (context summary)
/r           # Did we forget anything? (deterministic checks)
/s           # What are our options? (strategic thinking)
/p           # Make it work (implementation)
```

## Deprecations

- `/llm-brainstorm` -> `/s`
- `/llm-debate` -> `/s`
- `/strat` removed

## Version

**Version:** 2.4.0
