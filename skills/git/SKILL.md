---
name: git
version: "2.2.0"
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
  - '^python\s+P:/.claude/skills/git/sync\.py(?:\s|$)'
required_first_command_hint: Run sync.py first to discover repos and establish the sync plan.
description: Git sync with multi-repo discovery, dependency-first commit ordering, auto-push for all repos, worktree management, and smart conflict resolution.
triggers:
  - /git
args:
  - --verbose: Show full output during health check and sync
  - -v: Shorthand for --verbose
  - --health: Check configuration only (don't sync)
  - --fix: Auto-fix issues before syncing
  - --repos: Filter repos by type (all, packages, .claude, mcp, non-main)
  - --select: Select repos to push by index (e.g., "1,3" or "all")
  - --worktree: Worktree management mode (list, add, remove, prune)
  - --no-resolve: Skip automatic conflict resolution (manual mode)
execution:
  directive: "If --worktree: manage worktrees. Otherwise: discover all git repos, auto-sync all repos (commit first, push after dependency ordering). Use --select for selective pushing."
  default_args: ""
  examples:
    - "/git"
    - "/git --verbose"
    - "/git --health"
    - "/git --repos packages"
    - "/git --select 1,3"
    - "/git --select all"
    - "/git --worktree"
    - "/git --worktree add feature-name"
    - "/git --worktree remove feature-name"
    - "/git --worktree prune"
    - "/git --no-resolve"
do_not:
  - summarize this skill
  - search for sync.py implementation
  - use alternative approaches
---

# Git: Multi-Repo Sync + Worktree Management

## Quick Usage

```powershell
# Sync all repos (auto-push all)
/git

# Health check - see all repos status
/git --health

# Verbose output
/git --verbose

# Filter to specific repo types
/git --repos packages        # Only package repos
/git --repos .claude         # Only .claude internal repos

# Push specific repos by index (use with /git --health to see indices)
/git --select 1,3            # Push repos 1 and 3
/git --select all            # Push all repos with unpushed commits

# Worktree management
/git --worktree                # List all worktrees
/git --worktree add name       # Create new worktree
/git --worktree remove name    # Remove worktree
/git --worktree prune          # Clean up stale worktrees
```

---

## ⚡ EXECUTE

**MANDATORY ACTION: Run sync.py for multi-repo sync + worktree management**

```bash
python P:/.claude/skills/git/sync.py [args]
```

---

## Prerequisites

**1. GitHub CLI (`gh`) - REQUIRED for GitHub repo creation**
- Check: `/c/Program Files/GitHub CLI/gh.exe auth status` — should show "Logged in to github.com"
- If not installed: https://cli.github.com/manual/installation
- If not authenticated: `gh auth login`
- Location on Windows: `C:\Program Files\GitHub CLI\gh.exe`
- Note: Stored tokens can expire — verify before heavy operations

**2. Git authentication**
- GitHub: https://docs.github.com/en/authentication
- GitLab: https://docs.gitlab.com/ee/user/profile/preferences.html#access-tokens

**3. Windows users** - Configure credential helper:
```bash
git config --global credential.helper manager-core
```

**4. Test manually first** - Run `git push` once to authenticate before relying on auto-push. This confirms credentials work and prevents silent authentication failures during automated sync.

**Note**: The skill will show actionable error messages if authentication fails, but first-time setup is easier when done manually.

---

## What It Does

### Multi-Repo Discovery
Discovers all `.git` directories under `P:/`:
- **Main repo** (`P:/.git`) - auto-sync, auto-push
- **Package repos** (`packages/*/.git`) - auto-sync, auto-push
- **MCP repos** (`packages/.mcp/*/.git`) - auto-sync, auto-push
- **Internal repos** (`.claude/hooks/`, `.claude/skills/*/`) - auto-sync, auto-push

### Auto-Sync Behavior (All Repos)
- Auto-commits uncommitted changes with scoped commit messages
- Syncs non-main repos before the parent repo so gitlink updates are captured cleanly
- Auto-pushes to remote after commits (dynamic remote/branch detection)
- Verifies there are no uncommitted changes left after sync
- On push failure: shows actionable error with remote URL and fix advice
- Use `--select` flag for selective pushing (e.g., `/git --select 1,3`)

### Health Check (`--health`)
Shows all repos with their status:

| Icon | Meaning |
|------|--------|
| `✓` | Up-to-date with remote |
| `~` | Needs attention (unpushed commits, behind, or no remote) |
| `✗` | Error (diverged history) |

**Status details:**
- `(X ahead)` - Local has X commits not pushed to remote
- `(behind X)` - Remote has X commits not pulled locally
- `(diverged)` - Local and remote have diverged (needs manual resolution)
- `(no remote)` - No remote configured
- `(ok)` - In sync with remote
- `(dirty)` - Working tree still has uncommitted changes after sync

### Worktree Mode (`--worktree`)
| Action | Command | Description |
|--------|---------|-------------|
| List | `/git --worktree` | Show all worktrees with current (*) |
| Add | `/git --worktree add <name>` | Create worktree at `P:/worktrees/<name>` |
| Remove | `/git --worktree remove <name>` | Remove worktree (keeps branch) |
| Prune | `/git --worktree prune` | Clean up stale worktrees |

### Push Error Handling
Push failures show actionable messages:
- Authentication errors: suggests manual `git push` to authenticate
- Rejected pushes: suggests pulling first
- Missing remote: shows which repos have no remote

### Missing Remote Detection
If push fails with "remote not found" or repo doesn't exist on GitHub:
1. Detect: Check if `gh api repos/<owner>/<repo>` returns 404
2. Create: `gh repo create <owner>/<repo> --public` (or `--private` as needed)
3. Push: Retry git push to the newly created remote

Example workflow for new repos:
```bash
# Create GitHub repo and push in one step (if gh is available)
gh repo create <owner>/<repo> --public --source=. --push
# Or create first, then set remote and push
gh repo create <owner>/<repo> --public
git remote set-url origin https://github.com/<owner>/<repo>.git
git push -u origin main
```

---

**Version:** 2.2
**Updated:** April 13, 2026
**Status:** Production ready - dependency-first multi-repo sync + auto-push all repos
