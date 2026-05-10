---
name: recover
description: Recover deleted, overwritten, or missing files using git, file-history, transcripts, and checkpoints. Use when file is missing, accidentally deleted, overwritten by mistake, or user says "recover X" or "file was deleted" or "restore X".
trigger: "/recover"
version: 1.0.0
created: 2026-04-24
author: Bruce Thomson
enforcement: advisory
workflow_steps:
  - name: identify_file
    description: Determine target file path and name
  - name: check_git
    description: Try git restore / git checkout from prior commits
  - name: check_file_history
    description: Search ~/.claude/file-history/ for recovery candidates
  - name: check_transcripts
    description: Parse JSONL transcripts for Write/Edit tool usage of target file
  - name: present_options
    description: Show recovery candidates with sources and timestamps
  - name: restore
    description: Execute chosen recovery method
---

# /recover — File Recovery Skill

Recover deleted, overwritten, or missing files using multiple fallback sources: **git**, **file-history**, **transcript parsing**, and **checkpoints**.

## When to Use

- User says "recover X", "file was deleted", "restore X", "missing file"
- File path reported missing but should exist
- Accidental overwrite — file content changed unexpectedly
- Session transcript analysis for past file content

## Recovery Sources (Priority Order)

### 1. Git (fastest, most reliable)
```
git -C "P:/" log --all --full-history -- <file_path>  # Find commits touching file
git -C "P:/" show <commit>:<file_path>  # Preview content at commit
git -C "P:/" restore --source=<commit> <file_path>  # Restore
```
**When**: File was ever committed to git. Works for deleted AND modified files.

### 2. Claude File History (for untracked files)
Search `C:/Users/brsth/.claude/file-history/` — Claude maintains file revision history:
```
# Find file by hash/path pattern
ls "C:/Users/brsth/.claude/file-history/"  # List all tracked file histories

# File history structure:
# file-history/{uuid}/{version_hash}@v{version}
# e.g., file-history/4640cb47/020b57d9ba84affb@v1

# Read most recent version
Read("C:/Users/brsth/.claude/file-history/{uuid}/{hash}@v{max}")
```

### 3. Transcript Parsing (for file content from Write/Edit operations)
Parse session transcripts from `~/.claude/projects/`:
```
# Transcript location pattern:
# C:/Users/brsth/.claude/projects/P--/{session_id}.jsonl

# Look for Write/Edit tool calls with matching file_path
# Tool input: {"file_path": "X", "content": "..."}
```
**When**: File content was written by Claude in a prior session.

### 4. Checkpoints (built-in Claude rewind)
Use `/rewind` command — but note: **checkpoints only capture Write/Edit operations, NOT Bash commands**.

## Recovery Workflow

### Phase 1: Identify Target

```bash
# Get file path from user or last context
# Normalize path for cross-platform compatibility
```

### Phase 2: Try Git First (always)

```bash
# Step A: Check if file exists in git history
git -C "P:/" log --all --oneline -- <file_path>

# Step B: If found, show recent commits
git -C "P:/" log --all --oneline -10 -- <file_path>

# Step C: Get content from HEAD~N
git -C "P:/" show HEAD~1:<relative_path>
```

### Phase 3: Check File History

```bash
# Search file-history by filename pattern
find "C:/Users/brsth/.claude/file-history/" -name "*<filename>*" 2>/dev/null

# List all history for specific file
ls -la "C:/Users/brsth/.claude/file-history/{uuid}/" | grep <filename>
```

### Phase 4: Parse Transcripts

```bash
# Get recent session transcripts
ls -lt "C:/Users/brsth/.claude/projects/P--/"*.jsonl | head -5

# Search for file_path in transcripts
python - <<'PY'
import json
import sys
path = "TARGET_FILE_PATH"
transcripts = [
    r"C:\Users\brsth\.claude\projects\P--\RECENT_SESSION.jsonl",
]
for t in transcripts:
    try:
        with open(t, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                try:
                    e = json.loads(line.strip())
                    msg = e.get('message', {})
                    content = msg.get('content', '')
                    if isinstance(content, list):
                        content = ' '.join(c.get('text','') for c in content if isinstance(c,dict))
                    if path.lower() in content.lower() and 'Write' in str(e):
                        print(f"Found in {t}: {str(e)[:500]}")
                except:
                    pass
    except Exception as ex:
        pass
PY
```

### Phase 5: Present Options

```
RECOVERY OPTIONS for {filename}:

1. Git restore from {commit} ({date})
   Source: git log commit {hash}
   Preview: {first 3 lines of file}

2. File history version {v3} ({date})
   Source: ~/.claude/file-history/{uuid}/{hash}@v3
   Age: {days_ago} days

3. Transcript from session {id} ({date})
   Source: Write operation in session transcript
   Content length: {N} chars

4. Transcript from session {id2} ({date})
   Source: Edit operation in session transcript
   Content length: {N} chars

Choose option [1-4] or skip:
```

### Phase 6: Execute Recovery

```bash
# Based on user choice:
# Option 1 (git):
git -C "P:/" restore --source=<commit> <file_path>

# Option 2 (file-history):
cp "C:/Users/brsth/.claude/file-history/{uuid}/{hash}@v{max}" "<target_path>"

# Option 3-4 (transcript):
# Extract content from JSON, write to target path
```

## Recovery Sources Summary

| Source | What it recovers | Latency | Reliability |
|--------|-----------------|---------|------------|
| Git | Committed files (deleted or modified) | <1s | HIGH |
| File History | Untracked files with revisions | <2s | MEDIUM |
| Transcript | Content from Write/Edit operations | 5-30s | MEDIUM |
| Checkpoints | Write/Edit content (built-in `/rewind`) | interactive | HIGH |

## Key Insights from Research

- **Git is primary** — always try first, it's fast and reliable
- **Bash deletions are NOT recoverable** via checkpoints — only Write/Edit operations are captured
- **File-history is underused** — `~/.claude/file-history/` contains versioned copies most users don't know about
- **Transcripts are verbose** — parse with Python, don't grep raw JSONL
- **Pre-deletion hooks could prevent loss** — future hook could auto-git-add before destructive operations

## Tool Backends

- **search-research** — can search chat history for file mentions
- **git** — primary recovery source
- **Bash** — Python scripts for transcript parsing
- **file-history** — direct file system access

## Automation Opportunities (Future)

1. **Pre-deletion git stage hook** — auto-stage files before `rm`, `mv` operations
2. **Recovery suggestions on error** — when file missing error occurs, auto-suggest `/recover`
3. **Checkpoint+git hybrid** — commit before `/rewind` to preserve context
4. **Transcript indexing** — build searchable index of all Write/Edit operations across sessions