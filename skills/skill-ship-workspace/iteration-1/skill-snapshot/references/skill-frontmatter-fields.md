---
type: core
load_when: [creation, quality]
priority: mandatory
estimated_lines: 80
---

# SKILL.md Frontmatter Fields

Complete reference for all required and optional frontmatter fields in SKILL.md files.

## Required Fields

All skills MUST include these fields in their YAML frontmatter:

```yaml
---
name: my-skill
description: Brief description (one sentence, <1024 chars)
version: 1.0.0
category: orchestration
triggers:
  - /my-skill
  - "my skill trigger phrase"
aliases:
  - /my-skill
  - /ms
suggest:
  - /related-skill
depends_on_skills: []
workflow_steps:
  - step_one: Description of first workflow step
  - step_two: Description of second workflow step
---
```

## Enforcement Tier (REQUIRED)

**Valid values:** `strict`, `advisory`, `none`

**Purpose:** Determines how strictly the skill's workflow_steps are enforced

```yaml
enforcement: strict  # or 'advisory' or 'none'
```

### Tier Definitions

| Tier | Behavior | When to Use |
|------|----------|-------------|
| `strict` | Blocks on violation | High-stakes skills where bypassing causes significant problems |
| `advisory` | Warns but allows | Low-stakes skills where flexibility is valuable |
| `none` | No enforcement | Skills that don't need workflow enforcement |

### Selection Criteria

**Use `strict` when:**
- Bypassing the skill causes security issues, data loss, or system corruption
- The skill has complex multi-step workflows that must be followed exactly
- Users frequently try to bypass the skill

**Use `advisory` when:**
- The skill provides convenience features but direct tool usage is acceptable
- Blocking would interrupt legitimate workflows
- The skill is primarily for guidance/suggestions

**Use `none` when:**
- The skill is a knowledge skill (no execution workflow)
- The skill is a lightweight utility with no complex workflow

### Examples

```yaml
# High-stakes workflow skill - strict enforcement
enforcement: strict

# Convenience skill - advisory enforcement
enforcement: advisory

# Knowledge skill - no enforcement needed
enforcement: none
```

## Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ✅ | Skill identifier (kebab-case) |
| `description` | string | ✅ | One-sentence description, <1024 chars |
| `version` | string | ✅ | Semantic version (e.g., 1.0.0) |
| `category` | string | ✅ | Skill category (orchestration, analysis, testing, etc.) |
| `triggers` | list | ✅ | Phrases that trigger this skill |
| `aliases` | list | ✅ | Alternative names/shortcuts for this skill |
| `suggest` | list | ✅ | Related skills to suggest |
| `depends_on_skills` | list | ✅ | Skills this skill depends on |
| `workflow_steps` | list | ✅ | Required workflow steps for this skill |
| `enforcement` | string | ✅ | `strict`, `advisory`, or `none` |

## Validation

The `enforcement_tier_validator` hook automatically validates SKILL.md files:

- **Validates**: Enforcement field is present and contains a valid value
- **Default**: If not specified, defaults to `strict` (safer default)
- **Action**: Warns when SKILL.md is written/edited without valid enforcement tier

## Quick Reference

**Quick template for new skills:**

```yaml
---
name: my-new-skill
description: Brief one-sentence description of what this skill does
version: 1.0.0
category: orchestration
triggers:
  - /my-new-skill
  - "my skill trigger phrase"
aliases:
  - /my-new-skill
  - /mns
suggest:
  - /related-skill
depends_on_skills: []
workflow_steps:
  - step_one: Description of first workflow step
  - step_two: Description of second workflow step
enforcement: strict  # Choose: strict, advisory, or none
---
```

## Related Documentation

- **Enforcement Tier System**: `P:/.claude/hooks/CLAUDE.md#enforcement-tier-system-v50---2026-03-18`
- **Skill-Based Hooks**: `P:/.claude/hooks/CLAUDE.md#skill-enforcement-enhancement-v35---2026-03-12`
- **Quality Gates**: `P:/.claude/skills/skill-ship/references/skill-quality-gates.md`
