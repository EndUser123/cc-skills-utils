#!/usr/bin/env python3
"""
Build a two-file gitpack output for a codebase: signatures + full source.

No external AI tools required — uses AST parsing (Python) and direct file reads.

Workflow:
  python gitpack.py <target_dir> [--exclude <patterns>]

Produces two files in .aid/<name>/:
  - <name>_sig.md  — SIGNATURE TOC + DIRECTORY/FILE INDEX (compact, scannable)
  - <name>_full.md — same + APPENDIX with full source read from disk

Target dir is processed directly: files discovered via glob, signatures
extracted via AST (Python) or regex (other languages), appendix read
directly from source. Deterministic output.
"""

import ast
import sys
import re
import glob as glob_module
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Signature extraction — Python
# ---------------------------------------------------------------------------

def extract_py_signatures(filepath: str) -> list[str]:
    """Extract function/class signatures from a Python file via AST."""
    try:
        source = Path(filepath).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError:
        return _fallback_signature_extraction(source)

    lines_by_node: dict[int, str] = {}
    signatures: list[str] = []

    class SignatureExtractor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            lines_by_node[node.lineno] = _format_func(node.name, node.args, source, node.lineno)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            lines_by_node[node.lineno] = f"async {_format_func(node.name, node.args, source, node.lineno)}"
            self.generic_visit(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            lines_by_node[node.lineno] = f"class {node.name}"
            self.generic_visit(node)

    SignatureExtractor().visit(tree)

    for lineno in sorted(lines_by_node):
        signatures.append(lines_by_node[lineno])

    return signatures


def _format_func(name: str, args: ast.arguments, source: str, lineno: int) -> str:
    """Format a function signature from AST args + any type annotations on the def line."""
    arg_parts = []
    for arg in args.args:
        ann = arg.annotation
        if ann:
            ann_str = _get_annotation_str(ann, source)
            arg_parts.append(f"{arg.arg}: {ann_str}")
        else:
            arg_parts.append(arg.arg)

    if args.vararg:
        arg_parts.append(f"*{args.vararg.arg}")
    if args.kwarg:
        arg_parts.append(f"**{args.kwarg.arg}")

    return_annotation = _get_function_return_annotation(source, lineno)

    sig = f"{name}({', '.join(arg_parts)})"
    if return_annotation:
        sig += f" -> {return_annotation}"
    return sig


def _get_annotation_str(ann: ast.expr, source: str) -> str:
    """Get the string representation of an annotation from the source."""
    if isinstance(ann, ast.Name):
        return ann.id
    elif isinstance(ann, ast.Attribute):
        parts = []
        node = ann
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
        return ".".join(reversed(parts))
    elif isinstance(ann, ast.Subscript):
        base = _get_annotation_str(ann.value, source)
        if ann.slice:
            slice_str = _get_annotation_str(ann.slice, source)
            return f"{base}[{slice_str}]"
        return base
    elif isinstance(ann, ast.Constant):
        return repr(ann.value)
    elif isinstance(ann, ast.BinOp):
        left = _get_annotation_str(ann.left, source)
        right = _get_annotation_str(ann.right, source)
        return f"{left} | {right}"
    return "Any"


def _get_function_return_annotation(source: str, lineno: int) -> str:
    """Check the def line for a return type annotation."""
    lines = source.splitlines()
    if lineno < 1 or lineno > len(lines):
        return ""
    line = lines[lineno - 1].strip()
    m = re.search(r"->\s*([\w\[\]\|\s.,]+)\s*:\s*$", line)
    if m:
        return m.group(1).strip()
    return ""


def _fallback_signature_extraction(source: str) -> list[str]:
    """Fallback when AST parsing fails — use regex on lines."""
    sigs: list[str] = []
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("def ") or stripped.startswith("async def ") or stripped.startswith("class "):
            if not stripped.startswith("class "):
                m = re.match(r"(async\s+)?def\s+(\w+)\(.*\)(?:\s*->\s*[^\s:]+)?\s*:", stripped)
                if m:
                    sigs.append(stripped.rstrip(":"))
            else:
                m = re.match(r"class\s+(\w+).*", stripped)
                if m:
                    sigs.append(stripped.rstrip(":"))
    return sigs


# ---------------------------------------------------------------------------
# Signature extraction — generic (non-Python)
# ---------------------------------------------------------------------------

def _remove_fenced_blocks(source: str) -> str:
    """Strip triple-backtick fenced code blocks from source before pattern matching."""
    return re.sub(r"```[^\n]*\n[\s\S]*?```", "", source)


def _get_lang_schema(lang: str) -> str:
    """Return the appropriate regex pattern for a given language."""
    # (?m) must not appear inline — MULTILINE flag is passed at compile time
    schemas = {
        "markdown": (
            r"^#{1,6}\s+(.+)$|"  # headings
            r"^---+\s*$|"           # frontmatter separator
            r"^```\s*$|"            # code fence start
            r"^[ \t]*-[ \t]+(.+)$|"  # YAML list items (indented - key value)
            r"^\w[\w-]*:\s+(?!\s*$)"  # YAML keys (non-empty value)
        ),
        "javascript": (
            r"^(export\s+(default\s+)?(const|let|var|function|async\s+function|class))|"
            r"^(const|let|var)\s+(\w+)\s*=|"
            r"^function\s+(\w+)|"
            r"^async\s+function\s+(\w+)|"
            r"^class\s+(\w+)|"
            r"^export\s+\{[^}]+\}|"
            r"^import\s+.*from\s+['\"]"
        ),
        "typescript": (
            r"^(export\s+(default\s+)?(const|let|var|function|async\s+function|class|interface|type))|"
            r"^(const|let|var)\s+(\w+)\s*:|"
            r"^function\s+(\w+)|"
            r"^async\s+function\s+(\w+)|"
            r"^class\s+(\w+)|"
            r"^interface\s+(\w+)|"
            r"^type\s+(\w+)|"
            r"^export\s+\{[^}]+\}|"
            r"^import\s+.*from\s+['\"]"
        ),
        "html": (
            r"^<!--[\s\S]*?-->|"      # comments
            r"^<script[\s>]|"
            r"^<style[\s>]|"
            r"^<([a-z]+)[\s>]"
        ),
        "css": (
            r"^@[a-z-]+|"             # at-rules
            r"^[.#]?[a-z][\w-]*\s*\{|"
            r"^[a-z][\w-]*\s*:[^;]+;"
        ),
        "sql": (
            r"^(CREATE|ALTER|DROP|SELECT|INSERT|UPDATE|DELETE|FROM|WHERE|JOIN)\s+|"
            r"^(TABLE|VIEW|INDEX|PROCEDURE|FUNCTION|TRIGGER)\s+(\w+)|"
            r"^--"
        ),
        "yaml": (
            r"^[\w-]+:\s*(?!\s*$)"
        ),
        "json": (
            r"^\s*\"[^\"]+\"\s*:"
        ),
        "default": (
            r"^(def|class|function|const|let|var|public\s+static|private\s+static)\s+\w+|"
            r"^(export|import)\s+"
        ),
    }
    return schemas.get(lang.lower(), schemas["default"])


def extract_generic_signatures(filepath: str, lang: str = "default") -> list[str]:
    """Extract top-level signatures from a non-Python file via regex."""
    try:
        source = Path(filepath).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    if lang.lower() == "markdown":
        source = _remove_fenced_blocks(source)

    pattern = _get_lang_schema(lang)
    sigs: list[str] = []
    seen: set[str] = set()

    compiled = re.compile(pattern, re.MULTILINE)
    for match in compiled.finditer(source):
        line = source[:match.start()].count("\n") + 1
        line_text = source.splitlines()[line - 1].strip() if line <= len(source.splitlines()) else ""
        if line_text and line_text not in seen and len(sigs) < 100:
            seen.add(line_text)
            sigs.append(line_text)

    return sigs


def extract_signatures(filepath: str) -> list[str]:
    """Dispatch to the correct signature extractor based on file extension."""
    ext = Path(filepath).suffix.lower()
    lang_map = {
        ".py": "python",
        ".pyw": "python",
        ".js": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        ".jsx": "typescript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".html": "html",
        ".htm": "html",
        ".css": "css",
        ".scss": "css",
        ".sql": "sql",
        ".md": "markdown",
        ".markdown": "markdown",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
    }
    lang = lang_map.get(ext, "default")
    if lang == "python":
        return extract_py_signatures(filepath)
    return extract_generic_signatures(filepath, lang)


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

DEFAULT_EXCLUDES = [
    "__pycache__", "*.pyc", "*.pyo", "*.so", "*.dll", "*.exe",
    ".venv", "venv", "env", "site-packages",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox",
    ".git", ".hg", ".svn",
    "dist", "build", "out", "target", "egg-info",
    ".idea", ".vscode", ".DS_Store", "Thumbs.db",
    ".env", ".env.", "*.log", "*.min.js",
    "node_modules",
]

EXTENSIONS = ["*.py", "*.pyw", "*.js", "*.mjs", "*.cjs", "*.jsx", "*.ts", "*.tsx",
              "*.html", "*.htm", "*.css", "*.scss", "*.sql", "*.md", "*.markdown",
              "*.yaml", "*.yml", "*.json"]


def discover_files(target_dir: Path, exclude_patterns: str = "") -> list[str]:
    """Find all supported files in target_dir, excluding patterns."""
    patterns = DEFAULT_EXCLUDES + [p.strip() for p in exclude_patterns.split(",") if p.strip()]

    def is_excluded(path: Path) -> bool:
        path_str = str(path)
        for pattern in patterns:
            if pattern in path_str:
                return True
        return False

    # Track visited (device, inode) pairs to prevent symlink loops
    seen_inodes: set[tuple[int, int]] = set()

    files: list[str] = []
    for pattern in EXTENSIONS:
        for p in target_dir.glob(pattern):
            if is_excluded(p) or p.name.startswith("."):
                continue
            if p.is_symlink():
                continue
            if not p.is_file():
                continue
            try:
                stat = p.stat()
                inode_key = (stat.st_dev, stat.st_ino)
                if inode_key in seen_inodes:
                    continue
                seen_inodes.add(inode_key)
            except OSError:
                continue
            resolved = p.resolve()
            # Skip files that resolve outside target_dir (symlinks to other trees)
            try:
                resolved.relative_to(target_dir.resolve())
            except ValueError:
                continue
            files.append(str(resolved))

    return sorted(files)


# ---------------------------------------------------------------------------
# Markdown building
# ---------------------------------------------------------------------------

LANG_LABEL = {
    ".py": "python", ".pyw": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".jsx": "typescript", ".ts": "typescript", ".tsx": "typescript",
    ".html": "html", ".htm": "html",
    ".css": "css", ".scss": "css",
    ".sql": "sql",
    ".md": "markdown", ".markdown": "markdown",
    ".yaml": "yaml", ".yml": "yaml",
    ".json": "json",
}


def build_signatures_section(filepaths: list[str]) -> list[str]:
    lines = ["## SIGNATURE TOC", ""]
    for fp in filepaths:
        sigs = extract_signatures(fp)
        ext = Path(fp).suffix.lower()
        lang = LANG_LABEL.get(ext, "text")
        lines.append(f"### {fp}")
        lines.append(f"```{lang}")
        if sigs:
            lines.extend(sigs)
        else:
            lines.append("# (no public definitions)")
        lines.append("```")
        lines.append("")
    return lines


def group_by_dir(files: list[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for filepath in files:
        parts = filepath.replace("\\", "/").split("/")
        top = parts[-2] if len(parts) > 1 else parts[0] if parts else filepath
        groups.setdefault(top, []).append(filepath)
    return groups


def build_directory_index(files: list[str]) -> list[str]:
    groups = group_by_dir(files)
    lines = ["## DIRECTORY INDEX", "", "| Directory | Files |", "|---------|-------|"]
    for dir_name in sorted(groups):
        lines.append(f"| `{dir_name}/` | {len(groups[dir_name])} |")
    return lines


def build_tree(filepaths: list[str], target_dir: Path) -> list[str]:
    """Build a visual directory tree with file counts per folder."""
    tree: dict = {}
    for fp in filepaths:
        rel = Path(fp).relative_to(target_dir)
        parts = rel.parts
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = None

    def count_leaves(d: dict) -> int:
        return sum(1 if v is None else count_leaves(v) for v in d.values())

    total = count_leaves(tree)
    lines: list[str] = [f"{target_dir.name}/ ({total} files)"]
    MAX = 200
    truncated = False

    def render(d: dict, prefix: str) -> None:
        nonlocal truncated
        if truncated:
            return
        dirs = sorted([(k, v) for k, v in d.items() if isinstance(v, dict)])
        files = sorted([k for k, v in d.items() if v is None])
        items = [(n, v) for n, v in dirs] + [(f, None) for f in files]

        for i, (name, children) in enumerate(items):
            if len(lines) >= MAX:
                remaining = len(items) - i
                lines.append(f"{prefix}... ({remaining} more)")
                truncated = True
                return
            is_last = i == len(items) - 1
            c = "└── " if is_last else "├── "
            if children is None:
                lines.append(f"{prefix}{c}{name}")
            else:
                n = count_leaves(children)
                lines.append(f"{prefix}{c}{name}/ ({n})")
                ext = "    " if is_last else "│   "
                render(children, prefix + ext)

    render(tree, "")

    out = ["## DIRECTORY TREE", "", "```"]
    out.extend(lines)
    out.append("```")
    if truncated:
        out.append(f"\n> Truncated at {MAX} lines. See FILE INDEX for complete listing.")
    return out


def build_file_index(files: list[str]) -> list[str]:
    lines = ["", "## FILE INDEX", "", "| File | Language | Description |", "|------|-------------|"]
    for filepath in sorted(files):
        name = Path(filepath).stem
        parts = filepath.replace("\\", "/").split("/")
        ext = Path(filepath).suffix.lower()
        lang = LANG_LABEL.get(ext, "text")
        if name in ("__init__", "index", "main"):
            desc = f"Package: {parts[-2]}" if len(parts) > 1 else filepath
        else:
            desc = name.replace("_", " ").replace("-", " ")
        lines.append(f"| `{filepath}` | {lang} | {desc} |")
    return lines


def build_appendix(filepaths: list[str]) -> list[str]:
    lines = ["", "---", "", "## APPENDIX: FULL IMPLEMENTATIONS", ""]
    for fp in sorted(filepaths):
        ext = Path(fp).suffix.lower()
        lang = LANG_LABEL.get(ext, "text")
        lines.append(f"### {fp}")
        lines.append(f"```{lang}")
        try:
            lines.append(Path(fp).read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            lines.append(f"# <binary file — skipped>")
        except OSError as ex:
            lines.append(f"# Error reading file: {ex}")
        lines.append("```")
        lines.append("")
    return lines


def append_markdown_files(content: str, target_dir: Path, included_filepaths: list[str] | None = None) -> str:
    """Append top-level markdown files from target directory, skipping already-included files."""
    md_files: list[Path] = []
    for p in target_dir.glob("*.md"):
        md_files.append(p)
    for p in target_dir.glob("*.MD"):
        md_files.append(p)

    if not md_files:
        return content

    # Skip markdown files already included in the appendix (identified by filename match)
    skip_names: set[str] = set()
    if included_filepaths:
        for fp in included_filepaths:
            skip_names.add(Path(fp).name.lower())

    md_lines = ["", "---", "", "## ADDITIONAL FILES (markdown)"]
    for md_path in sorted(md_files):
        if md_path.name.lower() in skip_names:
            continue
        md_lines.append("")
        md_lines.append(f"### {md_path.name}")
        md_lines.append("```markdown")
        try:
            md_lines.append(md_path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            md_lines.append(f"# <binary file — skipped>")
        except OSError as ex:
            md_lines.append(f"# Error reading file: {ex}")
        md_lines.append("```")

    if len(md_lines) == 5:  # only the header was added, nothing to append
        return content

    return content + "\n" + "\n".join(md_lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_sig_pack(filepaths: list[str], dirname: str, target_dir: Path) -> str:
    total = len(filepaths)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    header = "\n".join([
        f"# {dirname} — LLM-READY PACK",
        "",
        "<!-- Generated by gitpack.py (pure Python) -->",
        "",
        "## PACK INFO",
        f"- **Files:** {total} files",
        f"- **Mode:** signatures only",
        f"- **Generated:** {stamp}",
        "",
        "## HOW TO USE",
        "",
        "This is the signatures-only pack. For full implementations, see the",
        "corresponding `_full.md` file.",
        "",
    ])

    return "\n".join([
        header,
        "\n".join(build_signatures_section(filepaths)),
        "\n".join(build_directory_index(filepaths)),
        "\n".join(build_tree(filepaths, target_dir)),
        "\n".join(build_file_index(filepaths)),
    ])


def build_full_pack(filepaths: list[str], dirname: str) -> str:
    total = len(filepaths)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    header = "\n".join([
        f"# {dirname} — LLM-READY PACK",
        "",
        "<!-- Generated by gitpack.py (pure Python) -->",
        "",
        "## PACK INFO",
        f"- **Files:** {total} files",
        f"- **Mode:** signatures + full appendix",
        f"- **Generated:** {stamp}",
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
    ])

    return "\n".join([
        header,
        "\n".join(build_signatures_section(filepaths)),
        "\n".join(build_directory_index(filepaths)),
        "\n".join(build_file_index(filepaths)),
        "\n".join(build_appendix(filepaths)),
    ])


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: gitpack.py <target_dir> [--exclude <patterns>]", file=sys.stderr)
        sys.exit(1)

    target = Path(sys.argv[1]).resolve()
    if not target.is_dir():
        print(f"ERROR: Not a directory: {target}", file=sys.stderr)
        sys.exit(1)

    exclude = ""
    if "--exclude" in sys.argv:
        idx = sys.argv.index("--exclude")
        exclude = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""

    name = target.name
    out_dir = target / ".aid" / name
    out_dir.mkdir(parents=True, exist_ok=True)

    files = discover_files(target, exclude)
    if not files:
        print("ERROR: No supported files found", file=sys.stderr)
        sys.exit(1)

    sig_path = out_dir / f"{name}_sig.md"
    full_path = out_dir / f"{name}_full.md"

    sig_content = build_sig_pack(files, name, target)
    sig_content = append_markdown_files(sig_content, target, files)
    sig_path.write_text(sig_content, encoding="utf-8")

    full_content = build_full_pack(files, name)
    full_content = append_markdown_files(full_content, target, files)
    full_path.write_text(full_content, encoding="utf-8")

    print(f"Signatures: {sig_path} — {len(sig_content):,} chars")
    print(f"Full:       {full_path} — {len(full_content):,} chars")
    print(f"Files: {len(files)} files")


if __name__ == "__main__":
    main()
