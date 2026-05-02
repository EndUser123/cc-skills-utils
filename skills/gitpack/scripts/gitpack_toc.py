#!/usr/bin/env python3
"""Prepend a structured TOC/index to an aid distillation output."""

import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def extract_files(content: str) -> list[tuple[str, str]]:
    """Extract (filepath, description) pairs from aid output.

    Each file in aid output looks like:
        ### P:\\path\\to\\file.py

        ```python
        ...code...
        ```
    """
    pattern = r"^### (.+?\.(?:py|ts|js|go|rs|java|cs|kt|cpp|c|h|php|rb|swift))$"
    files: list[tuple[str, str]] = []
    for line in content.splitlines():
        m = re.match(pattern, line.strip())
        if m:
            filepath = m.group(1).strip()
            # Build a description from the first non-empty line after the header
            files.append((filepath, _describe_file(filepath)))
    return files


def _describe_file(filepath: str) -> str:
    """Infer a brief description from the filepath."""
    name = Path(filepath).stem
    parts = filepath.split("\\")[-1].split("/")[-2:]
    if name in ("__init__", "index", "main"):
        return f"Package: {parts[0]}" if len(parts) > 1 else filepath
    return name.replace("_", " ").replace("-", " ")


def group_by_dir(files: list[tuple[str, str]]) -> dict[str, list[str]]:
    """Group files by top-level directory."""
    groups: dict[str, list[str]] = {}
    for filepath, desc in files:
        parts = filepath.replace("\\", "/").split("/")
        top = parts[0] if parts else filepath
        groups.setdefault(top, []).append(filepath)
    return groups


def build_toc(files: list[tuple[str, str]], dirname: str, mode: str) -> str:
    """Build the TOC section."""
    groups = group_by_dir(files)
    total = len(files)

    lines = [
        f"# {dirname} — LLM-READY PACK",
        "",
        "<!-- TOC is prepended by gitpack_toc.py -->",
        "",
        "## PACK INFO",
        f"- **Files:** {total} files distilled",
        f"- **Mode:** {mode}",
        f"- **Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## HOW TO USE THIS PACK",
        "",
        "This file is organized by directory. Use your LLM's search or jump-to-section",
        "to find the relevant code. Each `### path/to/file.py` header is a jump anchor.",
        "",
        "For token efficiency: read only the sections relevant to your task.",
        "",
        "## DIRECTORY INDEX",
        "",
        "| Directory | Files |",
        "|---------|-------|",
    ]

    for dir_name in sorted(groups.keys()):
        lines.append(f"| `{dir_name}/` | {len(groups[dir_name])} |")

    lines += [
        "",
        "## FILE INDEX",
        "",
        "| File | Description |",
        "|------|-------------|",
    ]

    for filepath, desc in sorted(files, key=lambda x: x[0]):
        lines.append(f"| `{filepath}` | {desc} |")

    lines += [
        "",
        "---",
        "",
    ]

    return "\n".join(lines)


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: gitpack_toc.py <aid_output.md> <dirname> [mode]", file=sys.stderr)
        sys.exit(1)

    aid_output = Path(sys.argv[1])
    dirname = sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) > 3 else "full fidelity"

    content = aid_output.read_text(encoding="utf-8")
    files = extract_files(content)

    if not files:
        print("WARNING: No files found in aid output — TOC may be empty", file=sys.stderr)
        toc = build_toc([], dirname, mode)
    else:
        toc = build_toc(files, dirname, mode)

    # Prepend TOC to content
    new_content = toc + "\n" + content

    aid_output.write_text(new_content, encoding="utf-8")

    total = len(files)
    print(f"TOC prepended: {total} files indexed in {len(content)} chars of content")


if __name__ == "__main__":
    main()
