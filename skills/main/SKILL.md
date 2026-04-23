---
name: main
description: Main Cognitive Steering Framework - system health checks and workspace validation (with optional enforcement hooks)
version: 1.0.0
status: stable
category: governance
triggers:
  - /main
  - /main-hooks
aliases:
  - /main
  - /health
  - /main-hooks
enforcement: advisory
version: 1.0.0
depends_on_skills: []
output_format: 2
workflow_steps:
  - health: Run main_health.py with appropriate flags
  - reflect: Optional /reflect invocation (skip if --quick used)
suggest:
  - /search
  - /standards
  - /dream
  - /top-problems

hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "python \"$CLAUDE_PROJECT_DIR/.claude/skills/main/hooks/PreToolUse_main_gate.py\""
          timeout: 10
---

# Main Cognitive Steering Framework

## Two Modes

| Mode | Trigger | Enforcement |
|------|---------|-------------|
| **Advisory** | `/main` | No hook enforcement |
| **Enforced** | `/main-hooks` | PreToolUse gate validates Bash calls to `main_health.py` |

Both modes run the same health checks. The `--hooks` flag enables hook enforcement for any invocation.

## EXECUTION DIRECTIVE

**When /main is invoked, IMMEDIATELY execute:**

```bash
python P:/.claude/skills/main/scripts/main_health.py
```

**Step 1: Parse CLI flags** (from the invocation or infer from context):

| Flag | When to use |
|------|-------------|
| *(none)* | Runs `cleanup.py --dry-run` first, then all health checks |
| `--quick` | Skip slow checks (<5s), still runs cleanup first |
| `--fix` | Auto-remediate safe issues |
| `--dry-run` | Preview what `--fix` would do (cleanup only) |
| `--json` | Machine-readable output |
| `--deps` | Include dependency audit (CVEs) |
| `--skip-cve` | Skip CVE remediation check |
| `--quiet` | Just pass/fail status line |
| `--history` | Show health score trend |
| `--upgrade` | Upgrade safe packages (minor/patch) |
| `--upgrade-all` | Upgrade all packages including majors |
| `--suggest` | Show skill suggestions at end of run |

**Step 2: Run `main_health.py`.**

On invocation (no flags), `main_health.py` runs `cleanup.py --dry-run` first with full interactive output, then proceeds to all health checks.

**Step 3: Display results** — pass through the script's own output verbatim. The script formats its own results.

**Step 4: Reflection (conditional)** — invoke `/reflect` only if `--quick` was NOT used.

**Execution notes:**
- Single Python script, no subprocess spawning from the skill side
- **Default behavior**: On invocation with no flags, `main_health.py` runs `cleanup.py --dry-run` first (full interactive output), then all health checks
- `main_health.py` internally runs checks sequentially (core checks always, slow checks skipped in `--quick` mode)
- `main_health.py` handles its own error isolation — individual check failures don't crash the run
- `main_health.py` subprocess calls: `pip-audit`, `pip list`, `pip install`, `cleanup.py`
- `main_health.py` returns exit codes: 0=healthy, 1=warnings, 2=critical

**DO NOT:**
- Display this documentation without executing
- Skip the Bash execution
- Run multiple parallel Bash tasks — use the single script

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `python main_health.py` | Runs `cleanup.py --dry-run` first, then all health checks |
| `python main_health.py --quick` | Skip slow checks (<5s) |
| `python main_health.py --fix` | Auto-remediate safe issues |
| `python main_health.py --dry-run` | Preview what --fix would do |
| `python main_health.py --json` | Machine-readable output |
| `python main_health.py --deps` | Include dependency audit (CVEs) |
| `python main_health.py --outdated` | Check for outdated packages |
| `python main_health.py --skip-cve` | Skip CVE remediation check |
| `python main_health.py --quiet` | Just pass/fail status line |
| `python main_health.py --history` | Show health score trend |
| `python main_health.py --upgrade` | Upgrade safe packages (minor/patch) |
| `python main_health.py --upgrade-all` | Upgrade all packages including majors |
| `python main_health.py --suggest` | Show skill suggestions at end of run |

---

## Health Checks (9 categories)

| Check | What It Validates |
|-------|-------------------|
| **settings** | settings.json size, env vars, hooks count |
| **hooks** | Timeout rates, latency, log bloat |
| **workspace** | RESTORE_CONTEXT.md, git locks, uncommitted changes |
| **cks** | Entry count, embedding coverage, staleness |
| **skills** | Duplicate triggers, alias collisions |
| **cve_remediation** | pip-audit --fix --dry-run for remediation options |
| **filesystem** | Filesystem violations (JSON parse of `cleanup.py --json --max 100`); default invocation runs `cleanup.py --dry-run` interactively first |
| **spec_drift** | SKILL.md execution directives reference scripts that don't exist |
| **skill_deps** | Skill `depends_on_skills`/`suggest` references point to missing skills |
| **wiki** | Wiki vault health — contradictions, orphan pages, broken wikilinks, stale claims (`/wiki lint`) |

---

## Output Interpretation

| Score | Status | Action |
|-------|--------|--------|
| >=80% | HEALTHY | All systems operational |
| 50-79% | WARNING | Investigate warnings |
| <50% | CRITICAL | Immediate attention required |

**Exit Codes:** 0 = healthy, 1 = warnings, 2 = critical

**Inline Skill Suggestions:** When a check fails, actionable skill suggestions appear inline below the check output as `💡 Run /skill-name`. Suggestions are capped at 3 per check to avoid verbosity. Use `--suggest` to see a consolidated summary of all suggestions at end of run.

**Periodic Problem Tracking:** For ongoing awareness of accumulating issues, consider running `/top-problems --diff` periodically. The `/main` health check covers system infrastructure; `/top-problems` covers evidence-accumulated risks from sessions, premortems, and critiques.

**Permission Prompt Hygiene:** Run `/fewer-permission-prompts` if it has been more than 5 days since the last run. This scans recent transcripts and refreshes the read-only allowlist in `P:/.claude/settings.json` to reduce unnecessary prompts. The last known run was 2026-04-19 — run the command to check current transcript coverage if uncertain.

**CLAUDE.md Health:** Run `/claude-md-management:claude-md-improver` if it has not been used in more than 5 days. Audits all CLAUDE.md files in the repo, scores them against a quality rubric, and proposes targeted improvements. Run after any significant project structure changes or before major development pushes.

**Hook Observability:** Run `/hook-obs` monthly to monitor hook performance and behavioral compliance. Use `stats`, `health`, `blocks`, and `escalation` for focused diagnostics. The `/main` health checks provide a compact infrastructure snapshot (timeouts, latency, log bloat); `/hook-obs` provides deep event-level diagnostics and compliance trends. (Legacy alias: `/hook-audit`.)

**Session Insights:** Run `/insights` monthly to analyze Claude Code session patterns and identify usage trends. Provides visibility into how the system is being used and where workflow improvements may exist.

---

## Thresholds

| Category | Thresholds |
|----------|-----------|
| **Settings** | Lines <=900, Size <=35KB, Env vars <=70, Hooks <=60 |
| **Hooks** | Timeout rate <=20%, Avg latency <=2000ms, Log dir <=10MB |
| **CKS** | Min entries >=100, Embedding coverage >=90%, Stale: 7 days |
| **Workspace** | No RESTORE_CONTEXT.md, No stale locks, Uncommitted <=20 |

---

## Detailed Reference Files

For comprehensive documentation on each subsystem, see:

| File | Contents |
|------|----------|
| `references/health-check-commands.md` | Full command reference, auto-fix details, package upgrades, hook system skills, legacy commands |
| `references/narrative-intent-detector.md` | Narrative intent detector phase migration, behavioral safety verification tests |
| `references/context-reuse-monitoring.md` | Context reuse monitoring procedures, regression detection, tuning guide |
| `HISTORY.md` | Archived sections (Serena validation, arch recommendation gate, system roadmap) |
