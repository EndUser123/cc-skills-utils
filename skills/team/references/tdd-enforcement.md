# TDD Enforcement Reference (MANDATORY for Code Changes)

**CRITICAL:** All code modification tasks must follow TDD workflow (RED -> GREEN -> REGRESSION).

## Task Type Detection

Auto-detect if task requires TDD enforcement:

```python
def detect_task_type(task: dict) -> str:
    """Determine if task requires TDD enforcement.

    Returns:
        'code_change' - Requires TDD (refactor, bug fix, feature)
        'exempt' - Exempt from TDD (docs, config)
        'unknown' - Manual review needed
    """
    if task.get('metadata', {}).get('tdd_required'):
        return 'code_change'

    task_type = task.get('type', '').lower()
    tdd_required_types = ['refactor', 'bug_fix', 'bug', 'feature', 'improvement']
    if task_type in tdd_required_types:
        return 'code_change'

    title = task.get('title', '').lower()
    desc = task.get('description', '').lower()
    tdd_keywords = ['fix:', 'fix ', 'implement', 'refactor', 'add ', 'change ']
    if any(kw in title or kw in desc for kw in tdd_keywords):
        exempt_keywords = ['documentation', 'readme', 'config', 'setup', 'update readme']
        if not any(kw in title or kw in desc for kw in exempt_keywords):
            return 'code_change'

    return 'unknown'
```

## TDD Workflow Function

Execute task with TDD enforcement:

```python
def execute_task_with_tdd(task: dict, skill_invoker):
    """Execute task with mandatory TDD phases.

    Args:
        task: Task dict with id, title, description, type
        skill_invoker: Function to invoke the specified skill

    Raises:
        RuntimeError: If any TDD phase is violated
    """
    task_id = task['id']
    task_type = detect_task_type(task)

    if task_type == 'exempt':
        print(f"[{task_id}] TDD exempt: {task.get('title')}")
        skill_invoker(task)
        return

    if task_type == 'unknown':
        print(f"[{task_id}] TDD status unknown - proceeding without TDD enforcement")
        skill_invoker(task)
        return

    print(f"[{task_id}] TDD required: {task.get('title')}")

    # Phase 1: RED - Write/test discovery
    test_file = ensure_test_exists(task)
    red_result = run_pytest(test_file, expect_failure=True)
    if not red_result.get('has_failures'):
        raise RuntimeError(
            f"TDD RED phase violated for task {task_id}:\n"
            f"  Task: {task.get('title')}\n"
            f"  Test: {test_file}\n"
            f"  Expected: Test must FAIL before changes\n"
            f"  Got: Test passed or no failures\n"
            "Action: Write test that FAILS, then retry"
        )
    print(f"[{task_id}] RED phase complete: {test_file} FAILS as expected")

    # Phase 2: GREEN - Execute the actual task
    try:
        skill_invoker(task)
    except Exception as e:
        raise RuntimeError(
            f"Task execution failed during GREEN phase:\n"
            f"  Task: {task_id}\n"
            f"  Error: {e}"
        )

    green_result = run_pytest(test_file, expect_pass=True)
    if not green_result.get('all_passed'):
        raise RuntimeError(
            f"TDD GREEN phase failed for task {task_id}:\n"
            f"  Task: {task.get('title')}\n"
            f"  Test: {test_file}\n"
            f"  Expected: Test must PASS after changes\n"
            f"  Got: Test has failures\n"
            "Action: Fix code to make test PASS, or revert changes"
        )
    print(f"[{task_id}] GREEN phase complete: {test_file} PASSES")

    # Phase 3: REGRESSION - Run related tests
    regression = run_regression_tests(task)
    if regression.get('has_new_failures'):
        raise RuntimeError(
            f"REGRESSION phase failed for task {task_id}:\n"
            f"  Task: {task.get('title')}\n"
            f"  New failures: {regression.get('new_failures', [])}\n"
            "Action: Fix regressions before marking complete"
        )
    print(f"[{task_id}] REGRESSION phase complete: No new failures")
    print(f"[{task_id}] TDD cycle complete")
```

## Helper Functions

### Ensure test exists for task

```python
def ensure_test_exists(task: dict) -> str:
    """Find or create test file for task."""
    desc = task.get('description', '')
    import re
    match = re.search(r'(\w+\.py):(\d+)', desc)
    if match:
        source_file = match.group(1)
        module_name = source_file.replace('.py', '')
        test_file = f"tests/test_{module_name}.py"
        from pathlib import Path
        if Path(test_file).exists():
            return test_file

    refactor_test = "tests/test_refactor_safety.py"
    if Path(refactor_test).exists():
        return refactor_test

    print(f"No test found for task {task['id']}, invoking tdd-test-writer...")
    test_file = invoke_tdd_test_writer(task)
    return test_file
```

### Run pytest with verification

```python
def run_pytest(test_file: str, expect_failure: bool = False, expect_pass: bool = False):
    """Run pytest and verify expected outcome."""
    import subprocess
    result = subprocess.run(
        ["pytest", test_file, "-v", "--tb=short"],
        capture_output=True, text=True
    )
    output = result.stdout + result.stderr
    has_failures = "FAILED" in output
    all_passed = result.returncode == 0 and "passed" in output

    if expect_failure and not has_failures:
        return {'has_failures': False, 'all_passed': True, 'output': output}
    if expect_pass and not all_passed:
        return {'has_failures': True, 'all_passed': False, 'failure_output': output}
    return {'has_failures': has_failures, 'all_passed': all_passed, 'output': output}
```

### Run regression tests

```python
def run_regression_tests(task: dict) -> dict:
    """Run related tests as regression check."""
    import subprocess, re
    result = subprocess.run(
        ["pytest", "tests/", "-v", "--tb=short"],
        capture_output=True, text=True
    )
    output = result.stdout + result.stderr
    has_new_failures = result.returncode != 0
    new_failures = []
    if has_new_failures:
        new_failures = re.findall(r'FAILED\s+(\S+)', output)
    return {'has_new_failures': has_new_failures, 'new_failures': new_failures, 'output': output}
```

## Enhanced Batch Mode with TDD

```python
# BEFORE (no TDD):
for task in matching:
    update(task['id'], status="in_progress", assignee=SESSION_ID)
    skill_invoker(task)  # No TDD check
    update(task['id'], labels=["workflow:review"])

# AFTER (TDD enforced):
for task in matching:
    update(task['id'], status="in_progress", assignee=SESSION_ID)
    task_type = detect_task_type(task)
    if task_type == 'code_change':
        execute_task_with_tdd(task, skill_invoker)
    else:
        skill_invoker(task)
    update(task['id'], labels=["workflow:review"])
```

### Example Output with TDD

```
User: /team --filter "yt-fts" --use /refactor --all

Claude: Found 3 yt-fts tasks:

Working through tasks sequentially with TDD enforcement...

[1/3] TDD required: Refactor strategy functions
[1/3] RED phase complete: tests/test_state_detection.py FAILS
[1/3] Running /refactor...
[1/3] GREEN phase complete: tests/test_state_detection.py PASSES
[1/3] REGRESSION phase complete: No new failures
[1/3] Marking for review...
[1/3] Complete.

... (remaining tasks)

All yt-fts tasks complete. 3 tasks processed with TDD enforcement.
```
