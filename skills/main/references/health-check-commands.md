# Health Check Command Reference

## Quick Reference

**Health Checks:**
| Command | Description |
|---------|-------------|
| `python main_health.py` | All checks, summary view |
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
| `python main_health.py --upgrade --limit N` | Limit upgrade to N packages |

**Hook Outcome Metrics:**
| Command | Description |
|---------|-------------|
| `python P:/.claude/hooks/scripts/monitor_hook_outcomes.py --days 7` | Principle violation trends (context_reuse, grounded_changes, etc.) |
| `python P:/.claude/hooks/scripts/cleanup_cks.py --min-quality 0.3 --dry-run` | Preview low-quality entry cleanup |

---

## Health Checks (7 categories)

| Check | What It Validates |
|-------|-------------------|
| **settings** | settings.json size, env vars, hooks count |
| **hooks** | Timeout rates, latency, log bloat |
| **workspace** | RESTORE_CONTEXT.md, git locks, uncommitted changes |
| **cks** | Entry count, embedding coverage, staleness |
| **skills** | Duplicate triggers, alias collisions |
| **cve_remediation** | pip-audit --fix --dry-run for remediation options (default) |
| **filesystem** | Filesystem structure violations via `/cleanup --json` |

**With --deps flag:**
| **dependencies** | pip-audit for vulnerability detection |

**With --outdated flag:**
| **outdated_packages** | pip list --outdated for version updates |

**Skip CVE check:**
| Use `--skip-cve` | Opt-out of CVE remediation check |

**Filesystem check details:**
- Calls `cleanup.py --json` to detect violations
- Reports violation count grouped by type (UNAUTHORIZED_ROOT_DIRECTORY, UNKNOWN_CONFIG_FILE, etc.)
- Status: `warning` if violations found, `healthy` otherwise
- Recommendation: Run `/cleanup` for detailed analysis with source code tracing

---

## Hook System Skills

Complementary hook observability commands for deeper system insights:

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `/hook-obs` | Performance, traces, health from events database | Hook latency analysis, trace waterfall, regression detection |
| `/hook-audit` | Behavioral compliance monitoring | Check LLM compliance with hook injections, blocking rates |
| `/hook-inventory` | File inventory audit | Classify hooks as dead/active/router-dispatched/utility |
| `/hooks-edit` | Edit hook files (operational) | Temporarily bypass hooks for editing |

**Quick Start:**
```bash
/hook-obs --health        # Hook health matrix
/hook-obs --slow 200      # Find slow hooks
/hook-audit               # Behavioral compliance dashboard
/hook-inventory           # File classification audit
```

---

## Output Interpretation

| Score | Status | Action |
|-------|--------|--------|
| ≥80% | HEALTHY | All systems operational |
| 50-79% | WARNING | Investigate warnings |
| <50% | CRITICAL | Immediate attention required |

**Exit Codes:**
- 0 = healthy
- 1 = warnings
- 2 = critical

---

## Auto-Fix (--fix)

Safe auto-remediations:

| Issue | Fix Action |
|-------|------------|
| Runaway watcher.log | Truncate to last 1000 lines |
| RESTORE_CONTEXT.md exists | Delete file |
| Stale .git/*.lock files | Delete locks |

---

## Package Upgrades (--upgrade)

The outdated packages check categorizes updates by risk:

| Category | Description | Default Action |
|----------|-------------|-----------------|
| **Safe upgrades** | Minor/patch version updates (e.g., 1.2.3 → 1.2.4) | Included with `--upgrade` |
| **Major bumps** | Major version changes (e.g., 1.x → 2.x) | Excluded by default, requires `--upgrade-all` |
| **Key packages** | Critical packages (anthropic, pytest, etc.) | Included with `--upgrade` |

**Recommended workflow:**
1. Run with `--outdated` to see what needs updating
2. Run with `--upgrade --dry-run` to preview safe upgrades
3. Run with `--upgrade` to apply safe upgrades
4. Review major bumps individually before using `--upgrade-all`

**Example:**
```bash
# Check what's outdated
python main_health.py --outdated

# Preview safe upgrades
python main_health.py --upgrade --dry-run

# Apply safe upgrades only
python main_health.py --upgrade

# Upgrade everything (use with caution)
python main_health.py --upgrade-all
```

Use `--dry-run` to preview fixes without applying.

---

## Historical Tracking (--history)

Health scores are recorded to `P:/.claude/session_data/health_history.jsonl`.

```
📊 Health Score Trend (last 20 checks)
==================================================
2026-01-31 15:30 │ █████████████████░░░ │  85% ✅
2026-01-31 14:15 │ ██████░░░░░░░░░░░░░░ │  32% ❌
2026-01-31 12:00 │ ████████████████░░░░ │  80% ✅

📈 Trend: Improving
```

---

## Legacy Commands (Still Work)

Individual check scripts in `P:/.claude/skills/main/scripts/`:

```bash
python settings_health_check.py    # Settings only
python hook_health_check.py        # Hooks only
python workspace_state_check.py    # Workspace only
python cks_health_check.py         # CKS only
python skill_collision_check.py    # Skills only
```

CSF system health (separate from above):
```bash
cd P:/__csf && python src/modules/observability/system_health.py
```

---

## Thresholds

**Settings:**
- Lines: ≤900 | Size: ≤35KB | Env vars: ≤70 | Hooks: ≤60

**Hooks:**
- Timeout rate: ≤20% | Avg latency: ≤2000ms | Log dir: ≤10MB

**CKS:**
- Min entries: ≥100 | Embedding coverage: ≥90% | Stale: 7 days

**Workspace:**
- No RESTORE_CONTEXT.md | No stale locks | Uncommitted: ≤20
