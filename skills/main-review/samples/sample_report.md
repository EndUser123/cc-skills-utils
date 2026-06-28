
[X] MAIN-REVIEW -- CRITICAL [4ms, since 365d]
================================================================
Transcripts scanned : 2
Diagnostics rows    : 12
Registered hooks    : 1
Findings            : 14 (crit 1, high 7, med 3, info 3)
Critic              : off

## UNSUPPORTED CLAIMS (5)
[!] [MR-0002] Confident verdict without a supporting tool receipt  (conf 0.80)
     - verdict phrase: 'Root Cause: the env var was unset. Fixed. Verified.'
     ref transcript:t1.jsonl#entry1
     -> Run the discriminating tool call before asserting the verdict, or hedge the claim (likely/probably).

[!] [MR-0003] Confident verdict without a supporting tool receipt  (conf 0.80)
     - verdict phrase: 't. Fixed. Verified.'
     ref transcript:t1.jsonl#entry1
     -> Run the discriminating tool call before asserting the verdict, or hedge the claim (likely/probably).

[!] [MR-0004] Confident verdict without a supporting tool receipt  (conf 0.80)
     - verdict phrase: 'as unset. Fixed. Verified.'
     ref transcript:t1.jsonl#entry1
     -> Run the discriminating tool call before asserting the verdict, or hedge the claim (likely/probably).

[!] [MR-0005] Confident verdict without a supporting tool receipt  (conf 0.80)
     - verdict phrase: 'Confirmed working now.'
     ref transcript:t1.jsonl#entry3
     -> Run the discriminating tool call before asserting the verdict, or hedge the claim (likely/probably).

[~] [MR-0001] Negative-existence claim without a search tool receipt  (conf 0.70)
     - claim: 'he helper is unused, so I removed it. ModuleNotFoundError:'
     ref transcript:t2.jsonl#entry0
     -> Back the claim with Grep/Glob/Read evidence before asserting absence.

## GATE HEALTH (3)
[!] [MR-0008] Gate-class hook never blocks (rca_gate: 6 invocations, 0 blocks)  (conf 0.70)
     - action distribution: {'allow': 6}
     ref diagnostics.db:hook=rca_gate
     -> Confirm the gate is fail-closed where it should be; a never-blocking gate may be warn-mode or fail-open.

[!] [MR-0009] Hook error-dominated (broken_hook: 6/6 errors)  (conf 0.80)
     - action distribution: {'error': 6}
     ref diagnostics.db:hook=broken_hook
     -> Inspect hook stderr; an erroring hook may be fail-open.

[~] [MR-0007] Registered hook with zero recent invocations: inert_ghost_Stop.py  (conf 0.60)
     - registered in hooks.json/settings.json, absent from diagnostics
     ref diagnostics.db:hook=inert_ghost_Stop.py
     -> Confirm the hook is wired and firing; it may be inert.

## REGRESSION CANDIDATES (2)
[!] [MR-0010] Recurring error signature across 2 transcripts  (conf 0.75)
     - signature: 'ModuleNotFoundError: No module named foo'
     - in: ['t1.jsonl', 't2.jsonl']
     ref transcript-cluster:ModuleNotFoundError: No module named foo
     -> Add a replay test that reproduces this signature.

[~] [MR-0011] Health check [cks] flipped healthy to critical 2 times  (conf 0.70)
     - flips observed: 2
     ref health_history.jsonl:check=cks
     -> Stabilize the check or its underlying subsystem.

## PROMOTION CANDIDATES (3)
[i] [MR-0012] Pattern [negative-existence-without-search] recurs across 1 source(s)  (conf 0.60)
     - recurrence: 1 finding(s), 1 source(s)
     ref transcript:t2.jsonl
     -> Consider graduating this into a deterministic runtime gate (conservative; gate should warn before block in production).
     propose gate: PreToolUse/Stop hook: on absence claims require a Grep/Glob/Read in the same turn; warn-first.

[i] [MR-0013] Pattern [verdict-without-receipt] recurs across 1 source(s)  (conf 0.60)
     - recurrence: 4 finding(s), 1 source(s)
     ref transcript:t1.jsonl
     -> Consider graduating this into a deterministic runtime gate (conservative; gate should warn before block in production).
     propose gate: Stop hook: regex-match verdict phrases (Root Cause/Fixed/Verified/Resolved) and require a tool_use event in the preceding window; warn-first.

[i] [MR-0014] Pattern [receipts] recurs across 1 source(s)  (conf 0.60)
     - recurrence: 1 finding(s), 1 source(s)
     ref transcript:t1.jsonl
     -> Consider graduating this into a deterministic runtime gate (conservative; gate should warn before block in production).
     propose gate: Stop hook: detect this recurring pattern and require supporting evidence; warn-first.

## RECOMMENDED ACTIONS
  - Triage 1 critical finding(s) first - each ships with explicit evidence refs.
  - Review 7 high-severity finding(s); reproduce before acting.
  - Evaluate 3 promotion candidate(s); replay-test before graduating to a runtime gate.
  - Verify liveness of 1 registered-but-silent hook(s).

