---
name: repomix
version: "1.0.0"
status: "stable"
category: integration
enforcement: advisory
description: Pack repository contents into AI-friendly formats (XML, Markdown, JSON, plain text) for LLM context.
workflow_steps:
  - pack_repository
  - configure_output
  - optional_skill_generation
triggers:
  - /repomix
---

# repomix

**Goal:** Pack repository contents into a single AI-friendly file for LLM context.

**Prerequisites:** `repomix` installed globally via `npm install -g repomix` or `pip install repomix`.

---

## Usage

```bash
# Basic usage — pack current directory
repomix

# Pack specific directory
repomix /path/to/repo

# Output to custom file
repomix -o output.xml

# Markdown output (most readable for LLMs)
repomix --style markdown

# Include git diffs and logs
repomix --include-diffs --include-logs

# Show only summary, no file contents
repomix --no-files

# Copy to clipboard
repomix --copy

# Output to stdout (pipe to LLM)
repomix --stdout > output.txt
```

---

## Output Formats

| Style | Use Case |
|-------|----------|
| `xml` | Default, structured parsing |
| `markdown` | Human-readable, most common |
| `json` | Structured data, tooling |
| `plain` | Raw text, minimal overhead |

---

## Key Options

### File Selection
- `--include <patterns>` — Include only matching files (glob patterns, comma-separated)
- `-i, --ignore <patterns>` — Exclude matching files
- `--top-files-len <N>` — Number of largest files to show in summary (default: 5)

### Output Control
- `--style <type>` — Output format (xml, markdown, json, plain)
- `-o, --output <file>` — Output file path
- `--compress` — Extract essential code structure only (classes, functions, interfaces) using Tree-sitter
- `--split-output <size>` — Split into multiple files (e.g., 500kb, 2mb)

### Git Integration
- `--include-diffs` — Add working tree and staged changes
- `--include-logs` — Add commit history (default: 50 recent commits)
- `--no-git-sort-by-changes` — Don't sort by git change frequency

### Content Filtering
- `--remove-comments` — Strip code comments
- `--remove-empty-lines` — Compact output
- `--truncate-base64` — Truncate long base64 strings

---

## Claude Code Skill Generation

Repomix can generate a SKILL.md for Claude Code:

```bash
repomix --skill --skill-dir /path/to/output
```

This generates:
- `SKILL.md` — Main skill file
- `project-structure.md` — Directory tree with line counts
- `files.md` — All file contents (searchable with `## File: <path>`)
- `tech-stacks.md` — Languages, frameworks, dependencies per package

---

## Examples

### Pack and copy to clipboard
```bash
repomix --style markdown --copy
```

### Pack with custom header
```bash
repomix --style markdown --header-text "My project context" -o context.md
```

### Compress large repo (extract structure only)
```bash
repomix --compress --style markdown -o compressed.md
```

### Git-aware output with diffs
```bash
repomix --style markdown --include-diffs --include-logs -o full-context.md
```

### Pipe directly to LLM
```bash
repomix --style markdown --stdout | cline "Analyze this codebase"
```

---

## Integration with LLMs

**Claude Code:** Use `--skill` flag for Claude-specific output format.

**Other LLMs:** Use `--style markdown` for best readability.

**Token estimation:** Repomix shows token counts per file and total — useful for context window management.

---

## Output Location

Default output: `repomix-output.xml` (or format based on `--style`).

Staging: For pipeline use, redirect to `P:/.staging/`.

---

## References

- Repomix GitHub: https://github.com/yamadashy/repomix
- Repomix docs: https://repomix.com