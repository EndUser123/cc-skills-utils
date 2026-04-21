# gitingest Reference: NotebookLM Upload

## CLI: nlm (notebooklm-mcp-cli)

**Package:** `notebooklm-mcp-cli` from [jacob-bd/notebooklm-mcp-cli](https://github.com/jacob-bd/notebooklm-mcp-cli)

**Install:** `uv tool install notebooklm-mcp-cli`

**Invocation:** The runner auto-detects bare `nlm` (on PATH) or `uv tool run --from notebooklm-mcp-cli nlm`.

## Source Limits (per notebook)

| Plan | Sources | Words/source | Notebooks | File size |
|------|---------|-------------|-----------|-----------|
| **Free** | 50 | 500,000 | 100 | 200 MB |
| **Plus** (Google One AI Premium $19.99/mo) | 300 | 500,000 | 500 | 200 MB |
| **Ultra** (Google AI Ultra $249.99/mo) | 600+ | 500,000 | 500+ | 200 MB |

> **Source = one uploaded slice file.** Each `nlm source add` call creates one source.

**To check auth and list notebooks:**
```bash
nlm login                          # authenticate (opens browser)
nlm notebook list                  # shows your notebooks and source counts
```

If `nlm` is not on PATH (uv tool install):
```bash
uv tool run --from notebooklm-mcp-cli nlm login
uv tool run --from notebooklm-mcp-cli nlm notebook list
```

## Create notebook

```bash
nlm notebook create "owner/repo"
```

## Upload slices

```bash
nlm source add "<notebook-id>" --file "/path/to/slice.md" --wait
```

## List sources

```bash
nlm source list "<notebook-id>"
```

## Delete source (for dedup)

```bash
nlm source delete "<source-id>"
```

## Common errors

| Error | Fix |
|-------|-----|
| `nlm: command not found` | Use `uv tool run --from notebooklm-mcp-cli nlm` or add `~/.local/bin` to PATH |
| `Not authenticated` | `nlm login` |
| `Source not ready` | Retry with `--wait` |
| `File not found` | Check path; temp dir may have been cleaned up |

## Cleanup

The runner handles clone dir cleanup automatically (even on error).
