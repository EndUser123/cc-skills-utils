# cc-skills-utils

Utility skills for Claude Code — discovery, git operations, hooks, and general tooling.

## Skills (34)

| Skill | Purpose |
|-------|---------|
| aid | AI Distiller — code analysis and distillation |
| ask | Ask skill — question answering |
| bf | Brainstorming engine |
| chs | Context-aware hint system |
| cks-usage | CKS usage tracker |
| cleanup | Directory structure violation cleanup |
| context-status | Session context status reporter |
| context7 | Context management via Context7 |
| crawl | Web content crawler |
| data-safety-vcs | Data safety and version control |
| discover | Discover skills and capabilities |
| explore | Unified local + web search |
| git | Git operations wrapper |
| gitbatch | Batch skill application via subagents |
| gitingest | Git data ingestion |
| gitpack | Git packaging and distribution |
| hooks-edit | Hook editing utilities |
| hook-obs | Hook observation and monitoring |
| init | Initialization skill |
| main | Main utility hub |
| main-hooks | Main hooks management |
| multi-instance-coherence | Multi-instance coordination |
| optimize-claude-md | CLAUDE.md optimization |
| recover | Recovery and restoration |
| repomix | Repository mixing and sampling |
| research | Research skill |
| search | Search across code and docs |
| ship | Shipping workflow |
| snapshot | Snapshot and state management |
| s | Strategy engine — multi-persona brainstorming |
| task | Task management |
| team | Team coordination |
| tilldone | Till-done workflow |
| usm | Unified skill management |

## Artifacts Convention

All runtime artifacts write to `P:/.claude/.artifacts/<terminal_id>/` (falls back to session dir).

Skills MUST NOT write state to their own directory or to the package root.

## Installation

Skills surfaced via junctions in `P:/packages/.claude-marketplace/plugins/cc-skills-utils/`.