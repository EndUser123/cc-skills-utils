---
name: tilldone
version: 1.0.0
status: "stable"
description: Run a command on each package in a target directory until phase states stop changing (till-done) or for a fixed count. Works with any slash command or CLI tool.
category: batch
enforcement: advisory
triggers:
  - /tilldone
aliases:
  - /tilldone
workflow_steps:
  - discover_targets
  - parse_phase_states
  - run_command_per_package
  - check_convergence
  - report_stability
  - repeat_until_done

suggest:
  - /gitready
---

# /tilldone — Batch Convergence Runner

## Purpose

Run a command on each package in a target directory with two modes:
- **Till-done**: Run until phase states in `references/changelog.md` stop changing (convergence)
- **Count**: Run exactly N passes per package

Stops on first stable package, reports, then continues to the next.

## Usage

```bash
/tilldone P:/packages --command "/gitready"                    # till-done
/tilldone P:/packages --command "/gitready" --count 3          # 3 passes
/tilldone P:/packages --command "/gitready" --dry-run          # preview targets
/tilldone P:/packages --command "/gitready" -- --publish --finalize  # pass flags
```

## Execution Steps

When `/tilldone` is invoked:

### Step 1: Discover targets
- Scan target directory for subdirs with a `.git/` folder
- Skip hidden dirs (starting with `.`)
- Output: list of package names

### Step 2: Loop over each package
For each package (in sorted order):

**If --count N was specified:**
- Run the command N times
- No convergence check

**If till-done (default):**
1. Read `references/changelog.md` → parse phase states (format: `- PHASE X.Y: Name -- STATUS`)
2. Run the command once
3. Re-read `references/changelog.md` → parse phase states again
4. If states are identical → **stable**, move to next package
5. If states changed → repeat (up to 20 iterations)
6. If not stable after 20 → mark unstable, move to next

### Step 3: Run the command
The command is run via `Skill` tool invocation — I execute it directly, not via subprocess.

For `/gitready`, use the Skill tool. For other slash commands, use Skill tool.

### Step 4: Report
After each package:
```
pkg-name: stable (N iters) | unstable (20 iters) | error (reason)
```

Final summary:
```
Total: X stable, Y errors, Z unstable
```

## Convergence Detection

Phase state format in `references/changelog.md`:
```
- PHASE 1: Diagnose and Prep -- COMPLETED
- PHASE 6: GitHub Publication -- SKIPPED
```

Parse all `- PHASE ... -- STATUS` lines. Compare dict of `{phase_name: status}` before and after command run. Identical = stable.

## Exit Codes
- `0` — all packages stable
- `1` — one or more packages did not converge

## Examples

```bash
# Polish all packages with gitready until phases settle
/tilldone P:/packages --command "/gitready" -- --publish --finalize

# Run exactly 3 passes on each package
/tilldone P:/packages --command "/gitready" --count 3

# Preview what would run
/tilldone P:/packages --command "/gitready" --dry-run

# Run refactor on all packages
/tilldone P:/worktrees --command "/refactor" --count 1
```