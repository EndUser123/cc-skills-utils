# Structure & Templates Reference (PHASE 2 + PHASE 3)

## PHASE 2: Build Structure - Directory Layouts

### Claude Skill Structure (`PACKAGE_TYPE=claude-skill`)

```
{{TARGET_DIR}}/
├── skill/                     # Single source of truth
│   ├── SKILL.md              # Skill definition
│   ├── resources/            # Templates, configs
│   ├── scripts/              # Hook scripts, utility scripts
│   ├── tests/                # Test suite (optional)
│   └── *.py                  # Python modules (if any)
├── README.md
├── LICENSE
└── .gitignore
```

**IMPORTANT**: Claude skills do NOT need `pyproject.toml`. Distributed via junctions (Windows) or symlinks (macOS/Linux).

### Claude Code Plugin Structure (`PACKAGE_TYPE=claude-plugin`)

```
{{TARGET_DIR}}/
├── .claude-plugin/            # Plugin metadata
│   └── plugin.json            # Minimal manifest
├── commands/                  # OPTIONAL: Slash commands (.md files)
├── agents/                    # OPTIONAL: Subagents (.md files)
├── skills/                    # OPTIONAL: Auto-activating skills
│   └── skill-name/
│       └── SKILL.md
├── hooks/
│   └── hooks.json             # Hook configuration
├── core/                      # Python code
│   ├── __init__.py
│   ├── main.py
│   └── utils/
├── scripts/                   # OPTIONAL: Helper scripts
├── tests/
├── .gitignore
├── README.md
└── LICENSE
```

**With MCP server**, also add:
- `.mcp.json` - MCP server config (NOT mcp/ directory)

### Plugin Configuration Files

**`.claude-plugin/plugin.json`:**
```json
{
  "name": "{{package_name}}",
  "description": "{{DESCRIPTION}}",
  "author": {
    "name": "{{AUTHOR_NAME}}",
    "email": "{{AUTHOR_EMAIL}}"
  }
}
```

**`hooks/hooks.json`:**
```json
{
  "{{HOOK_POINT}}": [{
    "matcher": ".*",
    "hooks": [{
      "type": "command",
      "command": "python CLAUDE_PLUGIN_ROOT/core/main.py"
    }]
  }]
}
```

**`.mcp.json`** (if HAS_MCP_SERVER):
```json
{
  "{{package_name}}": {
    "command": "python",
    "args": ["-m", "core.mcp.server"]
  }
}
```

### Python Library Structure (`PACKAGE_TYPE=python-library`)

```
{{TARGET_DIR}}/
├── src/
│   └── {{NAME}}/
│       └── __init__.py
├── tests/
│   └── __init__.py
├── pyproject.toml
├── README.md
├── LICENSE
├── CONTRIBUTING.md
└── SECURITY.md
```

## PHASE 3: README Templates

### README Structure Contract

**Required top-level README order:**
1. Project title, badges, and one-paragraph overview
2. `Quick Start`
3. `Explainer Video`
4. `What {{package_name}} Does`
5. `Development and Deployment`
6. `Additional Media Assets`
7. Lower-priority reference sections

**Rules:**
- Put the explainer video immediately after `Quick Start`
- Generate `docs/video.html` for GitHub Pages by default
- Do not generate extra Pages docs unless explicitly asked
- Link the README poster image to the GitHub Pages player page

### README Template for Claude Code Plugins

Include the "Three Deployment Models" section in every generated README.md. See `references/deployment-models.md` for the full template.

**Skill naming note:**
- The junction NAME should match the skill directory name in the package
- The skill's **aliases** in the frontmatter determine what users type to invoke it

### Media Assets Section Template

**After media generation completes (PHASE 4.7), add after `Development and Deployment`:**

```markdown
## Explainer Video

[![Watch the demo with audio](assets/videos/{{package_name}}_video_poster.png)](https://{{github_username}}.github.io/{{package_name}}/docs/video.html)

> **[Watch the explainer in the browser](https://{{github_username}}.github.io/{{package_name}}/docs/video.html)**
> **[Download the MP4 directly](https://github.com/{{github_username}}/{{package_name}}/releases/download/media/{{package_name}}_explainer_pbs.mp4)**
> *Browser playback requires GitHub Pages to be enabled for this repository.*

## Additional Media Assets

### Architecture Flowchart

graph TB with Mermaid showing: Detect -> Type -> Structure -> Polish -> Output

### Presentation Slides

[![Slide deck preview](assets/slides/{{package_name}}_slides_preview.png)](assets/slides/{{package_name}}_slides.pdf)
```

**Media layout rules:**
- **Images**: Use standard markdown `![alt](path)` syntax
- **Videos**: Link a verified still frame to GitHub Pages player page
- **PDFs**: Use direct markdown links - opens in GitHub's built-in PDF viewer
- **Badges**: Use shields.io badges for visual appeal
- **GitHub Pages**: Enable Pages from `main` root
- **Durations**: Never hardcode video runtimes - measure or omit

**For brownfield conversions**: See `references/brownfield-conversion.md` for README update instructions.

## PHASE 2 Build Steps

### For Claude Skills
1. Create directory structure: `mkdir -p {{TARGET_DIR}}/skill`
2. Generate README.md (see templates above)
3. Create LICENSE (MIT by default)
4. Create `scripts/install-dev.bat` (Windows junction automation)

### For Claude Code Plugins
1. Create directories: `.claude-plugin/`, `core/`, `hooks/`, `tests/`
2. Create `.claude-plugin/plugin.json`
3. Create `hooks/hooks.json` (if needed)
4. Create `.mcp.json` (if MCP server)
5. Create `core/__init__.py`
6. Create `.gitignore`
7. Generate README.md
8. Create LICENSE (MIT)

### For Python Libraries
1. Create directories: `src/{{NAME}}/`, `tests/`
2. Generate README.md
3. Create LICENSE (MIT)
4. Create pyproject.toml
5. Create CONTRIBUTING.md
6. Create SECURITY.md
