# Marketplace Data Update Guide

Procedures for updating `resources/marketplace-data.json` and the comparison dashboard.

## Live Update Procedure

Triggered when user asks to "update the marketplace comparison page".

### 1. Query All Live Sources (in parallel)

- SkillsMP: `curl -s "https://skillsmp.com/api/v1/skills/search?q=*&limit=1" -H "User-Agent: Universal-Skills-Manager"` -- extract `pagination.total`
- SkillHub: `curl -s "https://skills.palebluedot.live/api/skills?limit=1" -H "User-Agent: Universal-Skills-Manager"` -- extract `pagination.total`
- ClawHub: `curl -s "https://clawhub.ai/api/v1/skills?limit=1" -H "User-Agent: Universal-Skills-Manager"` -- extract `pagination.total`
- skillsdirectory.com: Web fetch the main page -- extract skill counts from displayed stats
- claudemarketplaces.com: Web fetch -- extract total from displayed counts
- claude-plugins-official: GitHub API `GET /repos/anthropics/claude-plugins-official/contents/marketplace.json` -- count entries
- ComposioHQ/awesome-claude-skills: GitHub API `GET /repos/ComposioHQ/awesome-claude-skills/contents` -- count files
- GitHub stars: `GET /repos/ComposioHQ/awesome-claude-skills` -- extract `stargazers_count`

### 2. Reconcile Against Existing Data

For each source, compare new value vs. `marketplace-data.json`. If a source is unreachable, preserve the last-known value and flag it in the output (do not zero out missing data).

### 3. Update marketplace-data.json

Write the new `lastUpdated`, updated `sources[]` entries, and recalculated `totals{}` and `securityGrades{}`.

### 4. Update the HTML Template

Copy the `sources[]` and `securityGrades{}` into the inline `const DATA` block in `resources/marketplace-comparison/index.html`.

### 5. Report

Show a diff-style summary of what changed vs. the last update.
