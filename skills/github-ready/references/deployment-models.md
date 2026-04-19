# Local Development Setup & Deployment Models (Detailed Reference)

## Three Deployment Models for Claude Code

### 1. SKILLS (Dev Deployment)

**For:** Packages with `skill/SKILL.md` directory

**Setup:**
```powershell
# Windows (Junction - Recommended, no admin required)
New-Item -ItemType Junction -Path "P:\.claude\skills\{{package_name}}" -Target "P:\packages\{{package_name}}\skill"

# macOS/Linux (Symlink)
ln -s /path/to/packages/{{package_name}}/skill ~/.claude/skills/{{package_name}}
```

**Key points:**
- Junction the entire `skill/` directory
- Skills auto-discovered from `P:/.claude/skills/`
- Edit in your package, changes work immediately

### 2. HOOKS (Dev Deployment)

**For:** Packages with hook files (`.py` files in `core/hooks/`)

**Setup:**
```powershell
# Symlinks go in P:/.claude/hooks/ (NOT ~/.claude/plugins/)
cd P:/.claude/hooks

# Symlink individual hook files from your package
ln -sf P:/packages/{{package_name}}/core/hooks/HookName.py HookName.py
```

**Key points:**
- Symlink individual `.py` hook files only (NOT the entire directory)
- Symlinks go in `P:/.claude/hooks/` (NOT `~/.claude/plugins/`)
- Dev-only symlinks for working directly on source code
- Routers or settings.json register the symlinks as actual code

### 3. PLUGINS (End User Deployment)

**For:** Distribution to end users via marketplace or GitHub

**Setup:**
```bash
# End users install via /plugin command
/plugin P:/packages/{{package_name}}

# Or from marketplace
/plugin install {{package_name}}
```

**Key points:**
- Plugin copied to `~/.claude/plugins/cache/`
- Registered in `~/.claude/plugins/installed_plugins.json`
- **NOT for local development** - requires reinstall on every change
- Use for distributing finished packages to users

## Which Model Does Your Package Need?

| Package Type | Dev Setup | End User Setup |
|--------------|-----------|----------------|
| **Skill only** | Skill junction | N/A (skill dev = use) |
| **Hooks only** | Hook symlinks | `/plugin` command |
| **Skill + Hooks** | Both | `/plugin` command |
| **Plugin** | Plugin junction to `~/.claude/plugins/local/` | `/plugin` command |

## Common Mistakes

- Don't use `/plugin` command for local development (requires reinstall on every change)
- Don't symlink entire directories to `P:/claude/hooks/` (only symlink `.py` files)
- Don't confuse skills (`P:/.claude/skills/`) with plugins (`~/.claude/plugins/`)
- Don't look for hook symlinks in `~/.claude/plugins/` - they go in `P:/.claude/hooks/`
- Don't forget to update symlinks after brownfield conversion - check for `src/` paths

## Multiple Skills or Hooks

Some plugins have **multiple skills** or **multiple hook files**. You need **one junction per skill** and **one symlink per hook file**.

### Multiple Skills (One Junction Per Skill)

```
my-plugin/
├── skills/
│   ├── skill-a/SKILL.md  -> Junction 1
│   ├── skill-b/SKILL.md  -> Junction 2
│   └── skill-c/SKILL.md  -> Junction 3
```

```powershell
New-Item -ItemType Junction -Path "P:\.claude\skills\skill-a" -Target "P:\packages\my-plugin\skills\skill-a"
New-Item -ItemType Junction -Path "P:\.claude\skills\skill-b" -Target "P:\packages\my-plugin\skills\skill-b"
New-Item -ItemType Junction -Path "P:\.claude\skills\skill-c" -Target "P:\packages\my-plugin\skills\skill-c"
```

**macOS/Linux equivalent:**
```bash
ln -s /path/to/packages/my-plugin/skills/skill-a ~/.claude/skills/skill-a
ln -s /path/to/packages/my-plugin/skills/skill-b ~/.claude/skills/skill-b
ln -s /path/to/packages/my-plugin/skills/skill-c ~/.claude/skills/skill-c
```

### Multiple Hook Files (One Symlink Per File)

```
my-plugin/
└── core/
    └── hooks/
        ├── hook1.py  -> Symlink 1
        ├── hook2.py  -> Symlink 2
        └── hook3.py  -> Symlink 3
```

```powershell
cd P:/.claude/hooks
cmd /c "mklink hook1.py P:\packages\my-plugin\core\hooks\hook1.py"
cmd /c "mklink hook2.py P:\packages\my-plugin\core\hooks\hook2.py"
cmd /c "mklink hook3.py P:\packages\my-plugin\core\hooks\hook3.py"
```

### Both Skills AND Hooks

```powershell
# 1. Create junctions for skills (one per skill)
New-Item -ItemType Junction -Path "P:\.claude\skills\skill-a" -Target "P:\packages\my-plugin\skills\skill-a"
New-Item -ItemType Junction -Path "P:\.claude\skills\skill-b" -Target "P:\packages\my-plugin\skills\skill-b"

# 2. Create symlinks for hook files (one per file)
cd P:/.claude/hooks
cmd /c "mklink hook1.py P:\packages\my-plugin\core\hooks\hook1.py"
cmd /c "mklink hook2.py P:\packages\my-plugin\core\hooks\hook2.py"
```

### Summary Table

| Plugin has... | Link type | How many? | Where? |
|---------------|-----------|-----------|--------|
| 1 skill | Junction | 1 | `P:/.claude/skills/skill-name` |
| 3 skills | Junctions | 3 (one per skill) | `P:/.claude/skills/skill-a`, `skill-b`, `skill-c` |
| 1 hook file | Symlink | 1 | `P:/.claude/hooks/hook.py` |
| 5 hook files | Symlinks | 5 (one per file) | `P:/.claude/hooks/hook1.py` through `hook5.py` |
| 2 skills + 3 hooks | Both | 2 junctions + 3 symlinks | Skills -> `P:/.claude/skills/`, Hooks -> `P:/.claude/hooks/` |

## Real-World Example: github-ready package

The github-ready package has:
- 1 skill: `skills/github-ready/SKILL.md`
- 0 hooks (no hook files)

Setup:
```powershell
# Just one junction needed
New-Item -ItemType Junction -Path "P:\.claude\skills\package" -Target "P:\packages\github-ready\skills\github-ready"
```
