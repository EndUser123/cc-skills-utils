---
name: plugin-installer
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

All plugins live directly in `P:/packages/.claude-marketplace/plugins/<name>/`. This IS the source — no separate source directory, no junctions. After editing plugin files, bump the version and reload to propagate to the version-keyed cache.

**Excluding packages:** Place a `.marketplace-exclude` file in a package directory to exclude it from marketplace requirements. The audit will skip it.

## Full Setup (no action specified)

When invoked without an action, run the complete check-fix-verify workflow.

1. **Audit all marketplace plugins** — scans `P:/packages/.claude-marketplace/plugins/` for all directories with `.claude-plugin/plugin.json`, detects unregistered packages, and checks drift:
   ```bash
   python3 "P:/packages/.claude-marketplace/plugins/cc-skills-utils/scripts/plugin-audit-and-fix.py" --packages-root "P:/packages" --auto-fix --summarize
   ```
   The `--summarize` flag pipes results through `summarize_audit.py` automatically, emitting a per-plugin prioritized action list with copy-paste fix commands. Without `--summarize`, the audit outputs raw structured findings only.

## Sync Rules

Plugins live in the marketplace directory. Cache at `C:\Users\brsth\.claude\plugins\cache\local\<name>\<version>/` is an install mirror.

The audit script uses **quality-aware conflict resolution** when both sides have different content:

- **JSON files**: parsed for validity + schema structure (e.g., `hooks.json` must have `"hooks"` key — `{"hooks": {}}` beats `{}`)
- **Python files**: `ast.parse` validity — syntax errors lose
- **Text files**: encoding validity + non-trivial content
- **Both pass quality checks** → source wins (canonical location)
- **One fails quality** → the passing side wins regardless of location
- **Both fail** → flagged for manual review

- **File only in source** → copy to cache
- **File only in cache** → quality-checked before restoring to source (broken files left as stale)

2. **Sync marketplace index**:
   ```bash
   claude plugin marketplace update local
   ```

3. **Verify cache is clean**:
   ```bash
   python3 "P:/packages/.claude-marketplace/plugins/cc-skills-utils/scripts/plugin-audit-and-fix.py" --packages-root "P:/packages" --drift
   ```

   If drift detected, **auto-bump** each drifted plugin to propagate source changes to cache:
   ```bash
   python3 "P:/packages/.claude-marketplace/plugins/cc-skills-utils/scripts/plugin-audit-and-fix.py" --bump <name> --marketplace-root "P:/packages/.claude-marketplace"
   ```

   `--bump` runs marketplace update and drift verification automatically — no manual sync needed.

   Skip bump only for plugins with **conflicts** (flagged during step 1) — those need manual review first.

4. **Validate** all marketplace plugins:
   ```bash
   python3 "P:/packages/.claude-marketplace/plugins/cc-skills-utils/scripts/plugin-audit-and-fix.py" --validate --marketplace-root "P:/packages/.claude-marketplace"
   ```

5. **Final sync + report**:
   ```bash
   claude plugin marketplace update local
   claude plugin list
   ```
   ⚠️ **Then type `/reload-plugins` manually**.

## Actions

### `/cc-skills-utils:plugin-installer audit [name]` — Audit plugin manifests

With no argument, audits all marketplace plugins:
```bash
python3 "P:/packages/.claude-marketplace/plugins/cc-skills-utils/scripts/plugin-audit-and-fix.py" --packages-root "P:/packages" --auto-fix --summarize
```

With a plugin name, audits only that plugin:
```bash
python3 "P:/packages/.claude-marketplace/plugins/cc-skills-utils/scripts/plugin-audit-and-fix.py" --packages-root "P:/packages" --auto-fix --summarize --plugins <name>
```

Then refresh:
```bash
claude plugin marketplace update local
```
⚠️ **Then type `/reload-plugins` manually**.

### `/cc-skills-utils:plugin-installer validate [name]` — Validate plugins

With no argument, validates all:
```bash
python3 "P:/packages/.claude-marketplace/plugins/cc-skills-utils/scripts/plugin-audit-and-fix.py" --validate --marketplace-root "P:/packages/.claude-marketplace"
```

With a plugin name, validates only that plugin:
```bash
python3 "P:/packages/.claude-marketplace/plugins/cc-skills-utils/scripts/plugin-audit-and-fix.py" --validate --marketplace-root "P:/packages/.claude-marketplace" --plugins <name>
```

### `/cc-skills-utils:plugin-installer install` — Install all marketplace plugins

```bash
claude plugin marketplace update local
ls P:/packages/.claude-marketplace/plugins/
# For each plugin directory:
claude plugin install <name>@local
claude plugin marketplace update local
```
⚠️ **After each install, type `/reload-plugins` manually**, then:
```bash
claude plugin list
```

### `/cc-skills-utils:plugin-installer sync` — Sync plugin to marketplace

Plugins live directly in the marketplace. No sync needed — edit files in place, then bump version to propagate to cache.

### `/cc-skills-utils:plugin-installer add <name>` — Add a plugin to marketplace

**Check before creating:**
1. Check if entry already exists: `ls P:/packages/.claude-marketplace/plugins/<name>`
2. If it exists → plugin already in marketplace, skip
3. If no entry exists → create the plugin directory with `.claude-plugin/plugin.json`

Creates a new plugin in the marketplace directory:

```bash
# 1. Create plugin directory
mkdir -p "P:/packages/.claude-marketplace/plugins/<name>/.claude-plugin"

# 2. Register in BOTH marketplace.json index files (install fails without this)
python3 -c "
import json
from pathlib import Path

name = '<name>'
src = Path('P:/packages/.claude-marketplace/plugins') / name
manifest = json.loads((src / '.claude-plugin/plugin.json').read_text())
entry = {
    'name': manifest['name'],
    'version': manifest['version'],
    'description': manifest.get('description', ''),
    'source': f'./plugins/{name}',
    'keywords': manifest.get('keywords', [])
}

for mp_path in [
    Path('P:/packages/.claude-marketplace/marketplace.json'),
    Path('P:/packages/.claude-marketplace/.claude-plugin/marketplace.json'),
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

Removes the plugin directory from marketplace and uninstalls it.

```bash
# 1. Remove plugin directory
Remove-Item "P:/packages/.claude-marketplace/plugins/<name>" -Recurse -Force

# 2. Remove from BOTH marketplace.json index files
python3 -c "
import json
from pathlib import Path
name = '<name>'
for mp_path in [
    Path('P:/packages/.claude-marketplace/marketplace.json'),
    Path('P:/packages/.claude-marketplace/.claude-plugin/marketplace.json'),
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
ls P:/packages/.claude-marketplace/plugins/
claude plugin install <name>@local
```
⚠️ **After each install, type `/reload-plugins` manually**.

**When to use** (vs `bump`):
- `bump` — source files changed, want a clean new version dir. Keeps old cache.
- `refresh` — cache is corrupted, stale, or mismatched. Nukes and reinstalls from marketplace.
- If `bump` + `/reload-plugins` doesn't pick up changes, use `refresh`.

### `/cc-skills-utils:plugin-installer bump <name>` — Bump plugin version

Bumps the patch version (e.g., `2.0.0` → `2.0.1`) in all version files AND updates `installed_plugins.json` so Claude Code loads the new version:

```bash
python3 "P:/packages/.claude-marketplace/plugins/cc-skills-utils/scripts/plugin-audit-and-fix.py" --bump <name> --marketplace-root "P:/packages/.claude-marketplace"
```

**What --bump does automatically:**
1. Increments patch version in `plugin.json` and both `marketplace.json` files
2. Syncs source → new cache dir (removes stale cache dir)
3. Updates `installed_plugins.json` version and `lastUpdated` timestamp
4. Runs `claude plugin marketplace update local` automatically
5. Verifies zero drift for the bumped plugin

After bumping, reload:
```
/reload-plugins
```

**When to use**: After editing any plugin files under `P:/packages/.claude-marketplace/plugins/<name>/` that should propagate to the running session. The plugin system loads from version-keyed cache, not source — without a version bump, changes are invisible.

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

**"failed to load" with hooks.json error:**
Plugin `hooks/hooks.json` must be `{"hooks": {}}` (valid but empty), not `{}`. The audit auto-fix corrects this. Plugins that register hooks via settings.json router hooks (not hooks.json) still need a valid `{"hooks": {}}` file — Claude Code validates the structure on load even when hooks.json has no entries.

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
