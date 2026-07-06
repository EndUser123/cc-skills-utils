---
name: main-review
description: Slow, evidence-first maintenance auditor for the main skill family — inspects recent transcripts, diagnostics, and gate telemetry to find unsupported claims, inert gates, receipt mismatches, and regression/promotion candidates.
version: 1.0.0
status: stable
category: governance
triggers:
  - /main-review
  - /main-checkup
  - /main-verify
aliases:
  - /main-review
  - /main-checkup
  - /main-verify
enforcement: advisory
depends_on_skills: []
output_format: 2
workflow_steps:
  - gather: Collect transcript / diagnostics / gate-telemetry slices for the window
  - detect: Run deterministic detectors (claims, gates, receipts, regression)
  - promote: Analyze recurring patterns for runtime-gate graduation
suggest:
  - /main
  - /top-problems
---

# Main Review — Evidence-First Behavioral Auditor

`/main-review` complements `/main`. Where `/main` probes **current infrastructure health**
(settings, hooks, workspace, cks, filesystem), `/main-review` audits **behavior over recent
history**: it scans transcripts, the diagnostics DB, gate telemetry, and health-history to
detect problems that only surface across time.

This is a **manually invoked, deliberately slow** maintenance command. Latency is acceptable;
completeness and low false positives are the priority. It is **not** a real-time blocker and
does **not** replace any runtime gate.

## EXECUTION DIRECTIVE

**When /main-review is invoked, IMMEDIATELY execute:**

```bash
python P:/packages/.claude-marketplace/plugins/cc-skills-utils/skills/main-review/scripts/main_review.py
```

**Step 1: Parse CLI flags** (from the invocation or infer from context):

| Flag | When to use |
|------|-------------|
| *(none)* | **Full comprehensive review (the default).** Do not default to quick mode. |
| `--since 7d` / `30d` / `2w` / `3m` | Window of history to audit (default `30d`) |
| `--focus gates` | Narrow to one category (repeatable): `claims`, `gates`, `receipts`, `regression`, `promotion` |
| `--json` | Machine-readable structured report |
| `--quiet` | One-line summary only |
| `--critic` | Enable the optional, vendor-neutral, evidence-only LLM critic |
| `--no-history` | Do not append a summary line to `review_history.jsonl` |
| `--max-transcripts N` | Cap transcripts scanned (default 50) |
| `--max-entries N` | Cap entries per transcript (0 = unlimited) |
| `--lookback N` | Receipt window in transcript entries, ~3 turns (default 6) |
| `--data-dir DIR` | Override the telemetry root (for dry-runs / tests) |
| `--self-test` | Run against a synthetic fixture (also generates sample outputs) |

**Step 2: Run `main_review.py`.** Pass through the script's own output verbatim. It formats
its own results and returns exit codes: `0` = clean, `1` = high/medium findings, `2` = critical.

**Step 3: Display results** — the script renders a structured report (scope → summary →
findings by category → recommended actions). For `--json`, emit the machine-readable object.

**Execution notes:**
- Single Python script, no subprocess spawning from the skill side.
- Deterministic-first: every detector is stdlib-only. The LLM critic (`--critic`) is opt-in and
  only ever inspects the **extracted evidence slices** already attached to suspicious findings —
  never whole repos.
- Defensive gatherers: a missing transcript root, diagnostics DB, or history file yields an
  `info` note and a skipped stage, never a crash.
- Severity guard: a finding is never `critical` without explicit `evidence` + `source_refs`.

**DO NOT:**
- Display this documentation without executing.
- Skip the Bash execution.
- Treat promotion candidates as already-shipped gates — they are conservative proposals that
  must be replay-tested before graduation.

---

## What It Detects

| Category | Detector |
|----------|----------|
| **claims** | Confident verdicts (`Root Cause:`, `Fixed.`, `Verified.`, `Resolved.`, …) with **no tool receipt** in the lookback window; negative-existence claims (`doesn't exist`, `no consumers`, `is unused`) with **no preceding search tool** (Grep/Glob/Read). |
| **gates** | Registered hooks with zero recent invocations (inert); gate-class hooks that never block (fail-open / warn-mode); error-dominated hooks (>50% errors). |
| **receipts** | A verdict immediately preceded by a tool_result containing a traceback/error/not-found — the receipt refutes the claim. Highest-confidence (`critical`). |
| **regression** | Recurring normalized error signatures across ≥N transcripts; health checks flipping healthy↔critical repeatedly. Each ships a `proposed_test`. |
| **promotion** | Recurring, narrow, low-ambiguity patterns (e.g. `verdict-without-receipt`) proposed for runtime-gate graduation, with a `proposed_runtime_gate` + `proposed_test`. Conservative by default. |

---

## Output Sections

`scope` · `summary` (by severity + category + overall) · `findings` · `unsupported_claims` ·
`gate_health_findings` · `regression_candidates` · `promotion_candidates` · `recommended_actions`.

Each `Finding`: `id, severity, category, title, evidence, confidence, source_refs,
recommended_action, rationale, promotion_ready, proposed_test?, proposed_runtime_gate?`.

---

## Relationship to `/main`

| | `/main` | `/main-review` |
|---|---|---|
| **Scope** | Current infra state | Behavior over recent history |
| **Speed** | Fast, operational | Slow, deliberate |
| **Examples** | settings/hooks/workspace/cks/filesystem size | unsupported claims, inert gates, receipt mismatches, regressions |
| **Role** | Real-time health probe | Periodic maintenance audit |

Run `/main-review` periodically (e.g. weekly, or after a stretch of debugging sessions) to
catch drift that real-time checks cannot see. See
`references/main-review-methodology.md` for the full pipeline, promotion criteria, and how to
wire an LLM critic. Sample outputs live in `samples/`.
