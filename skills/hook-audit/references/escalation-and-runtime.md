# Escalation Framework and Runtime Error Metrics

## Escalation Framework

### Phase 1 (Advisory)
- Inject context/reminders
- Log for auditing
- No blocking

### Phase 2 (Enforcement)
- Stop hook blocks non-compliant responses
- Requires evidence of >30% non-compliance in Phase 1

### Current Phase Status

| Hook | Phase | Compliance Target |
|------|-------|-------------------|
| Error Attribution | 1 (Advisory) | Reference error source |
| Assumption Audit | 1 (Advisory) | Use tools OR mark [UNVERIFIED] |
| Skill Enforcement | 2 (Blocking) | Use Skill tool for slash commands |
| Empirical Claims | 2 (Blocking) | Execute before claiming success |

## Runtime Error Metrics (Stop Router)

`/hook-audit health` includes runtime validator error metrics sourced from hook decision logs:
- `HOOK_RUNTIME_ERROR` (critical validator process failed)
- `HOOK_NON_JSON_OUTPUT` (critical validator returned unstructured output)

### Manual Query Examples

```bash
# Count runtime errors in decision logs
rg "HOOK_RUNTIME_ERROR|HOOK_NON_JSON_OUTPUT" P:/.claude/hooks/session_data/hook_decisions_*.jsonl

# Focus on one hook
rg "StopHook_cross_validator.py.*HOOK_RUNTIME_ERROR" P:/.claude/hooks/session_data/hook_decisions_*.jsonl
```

### Analysis Scripts

Located in `P:/.claude/hooks/`:

| Script | Purpose |
|--------|---------|
| `analyze_decision_patterns.py` | Next step pattern detection effectiveness |
| `analyze_error_attribution.py` | Error source injection tracking |
| `analyze_audit_compliance.py` | Assumption audit compliance |
| `analyze_assumption_audit.py` | Detailed assumption analysis (supports `--terminal`, `--all`) |
| `analyze_blocks.py` | Hook blocking events |
| `analyze_hooks.py` | General hook metrics |
| `hook_health_check.py` | Hook execution health |
