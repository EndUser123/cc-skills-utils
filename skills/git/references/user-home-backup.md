# User-Home Backup (--backup)

**Purpose**: Backup Claude Code user home directory (`C:/Users/brsth/.claude/`) to git for safekeeping.

## Why This Matters

Your Claude Code user home contains important development files:
- **skills/** - Custom Claude Code skills you've created
- **hooks/** - Shared hook infrastructure
- **memory/** - Learning data, CKS patterns, bugfixes
- **settings.json** - Claude Code configuration

Losing this directory means losing all your customizations and learning history.

## How It Works

```bash
# From user home directory, backup to git
cd C:/Users/brsth/.claude

# Add changes and commit with timestamp
git add -A
git commit -m "Auto-backup: $(date +'%Y-%m-%d %H:%M:%S')"

# Push to GitHub backup repository
git push
```

## What Gets Backed Up

**Included (version controlled):**
- `.gitignore` - Excludes cache/temporary/session data
- `settings.json` - Claude Code settings
- `skills/` - All custom skills
- `hooks/` - Hook infrastructure
- `memory/` - User learning data, CKS patterns, bugfixes

**Excluded (by .gitignore):**
- Cache files (`cache/`, `enhanced_cache/`, `__pycache__/`)
- Session state (`session_data/`, `checkpoints/`, `file-history/`)
- Large databases (`*.db`, `events.db`, `*.jsonl`, `history_faiss_index.bin`)
- Sensitive credentials (`.credentials.json`)
- Plugin cache (`plugins/cache/`)

## Automated Backup Setup

**Option 1: Scheduled Task (Windows)**

Create a scheduled task to run daily:

```powershell
# File: C:\Users\brsth\.claude\backup.bat
cd C:\Users\brsth\.claude
git add -A
git commit -m "Auto-backup: %date:~4% %time:~0%
git push
```

**Option 2: Git Alias (Quick manual backup)**

```bash
# Add alias to git config
git config --global alias.backup '!cd C:/Users/brsth/.claude && git add -A && git commit -m "Auto-backup: $(date +''%Y-%m-%d %H:%M:%S'') && git push'

# Usage (from any directory):
git backup
```

## Initial Setup (One-time)

```bash
# 1. Initialize git in user home (if not already done)
cd C:/Users/brsth/.claude
git init

# 2. Create .gitignore (exclude cache/session data)
# See: https://github.com/EndUser123/claude-user-home/blob/main/.gitignore

# 3. Initial commit
git add .gitignore settings.json skills/ hooks/ memory/
git commit -m "Initial commit: Claude Code user home backup"

# 4. Create GitHub repository
gh repo create claude-user-home --private --source=. --push

# 5. Set up automatic backup (choose Option 1 or 2 above)
```

## Recovery

If you lose your user home directory:

```bash
# Clone backup repository
git clone git@github.com:EndUser123/claude-user-home.git C:/Users/brsth/.claude

# Restore to Claude Code
# (All skills, hooks, memory, and settings will be restored)
```

**Repository**: https://github.com/EndUser123/claude-user-home
