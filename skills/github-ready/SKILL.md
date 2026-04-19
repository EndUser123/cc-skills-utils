---
name: github-ready
version: 5.13.0
status: "stable"
enforcement: advisory
description: "Creates GitHub-ready Python libraries, Claude skills, and Claude Code plugins with badges, CI/CD workflows, coverage metrics, and automatic plugin standards validation."
category: scaffolding
triggers:
  - /github-ready
aliases:
  - /github-ready
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
# /github-ready -- Universal Package Creator & Portfolio Polisher v5.13.0

## Purpose

**PRIMARY**: Create **Claude Code Plugins** for packages with hooks, skills, or Claude Code integration.

**SECONDARY**: Convert existing Python libraries to plugins (brownfield conversion).

**ADVANCED**: Create pure Python backend libraries (pip-installable, no hooks/skills) -- only when plugin architecture isn't appropriate.

All packages are polished into resume-worthy GitHub artifacts with badges, CI/CD workflows, coverage metrics, and media assets.

## Bundled Resources

**Scripts** (`resources/`): `badge_generator.py`, `check_standards.py`, `standards_compliance.py`, `recruiter_checklist.py`

**Templates** (`resources/`): `AGENTS.template.md`, `CHANGELOG.template.md`, `CONTRIBUTING.template.md`, `SECURITY.template.md`

**Reference Documentation** (`references/`):

| File | Contents |
|------|----------|
| `brownfield-conversion.md` | Python library to plugin conversion (src/ to core/) |
| `plugin-environment.md` | CLAUDE_PLUGIN_ROOT usage guide |
| `plugin-standards.md` | PHASE 1.7: Plugin standards validation, CRUD recommendations, auto-cleanup |
| `structure-templates.md` | PHASE 2-3: Directory layouts, README templates, media asset templates |
| `deployment-models.md` | Three deployment models, multi-skill/hook setup, common mistakes |
| `code-review-and-quality.md` | PHASE 4.5: Code review, meta-review, quality scanning |
| `media-generation.md` | PHASE 4.7: NotebookLM uploads, video compliance, banner validation, cleanup |
| `diagrams-and-pages.md` | Mermaid diagrams, GitHub Pages video player, slide deck integration |
| `changelog.md` | Full version history |

## Project Context

- **DEFAULT**: Claude Code Plugins (`.claude-plugin/`, `core/`, `hooks/`) for packages with hooks/skills
- **MIGRATION**: Convert existing Python libraries to plugins via brownfield conversion
- **ADVANCED**: Pure Python libraries (`src/`, `pyproject.toml`) only for backend code without Claude Code integration
- Windows-compatible: Junctions for skill directories, symlinks for individual files
- Solo-dev environment: pragmatic solutions, truthfulness required
- See `references/plugin-environment.md` for CLAUDE_PLUGIN_ROOT usage

## Workflow

**One command, full intelligent pipeline:**

1. **DETECT** -- Scan repository, identify gaps and needs
2. **ANALYZE** -- Determine package type automatically
3. **GENERATE** -- Create all missing artifacts
4. **VALIDATE** -- Verify everything works
5. **CLEANUP** -- Remove obsolete files from refactoring
6. **REPORT** -- Show what was created with evidence

**Override flags** (rarely needed): `--dry-run`, `--skip <phase>`, `--check-only`

### Usage

```bash
/github-ready                    # Full pipeline on current directory
/github-ready mylib              # Full pipeline with specific name
/github-ready --dry-run mylib    # Preview what will happen
/github-ready --skip media       # Skip media generation
/github-ready --check-only       # Analyze without creating
/github-ready --publish          # Publish to GitHub after polish
/github-ready --publish --finalize  # Publish + finalize (Pages, release, topics)
```

### Intent Interpreter

| User says | Action |
|-----------|--------|
| `/github-ready` | Full pipeline on current directory |
| `/github-ready <name>` | Full pipeline, create new package |
| `/github-ready --dry-run` | Preview without creating |
| `/github-ready --skip <phase>` | Skip specific phase |
| `/github-ready --check-only` | Analyze only |

---

## PHASE 0: Dry Run Preview (Optional)

Shows what will be created without writing files. Triggered by `--dry-run`.

---

## PHASE 1: Diagnose & Prep (30s)

1. Check existing structure: `tree {{TARGET_DIR}} -a -L 3`
2. Clear stale state files: `rm -f {{TARGET_DIR}}/.claude/state*.json`
3. Check for existing modules: `ls {{TARGET_DIR}}/src/`

Output: "Prep complete. Modules: [Y/N]. State cleared."

---

## PHASE 1.5: Detect Package Type (30s)

**Detection logic:** Checks for SKILL.md, `.claude-plugin/`, hook directories, `src/`, and `pyproject.toml` to determine package type.

| Type | Trigger | Use Case | Priority |
|------|---------|----------|----------|
| `claude-plugin` | `.claude-plugin/` exists | Packages with hooks/skills | **Primary** |
| `claude-plugin+mcp` | `.claude-plugin/` + `mcp_server.py` | Plugins with MCP server | MCP integration |
| `brownfield-plugin` | Python library + user confirms | Convert existing lib to plugin | Migration path |
| `python-library` | `src/` or `pyproject.toml` (no conversion) | Pure backend code | Advanced only |
| `claude-skill` | `SKILL.md` exists | Standalone skills | Skill-only |
| `hook-package` | `hook/` directory exists | Legacy hook distribution | Use plugin instead |

**Brownfield detection**: If Python library detected, offers conversion to plugin with confirmation.

---

## PHASE 1.6: Brownfield Conversion (Conditional)

**Only if `PACKAGE_TYPE=brownfield-plugin`**. See `references/brownfield-conversion.md` for the 7-step workflow.

**Pre-conversion checklist**: Fix hardcoded paths, platform-specific code, error handling, dependencies, test coverage.

**Rollback**: Backup at `.backup/` before conversion. To rollback: `cp -r .backup/* . && rm -rf core/ .claude-plugin/`

**Post-conversion**: Verify symlinks in `P:/.claude/hooks/` point to `core/hooks/` not old `src/` paths.

---

## PHASE 1.7: Plugin Standards Validation (Auto-invoked)

Scans root directory, compares against official Claude Code plugin standards, provides CRUD recommendations.

See `references/plugin-standards.md` for: detection logic, CRUD recommendations, auto-cleanup script, output format.

---

## PHASE 2: Build Structure (2min)

Creates directory structure based on detected package type.

See `references/structure-templates.md` for: directory layouts, plugin.json/hooks.json templates, build steps per package type.

---

## PHASE 3: Generate Templates

Generates README.md, LICENSE, AGENTS.md, and configuration files.

See `references/structure-templates.md` for: README structure contract, media assets template, deployment models template.

See `references/deployment-models.md` for: Three Deployment Models section to include in generated README.md.

---

## PHASE 4: Validate (1min)

**Checks:**
1. Platform compatibility (Windows docs vs .sh scripts in hook configs)
2. Symlink verification (for Claude skills)
3. Pytest collection: `pytest --collect-only {{TARGET_DIR}}/tests/`
4. Tree diff (pre vs post structure)

Output: "Validation complete. All checks passed."

---

## PHASE 4.5: Code Review & Meta-Review (Auto-invoked)

Runs automated code review + meta-review before portfolio polish.

See `references/code-review-and-quality.md` for: execution code, integration notes, optional quality scanning (`--scan-quality`).

---

## PHASE 4.7: Media Generation (Auto-invoked)

Generates professional portfolio assets: banners, diagrams, explainer videos, slide decks.

See `references/media-generation.md` for: asset table, nlm CLI commands, multi-source upload strategy, video compliance verification, notebook cleanup, banner validation.

**Auto-skip**: No README images detected, or `--skip media`.

**Duration**: 5-10 minutes.

---

## Diagrams & GitHub Pages

Generates GitHub-safe Mermaid flowcharts and video player page.

See `references/diagrams-and-pages.md` for: GitHub compatibility rules, diagram types, banned patterns, Mermaid vs NotebookLM comparison, slide deck integration.

---

## PHASE 5: Portfolio Polish (Auto-invoked)

Transforms package into portfolio-quality GitHub artifact.

**Auto-generated artifacts**: Badges (shields.io), CI/CD workflow, CHANGELOG.md, CONTRIBUTING.md, AGENTS.md, architecture flowchart, video playback page, Quick Start section.

**CI/CD** (`.github/workflows/test.yml`): Python 3.14, pytest with coverage, **no Codecov** -- local reporting only.

**Checks**: Platform compatibility, MCP structure, no secrets in git, test coverage badges.

---

## PHASE 6: GitHub Publication (Optional)

**Trigger**: `--publish` flag. Extracts from monorepo if needed, creates GitHub repo via `gh`.

Scripts: `scripts/extract_from_monorepo.py`, `scripts/create_github_repo.py`

Prerequisites: GitHub CLI (`gh`) installed and authenticated.

---

## PHASE 7: Repository Finalization (Optional)

**Trigger**: `--finalize` flag. Runs after PHASE 6.

1. Enables GitHub Pages
2. Creates initial release (`v0.1.0` or `v1.0.0`)
3. Adds repository topics (python, claude-code, plugin, etc.)
4. Generates CODEOWNERS and SECURITY.md

Script: `scripts/finalize_github_repo.py`

Options: `--package-type`, `--release-version`, `--username`, `--skip-pages`, `--skip-release`, `--skip-topics`, `--skip-codeowners`, `--skip-security`

---

## PHASE 8: Cleanup (Auto-invoked)

Detects and reports obsolete files: backups, orphaned tests, obsolete docs, duplicate implementations.

Output: `CLEANUP_REPORT.md` with categorized files, evidence, bulk removal commands.

---

## PHASE 9: Git Ready (Auto-invoked)

Initializes git repo (`git init`), creates initial commit, sets main branch. Skips if `.git/` already exists.

---

## PHASE 10: Recruiter Readiness Validation (Auto-invoked)

Validates package is showcase-ready: checks for TODOs, plan files, missing CI/CD, missing tests, low version numbers.

Scoring: 90-100 (Excellent), 70-89 (Good), 50-69 (Fair), <50 (Poor).

Output: `RECRUITER_READINESS_REPORT.md` with score, issues, and one-command fixes.

---

## Local Development Setup

Three deployment models for Claude Code packages. See `references/deployment-models.md` for full details.

| Model | For | Setup |
|-------|-----|-------|
| **SKILLS** (dev) | Active development | Junction `skill/` to `P:/.claude/skills/` |
| **HOOKS** (dev) | Hook file testing | Symlink `.py` files to `P:/.claude/hooks/` |
| **PLUGINS** (end user) | Distribution | `/plugin` command |

---

## Completion Report (Always Show at End)

After all phases, show one of these statuses:

**PUBLIC ON GITHUB**: Repo is live with all polish complete, tests passing, CI/CD configured.

**READY FOR GITHUB**: Polished and ready. Next step: `gh repo create package-name --public --source=. --push`

**LOCAL ONLY (NEEDS POLISH)**: List missing items. Run: `/github-ready <path> --polish`

---

## Integration

**Related skills**: `/init` (CLAUDE.md initialization)

**Deprecated skills**: `/media-pipeline` (merged into PHASE 4.7)

**Used by**: Claude Code Plugins (primary), Python library migration (secondary), pure Python libraries (advanced)

---

## Changelog

See `references/changelog.md` for full version history.

Current: v5.13.0 | Recent: Plugin standards validation (v5.6), GitHub Pages video playback (v5.5.6), Media generation integration (v5.4)
