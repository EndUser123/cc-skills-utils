# Main Skill Historical Documentation

Archived sections from SKILL.md that are kept for reference only.

---

## Serena Project Validation (Archived 2026-03-28)

**Original status**: Phase 1 active (data collection)
**Archived**: This section was stale — no evidence of recent activity, Phase 1 monitoring period had concluded

### Original Content

**Status**: Phase 1 active (data collection)
**Plan**: `P:\.claude\plans\plan-20260302-serena-project-validation.md`

#### Overview

Preventing P1 context management waste from the yt-fts debugging session — 6 failed API calls due to "No active project" errors before activating Serena project.

#### Current Phase: Data Collection (Phase 1)

**Objective**: Validate detection patterns against actual MCP payloads before enforcement.

**When to transition**: After 7 days of normal usage or 50+ Serena tool calls logged

#### Post-Data-Collection Actions

1. **Analyze logged tool names**:
   ```bash
   cat .claude/state/serena_calls.jsonl | jq -r '.tool_name' | sort -u
   ```

2. **Validate detection pattern** matches actual tool names:
   - Confirm "plugin:serena" pattern catches all Serena operations
   - Identify edge cases (unexpected tool name formats)
   - Update detection logic in `pre_tool_use_logic.py` if edge cases found

3. **Transition to Phase 2** (log-only deployment):
   - Implement `check_serena_project()` function
   - Deploy with `SERENA_PROJECT_LOG_ONLY=true`
   - Monitor violations for 3-5 days

#### How to Check Status

```bash
# Count logged Serena calls
wc -l .claude/state/serena_calls.jsonl

# View recent tool names
tail -20 .claude/state/serena_calls.jsonl | jq -r '.tool_name'

# Check if data collection hook is active
grep -q "PreToolUse_serena_detector" P:/.claude/hooks/PreToolUse.py && echo "✓ Active" || echo "✗ Not registered"
```

#### Critical Reminder

**DO NOT skip Phase 1 analysis** — unvalidated detection pattern risks blocking valid operations.

The architecture review identified that "plugin:serena" may not match actual MCP tool routing. Without validating against real payloads, we risk false positives (blocking valid operations) or false negatives (missing violations).

#### Implementation Timeline

- **Phase 1** (current): Data collection — 7 days passive monitoring
- **Phase 2**: Log-only deployment — 3-5 days validation
- **Phase 3**: Enable blocking — 1 hour
- **Phase 4**: Feature flag evaluation — optional, 30 days

**Total effort**: 12-15 hours over 2-3 weeks (mostly passive data collection)

#### Related Files

- Plan: `P:\.claude\plans\plan-20260302-serena-project-validation.md`
- Architecture decision: `P:\.claude\arch_decisions\2026-03-02_debugging_workflow_validation.md`
- Implementation: `P:\.claude\hooks/__lib/pre_tool_use_logic.py` (after Phase 1)

---

## Architectural Recommendation Gate Review (Archived 2026-03-28)

**Original due date**: 2026-03-19
**Archived**: 9 days overdue — decision was to archive rather than complete the overdue review

#### Original Status

**Task ID**: #1813
**Plan**: `P:\.claude\plans\plan-20260312-anti-laziness-arch-verification.md`
**Status**: Deployed in warn mode (7-day monitoring period)

#### Overview

Anti-laziness gate that prevents architectural recommendations without prior investigation (e.g., "move X to cognitive-stack" without reading /s/SKILL.md to verify actual architectural fit).

#### Original Review Checklist

1. **Check warning logs**:
   ```bash
   # Count architectural recommendation warnings
   wc -l .claude/state/logs/investigation_gate_arch_rec.jsonl

   # View recent warnings
   tail -20 .claude/state/logs/investigation_gate_arch_rec.jsonl | jq .

   # Analyze patterns
   cat .claude/state/logs/investigation_gate_arch_rec.jsonl | jq -r '.destination' | sort | uniq -c
   ```

2. **Count blocks by destination**:
   ```bash
   # Which destinations trigger the gate most?
   cat .claude/state/logs/investigation_gate_arch_rec.jsonl | jq -r '.destination' | sort | uniq -c | sort -rn
   ```

3. **Analyze false positives**:
   - Read warning messages manually
   - Count legitimate refactoring blocked (acceptable threshold: <10%)
   - Identify patterns causing false positives

4. **Decision tree**:
   - **If false positive rate <10%**: Switch to block mode (`CSF_ARCH_RECOMMENDATION_MODE=block`)
   - **If false positive rate >20%**: Tune detection patterns
   - **If 10-20%**: Extend monitoring period another 7 days

5. **Check /hook-audit integration**:
   ```bash
   # Verify blocks are logged to /hook-audit
   python -c "
   import json
   data = json.load(open('P:/.claude/hooks/logs/hook_audit_events.jsonl'))
   arch_blocks = [e for e in data if e.get('hook_name') == 'investigation_gate_arch_recommendation']
   print(f'Total arch recommendation blocks: {len(arch_blocks)}')
   "
   ```

#### How to Switch to Block Mode

After review, if false positive rate is acceptable:

```bash
# Update settings.json
jq '.env.CSF_ARCH_RECOMMENDATION_MODE = "block"' P:/.claude/settings.json > tmp.json
mv tmp.json P:/.claude/settings.json
```

#### Related Files

- Plan: `P:\.claude\plans\plan-20260312-anti-laziness-arch-verification.md`
- Implementation: `P:\.claude\hooks/PreToolUse_investigation_gate.py` (lines 82-428)
- Tests: `P:\.claude\hooks/tests/test_investigation_gate_arch_recommendations.py` (8 tests, all passing)
- Documentation: `P:\.claude\hooks\CLAUDE.md` (architectural recommendation gate section)

---

## System Roadmap & Recommendations (Archived 2026-03-28)

**Original date**: 2026-03-05
**Archived**: Completely stale — content is 23+ days old

### Original Short-term (Immediate - Optional)

**Commit session work** if not already committed:
```bash
git add .claude/hooks/PreToolUse.py
git add .claude/hooks/tests/test_research_router_fixed.py
git add .claude/hooks/RESEARCH_ROUTER_TEST_SUMMARY.md
git add memory/tool_usage_patterns.md
git add memory/bugfixes.md
git add memory/MEMORY.md
git commit -m "feat: research router + three-tier memory persistence"
```

**Cleanup standalone files** (optional, 5 minutes):
```bash
rm .claude/hooks/research_router.py
rm .claude/hooks/research_router_config.json
```

**Quick wins** (< 5 minutes each):
1. Monitor research router logs: `tail -f .claude/hooks/research_router.log.jsonl`
2. Store Edit tool pattern in CKS: See shared/memory-system.md for documentation

### Original Medium-term (1-2 weeks)

**Research Router Phase 2 Planning**:
1. Monitor `research_router.log.jsonl` for false positives
2. Identify non-research queries triggering logs (pattern tuning)
3. Adjust `_RESEARCH_KEYWORDS` or `_ESCAPE_PHRASES` based on observations
4. Document high-confidence patterns for hard-blocking

**Observation checklist**:
- [ ] Review logs after 50+ research queries logged
- [ ] Count false positives (acceptable threshold: <10%)
- [ ] Identify escape phrase gaps (add new phrases if needed)
- [ ] Test candidate patterns for Phase 2 blocking

**Log review commands**:
```bash
# Count research router triggers by tool
cat .claude/hooks/research_router.log.jsonl | jq -r '.tool_name' | sort | uniq -c

# View recent research queries
tail -20 .claude/hooks/research_router.log.jsonl | jq -r '.user_message'

# Check escape phrase effectiveness
grep -i "no research\|local only\|skip research" .claude/hooks/research_router.log.jsonl | wc -l
```

### Original Long-term (After observation period)

**Implement Phase 2: Selective Hard-Blocking**:

After 1-2 weeks of advisory mode data collection, implement selective blocking for high-confidence research patterns:

**Code template** (from RESEARCH_ROUTER_TEST_SUMMARY.md):
```python
# Add to PreToolUse.py after research router
if is_research and is_local and _should_hard_block(tool_name, user_message):
    response = _deny_tool_call(
        "This query requires web research first. "
        "Use WebSearch or a research agent, then retry.",
        "PreToolUse.py:research_router"
    )
    print(json.dumps(response))
    sys.exit(0)
```

**Implementation checklist**:
- [ ] Analyze 1-2 weeks of log data
- [ ] Select high-confidence patterns (0% false positives in observation)
- [ ] Implement `_should_hard_block()` function
- [ ] Test with synthetic input before enabling
- [ ] Monitor user feedback for 1 week after deployment
- [ ] Roll back if false positive rate >5%

**Rollback plan** (if hard-blocking fails):
```python
# Revert to advisory mode by commenting out deny response
# Keep logging active for continued observation
```

**Success criteria**:
- False positive rate <5%
- User feedback indicates improvement (not frustration)
- Research queries routed to WebSearch/research agents
- Local tools remain accessible for non-research queries

### Original Continuous Improvement (Ongoing)

**Weekly maintenance tasks**:
1. Review `research_router.log.jsonl` for emerging patterns
2. Add new research keywords as discovered
3. Update escape phrases based on user feedback
4. Check `tool_usage_patterns.md` for new patterns to document

**Monthly reviews**:
1. Analyze research router effectiveness (query volume, false positives)
2. Update MEMORY.md topic files with new learnings
3. Run `/gap-task-opportunities` to identify new gaps
4. Run `/reflect` to capture session patterns

**Quarterly planning**:
1. Evaluate Phase 2 hard-blocking effectiveness
2. Consider Phase 3 enhancements (semantic analysis, ML-based detection)
3. Review memory system architecture (topic files vs CKS integration)
4. Update skill documentation based on usage patterns

### Related Documentation

- Research Router Test Summary: `P:\.claude\hooks\RESEARCH_ROUTER_TEST_SUMMARY.md`
- Tool Usage Patterns: `C:\Users\brsth\.claude\projects\P--\memory\tool_usage_patterns.md`
- Gap Analysis: Run `/gap-task-opportunities` for current session gaps
