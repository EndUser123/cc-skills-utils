# gitingest — GitHub to NotebookLM Pipeline

**Ingest a GitHub repository into Google NotebookLM in one command.**

`gitingest` clones a GitHub repo, slices it into empirically-sized batches, and uploads to NotebookLM — preserving full file content for RAG-style chunking.

## Quick Start

```bash
/skill gitingest github.com/owner/repo
```

## Features

- **Automatic slicing** — Empirical batch sizing (not file count) keeps each slice under NotebookLM's ~500k-word limit
- **Three upload modes** — Reuse existing notebook, create new, or auto-detect
- **Full content preservation** — No pre-summarization; full file content survives NotebookLM's chunking
- **Clean cleanup** — Temp directories always removed, even on error

## Input Formats

| Input | Result |
|-------|--------|
| `/gitingest github.com/owner/repo` | Full repo, main branch |
| `/gitingest github.com/owner/repo/tree/v2.0` | Full repo, v2.0 branch |
| `/gitingest github.com/owner/repo/blob/feature/src/app.py` | Single file |
| `/gitingest owner/repo` | Full repo, main branch |
| `/gitingest owner/repo --branch feature` | Specific branch |
| `/gitingest owner/repo --new-notebook` | Force new notebook |
| `/gitingest owner/repo --notebook-id <id>` | Upload to existing |

## 6-Step Pipeline

1. **Parse** — Extract owner, repo, branch from GitHub URL
2. **Clone** — `git clone --depth=1` to temp directory
3. **Build file lists** — Generate `file-list.txt`, `agent-config-files.txt`, `doc-files.txt`
4. **Generate slices** — Split into ~50-file batches, inline full content
5. **Upload** — Add slices to NotebookLM via `nlm` CLI
6. **Cleanup** — Remove temp directory

## Output

```
## gitingest Complete

Notebook: owner/repo  (ID: abc123...)
Slices uploaded:
  - owner_repo_part-001.md  (N files across ~K slices)
  - owner_repo_part-002.md
  ...
Temp dir: /tmp/gitingest_owner_repo/  (cleaned up)
```

## Error Handling

| Situation | Action |
|-----------|--------|
| `nlm auth status` fails | Run `nlm login` first |
| Git clone fails | "Invalid GitHub URL or repo not found" |
| No slices generated | Report which file list was empty |
| Notebook create fails | Retry once, then report |
| Source add fails | Retry with `--wait`, then report |
| Any error | Report, then cleanup temp dir |

## Files

```
gitingest/
├── SKILL.md                  # Skill definition + 6-step pipeline
├── README.md                 # This file
├── LICENSE                   # MIT License
└── references/
    ├── github-urls.md       # URL parsing + clone commands
    └── notebooklm-upload.md # nlm CLI upload reference
```

## Prerequisites

- [ ] `nlm` CLI installed (v0.3.3+) — [installation guide](https://github.com/jacob-bd/notebooklm-mcp-cli)
- [ ] `gh` CLI authenticated (for `gh repo clone`)
- [ ] Google NotebookLM account

## See Also

- `/skill notebooklm` — NotebookLM research assistant
- `/skill notebooklm-expert` — NotebookLM CLI expert guide
