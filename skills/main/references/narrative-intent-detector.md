# Narrative Intent Detector (Stop Gate)

Catches un-hedged design-intent speculation — statements about WHY code exists, presented as fact without evidence or hedging. Separate from `unified_claim_verifier` which handles code-state claims ("file X exists").

**Module:** `P:/.claude/hooks/narrative_intent_detector.py`
**Gate position:** Stop.py → after `behavior_audit`, before `command_execution_validator`
**Tests:** `P:/.claude/hooks/tests/test_narrative_intent_detector.py` (38 tests)

## What It Catches

| Pattern | Example |
|---------|---------|
| Agent + intent verb | "The author included this for robustness" |
| Passive purpose | "This was designed to prevent session leaks" |
| Exists because | "The hook exists because users forget to run /clear" |
| Purpose framing | "The purpose of this matcher is to catch startup events" |
| Meant/intended | "It is meant to guard against double-fire" |

## What It Allows

| Scenario | Why |
|----------|-----|
| Hedged speculation | "The author **probably** wanted..." — labeled as uncertain |
| Cited evidence | "According to the README, this was designed to..." — backed by source |
| Code-behavior reasoning | "The function crashes because it mutates state" — not intent |
| Evidence-overlapping | Sentence mentions file path that's in the evidence store |

## Phase Migration Plan

| Phase | Mode | Behavior | Trigger to Promote |
|-------|------|----------|--------------------|
| **1 (current)** | warn | systemMessage back to model; model self-corrects | Review logs for 2+ weeks. If warn fires >5x/week with <10% false positives → promote |
| **2** | block (high-confidence) | Block when ≥2 un-hedged narratives in one response, OR classic patterns with zero evidence | If Phase 2 blocks are consistently justified → promote |
| **3** | block (context-gated) | Hard block for RCA, design review, security analysis tasks; soft warn for general Q&A | Steady state |

## How to Check Phase 1 Effectiveness

```bash
# Count recent narrative intent warnings from Stop hook logs
python -c "
import json, glob
for f in sorted(glob.glob('P:/.claude/hooks/logs/diagnostics/*.json'))[-20:]:
    try:
        data = json.load(open(f))
        if 'narrative_intent' in str(data):
            print(f)
    except: pass
"
```

**Promotion criteria for Phase 2:**
1. Phase 1 has been running for ≥2 weeks
2. Warning fires regularly (not dead code)
3. False positive rate is <10% (review flagged sentences manually)
4. The warn-only systemMessage is insufficient — model still produces un-hedged narratives despite warnings

**To promote to Phase 2**, change `evaluate_narratives` return from `"warn"` to `"block"` for high-confidence cases, and update `_run_narrative_intent` in `Stop.py` to handle the block decision.

---

## Behavioral Safety Verification

The following test suite verifies the core behavioral guardrails after hook pruning. It must be run to ensure unverified claims are correctly blocked.

### Subtraction Safety Test (`test_subtraction_safety.py`)

```python
#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

# Force hooks directory into path
HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

from unified_claim_verifier import evaluate_claims

class TestSubtractionSafety(unittest.TestCase):
    def test_unified_verifier_is_stricter_than_text_gate(self):
        """
        Verify that unified_claim_verifier catches unverified claims that
        the old text-gate would miss (or duplicate).
        """
        # Scenario: Assistant claims a file is VERIFIED but used a tool on a DIFFERENT file.
        # The old StopHook_truth_evidence_gate would ALLOW this because has_post_truth_evidence is True.
        # The unified_claim_verifier should BLOCK this because the entities don't match.

        response = "The file P:/critical_fix.py is VERIFIED."
        tool_sequence = [
            {"command": "ls P:/other_file.py", "output": "other_file.py"}
        ]

        result = evaluate_claims(response, tool_sequence=tool_sequence)

        self.assertEqual(result["decision"], "block", "Should block because critical_fix.py was not seen.")
        self.assertIn("UNVERIFIED_CLAIMS", result["reason"])

    def test_unified_verifier_blocks_without_any_tools(self):
        """Even without /truth active, unverified claims should be blocked."""
        response = "I have confirmed that P:/secret.txt is empty."
        result = evaluate_claims(response, tool_sequence=[])

        self.assertEqual(result["decision"], "block")

if __name__ == "__main__":
    unittest.main()
```
