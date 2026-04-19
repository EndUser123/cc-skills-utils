---
name: code-review-workflow
description: Streamlined automated code review workflow that dispatches parallel specialist agents and synthesizes actionable findings. Use when user says "review my code", "run code review", "analyze code quality", "check code for issues", or needs automated security/logic/performance review of code files or directories.
version: "0.1.0"
category: analysis
triggers:
  - /review-code
  - "review my code"
  - "run code review"
  - "analyze code quality"
  - "check code for issues"
  - "automate code review"
enforcement: advisory
depends_on_skills: []
---

# Code Review Workflow — Automated Multi-Agent Review

A skill that automates code review by dispatching specialist agents in parallel and synthesizing their findings into actionable recommendations.

## When to Use

- User wants comprehensive code review without manual analysis
- Multiple files or entire directories need review
- Security, logic, performance, and quality issues need detection
- Git diff needs automated review

## Review Workflow

### Step 1: Capture Review Target

**Context-Aware Resolution (in priority order):**

1. **Args specifies target** — If args contains paths or file descriptions, use those.
2. **Git diff** — If no args, check `git diff --name-only HEAD` for changed files
3. **Recent edits** — Check what was recently edited in the session
4. **Ask if ambiguous** — Only ask if no clear target exists

**Supported targets:**
- Single file: `P:/path/to/file.py`
- Multiple files: `P:/path/to/*.py`
- Directory: `P:/path/to/project/`
- Git diff: all changed files from HEAD

### Step 2: Create Review Session

Create a session for tracking review state:

```bash
python -c "
from pathlib import Path
import uuid
import json

session_id = str(uuid.uuid4())[:8]
session_dir = Path('P:/.claude/.evidence/code-review/') / session_id
session_dir.mkdir(parents=True, exist_ok=True)

target = '''{target}'''
work_file = session_dir / 'work.md'
specialists_dir = session_dir / 'specialists'
specialists_dir.mkdir(exist_ok=True)

# Resolve files
target_path = Path(target) if target else None
files = []
if target_path and target_path.is_file():
    files = [target_path]
elif target_path and target_path.is_dir():
    files = list(target_path.rglob('*.py')) + list(target_path.rglob('*.js'))
elif not target:
    # Auto-detect from git
    import subprocess
    result = subprocess.run(['git', 'diff', '--name-only', 'HEAD'], capture_output=True, text=True)
    changed = result.stdout.strip().split('\n')
    files = [Path(f) for f in changed if f.endswith(('.py', '.js', '.ts'))]

content = f'# Review Target\n\nTarget: {target or \"git diff\"}\n\n'
if files:
    content += f'Files ({len(files)}):\n'
    for f in files[:50]:
        content += f'- {f}\n'
    if len(files) > 50:
        content += f'- ... and {len(files) - 50} more\n'
work_file.write_text(content)

print(session_dir)
"
```

### Step 3: Dispatch Parallel Specialist Agents

Based on file types detected, dispatch appropriate specialists:

**For Python files:**
- `adversarial-security` — data access, auth, I/O, injection vectors
- `adversarial-logic` — off-by-one, wrong operators, conditionals
- `adversarial-performance` — hot paths, loops, N+1 queries
- `adversarial-quality` — tech debt, maintainability
- `adversarial-testing` — test coverage, edge cases

**For JavaScript/TypeScript:**
- `adversarial-security` — XSS, injection, auth issues
- `adversarial-logic` — async issues, error handling
- `adversarial-quality` — tech debt, maintainability

**Dispatch Pattern:**

```bash
# Dispatch all specialists in parallel via Task tool
Task(subagent_type="general-purpose",
     prompt=f"Review the code in files listed at P:/{{session_dir}}/work.md for [specialist-domain]. Write findings to: P:/{{session_dir}}/specialists/[specialist-name].md",
     description="[Specialist] review")
```

Wait for all specialist agents to complete.

### Step 4: Read Specialist Findings

```bash
cat "P:/{session_dir}/specialists/"*.md 2>/dev/null
```

### Step 5: Calculate Health Score

Health Score = `100 - (CRITICAL×20 + HIGH×10 + MEDIUM×5 + LOW×2)`, capped at 0-100.

| Score | Interpretation |
|-------|----------------|
| 80-100 | Healthy — Low risk, minor improvements possible |
| 50-79 | Warning — Significant issues, address HIGH items first |
| Below 50 | Critical — Systemic problems, do not deploy without fixes |

### Step 6: Synthesize Final Report

Write to `P:/{session_dir}/review.md`:

```markdown
# Code Review Report

**Target:** {target}
**Date:** {date}
**Session:** {session_id}

## Summary

[2-3 sentences overview of findings]

## Health Score: XX%

| Severity | Count |
|----------|-------|
| CRITICAL | N |
| HIGH | N |
| MEDIUM | N |
| LOW | N |

## Findings

### Critical Issues

1. [CRITICAL] issue description (file:line)

### High Priority

1. [HIGH] issue description (file:line)

### Medium Priority

1. [MEDIUM] issue description (file:line)

### Low Priority

1. [LOW] issue description (file:line)

## Recommendations

1. [Priority order, actionable items]

## Files Reviewed

[List of files analyzed]
```

### Step 7: Deliver Final Output

Read `P:/{session_dir}/review.md` and present as final output.

### Step 8: Session Persistence

Session directories persist at `P:/.claude/.evidence/code-review/{session_id}/` until manually removed.

## Output Format

Final review uses severity-tagged findings with file:line citations:

- **CRITICAL**: Security vulnerabilities, data corruption risks, correctness issues
- **HIGH**: Significant bugs, performance issues, maintainability problems
- **MEDIUM**: Minor issues, code smells, improvement opportunities
- **LOW**: Nitpicks, style suggestions, minor optimizations

## Integration with Existing Skills

This skill complements:
- `/adversarial-review` — More comprehensive 7-agent review with meta-analysis
- `/meta-review` — Cross-file architectural analysis for Python packages
- `/code-review` — Basic parallel specialist review

Use this skill for streamlined automated review; use `/adversarial-review` for deeper analysis.
