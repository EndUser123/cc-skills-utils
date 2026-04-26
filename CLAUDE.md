# cc-skills-utils

Utility skills for Claude Code — discovery, git operations, hooks, and general tooling.

## Skills (30)

| Skill | Purpose |
|-------|---------|
| aid | AI-Distiller wrapper for code analysis |
| ask | Universal CLI router for command discovery and orchestration |
| chs | Chat history search with summarization and filtering |
| cks-usage | Constitutional Knowledge System usage patterns |
| cleanup | Directory structure cleanup with LLM-guided analysis |
| context-status | Context usage statistics via compaction timing |
| context7 | Fetch fresh, version-specific documentation via Context7 API |
| data-safety-vcs | Data safety and version control standard for solo dev |
| discover | Codebase pattern discovery and architecture analysis |
| explore | Unified search across local data and web |
| git | Multi-repo sync, worktree management, conflict resolution |
| gitbatch | Batch skill execution across packages via subagents |
| gitingest | Ingest GitHub repos into NotebookLM |
| gitready | Universal package creator and portfolio polisher |
| snapshot | Session snapshot capture and restore |
| hook-obs | Hook observability — performance, traces, compliance, inventory |
| hooks-edit | Edit Claude Code hook files |
| init | Initialize CLAUDE.md at module/feature root |
| main | Cognitive Steering Framework — health checks and workspace validation |
| main-hooks | Cognitive Steering Framework with enforcement hooks |
| multi-instance-coherence | Coherence across multiple AI instances and concurrent tasks |
| optimize-claude-md | Evidence-based CLAUDE.md optimizer using chat transcripts |
| research | Web research with multiple providers |
| s | Exploratory strategy with multi-persona brainstorming |
| search | Unified local search (CKS, CHS, code, docs, skills) |
| ship | Deploy readiness and runtime snapshot |
| task | Task list orchestration |
| team | Multi-agent task coordination for parallel sessions |
| track | Work-in-progress tracking across terminals and sessions |
| usm | Skill and plugin discovery, installation, and sync across AI tools |

## Artifacts Convention

All runtime artifacts write to:



Skills MUST NOT write state to their own directory or to the package root.

## Installation

Skills surfaced via junctions in .claude/skills/.
