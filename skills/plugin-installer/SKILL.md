---
description: Manage development plugins — audit, validate, install, sync, add, remove, refresh, bump, status. Trigger when asked to "setup plugins", "install plugins", "audit plugins", "validate plugin manifests", "add plugin to marketplace", "remove plugin from marketplace", or "check plugin status".
enforcement: advisory
workflow_steps:
  - Route to appropriate plugin-installer sub-skill (/audit, /validate, /install, /sync, /add, /remove, /refresh, /bump, /status)
  - Sub-skills handle execution
  - Report results
---

# Claude Code Plugin Manager

Manage, audit, validate, install, and sync all development plugins.

## Marketplace Architecture

All plugins are junctioned — source at `P:\\\\\\packages/<name>/`, junction at `P:\\\\\\packages/.claude-marketplace/plugins/<name>`. Changes to source auto-pick up — no sync needed.

**Excluding packages:** Place a `.marketplace-exclude` file in a package directory to exclude it from marketplace junction requirements. The audit will skip it when reporting missing junctions.

## Full Setup (no action specified)

When invoked without an action, run the complete check-fix-verify workflow.

1. **Audit all source packages** — scans `P:\\\\\\packages/` for all directories with `.claude-plugin/plugin.json`, detects unregistered packages, and checks drift:
   ```bash
   python3 "P:\\\\\\packages/cc-skills-utils/scripts/plugin-audit-and-fix.py" --packages-root "P:\\\\\\packages" --auto-fix
   ```
   This scans ALL source packages (not just marketplace junctions), reports:
   - **Missing marketplace junctions** → suggests `/cc-skills-utils:plugin-installer add <name>`
   - **Source drift** → `robocopy /MIR` syncs cache from source
   - **Stale version dirs** → deleted from cache
   - **Cache-only files** → warned but preserved

2. **Sync marketplace index**:
   ```bash
   claude plugin marketplace update local
   ```

3. **Verify cache is clean**:
   ```bash
   python3 "P:\\\\\\packages/cc-skills-utils/scripts/plugin-audit-and-fix.py" --packages-root "P:\\\\\\packages" --drift
   ```

4. **Validate** all marketplace plugins:
   ```bash
   python3 "P:\\\\\\packages/cc-skills-utils/scripts/plugin-audit-and-fix.py" --validate --marketplace-root "P:\\\\\\packages/.claude-marketplace"
   ```

5. **Final sync + report**:
   ```bash
   claude plugin marketplace update local
   claude plugin list
   ```
   ⚠️ **Then type `/reload-plugins` manually**.

## Actions

### `/cc-skills-utils:plugin-installer audit [name]` — Audit plugin manifests

With no argument, audits all source packages:
```bash
python3 "P:\\\\\\packages/cc-skills-utils/scripts/plugin-audit-and-fix.py" --packages-root "P:\\\\\\packages" --auto-fix
```

With a plugin name, audits only that plugin:
```bash
python3 "P:\\\\\\packages/cc-skills-utils/scripts/plugin-audit-and-fix.py" --packages-root "P:\\\\\\packages" --auto-fix --plugins <name>
```

Then refresh:
```bash
claude plugin marketplace update local
```
⚠️ **Then type `/reload-plugins` manually**.

### `/cc-skills-utils:plugin-installer validate [name]` — Validate plugins

With no argument, validates all:
```bash
python3 "P:\\\\\\packages/cc-skills-utils/scripts/plugin-audit-and-fix.py" --validate --marketplace-root "P:\\\\\\packages/.claude-marketplace"
```

With a plugin name, validates only that plugin:
```bash
python3 "P:\\\\\\packages/cc-skills-utils/scripts/plugin-audit-and-fix.py" --validate --marketplace-root "P:\\\\\\packages/.claude-marketplace" --plugins <name>
```

### `/cc-skills-utils:plugin-installer install` — Install all marketplace plugins

```bash
claude plugin marketplace update local
ls P:\\\\\\packages/.claude-marketplace/plugins/
# For each plugin, check entry type before install:
# - Junction → source auto-pickup, safe to install
# - Real dir → warn: non-junction plugin, source changes won't auto-propagate
#   If source exists at P:\\\\\\packages/<name>/, suggest converting to junction instead
claude plugin install <name>@local
claude plugin marketplace update local
```
⚠️ **After each install, type `/reload-plugins` manually**, then:
```bash
claude plugin list
```

**Non-junction detection:** If a marketplace entry is a real directory AND the source exists at `P:\\\\\\packages/<name>/`, the plugin should be a junction instead. Flag it and suggest:
```bash
# Convert real-dir to junction:
rm -rf P:\\\\\\packages/.claude-marketplace/plugins/<name>
cmd /c mklink /J "P:\\\\\\\packages\\.claude-marketplace\\plugins\\<name>" "P:\\\\\\\packages\\<name>"
```

### `/cc-skills-utils:plugin-installer sync` — Sync cc-skills-utils source to marketplace

cc-skills-utils is a **junction** — source changes auto-pick up, no manual sync needed. If the junction is missing, recreate it:

```bash
cmd /c mklink /J "P:\\\\\\\packages\\.claude-marketplace\\plugins\\cc-skills-utils" "P:\\\\\\\packages\\cc-skills-utils"
```

### `/cc-skills-utils:plugin-installer add <name>` — Add a plugin to marketplace

**Check before creating a junction:**
1. Check if entry already exists: `ls -la P:\\\\\\packages/.claude-marketplace/plugins/<name>`
2. If it's a junction → plugin already in marketplace, skip creation
3. If it's a real directory → warn user, junction would conflict
4. If no entry exists → ask user before creating junction

Adds a plugin via junction. Assumes source at `P:\\\\\\packages/<name>/`:

```bash
# 1. Create junction
cmd /c mklink /J "P:\\\\\\\packages\\.claude-marketplace\\plugins\\<name>" "P:\\\\\\\packages\\<name>"

# 2. Register in BOTH marketplace.json index files (install fails without this)
python3 -c "
import json
from pathlib import Path

name = '<name>'
src = Path('P:\\\\\\packages') / name
manifest = json.loads((src / '.claude-plugin/plugin.json').read_text())
entry = {
    'name': manifest['name'],
    'version': manifest['version'],
    'description': manifest.get('description', ''),
    'source': f'./plugins/{name}',
    'keywords': manifest.get('keywords', [])
}

for mp_path in [
    Path('P:\\\\\\packages/.claude-marketplace/marketplace.json'),
    Path('P:\\\\\\packages/.claude-marketplace/.claude-plugin/marketplace.json'),
]:
    if not mp_path.exists():
        continue
    data = json.loads(mp_path.read_text())
    names = [p['name'] for p in data.get('plugins', [])]
    if manifest['name'] not in names:
        data['plugins'].append(entry)
        mp_path.write_text(json.dumps(data, indent=2) + '\n')
        print(f'Added to {mp_path}')
    else:
        print(f'Already in {mp_path}')
"

# 3. Sync and install
claude plugin marketplace update local
claude plugin install <name>@local
claude plugin marketplace update local
claude plugin list
```
⚠️ **After install, type `/reload-plugins` manually**.

### `/cc-skills-utils:plugin-installer remove <name>` — Remove a plugin from marketplace

Removes the junction from marketplace and uninstalls the plugin. Does NOT delete the source.

**Check first:** `ls -la P:\\\\\\packages/.claude-marketplace/plugins/<name>` to confirm it's a junction (not a real directory).

```bash
# 1. Remove junction
cmd /c rmdir "P:\\\\\\\packages\\.claude-marketplace\\plugins\\<name>"

# 2. Remove from BOTH marketplace.json index files
python3 -c "
import json
from pathlib import Path
name = '<name>'
for mp_path in [
    Path('P:\\\\\\packages/.claude-marketplace/marketplace.json'),
    Path('P:\\\\\\packages/.claude-marketplace/.claude-plugin/marketplace.json'),
]:
    if not mp_path.exists():
        continue
    data = json.loads(mp_path.read_text())
    before = len(data.get('plugins', []))
    data['plugins'] = [p for p in data.get('plugins', []) if p['name'] != name]
    if len(data['plugins']) < before:
        mp_path.write_text(json.dumps(data, indent=2) + '\n')
        print(f'Removed from {mp_path}')
    else:
        print(f'Not in {mp_path}')
"

# 3. Uninstall and sync
claude plugin uninstall <name>@local
claude plugin marketplace update local
claude plugin list
```
⚠️ **After uninstall, type `/reload-plugins` manually**.

### `/cc-skills-utils:plugin-installer status` — Check plugin status

```bash
claude plugin list
```

### `/cc-skills-utils:plugin-installer refresh [name]` — Nuke stale cache and reinstall

Fixes the common issue where source edits don't appear in the running session because the plugin loads from a version-keyed cache, not source. The official Claude Code docs recommend clearing the cache and reinstalling.

**With a plugin name** — targeted nuke (preferred):
```bash
# 1. Remove stale cache for this plugin only
rm -rf "C:/Users/brsth/.claude/plugins/cache/local/<name>"

# 2. Remove from installed_plugins.json
python3 -c "
import json
f = 'C:/Users/brsth/.claude/plugins/installed_plugins.json'
d = json.load(open(f))
d['plugins'].pop('<name>@local', None)
json.dump(d, open(f, 'w'), indent=2)
"

# 3. Sync marketplace + reinstall
claude plugin marketplace update local
claude plugin install <name>@local
claude plugin marketplace update local

# 4. Verify enabledPlugins registration (critical — install silently skips this for some plugins)
python3 -c "
import json
f = 'C:/Users/brsth/.claude/settings.json'
d = json.load(open(f))
key = '<name>@local'
if key not in d.get('enabledPlugins', {}):
    d.setdefault('enabledPlugins', {})[key] = True
    json.dump(d, open(f, 'w'), indent=2)
    print(f'FIXED: added {key} to enabledPlugins')
else:
    print(f'OK: {key} already in enabledPlugins')
"
```
⚠️ **After install, type `/reload-plugins` manually**.

**With no argument** — nuke all local plugin caches:
```bash
rm -rf "C:/Users/brsth/.claude/plugins/cache/local"
claude plugin marketplace update local
# Then reinstall each plugin:
ls P:\\\\\\packages/.claude-marketplace/plugins/
claude plugin install <name>@local
```
⚠️ **After each install, type `/reload-plugins` manually**.

**When to use** (vs `bump`):
- `bump` — source files changed, want a clean new version dir. Keeps old cache.
- `refresh` — cache is corrupted, stale, or mismatched. Nukes and reinstalls from marketplace.
- If `bump` + `/reload-plugins` doesn't pick up changes, use `refresh`.

### `/cc-skills-utils:plugin-installer bump <name>` — Bump plugin version

Bumps the patch version (e.g., `2.0.0` → `2.0.1`) in all three files that the plugin cache system reads:

```bash
python3 "P:\\\\\\packages/cc-skills-utils/scripts/plugin-audit-and-fix.py" --bump <name> --marketplace-root "P:\\\\\\packages/.claude-marketplace"
```

After bumping, run:
1. `/plugin marketplace update local`
2. `/reload-plugins`

**When to use**: After editing any plugin source files under `P:\\\\\\packages/<name>/` that should propagate to the running session. The plugin system loads from version-keyed cache, not source — without a version bump, changes are invisible.

## Troubleshooting

**If install succeeds but plugin doesn't load:**
`/plugin install` may silently fail to register the plugin in `enabledPlugins` in settings.json. Verify and fix:
```bash
python3 -c "
import json
f = 'C:/Users/brsth/.claude/settings.json'
d = json.load(open(f))
key = '<name>@local'
if key not in d.get('enabledPlugins', {}):
    d.setdefault('enabledPlugins', {})[key] = True
    json.dump(d, open(f, 'w'), indent=2)
    print(f'FIXED: added {key} to enabledPlugins')
else:
    print(f'OK: {key} already in enabledPlugins')
"
```
Then `/reload-plugins`. This is the most common cause of "plugin installed but not loading."

**If install fails:**
1. Run `claude plugin marketplace update local` then type `/reload-plugins`
2. Validate the specific plugin: `claude plugin validate <path>`
3. Re-run audit: `/cc-skills-utils:plugin-installer audit`

**To uninstall all marketplace plugins:**
```bash
# Discover what's installed:
claude plugin list
# Uninstall each:
claude plugin uninstall <name>@local
claude plugin marketplace update local
```
⚠️ **After uninstall, type `/reload-plugins` manually**.

**To add a new plugin to the marketplace:**
```bash
/cc-skills-utils:plugin-installer add <plugin-name>
```
