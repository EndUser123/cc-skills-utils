# cc-skills-utils

Utility skills for Claude Code — discovery, git operations, hooks, session management, and general tooling.

## Skills (49)

| Skill | Purpose |
|-------|---------|
| ask | First-tool coherence (v3.5): /ask is a router — its first substantive |
| chs | Chat History Search (/chs) |
| cks-usage | CKS Proper Usage Enforcement |
| cleanup | /cleanup - Directory Structure Cleanup |
| clear_restore | /clear_restore - Remove Context Restoration File |
| context-status | Context Status |
| daemon | /daemon - Semantic Daemon Management |
| discover | First-tool coherence (v3.5): /discover is for codebase exploration. |
| exec | /exec — CWO15 Execution Entry (Context-Aware) |
| explore | Explore (`/explore`) |
| file-relocation-recovery | Purpose |
| git | Git: Multi-Repo Sync + Worktree Management |
| git-conventional-commits | Conventional Commits for CSF NIP |
| gitbatch | /gitbatch — Batch Skill Execution (Agent-Based) |
| github-ready | /github-ready -- Universal Package Creator & Portfolio Polisher v5.13.0 |
| gitingest | gitingest |
| gitready | /gitready - Universal Package Creator and Portfolio Polisher v5.20.0 |
| handoff | Handoff - Enhanced Session Continuity and Handover System |
| health-monitor | Health Monitor Skill |
| hook-audit | /hook-audit - Hook Behavioral Compliance Monitoring |
| hook-inventory | /hook-inventory - Hook File Inventory Audit |
| hook-obs | /hook-obs - Hook Observability |
| hooks-edit | hooks-edit Skill |
| init | /init — Initialize CLAUDE.md |
| main | Main Cognitive Steering Framework |
| main-hooks | Main Cognitive Steering Framework (Hooks Mode) |
| memory-integration | Memory Integration |
| multi-instance-coherence | Purpose |
| optimize-claude-md | /optimize-claude-md - Evidence-Based CLAUDE.md Optimizer |
| push | /push - Fast Push |
| reports | Report Manager |
| research | Research Skill |
| restore | Restore CKS Checkpoint |
| s | /s - Strategy |
| sar-help | SAR Help |
| sar-inst | SAR Implementation |
| scratchpad | /scratchpad - Scratchpad Worktrees |
| search | Unified Search |
| serena | Serena API - Semantic Code Analysis |
| session | /session - Session Management CLI |
| sharing-skills | Sharing Skills - Meta-Skill |
| ship | /ship – Deploy Readiness & Runtime Snapshot |
| task | /task - Task Orchestration |
| task-unresolved | /task-unresolved |
| team | /team - Multi-Agent Task Coordination |
| telemetry | Telemetry Service |
| timeline | Timeline |
| track | /track — Work Thread Tracker |
| universal-skills-manager | Universal Skills Manager |

## Artifacts Convention

All runtime artifacts write to:



 from  env var (falls back to ).

Skills MUST NOT write state to their own directory or to the package root.

## Installation

Skills surfaced via junctions in :



Command frontends live in .
