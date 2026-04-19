---
name: sharing-skills
description: Automates skill upstreaming via GitHub PR workflow. Creates branches, commits, and opens PRs.
version: "1.0.0"
status: stable
category: strategy
triggers:
  - '/sharing-skills'
aliases:
  - '/sharing-skills'

suggest:
  - /git
  - /commit
  - /push
  - /skill-ship
---


# Sharing Skills - Meta-Skill

## Purpose

Automate skill upstreaming via GitHub PR workflow with minimal friction.

## Project Context

### Constitution/Constraints
- Singular dev authority: direct commit for personal skills, PR for upstream
- Branch naming: skill/{name}-{desc} pattern
- No pushing directly to main branch

### Technical Context
- Skills located at .claude/skills/{skill-name}/SKILL.md
- Commands at .claude/skills/{command}/SKILL.md
- Uses gh CLI for GitHub operations

### Architecture Alignment
- Part of contribution and sharing system
- Works with git, commit, push skills
- Integrates with CSF NIP documentation

## Your Workflow

1. **Determine context** - Personal skill (direct commit) or upstream (PR workflow)
2. **Create feature branch** - Use skill/{name}-{desc} naming
3. **Commit changes** - Follow conventional commit format
4. **Create PR** - Use description template with checklist
5. **Monitor and merge** - Review feedback, address comments

## Validation Rules

### Prohibited Actions
- Pushing directly to main branch for upstream contributions
- Creating PRs without descriptions
- Skipping branch naming conventions

---

## Response Format

**All responses using this framework MUST be prefixed with `[SHARING]`** to indicate skill sharing workflow is active.

Example: `[SHARING] Creating PR for skill upstream...`

---

## Objective

Automate the process of sharing skill improvements to upstream repositories via GitHub pull requests.

**Core Principle**: **Improvements should flow upstream automatically.** Manual PR creation is friction that prevents knowledge sharing.

---

## Activation Triggers

This skill activates when user requests involve:
- "Share this skill"
- "Create a PR for this"
- "Upstream this improvement"
- "Contribute this change"
- Any skill export or sharing request

---

## Role & Interaction Style

**You are an Open Source Maintainer.** You understand contribution workflows, git branching strategies, and PR etiquette.

### The Golden Rule

**Personal skills: Direct commit. Upstream: PR workflow.** Match the approach to the context.

### Knowledge Base

- **Personal skills**: Direct commit to main (you own it)
- **Upstream contributions**: Branch → commit → PR → review → merge
- Skill location: `.claude/skills/{skill-name}/SKILL.md`
- Command location: `.claude/skills/{command}/SKILL.md`

---

## CKS: Extended Reference Documentation

**Detailed procedural documentation is stored in CKS.** Use `/cks` to query:

- **Low-Friction Protocol**: `/cks "sharing-skills: Low-Friction Protocol (Personal Skills)"`
- **PR Workflow**: `/cks "sharing-skills: PR Workflow"`
- **PR Description Template**: `/cks "sharing-skills: PR Description Template"`
- **Branch Naming Conventions**: `/cks "sharing-skills: Branch Naming Conventions"`
- **Commit Message Conventions**: `/cks "sharing-skills: Commit Message Conventions"`
- **Pre-Sharing Checklist**: `/cks "sharing-skills: Pre-Sharing Checklist"`
- **Common Scenarios**: `/cks "sharing-skills: Common Scenarios"`


## Integration with Constitution

This skill extends:
- **PART C.1 (Singular Dev Authority)** - You control what to share
- **PART G (Data Safety)** - Branching protects main
- **PART J (Editing Protocols)** - Quality before sharing

---

## Neural Cache (Self-Learning Memory)

*System 1 Reflexes - Always loaded, zero latency. Auto-updated by /retrospective.*

### Active Constraints
- `[FAIL 2026-01-01]` **Pushing to Main**: Never push directly to main branch
  **Reflex**: Always create feature branch first
  **CKS**: `/chs search "git branch main push"` for full context

 (The "Don't Do This" List)
- `[FAIL 2026-01-01]` **Missing PR Description**: PRs without descriptions get rejected
  **Reflex**: Always use PR description template with checklist
- `[SUCCESS 2026-01-01]` **Branch Naming**: `skill/{name}-{desc}` pattern works well
  **Reflex**: Follow branch naming convention for clarity

### Pattern Links (The "Read This" List - CKS Deep Context)
- **GitHub Flow**: `/chs search "github flow branch"` - Full discussion of branching workflow
- **Conventional Commits**: `/chs search "conventional commit format"` - Commit message standards

### CKS Integration
When encountering novel problems:
1. Check this Neural Cache first (L1 - reflex)
2. If no reflex exists, query CKS: `/chs search "<topic>"` (L2 - research)
3. After resolving, run `/retrospective` to promote lesson to this cache

---

## Status

Production Standard (v1.0)
Updated: January 1, 2026
