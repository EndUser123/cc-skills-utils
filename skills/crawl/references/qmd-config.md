# QMD Configuration Reference

## Config File Location

`~/.config/qmd/index.yml` (Windows: `C:\Users\<user>\.config\qmd\index.yml`)

## Config Format

```yaml
collections:
  wiki:
    path: P:/.data/wiki
    pattern: '**/*.md'
  docs:
    path: P:/.data/docs
    pattern: '**/*.md'
```

## Vault Root Resolution

The script reads the `wiki` collection path and derives:
- **Vault root**: The path itself (e.g., `P:/.data/wiki`)
- **Log file**: `{vault_root}/log.md`
- **Sources dir**: `{vault_root}/sources/{domain}/`

## CLI Commands

```bash
# Update index after file changes
qmd update wiki

# Search with JSON output
qmd search "query" --collection wiki --format json --limit 10

# List all files in collection
qmd ls wiki

# Check status
qmd status
```

## Index Files

QMD creates `.qmd/index` for FTS5 full-text search. The crawler updates this automatically via `qmd update`.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Collection not found | Add to `~/.config/qmd/index.yml` |
| Empty search results | Run `qmd update <collection>` |
| Wrong vault path | Verify path in config matches actual location |
