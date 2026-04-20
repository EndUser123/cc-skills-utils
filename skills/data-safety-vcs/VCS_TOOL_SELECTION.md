VCS Tool Selection Rules (NON-NEGOTIABLE)

## Decision Matrix

| Location | Operation | Tool | Reason |
|----------|-----------|------|--------|
| P:\ root | ANY | git | Sapling scans Windows system folders, permission errors |
| P:\ root | status/add/commit | git | Sapling aborts on .BIN, System Volume Information |
| Any location | push/pull/fetch | git | Remote operations use git |
| Any location | rebase/merge | git | Complex operations safer with git |

## MANDATORY CHECKLIST
1. Check current directory: pwd
2. If at P:\ root -> use git
4. When unsure -> use git (always works)

## FORBIDDEN
- Using sl from P:\ root (permission errors)
- Using sl push (use git push instead)
- Attempting sapling operations without checking directory context