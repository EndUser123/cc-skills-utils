# Truth Validation Reference

Detailed scoring formulas and blocking logic for claim validation during /ask routing.

## 3.1 Claim Detection

Scan for assertion patterns:

- "I created...", "I implemented...", "I fixed..."
- "Tests pass", "Build succeeds", "Feature complete"
- References to files, tools, or implementations

## 3.2 Evidence-Based Scoring

| Evidence Type | Confidence Ceiling | Examples                              |
| ------------- | ------------------ | ------------------------------------- |
| Tier 1        | 95%                | Execution logs, test output, git diff |
| Tier 2        | 85%                | Documentation, specs, file existence  |
| Tier 3        | 75%                | Static analysis, code inspection      |
| Tier 4        | 50%                | Comments, unverified assertions       |

**Confidence calculation:**

```
base = 0.70
if tier_1_evidence: base += 0.15
if tier_2_evidence: base += 0.10
if cross_validated: base += 0.10
if unverified_assumptions > 2: base -= 0.20
final = max(0.30, min(0.98, base))
```

## 3.3 Blocking Logic

```
IF truth_score < 0.7:
    BLOCK with:
    - Current score and evidence gaps
    - Specific validation failures
    - Required evidence to proceed
    STOP routing

IF truth_score >= 0.7:
    PROCEED to routing
    NOTE any evidence gaps for downstream commands
```
