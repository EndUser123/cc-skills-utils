---
name: git
version: "3.0.0"
status: "stable"
category: vcs
enforcement: advisory
workflow_steps:
  - discover_repos
  - commit_changes
  - push_to_remote
allowed_first_tools:
  - Bash
required_first_command_patterns:
  - '^python\s+P:/packages/.claude-marketplace/plugins/cc-skills-utils/skills/git/sync\.py(?:\s|$)'
description: Unified Git & Fleet Management — multi-repo sync, batch skill application, and safety standards.
triggers:
  - /git
  - /gitbatch
  - /data-safety-vcs
---

# /git - Unified Fleet & Git Management

Single entry point for multi-repo synchronization, batch skill execution, and VCS safety enforcement.

## ⚡ EXECUTION DIRECTIVE

**When /git is invoked (no args or sync), IMMEDIATELY execute:**

```bash
python P:/packages/.claude-marketplace/plugins/cc-skills-utils/skills/git/sync.py [args]
```

---

## Subcommands

| Command | Purpose |
|---------|---------|
| `/git` (sync) | Multi-repo sync: discover, commit, and auto-push all repos. |
| `/git batch` | Execute skills in parallel across all packages using subagents. |
| `/git safety` | View VCS safety standards and "Anti-Bleed" protocols. |
| `/git worktree`| Manage git worktrees (list, add, remove, prune). |

---

## 1. Multi-Repo Sync (`/git`)

Discovers and synchronizes all `.git` directories under `P:/` (Main, Packages, MCP, Internal).

**Flags:**
- `--health`: Check status only (don't sync).
- `--repos [packages|.claude]`: Filter by repo type.
- `--select [ids|all]`: Selective pushing.
- `--no-resolve`: Manual conflict resolution.

---

## 2. Batch Execution (`/git batch`)

Execute a skill (e.g., `/p`, `/verify`) across multiple packages using **subagents with result envelopes**.

**Usage:**
```bash
/git batch /p                 # Run /p on all packages
/git batch /verify debugRCA   # Run /verify on specific package
/git batch --dry-run /p       # Preview execution plan
```

**Token Savings:** Orchestrator receives only a small JSON envelope per package (~100 tokens) instead of full skill output.

---

## 3. Data Safety & "Anti-Bleed" (`/git safety`)

Strict protocols to prevent data loss and session bleed.

**Core Rules:**
- **Explicit Paths ONLY**: Never use `git add .` or wildcards.
- **Commit Early**: Commit after each discrete unit of work.
- **Push Immediately**: Prevent local pileup.
- **Safe Checkout**: Destructive commands (checkout, reset) are blocked if staged changes exist.

---

## 4. Worktree Management (`/git worktree`)

| Action | Command |
|--------|---------|
| List | `/git worktree` |
| Add | `/git worktree add <name>` |
| Remove | `/git worktree remove <name>` |

---

## Prerequisites

- **GitHub CLI (`gh`)**: Required for repo creation and auth status.
- **Credential Helper**: `git config --global credential.helper manager-core`.
