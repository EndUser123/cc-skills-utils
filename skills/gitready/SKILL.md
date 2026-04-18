---
name: gitready
version: 5.25.0
status: "stable"
description: This skill should be used when the user asks to "create a package", "scaffold a Python library", "make a GitHub-ready repo", "generate badges", "convert to plugin", "brownfield conversion", "validate plugin standards", or mentions package scaffolding, portfolio polish, repository structure setup, badge generation, or plugin standards validation. Creates GitHub-ready Python libraries, Claude skills, and Claude Code plugins with badges, coverage metrics, media artifacts, interactive course modules, and automatic plugin standards validation. Includes PHASE 6: GitHub Publication and PHASE 7: Repository Finalization.
category: scaffolding
enforcement: advisory
triggers:
  - /gitready
aliases:
  - /gitready
workflow_steps:
  - detect_package_type
  - analyze_existing_structure
  - select_package_template
  - validate_plugin_standards
  - scaffold_project_structure
  - configure_ci_cd
  - generate_badges
  - create_documentation
  - validate_package
  - publish_to_github
  - finalize_repository
  - cleanup_obsolete_files

suggest:
  - /init
---
# /gitready - Universal Package Creator and Portfolio Polisher v5.20.0

## Purpose

**PRIMARY**: Create **Claude Code Plugins** (`.claude-plugin/`, `scripts/`, `hooks/`) for packages with hooks, skills, or Claude Code integration.

**SECONDARY**: Convert existing Python libraries to plugins (brownfield conversion).

**ADVANCED**: Create pure Python backend libraries (pip-installable) only when plugin architecture is not appropriate.

All packages are polished into resume-worthy GitHub artifacts with badges, coverage metrics, and media assets.

## Quick Start

```bash
/gitready                  # Full pipeline on current directory
/gitready <name>           # Scaffold new package
/gitready --status         # Show phase status (COMPLETED/SKIPPED/PENDING)
/gitready --dry-run        # Preview without creating
/gitready --skip <phase>   # Skip specific phase (e.g., --skip media)
/gitready --check-only     # Analyze without creating
/gitready --publish        # Publish to GitHub after polish
/gitready --finalize       # Finalize after GitHub publication
```

| User says | Action |
|-----------|--------|
| `/gitready` | Full pipeline on current directory |
| `/gitready <name>` | Scaffold new package with full pipeline |
| `/gitready --status` | Show all phase states for a package (✓ COMPLETED, ⏭ SKIPPED, ○ PENDING) |
| `/gitready --dry-run` | Preview what will happen |
| `/gitready --skip media` | Skip NotebookLM media generation |
| `/gitready --check-only` | Analyze without creating |

## Workflow Overview

One command runs the full intelligent pipeline:

1. **DETECT** (PHASE 1) - Scan repository, identify gaps and needs
2. **ANALYZE** (PHASE 1.5) - Determine package type automatically
3. **GENERATE** (PHASE 2-3) - Create all missing artifacts
4. **VALIDATE** (PHASE 4) - Verify everything works
5. **REVIEW** (PHASE 4.5-4.6) - Code review and quality checks
6. **MEDIA** (PHASE 4.7-4.8) - Optional media and course generation (track as SKIPPED if auth unavailable)
7. **POLISH** (PHASE 5) - Portfolio-quality badges, docs
8. **CLEANUP** (PHASE 8) - Remove obsolete files
9. **GIT** (PHASE 9) - Initialize repo and commit
10. **REPORT** (PHASE 10) - Show completion status

**Phase states:** ✓ COMPLETED (done) · ⏭ SKIPPED (conditional — auth missing or flag not provided) · ⏭ N/A (not applicable to this package type)

## Package Types

| Type | Trigger | Use Case |
|------|---------|----------|
| `claude-plugin` | `.claude-plugin/` or empty dir | **DEFAULT**: Packages with hooks/skills |
| `claude-plugin+mcp` | `.claude-plugin/` + `mcp_server.py` | Plugins with MCP server |
| `brownfield-plugin` | `src/` + `pyproject.toml` | Convert existing Python lib to plugin |
| `python-library` | Only `pyproject.toml`, no `src/` | **ADVANCED**: Pure backend, no hooks |
| `claude-skill` | `SKILL.md` exists | Standalone Claude skills |
| `hook-package` | `hook/` directory exists | Legacy hook distribution |

> Full detection script: `references/package-type-detection.md`

## Project Context

- Solo-dev environment with pragmatic solutions
- **DEFAULT**: Claude Code Plugins for packages with hooks/skills
- Windows-compatible: **Junctions** for skill dirs (no admin), **Symlinks** for individual files
- **CRITICAL**: Add junction target to `.gitignore` to prevent dual git tracking
- `CLAUDE_PLUGIN_ROOT` for all path references - see `references/plugin-environment.md`

## Bundled Resources

**Scripts** (`resources/`):
- `badge_generator.py` - Generate badges from shields.io
- `check_standards.py` - Validate package standards compliance
- `standards_compliance.py` - Check Python/Claude skill standards
- `recruiter_checklist.py` - Portfolio optimization checklist

**Templates** (`resources/`): `AGENTS.template.md`

**Reference Docs** (`resources/`): `BADGE_GENERATION_GUIDE.md`, `STANDARDS_VALIDATION.md`, `V5.2_UPDATE_SUMMARY.md`

---

## PRE-CHECK: Stale Location Guard (Always Runs First)

**Before any phase is selected**, detect and resolve stale install locations:

```bash
TARGET_DIR="$1"  # from gitready argument
SKILL_NAME=$(basename "$TARGET_DIR")

# Detect if pointing at old canonical install location
if [[ "$TARGET_DIR" == "P:/.claude/skills/"* ]]; then
    echo "WARNING: gitready was invoked on an installed skill location."
    echo "The source of truth should be at P:/packages/$SKILL_NAME"
    if [ -d "P:/packages/$SKILL_NAME" ]; then
        echo "Auto-resolving to source location..."
        TARGET_DIR="P:/packages/$SKILL_NAME"
    else
        echo "ERROR: No package found at P:/packages/$SKILL_NAME"
        echo "Migration needed: cp -r $TARGET_DIR/* P:/packages/$SKILL_NAME/"
        exit 1
    fi
fi
```

**Why**: gitready must always process the **packages source of truth**, never an installed junction location. Processing the stale location creates dual implementations that cause confusion and stale code.

---

## PHASE 0: Dry Run Preview (Optional)

**Trigger**: `--dry-run` flag. Shows directory structure, files to create, and next steps. No files written.

---

## PHASE 1: Diagnose and Prep (30s)

**Prerequisite** (auto-runs before any phase):
```bash
python resources/phases/validate_pointers.py
```
Validates all bundled-resource pointers resolve to existing, non-empty files. Stop and fix broken pointers before continuing.

**Read completed phases** (from target's `references/changelog.md`):
```bash
python resources/phases/track_phases.py {{TARGET_DIR}} --read
```
Reports which phases already completed; skips phases marked `-- COMPLETED` or `-- SKIPPED`.

**Steps**:
1. Check existing structure: `tree {{TARGET_DIR}} -a -L 3`
2. Clear state files: `rm -f {{TARGET_DIR}}/.claude/state*.json`
3. Check for existing modules: `ls {{TARGET_DIR}}/src/`
4. **Track completion**: `python resources/phases/track_phases.py {{TARGET_DIR}} --write 1`

**Output**: "Prep complete. Modules: [Y/N]. State cleared."

---

## PHASE 1.5: Detect Package Type (30s)

> See `references/package-type-detection.md` for full detection script and package type table.

Auto-detects package type. Python libraries with `src/` + `pyproject.toml` auto-convert to `brownfield-plugin`.

**Track completion**: `python resources/phases/track_phases.py {{TARGET_DIR}} --write 1.5`

---

## PHASE 1.6: Brownfield Conversion (2min) - ONLY IF brownfield-plugin

**Pre-Conversion Checklist**:
- Fix hardcoded paths (no `P:/`, `/Users/`, `C:/` in source code)
- Fix platform-specific code (`.sh` scripts need `.bat` equivalents)
- Add error handling and logging
- Verify dependencies
- Expand test coverage

> See `references/brownfield-conversion.md` for detailed 7-step workflow.

**Rollback**: Backup at `.backup/`. To rollback: `cp -r .backup/* . && rm -rf scripts/ .claude-plugin/`

**Track completion**: `python resources/phases/track_phases.py {{TARGET_DIR}} --write 1.6 --status N/A`
*(If not brownfield-plugin, this phase is N/A — track as N/A, not SKIPPED)*

---

## PHASE 1.6.5: Intentional Exception Registry (Auto-invoked)

> See `references/exception-registry.md` for full 4-step workflow.

Documents known deviations from plugin standards in `.gitready/exceptions.json` so gitready stops repeatedly flagging them.

**Track completion**: `python resources/phases/track_phases.py {{TARGET_DIR}} --write 1.6.5`

---

## PHASE 1.7: Plugin Standards Validation (Auto-invoked)

> READ: `resources/phases/PHASE-1.7-plugin-standards.md`
> See `references/exception-aware-validation.md` for waiver logic.

Validates plugin files/folders against Claude Code plugin standards. Exception-aware: skips waived violations from `.gitready/exceptions.json`.

**Track completion**: `python resources/phases/track_phases.py {{TARGET_DIR}} --write 1.7`

---

## PHASE 1.8: Stale Location Cleanup and Junction/Symlink Setup (Auto-invoked)

> See `references/stale-location-cleanup.md` for full 8-step workflow.

Cleans old canonical locations, creates proper junctions/symlinks pointing to `P:/packages/` source of truth.

**Track completion**: `python resources/phases/track_phases.py {{TARGET_DIR}} --write 1.8`

---

## PHASE 2: Build Structure (2min)

> See `references/build-structure.md` for directory layouts per package type.

Creates directory structure based on detected package type. Claude skills get `skill/`, plugins get `.claude-plugin/` + `scripts/` + `hooks/`, libraries get `src/` + `pyproject.toml`.

**Local Development Setup**: See `references/deployment-models.md` for junction/symlink setup, multiple skills/hooks patterns, and cleanup after relocation.

**Track completion**: `python resources/phases/track_phases.py {{TARGET_DIR}} --write 2`

---

## PHASE 3: Generate Templates

> READ: `resources/phases/PHASE-3-templates.md`

**Track completion**: `python resources/phases/track_phases.py {{TARGET_DIR}} --write 3`

---

## PHASE 4: Validate (1min)

> See `references/validation-scripts.md` for platform compatibility checks, symlink tests, pytest collect, and tree diff.

**Track completion**: `python resources/phases/track_phases.py {{TARGET_DIR}} --write 4`

---

## PHASE 4.5: Code Review and Meta-Review (Auto-invoked)

> See `references/advanced-phases.md` for full execution details.

Runs code-review plugin (security, performance, maintainability) and meta-review (path traversal, import graph, doc consistency). Critical findings must be fixed before PHASE 5.

**Track completion**: `python resources/phases/track_phases.py {{TARGET_DIR}} --write 4.5`

---

## PHASE 4.7: Media Generation (Auto-invoked)

> READ: `resources/phases/PHASE-4.7-media-gen.md`
> IMPORTANT: READ `references/notebooklm-integration.md` for auth credentials, valid video styles (NOT "documentary"), file upload workaround, and download commands.

Requires NotebookLM auth. If auth is not available, track as SKIPPED:
```
python resources/phases/track_phases.py {{TARGET_DIR}} --write 4.7 --status SKIPPED
```

**Track completion**: `python resources/phases/track_phases.py {{TARGET_DIR}} --write 4.7`

---

## PHASE 4.8: Interactive Course (Auto-invoked)

> READ: `resources/phases/PHASE-4.8-interactive-course.md`
> IMPORTANT: The course is built using the 4-pass pipeline in the phase doc — design-system.md and interactive-elements.md are bundled with this skill at `resources/codebase-to-course/`. READ them before generating.

Requires NotebookLM auth. If auth is not available, track as SKIPPED:
```
python resources/phases/track_phases.py {{TARGET_DIR}} --write 4.8 --status SKIPPED
```

**Track completion**: `python resources/phases/track_phases.py {{TARGET_DIR}} --write 4.8`

---

## PHASE 5: Portfolio Polish (Auto-invoked)

**Auto-generated artifacts** (if missing):
- **Badges**: Coverage, version, license, CI status (shields.io)
- **Documentation**: CHANGELOG.md, CONTRIBUTING.md, AGENTS.md, API docs
- **Architecture flowchart**: GitHub-safe Mermaid in README.md
- **Video playback**: `docs/video.html` for GitHub Pages
- **Quick Start**: Installation and usage examples

**Track completion**: `python resources/phases/track_phases.py {{TARGET_DIR}} --write 5`

---

## PHASE 6: GitHub Publication (Optional)

> See `references/advanced-phases.md` for details.

**Trigger**: `--publish` flag. Extracts from monorepo, creates GitHub repo via GitHub API.

**GitHub API Creation**: Uses `resources/create_github_repo_api.py` which:
- Auto-detects GitHub token from git remote URL or `GITHUB_TOKEN` env var
- Creates public repositories by default (use `--private` for private)
- Validates token has `repo` scope before attempting creation
- Checks for existing repos to avoid conflicts

**Usage:**
```bash
/gitready my-package --publish

# Or manually
python resources/create_github_repo_api.py my-package "Description here"
```

If `--publish` flag is not provided, track as SKIPPED:
```
python resources/phases/track_phases.py {{TARGET_DIR}} --write 6 --status SKIPPED
```

**Track completion**: `python resources/phases/track_phases.py {{TARGET_DIR}} --write 6`

---

## PHASE 7: Repository Finalization (Optional)

> See `references/advanced-phases.md` for details and options.

**Trigger**: `--finalize` flag. Enables GitHub Pages, creates initial release, adds topics/tags, generates CODEOWNERS and SECURITY.md.

If `--finalize` flag is not provided, track as SKIPPED:
```
python resources/phases/track_phases.py {{TARGET_DIR}} --write 7 --status SKIPPED
```

**Track completion**: `python resources/phases/track_phases.py {{TARGET_DIR}} --write 7`

---

## PHASE 4.6: Quality Scanning (Auto-invoked)

> See `references/advanced-phases.md` for details and options.

Security scanning (bandit, safety), dependency auditing (pip-audit), badge validation, quality metrics.

**Track completion**: `python resources/phases/track_phases.py {{TARGET_DIR}} --write 4.6`

---

## PHASE 8: Cleanup (Auto-invoked)

Detects and reports obsolete files: backup files (`*.backup-*`, `*.old`, `*.bak`), orphaned test files, obsolete documentation, duplicate implementations. Output: `CLEANUP_REPORT.md` with categorized removal commands.

**Track completion**: `python resources/phases/track_phases.py {{TARGET_DIR}} --write 8`

---

## PHASE 9: Git Ready (Auto-invoked)

Initialize git repo (if not already): `git init`, add all files, initial commit, set main branch. Skips if `.git/` exists.

**Track completion**: `python resources/phases/track_phases.py {{TARGET_DIR}} --write 9`

---

## PHASE 10: Recruiter Readiness Validation (Auto-invoked)

**Checks**: TODOs in pyproject.toml, plan files in root, no tests, version 0.0.x/0.1.x.
**Scoring**: 90-100 (Excellent), 70-89 (Good), 50-69 (Fair), <50 (Poor).
**Auto-fixes**: Remove TODOs, move plans to `docs/planning/`, bump version.
**Output**: `RECRUITER_READINESS_REPORT.md`

**Track completion**: `python resources/phases/track_phases.py {{TARGET_DIR}} --write 10`

---

## Completion Report (Always Show at End)

> See `references/completion-report.md` for full templates and truth-claim rules.

**MANDATORY**: After all phases, show GitHub readiness status with phase execution evidence.

Three statuses:
1. **PUBLIC ON GITHUB** - Live and accessible
2. **READY FOR GITHUB** - Core phases complete; conditional phases (GitHub Publication, Repository Finalization) pending flag authorization
3. **LOCAL ONLY** - Core phases incomplete or blocked

**Do not claim "no pending work" when conditional phases are SKIPPED.** SKIPPED means the phase was not run because a flag was not provided — it is not settled, it is deferred. Pending flags = outstanding decisions.

**When reporting skipped phases, use full phase names (not numbers). Show N/A separately from SKIPPED:**
- ⏭ SKIPPED → Media Generation, Interactive Course, GitHub Publication, Repository Finalization (conditional — not run because auth missing or flag not provided; outstanding until flag is added)
- ⏭ N/A → Brownfield Conversion (not applicable to this package type)

---

## Integration

**Related skills**: `/init` - Initialize CLAUDE.md for new projects

**Used by**: Claude Code Plugins (primary), Python library conversion (migration), pure Python backend libraries (advanced)

---

## Changelog

> See `references/changelog.md` for full version history.
