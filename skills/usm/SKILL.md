---
name: usm
description: "The master coordinator for AI skills and Claude Code plugins. Discovers skills from multiple sources (SkillsMP.com, SkillHub, ClawHub, and skills.sh) and plugins from multiple sources (official marketplace, community directories, and GitHub curations), manages installation, and synchronization across Claude Code, Gemini CLI, Google Anti-Gravity, OpenCode, and other AI tools. Handles User-level (Global) and Project-level (Local) scopes."
version: "1.8.0"
status: stable
category: utility
compatibility: "Requires python3, curl, and network access to skillsmp.com, skills.palebluedot.live, clawhub.ai, skills.sh, claude.com/plugins, claudemarketplaces.com, claude-plugins.dev, buildwithclaude.com, and github.com"
enforcement: advisory
metadata:
  homepage: https://github.com/jacob-bd/universal-skills-manager
  disable-model-invocation: "true"
  requires-bins: "python3, curl"
  primaryEnv: SKILLSMP_API_KEY
---

<!-- Version: 1.8.0 -->

# Universal Skills Manager

Centralized skill and plugin manager for AI tools. Discovers skills from SkillsMP.com, SkillHub, ClawHub, and skills.sh; discovers plugins from official marketplace, community directories, and GitHub curations. Unifies management across Claude Code, Gemini, Anti-Gravity, OpenCode, Cline, Cursor, and more.

## When to Use

- Find or **search** for new skills or plugins
- **Install** a skill or plugin
- **Sync** skills between AI tools
- **Move or copy** skills between scopes (User vs. Project)
- **Package** a skill for claude.ai or Claude Desktop (ZIP upload)

## Supported Ecosystem

| Tool | User Scope (Global) | Project Scope (Local) |
| :--- | :--- | :--- |
| **Claude Code** | `~/.claude/skills/` | `./.claude/skills/` |
| **Gemini CLI** | `~/.gemini/skills/` | `./.gemini/skills/` |
| **Google Anti-Gravity** | `~/.gemini/antigravity/skills/` | `./.antigravity/extensions/` |
| **OpenCode** | `~/.config/opencode/skills/` | `./.opencode/skills/` |
| **OpenClaw** | `~/.openclaw/workspace/skills/` | `./.openclaw/skills/` |
| **OpenAI Codex** | `~/.codex/skills/` | `./.codex/skills/` |
| **block/goose** | `~/.config/goose/skills/` | `./.goose/agents/` |
| **Roo Code** | `~/.roo/skills/` | `./.roo/skills/` |
| **Cursor** | `~/.cursor/skills/` | `./.cursor/skills/` |
| **Cline** | `~/.cline/skills/` | `./.cline/skills/` |

**claude.ai / Claude Desktop:** Upload ZIP via Settings -> Capabilities -> Upload Skill.

**Platform Limitations:**
- **claude.ai:** No outbound network access -- USM cannot function. Package OTHER skills instead.
- **Claude Desktop:** Known bug with custom domain JWT tokens. Use Claude Code CLI instead.

## Skill Sources

| Source | Auth | Search Type | Install From |
|--------|------|-------------|--------------|
| **SkillsMP** | API key (`sk_live_skillsmp_`) | Keyword + AI semantic | `githubUrl` field |
| **SkillHub** | None | Keyword only | `skillPath` + `branch` from detail endpoint |
| **ClawHub** | None | Semantic (vector) + browse | `/file` endpoint (direct hosting) |
| **skills.sh** | None | Keyword only | GitHub raw URL from `source` field |

## Plugin Sources

| Source | Type | Discovery Method |
|--------|------|-----------------|
| Official marketplace | Official | `/plugin marketplace` CLI |
| claudemarketplaces.com | Community | Web search/browse |
| claude-plugins.dev | Community | Web search/browse |
| buildwithclaude.com | Community | Web search/browse |
| skillsdirectory.com | Directory | Web search (36K+ skills) |
| `ComposioHQ/awesome-claude-skills` | GitHub curation | Repo browse |
| `quemsah/awesome-claude-plugins` | GitHub curation | Repo browse |

## Core Capabilities

### 1. Smart Installation & Synchronization

**Trigger:** User asks to install a skill.

**Procedure:**
1. **Identify source** from search result or search available sources by name/ID
2. **Verify repo structure** -- browse GitHub repo to find folder containing `SKILL.md`
3. **Download** using `install_skill.py`:
   ```bash
   python3 ~/.claude/skills/usm/scripts/install_skill.py \
     --url "https://github.com/{owner}/{repo}/tree/{branch}/{skill-folder}" \
     --dest "{target-path}" --dry-run
   ```
   Script handles: atomic install, validation, security scan, update detection.
4. **Determine scope:** Ask Global vs Local. For claude.ai/Desktop target, see Section 6.
5. **Sync check:** Scan for other installed tools, offer to sync.
6. **Execute:** Create directories, run install for each target.
7. **Report:** Show skill name, author, location(s), GitHub URL.

> See `references/install-procedures.md` for source-specific install flows (SkillsMP, SkillHub, ClawHub, skills.sh, Local).

### 2. Updates & Consistency Check

**Trigger:** User modifies a skill or asks to "sync".

1. **Compare** modification times/content across all installed locations.
2. **Report** which is newer.
3. **Offer** to overwrite older versions.

### 3. Language Detection & Translation

**Trigger:** After downloading, before installation.

1. **Detect** non-ASCII characters and language patterns in prose sections.
2. **Ask user:** Translate to English, install as-is, or skip.
3. **Translate** preserving YAML frontmatter and code blocks exactly.

> See `references/translation-guide.md` for detection code and translation quality checks.

### 4. Skill Discovery (Multi-Source)

**Trigger:** User searches for skills.

1. **Discover API key:** Read `~/.claude/skills/usm/config.json` via Read tool (not bash -- PreToolUse hook compatibility). Fallback: `$SKILLSMP_API_KEY` env var.
   - Key validation: Must start with `sk_live_skillsmp_`
   - Security: Never log or display the full API key.
2. **Execute search** based on available sources:

   **SkillsMP (requires key):**
   ```bash
   curl -X GET "https://skillsmp.com/api/v1/skills/ai-search?q={query}" \
     -H "Authorization: Bearer ${API_KEY}" -H "User-Agent: Universal-Skills-Manager"
   ```
   **SkillHub (always available):**
   ```bash
   curl -X GET "https://skills.palebluedot.live/api/skills?q={query}&limit=20" \
     -H "User-Agent: Universal-Skills-Manager"
   ```
   **ClawHub (always available):**
   ```bash
   curl -X GET "https://clawhub.ai/api/v1/search?q={query}&limit=20" \
     -H "User-Agent: Universal-Skills-Manager"
   ```
   **skills.sh (always available):**
   ```bash
   curl -X GET "https://skills.sh/api/search?q={query}&limit=20" \
     -H "User-Agent: Universal-Skills-Manager"
   ```

3. **Display results** in unified table with Source column:
   ```
   | # | Skill | Author | Stars | Source | Description |
   |---|-------|--------|-------|--------|-------------|
   | 1 | debugging-strategies | wshobson | 27,021 | SkillHub | Master systematic debugging... |
   ```

4. **Search all sources** by default (parallel queries). Deduplicate by full skill ID or name.
5. **Offer installation** from selected result.

> See `references/api-reference.md` for full API response formats, pagination, and error handling.

### 5. Skill Matrix Report

**Trigger:** "Show my skills", "What skills do I have?", "Compare my tools".

1. **Detect** installed tools by checking skills directories exist.
2. **Collect** all skill folders across tools.
3. **Generate** matrix table (rows = skills, columns = tools, cells = installed/missing).
4. **Summarize:** Total skills, unique-to-one-tool, installed-everywhere.

### 6. Package for claude.ai / Claude Desktop

**Trigger:** User wants to upload a skill to claude.ai or Claude Desktop.

1. **Validate frontmatter** with `validate_frontmatter.py` -- do this BEFORE packaging.
2. **Collect API key** (optional -- SkillHub/ClawHub work without one).
3. **Create ZIP** with SKILL.md, config.json (if key provided), and scripts/.
4. **Provide upload instructions** and security reminder.

> See `references/packaging-guide.md` for full ZIP creation procedure and credential safety.
> See `references/frontmatter-validation.md` for Agent Skills spec compliance details.

### 7. Plugin Discovery & Installation

**Trigger:** User asks to find or install Claude Code plugins.

1. **Discover** via `/plugin marketplace` CLI, web search, or GitHub curation repos.
2. **Install** via `/plugin install <name>` or `/plugin marketplace add <owner>/<repo>`.
3. **Verify** with `/plugin list`.

**Plugin vs Skill:** Skills = textual SKILL.md files; Plugins = binary packages via `/plugin` CLI. Keep discovery flows separate.

## Operational Rules

1. **Structure integrity:** Skills get their own folder (`.../skills/{name}/`). Always `mkdir -p` first.
2. **Conflict safety:** Always ask before overwriting existing skills.
3. **User-Agent required:** Include `-H "User-Agent: Universal-Skills-Manager"` in ALL curl requests. APIs behind Cloudflare return 403 without it.
4. **OpenClaw note:** May require restart if `skills.load.watch` is not enabled.
5. **Cross-platform adaptation:** Cline reads `.claude/skills/` automatically. Generate manifests for tools that need them.
6. **Security scanning:** Runs on all installs. Our `scan_skill.py` is authoritative regardless of source security scores.

## Guidelines

- **Multi-source search:** Default to searching ALL available sources simultaneously.
- **Semantic search preferred:** Use SkillsMP `/ai-search` or ClawHub `/search` for natural language queries.
- **Source labeling:** Always tag results with source (`[SkillsMP]`, `[SkillHub]`, `[ClawHub]`, `[skills.sh]`, `[Plugin]`).
- **SkillHub detail lookup:** Always fetch detail endpoint first for `skillPath` and `branch`. Never parse `id` as file path.
- **ClawHub direct hosting:** Use `/file` endpoint. No GitHub URL construction needed.
- **Deduplication:** By full skill ID across SkillsMP/SkillHub/skills.sh; by name for ClawHub.
- **Content verification:** Always check for valid YAML frontmatter after download.
- **Plugin install:** Always use `/plugin install` command, never manual file copying.

## Reference Files

| File | Contents |
|------|----------|
| `references/api-reference.md` | Full API response formats, endpoints, pagination, error codes |
| `references/install-procedures.md` | Source-specific install flows (SkillsMP, SkillHub, ClawHub, skills.sh, Local) |
| `references/packaging-guide.md` | ZIP creation, credential safety, upload instructions |
| `references/translation-guide.md` | Language detection code, translation workflow, quality checks |
| `references/frontmatter-validation.md` | Agent Skills spec, validation script usage, manual checks |
| `references/marketplace-update-guide.md` | Marketplace data live update procedure |

## Available Tools

- `bash` (curl): API calls, GitHub browsing, marketplace fetching
- `web_fetch`: Alternative to curl for fetching content
- `read_file` / `write_file`: Manage local skill files
- `glob`: Find existing skills in local directories
