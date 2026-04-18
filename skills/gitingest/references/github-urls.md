# gitingest Reference: GitHub URL Patterns

## Supported URL Formats

| Input | owner | repo | branch | path |
|-------|-------|------|--------|------|
| `github.com/owner/repo` | owner | repo | main | — (full repo) |
| `github.com/owner/repo/tree/branch` | owner | repo | branch | — |
| `github.com/owner/repo/blob/branch/path/to/file` | owner | repo | branch | path/to/file |
| `github.com/owner/repo/blob/branch/path/to/dir/` | owner | repo | branch | path/to/dir/ |
| `owner/repo` | owner | repo | main | — |
| `owner/repo:branch` | owner | repo | branch | — |
| `owner/repo:branch/path` | owner | repo | branch | path |

## Regex Pattern

```bash
# Extract components from GitHub URL
# Supports: github.com/owner/repo, github.com/owner/repo/tree/branch, github.com/owner/repo/blob/branch/path
GITHUB_REGEX='github\.com/([^/]+)/([^/]+)(?:/(?:tree|blob)/([^/]+)(?:/(.+))?)?'

# Extract from shorthand (owner/repo)
SHORTHAND_REGEX='^([^/]+)/([^:]+)(?::(.+))?$'
```

## Clone Strategy

### Full repo (no path)
```bash
git clone --depth=1 --filter=blob:none "https://github.com/owner/repo" "/tmp/gitingest_owner_repo"
cd "/tmp/gitingest_owner_repo"
git checkout branch
```

### With path (sparse checkout)
```bash
git clone --depth=1 --filter=blob:none --no-checkout "https://github.com/owner/repo" "/tmp/gitingest_owner_repo"
cd "/tmp/gitingest_owner_repo"
git sparse-checkout init --cone
git sparse-checkout set path/to/dir
git checkout branch
```

## Temp Directory Naming

```bash
sanitized_owner=$(echo "$owner" | tr '/' '_')
sanitized_repo=$(echo "$repo" | tr '/' '_')
TEMP_DIR="/tmp/gitingest_${sanitized_owner}_${sanitized_repo}"
```

Always clean up with `rm -rf "/tmp/gitingest_${sanitized_owner}_${sanitized_repo}"` even on error.
