---
name: daemon
description: Semantic Daemon Management - control CHS/CKS search daemon
version: "1.0.0"
status: "stable"
category: system
triggers:
  - /daemon

suggest:
  - /chs
  - /cks
  - /search
  - /debug
---

# /daemon - Semantic Daemon Management

## Purpose

Control the unified semantic daemon that provides fast search for:
- **CHS**: Chat History Search (conversations, sessions)
- **CKS**: Constitutional Knowledge System (patterns, memories, knowledge)

## What is the Semantic Daemon?

Background Windows service that:
- Pre-loads embedding models for <1s semantic search
- Automatically indexes new chat history every 5 minutes
- Serves search requests via named pipe (`\\.\pipe\csf_nip_semantic`)
- Auto-starts on Claude session initialization (via SessionStart hook)

## Your Workflow

1. **Parse command** - Extract subcommand (status, reindex, restart, stop)
2. **Execute CLI** - Call `daemon_manage.py` with appropriate args
3. **Present results** - Show user-friendly output
4. **Suggest follow-up** - Related commands based on result

## Commands

### `/daemon status` - Show Daemon Health

Shows:
- Daemon running status
- Named pipe connectivity
- CHS database path and existence
- Last indexed message ID
- Number of CHS entries in CKS
- Current indexing progress
- Time since last re-index

**Example output:**
```
📊 Semantic Daemon Status
==================================================
✅ Daemon is RUNNING
Pipe: \\.\pipe\csf_nip_semantic

📚 CHS Index Status:
------------------------------
DB Exists: True
DB Path: P:\__csf\data\chat_history.db
Last Indexed ID: 520746
CHS Entries in CKS: 125,432
Indexing In Progress: False
Last Re-index: 2.3 minutes ago
```

### `/daemon reindex` - Trigger CHS Re-indexing

Forces the daemon to re-index chat history from the database.
Runs in background, doesn't block searches.

**When to use:**
- After importing old chat sessions
- When recent conversations aren't appearing in search
- After database migration or restore
- When `/chs` returns stale results

**Process:**
1. Connects to daemon via named pipe
2. Triggers `_ensure_chs_indexed()` method
3. Spawns background indexing thread
4. Returns immediately (non-blocking)

**Example:**
```
Connecting to semantic daemon...
Triggering CHS re-index...
✅ CHS re-index triggered successfully

Re-indexing runs in background. Check status with:
  /daemon status
```

### `/daemon restart` - Restart Daemon

Stops and restarts the semantic daemon. Useful for:
- Applying code changes to daemon
- Clearing stale state
- Recovering from crashes

**Process:**
1. Stops daemon process (via taskkill)
2. Removes PID file
3. Instructions to start new Claude session (auto-starts via hook)

**Example:**
```
Restarting semantic daemon...
Stopping daemon (PID 12345)...
✅ Daemon stopped

Starting daemon...
ℹ️  Daemon will auto-start on next Claude session
   Or start a new session to trigger SessionStart hook
```

### `/daemon stop` - Stop Daemon

Stops the semantic daemon gracefully. Use when:
- Debugging daemon issues
- Freeing resources
- Before daemon code updates

**Example:**
```
Stopping daemon (PID 12345)...
✅ Daemon stopped
```

## Execution Directive

**Execute the appropriate CLI command based on subcommand:**

```bash
# Status
cd "P:\__csf" && python -m src.commands.daemon_manage status

# Reindex
cd "P:\__csf" && python -m src.commands.daemon_manage reindex

# Restart
cd "P:\__csf" && python -m src.commands.daemon_manage restart

# Stop
cd "P:\__csf" && python -m src.commands.daemon_manage stop
```

## Integration Notes

- **Location**: `P:\__csf\src\daemons\unified_semantic_daemon.py`
- **PID File**: `P:\__csf\data\semantic_daemon.pid`
- **Log File**: `P:\__csf\data\semantic_daemon.log`
- **Auto-start**: Via `P:\.claude\hooks\SessionStart_semantic_daemon.py`

## Troubleshooting

**Daemon won't start:**
1. Check PID file doesn't exist: `del P:\__csf\data\semantic_daemon.pid`
2. Start new Claude session (triggers SessionStart hook)
3. Check log: `type P:\__csf\data\semantic_daemon.log`

**Search returns old data:**
1. Run `/daemon status` to check last re-index time
2. Run `/daemon reindex` to force update
3. Wait 30 seconds for background indexing
4. Check status again

**Pipe errors:**
- Verify pywin32 installed: `pip list | findstr pywin32`
- Check no stuck processes: `tasklist | findstr python`
- Restart daemon: `/daemon restart`
