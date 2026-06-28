# `/main-review` Methodology

A concise reference for the pipeline, evidence discipline, promotion criteria, and how to wire
an LLM critic. The implementation lives in `scripts/main_review.py`.

## Pipeline (5 stages)

1. **Gather (defensive).** Collect telemetry slices for the `--since` window:
   - Transcripts: `~/.claude/projects/*/*.jsonl`, mtime >= cutoff, capped by `--max-transcripts`
     (dropped count is surfaced, never silently truncated).
   - Diagnostics: `P:/.claude/hooks/logs/diagnostics/diagnostics.db`, opened **read-only** and
     **schema-introspected** (discovers the invocations table + columns rather than hardcoding).
   - Health history: `P:/.claude/session_data/health_history.jsonl`.
   - Registered hooks: best-effort scan of `settings.json` + plugin `hooks.json` command strings.
   - A missing source yields an `info` note and a skipped stage — never a crash.

2. **Detect (deterministic, pure).** Stdlib regex/state detectors over the gathered slices:
   - **Verdict-without-receipt** — `Root Cause:` / `The fix is` / `This works because` /
     `Confirmed working` / `Verified.` / `Fixed.` / `Resolved.` / `Done.` in assistant prose
     with no `tool_use` in the lookback window. `high`. (Anchored on trailing punctuation so
     "I verified the path exists" is **not** a verdict.)
   - **Negative-existence-without-search** — `doesn't exist`, `no consumers`, `is unused`, etc.
     with no preceding Grep/Glob/Read/LS. `medium`. Scanned in assistant prose only, never in
     `tool_result` text.
   - **Receipt mismatch** — a verdict preceded (in window) by a `tool_result` matching the
     contradiction regex (Traceback/Error/not found/...). `critical` — the cited receipt refutes
     the claim.
   - **Gate health** — registered-but-zero-invocation (inert, `medium`); gate-class hook
     (`gate|stop|pretooluse|posttooluse|rca|verif|claim`) with >=5 invocations and 0 blocks
     (`high`); error-dominated >50% (`high`).

3. **Critic (optional, vendor-neutral).** Only runs with `--critic`. It receives **only the
   extracted evidence slices** attached to `critical`/`high` findings — never whole repos or
   raw transcripts. The default `_critic_backend()` is a no-op (deterministic, no dependency).
   To wire a real backend, override `_critic_backend(f)` to call a subagent / `agy` / `pi` /
   any OpenAI-compatible endpoint and return a short note; it is appended to `evidence` and
   nudges `confidence` up by 0.05 (capped at 0.99).

4. **Regression candidates.** Cluster normalized error signatures across >=N distinct
   transcripts (default N=3) -> each ships a `proposed_test`. Also: health checks flipping
   healthy->critical >=N times in `health_history.jsonl`.

5. **Promotion analysis.** Group `claims`/`receipts` findings by pattern
   (`verdict-without-receipt`, `negative-existence-without-search`, ...). A pattern recurring
   across >=N distinct sources (default N=3) becomes a `promotion_ready` candidate with a
   concrete `proposed_runtime_gate` + `proposed_test`.

## Evidence discipline

- **No `critical` without explicit refs.** `finalize()` downgrades any `critical` finding that
  lacks `evidence` or `source_refs` to `high` and annotates the rationale.
- **Facts vs inference vs speculation.** Deterministic findings carry measured confidence
  (0.6-0.9); the critic can only nudge up slightly and must cite its note.
- **Deterministic first, LLM only on suspicious slices.** The LLM never sees broad context.
- **No vendor lock-in.** The critic is an override hook; the tool ships dependency-free.

## Promotion criteria (conservative)

A pattern is `promotion_ready` only when it meets the recurrence bar (the other four criteria
are documented in `PROMOTION_CRITERIA` and are expected to be confirmed by a replay pass before
any gate ships):

1. **Recurrence** — appears across >= `promotion_recurrence` distinct sources.
2. **Narrow & teachable** — a single, detectable pattern.
3. **Low ambiguity** — a regex/state check can decide it.
4. **Testable** — a fixture can reproduce it.
5. **Low false-positive** — replay suggests few FPs.

Proposed gates are **warn-first** by design: graduate to block mode only after a replay pass
confirms low FP. This command never installs a runtime gate itself.

## History

Each run appends one line to `P:/.claude/session_data/review_history.jsonl`
(`timestamp, overall, total_findings, by_severity`), mirroring `health_history.jsonl`. Use
`--no-history` to skip (e.g. in CI / tests).

## Testing

- `scripts/tests/test_main_review.py` — unit (pure detectors + schema), regression
  (the verdict-without-receipt failure class), integration (`run()` over a synthetic telemetry
  root), and smoke (`main(["--self-test", ...])`).
- `--self-test` materializes a synthetic fixture and is the reproducible sample-output
  generator (`samples/sample_report.{json,md}`).

## Exit codes

`0` clean · `1` high/medium findings · `2` critical findings.