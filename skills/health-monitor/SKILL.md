---
name: health-monitor
version: "1.0.0"
status: "stable"
description: System health monitoring with real-time memory checks, hook validation, and remediation guidance.
category: strategy
triggers:
  - /health-monitor
aliases:
  - /health-monitor

suggest:
  - /nse
  - /q
  - /debug
---

# Health Monitor Skill

Teaches Claude how to effectively monitor, diagnose, and report on system health issues in CSF NIP environments.

## Purpose

System health monitoring with real-time memory checks, hook validation, and remediation guidance.

## Project Context

### Constitution/Constraints
- Per solo-dev-authority: No continuous monitoring without idle timeout
- Real-time measurement required (no cached values for time-sensitive metrics)

### Technical Context
- Memory measured via `psutil.Process().memory_info().rss`
- Hook health check exit codes: 0 (healthy), 1 (some unhealthy), 2 (critical), 3 (unapproved changes)
- Database health: CKS + Session Memory

### Architecture Alignment
- Integrates with `/main` command for primary health check interface
- Works with `/chs` for pattern analysis
- Integrates with `/analytics` for production dashboard

## Your Workflow

When health issues detected:
1. Measure current state (don't assume from cached data)
2. Identify severity (Critical vs Warning vs Info)
3. Provide specific action (what should user do?)
4. Check for false positives (stale cache, recent changes)

## Validation Rules

### Real-Time Measurement
- DO NOT use cached JSON values for memory
- Use `psutil.Process().memory_info().rss` for current memory
- Memory thresholds: ≤500 MB (healthy), 500-1000 MB (moderate), >1000 MB (high)

## Core Principles

1. **Real-time measurement** - Always measure current state, never rely on cached values for time-sensitive metrics
2. **Actionable warnings** - Only alert when there's an actual problem, with specific remediation steps
3. **Context-aware thresholds** - Warning levels should reflect actual system capacity and typical usage patterns

## Health Check Categories

### 1. Memory Resources (REAL-TIME)

**Always measure current process memory using psutil:**
```python
import psutil
import os
process = psutil.Process(os.getpid())
memory_mb = process.memory_info().rss / (1024 * 1024)
```

**Thresholds:**
| Memory Level | Status | Action |
|--------------|--------|--------|
| ≤ 500 MB | Healthy | No action needed |
| 500-1000 MB | Moderate | Monitor trends |
| > 1000 MB | High | Restart Python session |

**DO NOT use cached JSON values** - memory changes in real-time and stale data creates false positives.

### 2. Hook Health

**Exit codes:**
- `0` - All healthy
- `1` - Some unhealthy hooks
- `2` - Critical hook failures
- `3` - Unapproved changes since baseline

**When exit code 3 appears:**
1. Check what changed: `python P:/.claude/hooks/hook_health_check.py`
3. If intentional (still optimizing): No action needed
4. If complete: Save baseline: `python P:/.claude/hooks/hook_health_check.py --save-baseline`

### 3. Database Health (CKS + Session Memory)

**Check:**
- Database file exists and is readable
- Can execute queries
- Database size is reasonable (< 200 MB warning, < 500 MB critical)

### 4. API Endpoints

**Check availability:**
- OpenRouter - API key validation
- Gemini - API key validation
- Groq - API key validation
- GitHub - Token validation

## Diagnosis Flow

When health issues are detected:

1. **Measure current state** - Don't assume from cached data
2. **Identify severity** - Critical vs Warning vs Info
3. **Provide specific action** - What should the user do?
4. **Check for false positives** - Stale cache, recent changes, etc.

## Common Issues

### False Positive Memory Warnings

**Symptom:** Health check shows "X MB RAM" but current usage is much lower

**Cause:** Reading from cached unified_health_*.json instead of measuring real-time

**Fix:** Use `psutil.Process().memory_info().rss` for current memory, not cached values

### Hook Baseline Drift

**Symptom:** Exit code 3 on hook health check

**Cause:** Hook files modified since baseline was saved

**Action:**
- If still developing: Ignore, will save baseline when done
- If complete: `python P:/.claude/hooks/hook_health_check.py --save-baseline`

## Commands Reference

```bash
# Run full health check
python P:/__csf/src/csf/cli/nip/main_code.py --mode full --execute-health-checks

# Check hook health specifically
python P:/.claude/hooks/hook_health_check.py

# Save hook baseline (approving current state)
python P:/.claude/hooks/hook_health_check.py --save-baseline

# Show what changed in hooks
python P:/.claude/hooks/hook_health_check.py --show-changes
```

## Examples

**Example 1: Diagnosing memory warning**
```
User: "Health check shows 588 MB RAM warning"
Claude: "Let me check current memory usage..."
[Measures with psutil]
"Current memory is actually 18 MB - the warning was from stale cached data.
The output_formatter has been fixed to use real-time values."
```

**Example 2: Hook baseline exit code 3**
```
User: "Hooks check failed with exit 3"
Claude: "This means hooks were modified since baseline. Checking what changed..."
[Shows git diff of modified hook]
"The pre_tool_use hook was modified to add RBW-001 enforcement.
Is this optimization complete, or still in progress?"
```

## Integration Notes

This skill works with:
- `/main` command - Primary health check interface
- `/chs` - Chat history search for pattern analysis
- `/analytics` - Production analytics dashboard

## Metadata

**Version:** 1.0.0
**Created:** 2025-12-27
**Purpose:** Fix false-positive health warnings and provide actionable monitoring
