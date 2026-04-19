# System Overview Diagrams & GitHub Pages (Detailed Reference)

## System Overview Diagrams (GitHub-First Mermaid)

**Objective**: Generate editable Mermaid architecture flowcharts that render cleanly on GitHub.

**When**: Runs automatically after NotebookLM media generation.

**What this does**:
- Creates plain Mermaid flowcharts for the README and optional supporting docs
- Generates a high-level system overview and workflow diagram
- Outputs source diagrams to `docs/diagrams/` for easy editing and git tracking
- Embeds the GitHub-safe overview directly in `README.md`

### GitHub Compatibility Rules (Mandatory)

- Target **GitHub's Mermaid renderer**, not Mermaid Live's broader feature set
- Prefer `graph TB` or `flowchart TB` system-overview diagrams for README embedding
- Keep labels short and structural: phases, systems, outputs, decisions
- Do **not** use Mermaid C4 blocks (`C4Context`, `C4Container`, `C4Component`) in GitHub-facing README sections
- Do **not** emit `UpdateLayoutConfig(...)`, `include:`, or malformed init closers like `%%%`
- If technical C4 diagrams are still useful, keep them as optional secondary docs

### Diagram Types Generated

| Diagram | Purpose | Output File | Style |
|---------|---------|-------------|-------|
| **System Overview** | High-level architecture and outputs | `docs/diagrams/system_overview.mmd` | Mermaid flowchart |
| **Workflow** | Phase-by-phase pipeline view | `docs/diagrams/workflow.mmd` | Mermaid flowchart |

### Banned Patterns (scan before finishing)

Scan `README.md` and `docs/diagrams/*.mmd` for:
- `C4Context`, `C4Container`, `C4Component`
- `System_Bnd`, `Container_Bnd`, `Component_Bnd`
- `UpdateLayoutConfig`, `include:`, `%%%`

### Comparison: Mermaid vs NotebookLM Diagrams

| Aspect | Mermaid Diagrams | NotebookLM Diagrams |
|--------|-----------------|---------------------|
| **Format** | Text (`.mmd` files) | Images (`.png`) |
| **Version control** | Git-diff friendly | Binary changes |
| **Editability** | Text editor | Regenerate only |
| **Renderers** | GitHub, VS Code, Mermaid Live | Image viewers |
| **Best for** | Technical documentation, architecture specs | Social preview, quick visuals |
| **Location** | `docs/diagrams/` | `assets/infographics/` |

## GitHub Pages Video Player

**Objective**: Generate a single-purpose HTML page for browser playback of the explainer video.

**When**: Runs after the explainer video is generated.

**Generated asset:**

| Asset | Purpose | Format | Output |
|-------|---------|--------|--------|
| **Video player page** | Browser playback for the README video link | HTML | `docs/video.html` |

**Integration with README.md:**

```markdown
[![Watch the demo with audio](assets/videos/{{package_name}}_video_poster.png)](https://{{github_username}}.github.io/{{package_name}}/docs/video.html)
```

**Rules:**
- Do not create extra GitHub Pages docs unless explicitly asked
- Keep GitHub as the source of truth for technical documentation
- Use GitHub Pages only to solve the inline video playback limitation

## Code Flow Diagrams (On-Demand)

**For function-level visualization**, use `/code-flow-visualizer` separately:

```bash
/code-flow-visualizer path/to/file.py function_name
/code-flow-visualizer path/to/file.py  # auto-detect
```

**When to use:**
- Documenting complex algorithm logic
- Explaining code flow in pull requests
- Creating onboarding diagrams
- Analyzing unfamiliar codebases

**Note:** Not automatically invoked by `/package` - use on-demand for specific files.

## GitHub Slide Deck Integration

**Recommended approach:**
1. Keep the published slide deck in `assets/slides/` as PDF
2. Make the PDF the first and most prominent slide link in `README.md`
3. Use a slide preview image that links directly to the PDF
4. Prefer pattern: `View Slides (PDF)`, then `Download PDF`

| Format | Best For | GitHub Integration |
|--------|----------|-------------------|
| **PDF** | Primary viewing format on GitHub | `[View Slides (PDF)](assets/slides/{package}_slides.pdf)` |
