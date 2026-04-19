# PHASE 1.7: Plugin Standards Validation (Detailed Reference)

**Objective**: Validate existing files/folders against OFFICIAL Claude Code plugin standards and provide CRUD recommendations.

**When**: Automatically runs after PHASE 1.5 (Detect Package Type) completes, for ALL plugin package types.

**What this does**:
- Scans root directory for files/folders
- Compares against OFFICIAL plugin-dev:plugin-structure standards
- Identifies non-standard files that violate plugin conventions
- Provides CRUD recommendations (Create, Update, Delete)
- Offers auto-cleanup with confirmation
- **NO ARGUMENTS REQUIRED** - runs automatically

**Standards Source**: OFFICIAL Claude Code plugin documentation from:
- **plugin-dev:plugin-structure** (authoritative source)
- **plugin-dev:plugin-settings** (configuration reference)
- **plugin-dev:create-plugin** (creation workflow)

## OFFICIAL Claude Code Plugin Structure

**Required Directories**:
- **`.claude-plugin/`** - Plugin metadata (contains ONLY `plugin.json`)
- **Component dirs at ROOT** - `commands/`, `agents/`, `skills/`, `hooks/` (NOT nested in `.claude-plugin/`)

**Optional Directories** (created as needed):
- **`commands/`** - Slash commands (.md files)
- **`agents/`** - Subagent definitions (.md files)
- **`skills/`** - Agent skills (subdirectories with `SKILL.md`)
- **`hooks/`** - Hook configuration (`hooks.json`)
- **`scripts/`** - Helper scripts and utilities (Python code goes here)
- **`.github/`** - GitHub workflows

**CRITICAL CORRECTION FROM v5.6.0**:
- WRONG: `core/` directory is NOT in official spec
- CORRECT: Python code in `scripts/` or component directories
- CORRECT: Components at ROOT level (not nested in `.claude-plugin/`)

**Required Files** (root):
- **`README.md`** - Portfolio documentation
- **`LICENSE`** - License file

**Optional Files** (root):
- **`CHANGELOG.md`** - Version history
- **`AGENTS.md`** - AI-maintainable documentation
- **`CONTRIBUTING.md`** - Contribution guidelines
- **`.gitignore`** - Version control exclusions

**FORBIDDEN Files** (violate plugin standards):
- **`pyproject.toml`** - Plugins don't use pip packaging
- **`setup.py`** - Plugins don't use pip packaging
- **`setup.cfg`** - Plugins don't use pip packaging
- **`core/`** directory - NOT in official plugin structure
- **`src/`** directory - Use appropriate component directories instead

## Detection Logic

```bash
cd {{TARGET_DIR}}
ROOT_ITEMS=$(find . -maxdepth 1 -type d ! -name ".*" ! -name "." | sort)
ROOT_FILES=$(find . -maxdepth 1 -type f ! -name ".*" | sort)

# Check for forbidden files
FORBIDDEN=""
if [ -f "pyproject.toml" ]; then
    FORBIDDEN="$FORBIDDEN\nDELETE: pyproject.toml (plugins don't need pip packaging)"
fi
if [ -d "src" ]; then
    FORBIDDEN="$FORBIDDEN\nDELETE/MIGRATE: src/ (use core/ for plugins)"
fi

# Check for non-standard files (artifact patterns)
TEMP_FILES=$(find . -maxdepth 1 -name "*SUMMARY*.md" -o -name "*REPORT*.md" -o -name "*CHECKLIST*.md" -o -name "*AUDIT*.md" -o -name "*TREE*.txt" -o -name "README_*.md" 2>/dev/null)
if [ -n "$TEMP_FILES" ]; then
    FORBIDDEN="$FORBIDDEN\nMOVE TO docs/: Temporary documentation artifacts"
fi

# Check for test scripts in root
TEST_SCRIPTS=$(find . -maxdepth 1 -name "test_*.py" -o -name "verify_*.py" -o -name "analyze_*.py" -o -name "diagnose_*.py" 2>/dev/null)
if [ -n "$TEST_SCRIPTS" ]; then
    FORBIDDEN="$FORBIDDEN\nMOVE TO tests/: Standalone test scripts"
fi
```

## CRUD Recommendations

**DELETE** (violates plugin standards):
- `pyproject.toml`, `setup.py`, `setup.cfg` - Plugins don't use pip
- `src/` directory - Wrong structure, use `core/`
- `*.backup`, `*.old`, `*.bak` - Backup files
- `test_*.py`, `verify_*.py`, `analyze_*.py` - Temporary test scripts
- `*SUMMARY*.md`, `*REPORT*.md`, `*CHECKLIST*.md` - Temporary documentation
- `*TREE*.txt`, `README_NEW.md` - Diagnostic artifacts
- `.coverage`, `coverage.json` - Generated coverage files

**MOVE TO `docs/`** (historical context, not root clutter):
- `*_STRUCTURE.md`, `*_AUDIT*.md`, `*_VALIDATION*.md`
- `*_BREAKDOWN*.md`, `*_FIX*.md`, `*_DATA*.md`
- `*_IMPLEMENTATION*.md`, `*_PHASE*.md`

**MOVE TO `tests/`** (test suite organization):
- `test_*.py` (if useful tests)
- `verify_*.py` (if verification scripts)
- Review bundles, test fixtures

**KEEP IN ROOT** (standard plugin files):
- `README.md`, `LICENSE`, `CHANGELOG.md`
- `AGENTS.md`, `CONTRIBUTING.md`, `.gitignore`

## Auto-Cleanup Script

```bash
#!/bin/bash
# Auto-cleanup non-standard plugin files

mkdir -p docs tests/fixtures

# Delete forbidden files
rm -f pyproject.toml setup.py setup.cfg
rm -f *.backup *.old *.bak
rm -f *SUMMARY*.md *REPORT*.md *CHECKLIST*.md *AUDIT*.md
rm -f *TREE*.txt README_NEW.md
rm -f test_*.py verify_*.py analyze_*.py diagnose_*.py
rm -f .coverage coverage.json

# Move documentation to docs/
mv *_STRUCTURE.md docs/ 2>/dev/null || true
mv *_AUDIT*.md docs/ 2>/dev/null || true
mv *_VALIDATION*.md docs/ 2>/dev/null || true
mv *_DATA*.md docs/ 2>/dev/null || true
mv *_IMPLEMENTATION*.md docs/ 2>/dev/null || true
mv *_PHASE*.md docs/ 2>/dev/null || true
mv review_bundle_*.md tests/fixtures/ 2>/dev/null || true

echo "Cleanup complete"
```

## Output Format

**PLUGIN_STANDARDS_REPORT.md**:
```markdown
# Plugin Standards Validation Report

## Package Type: claude-plugin
## Compliance Score: 85/100

### Standards Compliant
- .claude-plugin/ exists
- core/ directory present
- hooks/ configuration present
- README.md with badges

### Standards Violations (5 items)
- **DELETE**: pyproject.toml (plugins don't need pip packaging)
- **MOVE TO docs/**: HANDOFF_QUALITY_CHECKLIST.md (7 files)
- **MOVE TO tests/**: test_handoff_save_direct.py (2 files)
- **DELETE**: pre-pack-tree.txt (diagnostic artifact)

### Auto-Cleanup Available
Run this command to auto-fix all violations:
cd P:/packages/handoff && bash cleanup_plugin_standards.sh
```

**Integration**: Runs automatically after package type detection, before structure building. Can be invoked standalone with `/github-ready --check-standards`.
