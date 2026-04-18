# Context Reuse Monitoring (Weekly Check)

**Status**: Active monitoring
**Plan**: `P:\.claude\hooks\docs\context_summary_implementation.md`
**Data**: `P:\.claude\logs\principle-events.jsonl`

## Overview

Prevent context_reuse violations (asking questions about information already in conversation context). The context_summary.py hook injects key facts from recent turns at context top to reduce these violations.

## Weekly Monitoring Checklist

**Run every 7 days**:
```bash
# Check principle violations
python P:/.claude/hooks/hook_audit_dashboard.py principles --days 7
```

## Action Thresholds

**Based on violation trends**:

| Trend | Action |
|-------|--------|
| **IMPROVING** (>10% reduction) | Context summary working - no action needed |
| **STABLE** (±10% change) | Monitor - check if violation count is acceptable |
| **REGRESSING** (>10% increase) | Investigate - context summary may need tuning |

## If Regression Detected

1. **Check context_summary.py status**:
   ```bash
   # Verify hook is registered
   grep -q "context_summary" P:/.claude/hooks/UserPromptSubmit_modules/registry.py && echo "Registered" || echo "Missing"

   # Check if enabled
   grep CONTEXT_SUMMARY_ENABLED P:/.claude/settings.json
   ```

2. **Analyze violation patterns**:
   ```bash
   # View recent context_reuse violations
   python -c "
   import json
   from pathlib import Path
   from datetime import datetime, timedelta

   log = Path('P:/.claude/logs/principle-events.jsonl')
   cutoff = datetime.now() - timedelta(days=7)

   for line in log.read_text().splitlines()[-50:]:
       e = json.loads(line)
       if e.get('principle') == 'context_reuse':
           print(f\"{e['ts'][:19]}: {e['assistant_preview'][:60]}\")
   "
   ```

3. **Tune extraction patterns** (if needed):
   - Edit `P:\.claude/hooks/UserPromptSubmit_modules/context_summary.py`
   - Adjust `NUM_TURNS` (default: 5) - increase if missing older context
   - Adjust `MAX_FACTS` (default: 7) - increase if not enough facts extracted
   - Add new regex patterns to `_extract_key_facts()` if certain fact types are missed

4. **Verify effectiveness**:
   - Monitor for 7 days after tuning
   - Re-check principles dashboard
   - Target: <50 violations/day average

## Quick Reference Commands

```bash
# Standalone principles check
python P:/.claude/hooks/hook_audit_dashboard.py principles --days 7

# Full dashboard (includes principles)
python P:/.claude/hooks/hook_audit_dashboard.py dashboard --days 7

# Check hook registration
grep "context_summary" P:/.claude/hooks/UserPromptSubmit_modules/registry.py

# View raw logs
tail -50 P:/.claude/logs/principle-events.jsonl | jq .
```

## Related Files

- Implementation: `P:\.claude\hooks\UserPromptSubmit_modules\context_summary.py`
- Documentation: `P:\.claude\hooks\docs\context_summary_implementation.md`
- Dashboard: `P:\.claude\hooks\hook_audit_dashboard.py` (principles subcommand)
- Principle monitor: `P:\.claude\hooks\principle_monitor.py` (logs violations)
