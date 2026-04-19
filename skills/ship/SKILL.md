---
name: ship
description: Deploy readiness and runtime snapshot for pre/post deployment validation
version: "1.0.0"
status: stable
category: deployment
triggers:
  - /ship
  - "deploy readiness"
  - "ship pre"
  - "ship post"
aliases:
  - /ship

suggest:
  - /vdate-deploy
  - /verify
  - /qa
  - /analyze
---

# /ship – Deploy Readiness & Runtime Snapshot

## Purpose

Aggregate git, verification, QA, CI/CD, and basic runtime signals into a single "ship readiness" or "post-deploy health" verdict.

## When to Use

- Before merging or deploying a change (`/ship pre`).
- After deploying a change (`/ship post`).
- Any time you want to see current readiness/health (`/ship status`).

## Inputs

- Optional mode (natural language or arg):
  - `pre` – pre-deploy readiness.
  - `post` – post-deploy health.
  - `status` – current status (auto-detected if not provided).
- Optional: branch/service/environment if not obvious from cwd.

## Dependencies

- Skills:
  - `/vdate-deploy` – git cleanliness and branch verification.
  - `/verify` – T1/T2/T3 verification (syntax/types/tests).
  - `/qa` – 4-phase QA certification (sanity/E2E/chaos/report).
- Tools/CLI:
  - Git CLI.
  - Test/QA tooling (pytest, coverage, bandit, Playwright, hypothesis, schemathesis, locust).
  - CI/CD API or CLI (if available).
  - Basic logs/metrics endpoints (optional).

## High-Level Behavior

### 1. Mode Detection
Infer `pre`, `post`, or `status` from user request and context. If ambiguous, ask: "Pre-deploy check, post-deploy health, or status snapshot?"

### 2. Pre-deploy (`pre`) Flow
1. Run `/vdate-deploy` to confirm:
   - Git status is clean.
   - On the expected branch.
2. Run `/verify`:
   - At least T1+T2.
   - Optionally T3 if changes are non-trivial or user requests full verification.
3. Optionally run `/qa`:
   - At least Phase 1 (sanity).
   - Full suite if risk is high or user requests full QA.
4. Query CI/CD:
   - Latest pipeline status for current branch.
5. Aggregate into a single readiness verdict:
   - Ready / Caution / Blocked.
   - Include a short checklist explaining why.

### 3. Post-deploy (`post`) Flow
1. Identify last deployment for current branch/service.
2. Compare key metrics before vs after deploy:
   - Error rates, latency, basic health checks (if available).
3. Detect regressions or anomalies.
4. Suggest next actions:
   - Investigate with `/analyze` or `/guard`.
   - Consider rollback.
   - Capture an incident note for `/rr` if needed.

### 4. Status Flow
Provide a combined summary of:
- Current git/verify/QA/CI state.
- Recent deployments and basic runtime health.
- No hard go/no-go verdict; this is informational.

## Output Format

- Concise "ship report" including:
  - Mode: pre/post/status.
  - Git & branch status (clean/dirty, branch name).
  - Verify tiers run and results.
  - QA phases run and results (if applicable).
  - CI/CD status summary.
  - Runtime health summary (post/status).
  - Final verdict (Ready/Caution/Blocked for `pre`, Healthy/Watch/Degraded for `post`).
  - 2–3 recommended next actions.

## Notes

- Prefer small, actionable suggestions over long narratives.
- Do not auto-deploy; only assess and recommend.
