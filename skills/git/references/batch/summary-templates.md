# Skill-Adaptive Summary Templates

> Reference for gitbatch Step 4: Report Results
> Used after batch execution to generate skill-specific summaries

## Template Structure (All Skills)

```
--- Batch Summary ---
Skill: <skill>
Packages: N passed, M failed, K skipped

PACKAGE HEALTH:
  * <pkg>: <status> (<notes>)

FAILURE THEMES:
  * <theme>: <count> failures
    - <specific issue>
    - <specific issue>

ACTIONABLE:
  1. <priority action>
  2. <priority action>
```

## Skill-Specific Guidance

### `/p` (Code Maturation Pipeline) -- Report test results

```
PACKAGE HEALTH:
  * <pkg>: PASS|FAIL (<test_summary>)
    - Pre-existing vs new failures
    - Coverage % if available

FAILURE THEMES:
  * <category>: <count> failures
    - Test name pattern or root cause

ACTIONABLE:
  1. Fix <category> in <pkg> (blocking/non-blocking)
```

### `/gitready` (Skill Readiness) -- Report validation results

```
PACKAGE HEALTH:
  * <pkg>: READY|NOT_READY (<missing_items>)
    - Pointer completeness
    - Documentation status

FAILURE THEMES:
  * <category>: <count> packages
    - Missing: <item1>, <item2>

ACTIONABLE:
  1. Complete <item> in <pkg>
```

### `/critique` (Adversarial Review) -- Report findings

```
PACKAGE HEALTH:
  * <pkg>: <critical/high/medium/low> findings

FAILURE THEMES:
  * <category>: <count> findings
    - <finding_description>

ACTIONABLE:
  1. Address <severity> findings in <pkg>
```

### Generic Skill -- Minimal summary

```
PACKAGE HEALTH:
  * <pkg>: <status>

ACTIONABLE:
  1. Run /<skill> individually on failed packages for details
```
