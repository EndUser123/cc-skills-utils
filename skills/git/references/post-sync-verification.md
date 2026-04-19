# Post-Sync Verification (MANDATORY)

**After sync completes, verify changes propagated correctly:**

## Verification Commands

```bash
# 1. Check for uncommitted changes (should be empty)
git status --short

# 2. Verify worktree has no commits ahead of main
git log main..HEAD  # Should show "main..HEAD is empty"

# 3. Verify main has worktree commits
git log HEAD..main  # Should show "HEAD..main is empty"

# 4. Spot-check specific files changed in session
# From worktree: compare worktree (HEAD) to main
git diff main HEAD -- .claude/skills/team/SKILL.md
# Expected: No output (files identical)

# From main: compare main to worktree branch (replace <worktree-name>)
git diff main <worktree-branch> -- <file-path>

# 5. Show what was merged (for confirmation)
git log --oneline -3  # Recent commits should appear in both branches
```

## Verification Checklist

- [ ] No uncommitted changes
- [ ] No commits in worktree that aren't in main
- [ ] No commits in main that aren't in worktree
- [ ] Changed files are identical in both branches
- [ ] Recent commits appear in both branch histories

## Troubleshooting

**If verification fails:**
- Uncommitted changes exist -> Re-run `/git`
- Commits out of sync -> Re-run `/git` to catch up
- Files differ -> Check merge conflicts, resolve manually
