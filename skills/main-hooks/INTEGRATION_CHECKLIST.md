# Integration Checklist for /main

## Files Created

### Simple Mode (Option 1)
- [x] `P:/.claude/skills/main/skill.md` (EXECUTION DIRECTIVE, fixed Quick Start)

### Hooks Mode (Option 2) - Separate Skill
- [x] `P:/.claude/skills/main-hooks/skill.md` (with hooks in frontmatter)
- [x] `P:/.claude/skills/main-hooks/hooks/PreToolUse_main_gate.py`

---

## Frontmatter Hooks Registration

`main-hooks/skill.md` includes hooks configuration that activates when `/main-hooks` is used:
- PreToolUse gate validates that Bash commands call `system_health.py`
- Blocks incorrect commands with helpful message

Hooks use `$CLAUDE_PROJECT_DIR` for portable path references.

---

## Testing Steps

### Test Simple Mode
1. Invoke: `/main`
2. Verify: EXECUTION DIRECTIVE is present
3. Verify: Quick Start shows actual CLI commands
4. Test: Skill executes `system_health.py` when invoked

### Test Hooks Mode
1. Invoke: `/main-hooks`
2. Verify: Frontmatter hooks load automatically
3. Test: Try incorrect Bash command → should be blocked
4. Test: Try correct `system_health.py` command → should be allowed
5. Logs: Check `P:/.claude/logs/hooks.jsonl` for hook activity

---

## Usage

```bash
# Simple mode - instructions only
/main

# Hooks mode - with enforcement
/main-hooks
```

Both skills coexist. Choose per-session based on need:
- Use `/main` for quick health checks
- Use `/main-hooks` when you need strict command validation

---

## Rollback (if needed)

```bash
# Restore original main skill
git checkout P:/.claude/skills/main/skill.md

# Remove main-hooks skill
rm -rf P:/.claude/skills/main-hooks/
```

---

## Customization Points

Edit these files to customize validation:

### Simple Mode
- `P:/.claude/skills/main/skill.md`:
  - Lines 18-31: EXECUTION DIRECTIVE
  - Lines 41-48: Quick Start commands

### Hooks Mode
- `P:/.claude/skills/main-hooks/skill.md` frontmatter: Adjust hooks matchers/commands
- `P:/.claude/skills/main-hooks/hooks/PreToolUse_main_gate.py`:
  - Lines 26-32: Command validation logic
  - Lines 33-41: Block message content

---

## Architecture Notes

### Why Two Skills?

**Problem:** PreToolUse gates CAN check for conditions, but PostToolUse hooks CANNOT access user's original command flags.

**Solution:** Two separate skills provide clean separation:
- `/main` → Simple mode (no hooks)
- `/main-hooks` → Hooks mode (full enforcement)

**Benefits:**
- No conditional complexity
- Clear separation — user knows which mode they're in
- Both skills coexist, user chooses per-session
- Can try Simple first, switch to Hooks if needed
