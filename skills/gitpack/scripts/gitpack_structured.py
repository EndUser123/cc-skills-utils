#!/usr/bin/env python3
"""
Build a two-file gitpack output: signatures-only + full implementations.

Workflow:
  1. Run aid --quick  → signatures-only output
  2. python gitpack_structured.py <sig_output.md> <dirname> [target_dir]

Produces two files:
  - <name>_sig.md  — SIGNATURE TOC + DIRECTORY/FILE INDEX (small, scannable)
  - <name>_full.md — same + APPENDIX with full source code read from disk

Source files are read directly from disk for the APPENDIX to avoid aid's
markdown corruption.
"""

import re
import sys
import glob as glob_module
from datetime import datetime, timezone
from pathlib import Path


def parse_aid_output(content: str) -> dict[str, dict[str, str]]:
    """Parse aid output into {filepath: {"sig": "...", "body": "..."}}.

    Each file section looks like:
        ### path/to/file.py

        ```python
        ...code...
        ```
    """
    # Match "### path/to/file.py" at start of line
    file_pattern = re.compile(r"^###\s+(.+?\.\w+)\s*$", re.MULTILINE)

    sections: dict[str, dict[str, str]] = {}
    matches = list(file_pattern.finditer(content))

    for i, m in enumerate(matches):
        filepath = m.group(1).strip()
        # Content starts after the header line
        start = m.end() + 1  # skip the newline
        # End is start of next header, or end of file
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        section_text = content[start:end].strip()
        sections[filepath] = {"raw": section_text}
    return sections


def append_markdown_files(content: str, target_dir: str) -> str:
    """Append markdown files from target directory as additional sections.

    aid does not process .md files, so they must be appended raw after structuring.
    """
    md_files = []
    for pattern in ["*.md", "*.MD"]:
        md_files.extend(glob_module.glob(str(Path(target_dir) / pattern)))

    if not md_files:
        return content

    md_lines = ["", "---", "", "## ADDITIONAL FILES (markdown)"]
    for md_path in sorted(md_files):
        # Skip SKILL.md in subdirectories (only include top-level)
        rel = Path(md_path).resolve().relative_to(Path(target_dir).resolve())
        if len(rel.parts) > 1:
            continue  # skip subdir markdown (likely README in subdir)
        md_lines.append("")
        md_lines.append(f"### {rel}")
        md_lines.append("```markdown")
        try:
            text = Path(md_path).read_text(encoding="utf-8")
            md_lines.append(text)
        except Exception as ex:
            md_lines.append(f"# Error reading file: {ex}")
        md_lines.append("```")

    return content + "\n" + "\n".join(md_lines)


def extract_signature(filepath: str, raw_section: str) -> str:
    """Extract the signature portion from a raw aid section.

    For --quick mode output: section IS the signature - just extract clean code block.
    For full mode: need to extract def/class/async def lines before implementation body.
    """
    lines = raw_section.splitlines()
    sig_lines = []
    in_code = False
    brace_depth = 0
    has_def_lines = False

    # Pre-check: does this look like full mode (has def/class lines)?
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("def ") or stripped.startswith("class ") or stripped.startswith("async def "):
            has_def_lines = True
            break

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            if stripped.startswith("```python") or stripped.startswith("```"):
                in_code = True
            else:
                in_code = False
            continue
        if not in_code:
            continue

        if has_def_lines:
            # Full mode: collect def/class/async def lines + imports
            if any(stripped.startswith(kw) for kw in ["def ", "class ", "async def "]):
                sig_lines.append(line)
            elif stripped.startswith("import ") or stripped.startswith("from "):
                sig_lines.append(line)
            elif sig_lines:
                # Stop at first non-def, non-import, non-annotation after signatures start
                if not stripped.endswith(":") and not stripped.startswith("@") and not stripped.startswith('"""'):
                    # Likely implementation body
                    break
        else:
            # --quick mode: collect all signature lines (look like "func(args) -> type")
            if stripped.startswith("import ") or stripped.startswith("from "):
                continue  # skip imports
            if "(" in stripped or "->" in stripped:
                sig_lines.append(line)

    return "\n".join(sig_lines).strip()


def group_by_dir(files: list[str]) -> dict[str, list[str]]:
    """Group files by top-level directory."""
    groups: dict[str, list[str]] = {}
    for filepath in files:
        parts = filepath.replace("\\", "/").split("/")
        top = parts[0] if parts else filepath
        groups.setdefault(top, []).append(filepath)
    return groups


def _build_header(dirname: str, total: int, mode: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return "\n".join([
        f"# {dirname} — LLM-READY PACK",
        "",
        "<!-- Generated by gitpack_structured.py -->",
        "",
        "## PACK INFO",
        f"- **Files:** {total} files",
        f"- **Mode:** {mode}",
        f"- **Generated:** {stamp}",
        "",
    ])


def _build_toc(sig_sections: dict) -> list[str]:
    lines = ["## SIGNATURE TOC", ""]
    for filepath in sorted(sig_sections):
        sig = extract_signature(filepath, sig_sections.get(filepath, {}).get("raw", ""))
        lines.append(f"### {filepath}")
        lines.append("```python")
        lines.append(sig)
        lines.append("```")
        lines.append("")
    return lines


def _build_indexes(all_files: list[str]) -> tuple[list[str], list[str]]:
    groups = group_by_dir(all_files)
    dir_lines = ["## DIRECTORY INDEX", "", "| Directory | Files |", "|---------|-------|"]
    for dir_name in sorted(groups):
        dir_lines.append(f"| `{dir_name}/` | {len(groups[dir_name])} |")

    file_lines = ["", "## FILE INDEX", "", "| File | Description |", "|------|-------------|"]
    for filepath in sorted(all_files):
        name = Path(filepath).stem
        parts = filepath.replace("\\", "/").split("/")
        if name in ("__init__", "index", "main"):
            desc = f"Package: {parts[0]}" if len(parts) > 1 else filepath
        else:
            desc = name.replace("_", " ").replace("-", " ")
        file_lines.append(f"| `{filepath}` | {desc} |")
    return dir_lines, file_lines


def _lang_for(filepath: str) -> str:
    ext = Path(filepath).suffix.lower()
    return {
        ".py": "python", ".pyw": "python",
        ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
        ".jsx": "typescript", ".ts": "typescript", ".tsx": "typescript",
        ".html": "html", ".htm": "html",
        ".css": "css", ".scss": "css",
        ".sql": "sql",
        ".md": "markdown", ".markdown": "markdown",
        ".yaml": "yaml", ".yml": "yaml",
        ".json": "json",
    }.get(ext, "text")


def _build_appendix(all_files: list[str], full_sections: dict) -> list[str]:
    lines = ["", "---", "", "## APPENDIX: FULL IMPLEMENTATIONS", ""]
    for filepath in sorted(all_files):
        source_path = Path(filepath)
        if source_path.exists():
            raw = source_path.read_text(encoding="utf-8")
        else:
            raw = full_sections.get(filepath, {}).get("raw", f"# {filepath}\n# (not found)")
        lang = _lang_for(filepath)
        lines.append(f"### {filepath}")
        lines.append(f"```{lang}")
        lines.append(raw)
        lines.append("```")
        lines.append("")
    return lines


def build_sig_pack(sig_sections: dict, dirname: str) -> str:
    """Signatures-only pack: TOC + indexes. No implementations."""
    all_files = list(sig_sections.keys())
    total = len(all_files)
    dir_lines, file_lines = _build_indexes(all_files)
    return "\n".join([
        _build_header(dirname, total, "signatures only"),
        "",
        "## HOW TO USE",
        "",
        "This is the signatures-only pack. For full implementations, see the",
        "corresponding `_full.md` file.",
        "",
        "\n".join(_build_toc(sig_sections)),
        "\n".join(dir_lines),
        "\n".join(file_lines),
    ])


def build_full_pack(sig_sections: dict, full_sections: dict, dirname: str) -> str:
    """Full pack: TOC + indexes + appendix with full source."""
    all_files = list(sig_sections.keys())
    total = len(all_files)
    dir_lines, file_lines = _build_indexes(all_files)
    return "\n".join([
        _build_header(dirname, total, "signatures + full appendix"),
        "",
        "## HOW TO USE THIS PACK",
        "",
        "1. **SIGNATURE TOC** — scan all file signatures to find relevant code",
        "2. **FILE INDEX** — jump to specific files by name",
        "3. **APPENDIX: FULL IMPLEMENTATIONS** — read full implementation on demand",
        "",
        "For token efficiency: start with the SIGNATURE TOC, pull full code from",
        "the APPENDIX only when you need the implementation details.",
        "",
        "\n".join(_build_toc(sig_sections)),
        "\n".join(dir_lines),
        "\n".join(file_lines),
        "\n".join(_build_appendix(all_files, full_sections)),
    ])


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: gitpack_structured.py <sig_output.md> <dirname> [target_dir]", file=sys.stderr)
        sys.exit(1)

    sig_path = Path(sys.argv[1])
    dirname = sys.argv[2]
    target_dir = sys.argv[3] if len(sys.argv) > 3 else dirname

    if not sig_path.exists():
        print(f"ERROR: Signature file not found: {sig_path}", file=sys.stderr)
        sys.exit(1)

    sig_content = sig_path.read_text(encoding="utf-8")
    sig_sections = parse_aid_output(sig_content)

    sig_count = len(sig_sections)
    if sig_count == 0:
        print("WARNING: No file signatures found in --quick output", file=sys.stderr)
        sys.exit(1)

    # Derive full pack path: _sig.md → _full.md
    full_path = sig_path.parent / sig_path.name.replace("_sig.", "_full.")

    # Build and write signatures-only pack
    sig_pack = build_sig_pack(sig_sections, dirname)
    sig_pack = append_markdown_files(sig_pack, target_dir)
    sig_path.write_text(sig_pack, encoding="utf-8")

    # Build and write full pack (signatures + appendix)
    full_pack = build_full_pack(sig_sections, {}, dirname)
    full_pack = append_markdown_files(full_pack, target_dir)
    full_path.write_text(full_pack, encoding="utf-8")

    source_reads = sum(1 for f in sig_sections if Path(f).exists())
    print(f"Sig pack:  {sig_path} — {len(sig_pack):,} chars")
    print(f"Full pack: {full_path} — {len(full_pack):,} chars")
    print(f"Files: {sig_count} ({source_reads} from source)")


if __name__ == "__main__":
    main()
