# Subcommand Details

Full descriptions and output details for each `/hook-audit` subcommand.

## Default / decision-patterns - Decision Pattern Monitoring

```bash
/hook-audit
/hook-audit decision-patterns
/hook-audit decision-patterns --days 7
```

Shows:
- Decision type distribution (validates 86%/10%/3%/2% assumptions)
- Option extraction rates
- Actual vs expected pattern accuracy
- Recommendations for fine-tuning detection patterns

Use this to monitor and tune the next step menu system.

## blocks - Hook Blocking Events

What hooks are blocking and why:

```bash
/hook-audit blocks
/hook-audit blocks --days 14
```

Shows:
- Total blocks by hook
- Block reasons
- Recent blocking events
- Repeated failure patterns (Catch-22 detection)

## assumptions - Assumption Audit Compliance

Whether LLM uses tools or marks [UNVERIFIED] when required:

```bash
/hook-audit assumptions
/hook-audit assumptions --days 7
```

Shows:
- Audit trigger count
- Compliance rate (tool use OR [UNVERIFIED] marker)
- Non-compliant cases (claims without verification)

## attribution - Error Attribution Compliance

Whether LLM references correct error sources:

```bash
/hook-audit attribution
/hook-audit attribution --days 7
```

Shows:
- Error attribution injections
- By source type (hook_file, hook_event, etc.)
- Top error sources
- Escalation recommendation

## speculation - Speculation Gate Compliance

Whether LLM verifies before diagnostic claims:

```bash
/hook-audit speculation
/hook-audit speculation --days 7
```

Shows:
- Speculation violations
- Block events
- Pattern types

## friction - Style Friction Analysis

Whether output-style settings cause user friction:

```bash
/hook-audit friction
/hook-audit friction --days 7
```

Shows:
- Friction events by type (permission_seeking, too_terse, repeat_request)
- Tuning recommendations
- Percentage breakdown

Use this to tune `/output-style` settings when expert mode is too aggressive.

## reasoning - THINK Profile Routing Quality

Reasoning profile telemetry for intelligent THINK auto-activation:

```bash
/hook-audit reasoning
/hook-audit reasoning --days 14
```

Shows:
- Auto vs explicit THINK trigger rates
- Profile selection distribution (debug/decision/designitecture/risk)
- Injection rate and skipped-in-cooldown rates
- Recommendation-quality block counts

## health - Hook System Health

Hook execution health (timeouts, failures):

```bash
/hook-audit health
```

Shows:
- Hook execution times
- Timeout rates
- Failed hooks
- Missing entrypoints
- Shared enforcement metrics:
  - warn-then-block counts
  - autofix attempt/success rate
  - average `write_router` / `stop_router` latency
- Validator runtime stability from Stop router decision logs:
  - `HOOK_RUNTIME_ERROR`
  - `HOOK_NON_JSON_OUTPUT`

## escalation - Escalation Recommendations

What needs Phase 2 enforcement:

```bash
/hook-audit escalation
```

Analyzes all compliance metrics and recommends:
- Which Phase 1 (advisory) hooks should become Phase 2 (blocking)
  - Based on >30% non-compliance threshold

## replay - Enforcement Replay Quality

Counterfactual quality view for warn-then-block and autofix effectiveness:

```bash
/hook-audit replay
/hook-audit replay --days 14
/hook-audit replay --terminal
```

Shows:
- Simulated pre-ladder immediate-block rate vs actual post-ladder block rate
- Ladder-deflected block count
- Autofix success rate
- Top violation categories/hooks
- Stop-router hook latency percentiles (p50/p95)
