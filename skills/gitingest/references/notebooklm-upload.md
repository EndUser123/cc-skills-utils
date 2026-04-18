# gitingest Reference: NotebookLM Upload

## Source Limits (per notebook)

| Plan | Sources | Words/source | Notebooks | File size |
|------|---------|-------------|-----------|-----------|
| **Free** | 50 | 500,000 | 100 | 200 MB |
| **Plus** (Google One AI Premium $19.99/mo) | 300 | 500,000 | 500 | 200 MB |
| **Ultra** (Google AI Ultra $249.99/mo) | 600+ | 500,000 | 500+ | 200 MB |

> **Source = one uploaded slice file.** Each `nlm source add` call creates one source.
> The 50-source Free limit is the default. If you have Plus/Ultra, you have 300-600 headroom.

**To check your plan:**
```bash
nlm login   # authenticate first
nlm notebook list  # shows your notebooks and source counts
```

## Prerequisite: Auth check

```bash
nlm login
```

This opens Chrome for authentication. Sessions last ~20 min; re-login if operations fail.

## Create notebook

```bash
nlm notebook create "owner/repo"
```

Output: `ID: abc123...` — capture this for subsequent commands.

## Upload slices

```bash
# Upload each slice file (use --wait so source is ready before next add)
nlm source add "<notebook-id>" --file "/path/to/slice.md" --wait
```

Alternative using notebook name (if set as alias):

```bash
nlm source add "owner/repo" --file "/path/to/slice.md" --wait
```

## List sources

```bash
nlm source list "<notebook-id>"
```

## Common errors

| Error | Fix |
|-------|-----|
| `Not authenticated` | `nlm login` |
| `Source not ready` | Retry with `--wait` |
| `File not found` | Check path; temp dir may have been cleaned up |

## Cleanup

Always clean up the temp clone dir:
```bash
rm -rf /tmp/gitingest_OWNER_REPO
```

This must run even if upload fails — use a `finally`-equivalent or manual cleanup after reporting the error.
