# Changelog

## v5.13.0 (Current)
- Comprehensive reference extraction to `references/` directory
- SKILL.md reduced to under 500 lines with progressive disclosure

## v5.6.0 (2026-03-14)
- **PLUGIN STANDARDS VALIDATION**: Added PHASE 1.7 - automatic validation against Claude Code plugin standards
- **CRUD RECOMMENDATIONS**: Auto-detects non-standard files and provides Create/Update/Delete recommendations
- **MULTI-PLUGIN VALIDATION**: Standards validated against multiple production plugins
- **AUTO-CLEANUP**: One-command cleanup script for removing/moving non-standard files
- **FORBIDDEN FILE DETECTION**: Identifies `pyproject.toml`, `src/`, `setup.py` violations
- **TEMPORARY FILE DETECTION**: Finds test scripts, diagnostic artifacts, temporary documentation
- **COMPLIANCE SCORING**: Generates compliance scores (0-100) with detailed violation reports

## v5.5.6 (2026-03-11)
- **GITHUB PAGES VIDEO PLAYBACK**: README links preview GIFs to `docs/video.html` on GitHub Pages
- README architecture defaults to GitHub-safe Mermaid flowcharts instead of C4 blocks
- Media guidance updated to treat direct MP4 links as fallback

## v5.5.5 (2026-03-10)
- **GITHUB-COMPATIBLE MEDIA**: Fixed README media template for GitHub compatibility
- Replaced inline README video attempts with GitHub-safe links
- Added shields.io badges for visual appeal

## v5.5.4 (2026-03-10)
- **MEDIA ASSETS TEMPLATE**: Added Media Assets section template to PHASE 3
- Center-aligned media with proper markdown image embedding

## v5.5.3 (2026-03-10)
- **COMPLETION REPORT**: Added GitHub readiness status check at end of workflow
- Three clear statuses: PUBLIC, READY FOR GITHUB, LOCAL ONLY

## v5.5.2 (2026-03-10)
- **CI/CD TEMPLATE**: Added explicit GitHub Actions workflow template
- **NO CODECOV**: CI workflows should NOT upload to external coverage services

## v5.5.1 (2026-03-10)
- **DOCUMENTATION**: Added "Three Deployment Models" template
- README templates include SKILLS/HOOKS/PLUGINS deployment comparison

## v5.4.3 (2026-03-10)
- Comprehensive usage examples for NotebookLM cleanup
- Troubleshooting section with 4 common issues and solutions

## v5.4.2 (2026-03-10)
- **SECURITY FIX**: Added defensive error handling to NotebookLM cleanup
- Confirmation prompt required before deletion

## v5.4.1 (2026-03-10)
- NotebookLM temporary notebooks use clear naming pattern
- Added notebook cleanup instructions after asset generation

## v5.4.0 (2026-03-09)
- **MERGED**: /media-pipeline integrated as PHASE 4.7 (Media Generation)
- Auto-generates professional portfolio assets
- NotebookLM integration for architecture diagrams and explainer videos
- Vision API verification for asset quality
- **DEPRECATED**: Standalone /media-pipeline skill

## v5.5.0 (2026-03-10)
- Integrated meta-review system into PHASE 4.5 (T-007)
- Cross-file analysis: path_traversal, import_graph, doc_consistency

## v5.3.0 (2026-03-07)
- Added PHASE 4.5: Code Review (code-review plugin integration)
- Automated quality validation before portfolio polish
- Confidence-based scoring (80+ threshold)

## v5.2.0 (2025-03-07)
- Updated to Claude Code plugin best practices (v5.2 structure)
- Added `core/` directory for Python code
- Added `hooks/hooks.json` for hook configuration
- Added `.mcp.json` for MCP server configuration
- Removed `pyproject.toml` (plugins don't need pip packaging)
- Added local development setup (junctions/symlinks)
- Added brownfield conversion workflow (src/ -> core/)

## v5.1.0
- Initial router-based hook package support
- MCP server directory structure
- pyproject.toml packaging

## v5.0.0
- Python library scaffolding
- Claude skill creation
- Badge generation
- CI/CD workflows
