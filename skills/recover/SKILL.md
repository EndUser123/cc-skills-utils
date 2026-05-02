---
name: recover
description: Recover deleted, overwritten, or missing files using git, file-history, transcripts, and checkpoints. Use when file is missing, accidentally deleted, overwritten by mistake, or user says "recover X" or "file was deleted" or "restore X".
trigger: "/recover"
version: 2.0.0
created: 2026-04-24
author: Bruce Thomson
enforcement: advisory
workflow_steps:
  - name: identify_target
    description: Determine target file/directory path and name
  - name: check_git
    description: Try git restore / git checkout from prior commits
  - name: check_junction
    description: For deleted dirs, check if it was a junction to content that still exists
  - name: check_file_history
    description: Search ~/.claude/file-history/ for recovery candidates
  - name: search_all_transcripts
    description: Search ALL project dirs for Write/Edit/Bash/Read operations matching target
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
git -C "P:/" log --all --oneline -- <file_path>
git -C "P:/" log --all --full-history -- <file_path>
git -C "P:/" show <commit>:<file_path>
git -C "P:/" restore --source=<commit> <file_path>
git -C "P:/" reflog --date=iso -20
```
Always use `--all` — deleted files may exist on other branches. Check `git worktree list`.

### 2. Junction Detection (before declaring unrecoverable)
If `rm -rf` deleted a directory that was a junction, the target content is still intact.
```
# Check if similar content exists elsewhere
# Common junction targets in this repo:
#   P:/packages/<name>  →  P:/packages/cc-skills-<cluster>/subdir/
#   P:/packages/<name>  →  P:/packages/<cluster>/skills/<name>/

# Search for the directory name as a subdirectory of other packages
find P:/packages/ -type d -name "<deleted_name>" 2>/dev/null

# If found, recreate the junction:
cmd //c "mklink /J P:\\packages\\<name> P:\\packages\\<cluster>\\<subpath>"
```
**When**: Directory was deleted via `rm -rf` and may have been a junction/symlink. The target content survives even after the junction is destroyed.

### 3. Claude File History (for untracked files)
Search `C:/Users/brsth/.claude/file-history/`:
```
find "C:/Users/brsth/.claude/file-history/" -name "*<filename>*" 2>/dev/null
```

### 4. Transcript Parsing (for files written by Claude)

**CRITICAL**: Search ALL project directories, not just one. There are multiple project dirs:
```
ls "C:/Users/brsth/.claude/projects/"   # Lists all project dirs
```

Files are created via Write/Edit AND via Bash (mkdir, cp, python scripts). Search both.

**Fast path** — transcript index:
```bash
python P:/.data/recover_index/indexer.py --stats
python P:/.data/recover_index/indexer.py --lookup "TARGET" --limit 10
# If index stale (>24h), rebuild first:
python P:/.data/recover_index/indexer.py
```

**Deep search** — parse ALL transcripts across ALL project dirs:
```python
import json
from pathlib import Path

project_dirs = list(Path(r'C:/Users/brsth/.claude/projects').iterdir())
target = 'packages/TARGET_NAME'
target_win = 'packages\\TARGET_NAME'

for pdir in project_dirs:
    if not pdir.is_dir():
        continue
    for tf in pdir.glob('*.jsonl'):
        try:
            with open(tf, 'r', encoding='utf-8', errors='replace') as fh:
                for line in fh:
                    try:
                        entry = json.loads(line.strip())
                        msg = entry.get('message', {})
                        content = msg.get('content', [])
                        if isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get('type') == 'tool_use':
                                    name = block.get('name', '')
                                    inp = block.get('input', {})
                                    # Check Write/Edit
                                    if name in ('Write', 'write', 'Edit', 'edit'):
                                        fp = inp.get('file_path', '')
                                        if target in fp or target_win in fp:
                                            print(f"WRITE: {pdir.name}/{tf.name} | {fp} ({len(inp.get('content',''))} chars)")
                                    # Check Bash (mkdir, cp, python scripts creating files)
                                    elif name == 'Bash':
                                        cmd = inp.get('command', '')
                                        if target in cmd:
                                            print(f"BASH: {pdir.name}/{tf.name} | {cmd[:200]}")
                                    # Check Read (proves file existed)
                                    elif name == 'Read':
                                        fp = inp.get('file_path', '')
                                        if target in fp or target_win in fp:
                                            print(f"READ: {pdir.name}/{tf.name} | {fp}")
                    except:
                        pass
        except:
            pass
```

**Recovering content from transcripts**: Extract Write tool `content` field and write to target path. Use a Python script (not inline) to avoid Windows quoting issues with backslash paths.

### 5. Checkpoints (built-in Claude rewind)
Use `/rewind` — but note: **checkpoints only capture Write/Edit operations, NOT Bash commands**.

## Recovery Workflow

### Phase 1: Identify Target
Determine file/directory path from user or context. Normalize for cross-platform.

### Phase 2: Try Git First
```bash
git -C "P:/" log --all --oneline -- <file_path>
git -C "P:/" restore --source=<commit> <file_path>
```

### Phase 3: Check Junction (for deleted directories)
If git has no record, the directory may have been a junction:
```bash
# Search for the directory name as a subdirectory elsewhere
find P:/packages/ -type d -name "<deleted_name>" 2>/dev/null | head -10
# If found, recreate junction pointing to it
```
**Do NOT skip this step.** If a directory was never committed to git AND never written by Claude's Write tool, it was almost certainly a junction to content that still exists.

### Phase 4: Check File History
```bash
find "C:/Users/brsth/.claude/file-history/" -name "*<filename>*" 2>/dev/null
```

### Phase 5: Search ALL Transcripts (not just one project dir)
1. Check transcript index first
2. If no results, deep-search ALL `~/.claude/projects/*/` directories
3. Search for Write, Edit, Bash, AND Read operations
4. Read operations prove the file existed — follow up with the session that read it to find what created it

### Phase 6: Present Options

```
RECOVERY OPTIONS for {filename}:

1. Git restore from {commit} ({date})
2. Junction recreation → {target_path} (content intact)
3. File history version {v3} ({date})
4. Transcript from session {id} ({date}) — {N} chars
5. Transcript from session {id2} ({date}) — {N} chars

Choose option [1-5] or skip:
```

### Phase 7: Execute Recovery

```bash
# Git:
git -C "P:/" restore --source=<commit> <file_path>

# Junction:
cmd //c "mklink /J P:\\packages\\<name> P:\\packages\\<target>"

# File-history:
cp "C:/Users/brsth/.claude/file-history/{uuid}/{hash}@v{max}" "<target_path>"

# Transcript: extract Write tool content field, write to target
# Use a .py script file (not inline python) to avoid Windows quoting issues
```

## Recovery Sources Summary

| Source | What it recovers | Latency | Reliability |
|--------|-----------------|---------|------------|
| Git | Committed files | <1s | HIGH |
| Junction recreation | Directories that were junctions | <1s | HIGH |
| File History | Untracked files with revisions | <2s | MEDIUM |
| Transcript (all dirs) | Write/Edit/Bash tool output | 10-60s | MEDIUM |
| Transcript Index | Fast lookup across sessions | <1s | MEDIUM |
| `/rewind` | Checkpoint snapshots | interactive | HIGH |

## Key Lessons (from actual recoveries)

- **Junctions survive rm -rf**: The junction is destroyed but target content remains. Always check if deleted dirs were junctions.
- **Never declare "unrecoverable" without checking ALL project dirs**: There are 10+ project directories under `~/.claude/projects/`. Searching only one misses results.
- **Bash tool creates files too**: Not just Write/Edit. Files created by `mkdir`, `cp`, Python scripts via Bash are recorded in transcripts.
- **Read operations are breadcrumbs**: If you find a Read of the target file, that session (or nearby sessions) likely created it. Follow the trail.
- **Use script files, not inline Python**: Windows cmd quoting breaks inline Python with backslash paths. Write a temp .py file, run it, delete it.
- **Git auto-stage hook** (`PreToolUse_git_auto_stage.py`) stages files before deletion — git recovery works even for recently-created files.