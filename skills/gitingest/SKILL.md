---
name: gitingest
version: "1.0.1"
status: "stable"
category: integration
enforcement: advisory
description: Ingest GitHub repos into NotebookLM — clone, slice, and upload in one pipeline.
workflow_steps:
  - execute_gitingest_workflow
---

# gitingest

**Goal:** Ingest GitHub repos into NotebookLM — clone, slice, and upload in one pipeline.

**Prerequisites:** `nlm` CLI from [jacob-bd/notebooklm-mcp-cli](https://github.com/jacob-bd/notebooklm-mcp-cli) — install via `uv tool install notebooklm-mcp-cli`. The runner auto-detects bare `nlm` (on PATH) or `uv tool run` invocation.

---

## Usage

```bash
# 1. Copy the config template to .staging
cp references/repos-template.yaml P:/.staging/my-repos.yaml

# 2. Edit the config — add your repos and notebook ID
vim P:/.staging/my-repos.yaml

# 3. Dry run (verify what would happen)
python scripts/gitingest_runner.py --config P:/.staging/my-repos.yaml --dry-run

# 4. Run for real
python scripts/gitingest_runner.py --config P:/.staging/my-repos.yaml
```

---

## Config file (`references/repos-template.yaml`)

**Config files are templates in `references/` — actual configs live in `P:/.staging/` (not `/tmp/`), never in the skill itself.**

> **Note:** On this system, `/tmp` is blocked by `PreToolUse_directory_policy.py`. Use `P:/.staging/` instead.

```yaml
notebooklm_id: "your-notebook-id-from-url"
repos:
  - url: "https://github.com/owner/repo"
    branch: "main"   # optional, default: main
    path: ""         # optional: sparse checkout path
    skip: false      # optional: skip this repo
```

---

## Pipeline (6 steps, executed by `scripts/gitingest_runner.py`)

1. **Clone** — `git clone --depth=1 --filter=blob:none`, optionally sparse
2. **File lists** — `git ls-files` (repo), `.claude/` configs, `docs/` + top-level README
3. **Slice** — repo-index, agent-configs, docs; ≤150 lines/slice; entry points inlined
4. **Upload** — file source (`--file <slice> --wait`) + web source (`--url <repo_url>` for clickable GitHub link)
5. **Cleanup** — removes clone dir (always, even on error)
6. **Status** — saves `status.json` to staging dir after each repo

---

## Deduplication Lifecycle

NotebookLM has no native replace API. Sources are deduplicated by title:

1. **List** existing sources via `nlm source list`
2. **Detect** if source title already exists → capture its `source_id`
3. **Delete** old source via `nlm source delete <source_id>`
4. **Poll** until source_id disappears from list (up to 10 attempts × 1s interval)
5. **Upload** new source with same title

If poll confirmation fails after max attempts, the upload is skipped with a warning.

---

## Web Sources — Clickable GitHub Links

NotebookLM has two source types with different behaviors:

| `nlm source add` flag | NotebookLM type | Clickable? | Content |
|---|---|---|---|
| `--file <path>` | `generated_text` | No | Full file content (slice) |
| `--url <url>` | `web_page` | **Yes** | Link to original page |

**The runner automatically adds both for each repo:**
1. A **file source** with the full sliced repo content (for NotebookLM to index and answer questions from)
2. A **web source** linking to `https://github.com/owner/repo` (clickable in the NotebookLM UI)

The web source title is set to `GitHub - owner/repo` so it's easy to identify. This is what users click to go straight to GitHub.

### Adding extra web sources

You can also add additional web sources via config:

```yaml
notebooklm_id: "your-notebook-id-from-url"
repos:
  - url: "https://github.com/owner/repo"
sources:
  web:
    - url: "https://example.com/docs"
      label: "Example Docs"   # used as title in NotebookLM
```

All web sources use the same dedup lifecycle (delete → poll → re-add).

### Adding a clickable link manually

If you need to add a clickable link outside the pipeline:

```bash
nlm source add "<notebook-id>" --url "https://github.com/owner/repo" --title "GitHub - owner/repo"
```

This creates a `web_page` source that appears as a clickable link in NotebookLM's source list.

---

## CLI Detection

The runner auto-detects how to invoke `nlm`:

1. **Bare `nlm`** — if `nlm` is on PATH (`pip install` or `uv tool install` with `~/.local/bin` on PATH)
2. **`uv tool run --from notebooklm-mcp-cli nlm`** — fallback for uv-based installs where `nlm` isn't on PATH

Install: `uv tool install notebooklm-mcp-cli`

Auth check runs before any operations. If not authenticated, the runner prints the login command and aborts (unless `--dry-run`).

---

## Error Handling

- **Clone failure**: repo skipped, error logged to status.json
- **Upload failure**: source skipped, pipeline continues to next source
- **Delete failure**: warning printed, upload still attempted
- **Poll timeout**: warning printed, upload skipped (prevents race condition where upload fails because old source still exists)
- **API error on list**: pipeline proceeds without deduplication (safe to re-add, may create duplicate — user can clean up manually)

---

## Output

```
=== [1/17] owner/repo ===
--- clone ---
  $ git clone ...
--- file lists ---
  → 42 repo files, 3 agent configs, 2 docs
--- slices ---
  → slice: repo-index-part-1.md (8.2 KB)
  → slice: agent-configs-part-1.md (1.1 KB)
--- upload ---
  ✓ repo-index-part-1.md uploaded
  ✓ agent-configs-part-1.md uploaded
✓ owner/repo done

=== Summary ===
  ✓ 15 succeeded
  ✗ 2 failed:
    - owner/bad-repo: clone failed
```

---

## References

- `references/repos-template.yaml` — config template (copy to `/tmp/` before use)
- `references/github-urls.md` — URL parsing + clone commands
- `references/notebooklm-upload.md` — nlm CLI commands
- `scripts/gitingest_runner.py` — the pipeline engine
