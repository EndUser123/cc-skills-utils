---
name: id
description: Report authoritative Claude Code session identity — session_id, transcript_path, terminal_id. No heuristics, no guessing.
version: "1.0.0"
status: "stable"
category: utilities
triggers:
  - /id
aliases:
  - /id
allowed-tools: Bash, Read
---

# /id — Strict Identity Command

Report authoritative identity for the current Claude Code session in this terminal.

## Contract

This skill uses **hook-captured identity only**. It does not guess, scan files by mtime, or fall back to heuristics.

Authoritative sources:
- `WT_SESSION` env var → terminal identity (per-tab UUID)
- `P:/.claude/.artifacts/{terminal_id}/identity.json` → session_id, transcript_path, cwd (written by SessionStart hook)

## Execution

1. Read `WT_SESSION` from environment:

```bash
echo $WT_SESSION
```

2. Build terminal_id as `console_{WT_SESSION}` and read the identity cache:

```bash
cat "P:/.claude/.artifacts/console_${WT_SESSION}/identity.json"
```

3. Validate required fields are present and non-empty:
   - `terminal.id`
   - `claude.session_id`
   - `claude.transcript_path`

4. Verify transcript file exists:

```bash
ls -la "$(python -c "import json,sys; d=json.load(open(sys.argv[1])); print(d['claude']['transcript_path'])" "P:/.claude/.artifacts/console_${WT_SESSION}/identity.json")"
```

5. Report identity in this format:

```
## Session Identity

| Field | Value |
|-------|-------|
| Terminal | console_{WT_SESSION} |
| Session ID | {session_id} |
| Previous transcript | {transcript_path} |
| CWD | {cwd} |
| Captured | {captured_at} |
```

6. Show session history from the session registry (last 5 entries for this terminal):

```bash
python -c "
import json, sys
registry = Path('P:/.claude/.artifacts/session_registry.jsonl')
tid = f'console_{os.environ.get(\"WT_SESSION\",\"\")}'
if not registry.exists():
    sys.exit(0)
entries = []
for line in registry.read_text(encoding='utf-8').splitlines():
    try:
        e = json.loads(line)
        if e.get('terminal_id') == tid:
            entries.append(e)
    except json.JSONDecodeError:
        pass
for e in entries[-5:]:
    ts = e.get('ts','?')[:19].replace('T',' ')
    goal = e.get('goal','')[:60]
    pct = e.get('progress_percent', '?')
    print(f'  {ts}  {goal}  ({pct}%)')
"
```

If registry is empty or missing, omit the history section silently.

## Failure modes

If any step fails:
- `WT_SESSION` empty → report: "Not running inside Windows Terminal. Identity unavailable."
- Identity cache missing → report: "No identity cache for this terminal. SessionStart hook may not have fired."
- Required field empty → report: "Identity cache incomplete: missing {field}."
- Transcript file missing → report: "Transcript path in cache does not exist: {path}"

Do NOT fall back to scanning `.jsonl` files or guessing by modification time.

## Architecture

```
SessionStart hook fires
  → reads session_id, transcript_path, cwd from hook stdin JSON
  → reads WT_SESSION from env
  → writes P:/.claude/.artifacts/{terminal_id}/identity.json

/id skill fires
  → reads WT_SESSION from env
  → reads identity cache
  → validates and reports
```
