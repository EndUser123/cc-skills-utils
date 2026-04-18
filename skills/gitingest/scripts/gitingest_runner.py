#!/usr/bin/env python3
"""
gitingest_runner.py — Pipeline engine for ingesting GitHub repos into NotebookLM.

Run: python gitingest_runner.py --config /path/to/repos.yaml [--dry-run]

The config file is the only required argument. The runner manages the full lifecycle:
  clone → file-lists → slice → upload → cleanup (even on error)

Staging dir: system temp directory / gitingest_{session_id}/
  Contains: cloned repos, generated slices, status.json
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

GITHUB_REGEX = re.compile(
    r"^(?:https?://)?github\.com/([^/]+)/([^/]+)(?:/(?:tree|blob)/([^/]+)(?:/(.+))?)?$"
)
SHORTHAND_REGEX = re.compile(r"^([^/]+)/([^:]+)(?::(.+))?$")


@dataclass
class RepoSpec:
    """Parsed repo specification from config."""

    owner: str
    repo: str
    branch: str = "main"
    path: str = ""
    skip: bool = False
    url: str = ""


@dataclass
class RepoResult:
    """Outcome for a single repo ingestion."""

    owner: str
    repo: str
    success: bool
    error: Optional[str] = None
    slices: list[str] = field(default_factory=list)


@dataclass
class RunState:
    """Shared state across the run, persisted to status.json."""

    session_id: str
    staging_dir: Path
    notebooklm_id: str
    results: list[RepoResult] = field(default_factory=list)

    def save(self) -> None:
        path = self.staging_dir / "status.json"
        data = {
            "session_id": self.session_id,
            "notebooklm_id": self.notebooklm_id,
            "results": [
                {
                    "owner": r.owner,
                    "repo": r.repo,
                    "success": r.success,
                    "error": r.error,
                    "slices": r.slices,
                }
                for r in self.results
            ],
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, staging_dir: Path) -> "RunState":
        path = staging_dir / "status.json"
        if not path.exists():
            raise FileNotFoundError(f"No status.json found in {staging_dir}")
        with open(path) as f:
            data = json.load(f)
        results = [
            RepoResult(
                owner=r["owner"],
                repo=r["repo"],
                success=r["success"],
                error=r.get("error"),
                slices=r.get("slices", []),
            )
            for r in data["results"]
        ]
        return cls(
            session_id=data["session_id"],
            staging_dir=staging_dir,
            notebooklm_id=data["notebooklm_id"],
            results=results,
        )


# ---------------------------------------------------------------------------
# Config parsing
# ---------------------------------------------------------------------------

def parse_github_url(url: str) -> RepoSpec:
    """Parse a GitHub URL or shorthand into a RepoSpec."""
    url = url.strip().rstrip("/")

    # Try full URL first
    m = GITHUB_REGEX.match(url)
    if m:
        owner, repo, branch, path = m.groups()
        return RepoSpec(
            owner=owner,
            repo=repo,
            branch=branch or "main",
            path=path or "",
            url=f"https://github.com/{owner}/{repo}",
        )

    # Try shorthand (owner/repo or owner/repo:branch)
    m = SHORTHAND_REGEX.match(url)
    if m:
        owner, repo, branch = m.groups()
        return RepoSpec(
            owner=owner,
            repo=repo,
            branch=branch or "main",
            path="",
            url=f"https://github.com/{owner}/{repo}",
        )

    raise ValueError(f"Cannot parse GitHub URL: {url}")


def load_config(config_path: Path) -> tuple[str, list[RepoSpec]]:
    """Load and validate the repos.yaml config file."""
    with open(config_path) as f:
        raw = yaml.safe_load(f)

    notebooklm_id = raw.get("notebooklm_id", "")
    if not notebooklm_id:
        raise ValueError("config must have notebooklm_id")

    repos = []
    for entry in raw.get("repos", []):
        url = entry.get("url", "")
        if not url:
            continue
        spec = parse_github_url(url)
        spec.skip = entry.get("skip", False)
        spec.branch = entry.get("branch", spec.branch)
        spec.path = entry.get("path", spec.path)
        repos.append(spec)

    return notebooklm_id, repos


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def _run(cmd: list[str], cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command, returning the result."""
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True)


def clone_repo(spec: RepoSpec, clone_root: Path, dry_run: bool = False) -> Path:
    """Clone a repo (full or sparse) into clone_root."""
    dest = clone_root / f"{spec.owner}__{spec.repo}"
    if dry_run:
        print(f"  [DRY] git clone {'--sparse ' if spec.path else ''}https://github.com/{spec.owner}/{spec.repo} → {dest}")
        return dest

    if spec.path:
        # Sparse checkout
        _run(
            [
                "git", "clone", "--depth=1", "--filter=blob:none", "--no-checkout",
                f"https://github.com/{spec.owner}/{spec.repo}",
                str(dest),
            ],
            check=True,
        )
        _run(["git", "sparse-checkout", "init", "--cone"], cwd=dest)
        _run(["git", "sparse-checkout", "set", spec.path], cwd=dest)
        _run(["git", "checkout", spec.branch], cwd=dest)
    else:
        _run(
            [
                "git", "clone", "--depth=1", "--filter=blob:none",
                f"https://github.com/{spec.owner}/{spec.repo}",
                str(dest),
            ],
            check=True,
        )
        if spec.branch != "main":
            _run(["git", "checkout", spec.branch], cwd=dest)

    return dest


def build_file_lists(repo_dir: Path, notebooklm_dir: Path, dry_run: bool = False) -> Path:
    """Build the three file lists (repo files, agent configs, docs). Returns notebooklm_dir."""
    notebooklm_dir.mkdir(parents=True, exist_ok=True)

    if dry_run:
        print(f"  [DRY] build file lists in {repo_dir} → {notebooklm_dir}")
        return notebooklm_dir

    # Repo files (excluding tests/binaries/lockfiles/images/dotfiles)
    result = _run(["git", "ls-files", "-z"], cwd=repo_dir, check=False)
    all_files = result.stdout.split("\0")
    exclude_patterns = [".png", ".jpg", ".jpeg", ".gif", ".lock", ".bin", ".so", ".dll", ".exe"]
    repo_files = [
        f for f in all_files
        if f
        and not any(f.endswith(pat) for pat in exclude_patterns)
        and not f.startswith(".")
        and "/." not in f
    ]
    file_list_path = notebooklm_dir / "file-list.txt"
    with open(file_list_path, "w") as f:
        f.write("\n".join(sorted(repo_files)) + "\n")

    # .claude configs (non-hidden, non-evidence)
    agent_configs: list[str] = []
    claude_dir = repo_dir / ".claude"
    if claude_dir.exists():
        for p in claude_dir.rglob("*"):
            if p.is_file() and ".evidence" not in str(p) and not any(
                part.startswith(".") for part in p.relative_to(claude_dir).parts
            ):
                agent_configs.append(str(p.relative_to(claude_dir)))
    agent_configs_path = notebooklm_dir / "agent-config-files.txt"
    with open(agent_configs_path, "w") as f:
        f.write("\n".join(sorted(agent_configs)) + "\n")

    # Doc files: docs/ + top-level README*.md and *.md (excluding CLAUDE, AGENTS, .mcp.json)
    doc_files: list[str] = []
    docs_dir = repo_dir / "docs"
    if docs_dir.exists():
        doc_files.extend(str(p.relative_to(repo_dir)) for p in docs_dir.rglob("*") if p.is_file())

    for pattern in ["README.md", "README*.md", "CONTRIBUTING.md", "ARCHITECTURE.md", "*.md"]:
        for p in repo_dir.glob(pattern):
            if p.is_file() and p.name not in {"CLAUDE.md", "AGENTS.md", ".mcp.json"}:
                doc_files.append(p.name)
    doc_files = sorted(set(doc_files))
    doc_files_path = notebooklm_dir / "doc-files.txt"
    with open(doc_files_path, "w") as f:
        f.write("\n".join(doc_files) + "\n")

    print(f"  → {len(repo_files)} repo files, {len(agent_configs)} agent configs, {len(doc_files)} docs")
    return notebooklm_dir


# ---------------------------------------------------------------------------
# Slicing — word-count based accumulation
# ---------------------------------------------------------------------------

def _word_count(text: str) -> int:
    """Estimate word count. Uses char count / 4 as proxy for English text."""
    return len(text) // 4


def _read_content(path: Path, max_chars: Optional[int] = None) -> str:
    """Read file content, optionally truncated."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        if max_chars and len(content) > max_chars:
            return content[:max_chars]
        return content
    except Exception:
        return ""


def _build_file_tree(files: list[str]) -> str:
    """Build a markdown file tree from a list of file paths."""
    lines: list[str] = []
    tree: dict[str, list[str]] = {}
    for f in files:
        parts = f.split("/")
        if len(parts) == 1:
            tree.setdefault(".", []).append(f)
        else:
            tree.setdefault("/".join(parts[:-1]), []).append(parts[-1])
    for key in sorted(tree.keys()):
        if key != ".":
            indent = "  " * key.count("/")
            lines.append(f"{indent}📁 {key}/\n")
        for f in sorted(tree.get(key, [])):
            indent = "  " * (key.count("/") + 1)
            ext = Path(f).suffix
            icon = "🐍" if ext == ".py" else "📄"
            lines.append(f"{indent}{icon} {f}\n")
    return "".join(lines)


def _group_files_by_dir(files: list[str]) -> list[tuple[str, list[str]]]:
    """Group files by top-level directory. Returns sorted (dir, files) pairs."""
    groups: dict[str, list[str]] = {}
    for f in sorted(files):
        parts = f.split("/")
        key = parts[0] if len(parts) > 1 else "."
        groups.setdefault(key, []).append(f)
    return sorted(groups.items())


def generate_slices(repo_dir: Path, notebooklm_dir: Path, spec: RepoSpec) -> list[Path]:
    """
    Strategy per user request:
      1. Build full repo content (repo files + agent configs + docs)
      2. Count words
      3. If < 500K words → one slice named {owner}-{repo}.md
      4. If >= 500K words → split at natural (directory) boundaries

    NotebookLM limit: 500,000 words per source.
    """
    slices: list[Path] = []
    entry_point_names = {"__main__.py", "cli.py", "app.py", "main.py"}
    MAX_WORDS = 500_000
    MAX_CHARS = MAX_WORDS * 4

    file_list_path = notebooklm_dir / "file-list.txt"
    if not file_list_path.exists():
        print("  ⚠ no file-list.txt, skipping")
        return slices

    repo_files = [f for f in file_list_path.read_text().splitlines() if f]

    def file_header(f: str, is_entry: bool) -> str:
        kind = "entry point — full" if is_entry else "file"
        return f"\n### 📄 `{f}` _(_{kind}_)\n\n"

    def read_file_content(full_path: Path, f: str) -> tuple[str, str]:
        """Returns (block_text, raw_content)."""
        ext = Path(f).suffix
        name = Path(f).name
        is_entry = name in entry_point_names or f.endswith("__main__.py")
        if is_entry and ext in {".py", ".js", ".ts", ".sh", ".bash"}:
            content = _read_content(full_path)
        elif ext in {".md", ".txt", ".rst"}:
            content = _read_content(full_path, max_chars=200_000)
        else:
            size = full_path.stat().st_size
            content = f"[{size:,} bytes — binary/file excluded]"
        block = file_header(f, is_entry) + f"```\n{content}\n```\n"
        return block, content

    # --- Phase 1: Accumulate ALL content (repo files + agent configs + docs) ---
    all_groups: list[tuple[str, list[str]]] = []
    # Group repo files by top-level directory
    dir_groups: dict[str, list[str]] = {}
    for f in sorted(repo_files):
        key = f.split("/")[0]
        dir_groups.setdefault(key, []).append(f)
    all_groups.append(("## Repository files", []))

    for dir_key, files_in_dir in sorted(dir_groups.items()):
        for f in files_in_dir:
            full_path = repo_dir / f
            if full_path.exists():
                all_groups[0][1].append(f)

    # Agent configs
    agent_list_path = notebooklm_dir / "agent-config-files.txt"
    agent_content_blocks: list[str] = []
    if agent_list_path.exists():
        for af in agent_list_path.read_text().splitlines():
            if af:
                full_path = repo_dir / ".claude" / af
                if full_path.exists():
                    content = _read_content(full_path, max_chars=10000)
                    agent_content_blocks.append(f"## {af}\n\n```\n{content}\n```\n")
    if agent_content_blocks:
        all_groups.append(("## Agent configs (.claude/)", agent_content_blocks))

    # Docs
    doc_list_path = notebooklm_dir / "doc-files.txt"
    doc_content_blocks: list[str] = []
    if doc_list_path.exists():
        for df in doc_list_path.read_text().splitlines():
            if df:
                full_path = repo_dir / df
                if full_path.exists():
                    content = _read_content(full_path, max_chars=200_000)
                    doc_content_blocks.append(f"## {df}\n\n```\n{content}\n```\n")
    if doc_content_blocks:
        all_groups.append(("## Documentation", doc_content_blocks))

    # --- Phase 2: Estimate total word count ---
    total_chars = 0
    for section_title, items in all_groups:
        if isinstance(items, list) and len(items) > 0 and isinstance(items[0], str) and "\n" in items[0]:
            # it's a content block list (agent configs / docs)
            for block in items:
                total_chars += len(block)
        else:
            # it's a file path list
            for f in items:
                full_path = repo_dir / f
                if full_path.exists():
                    ext = Path(f).suffix
                    name = Path(f).name
                    is_entry = name in entry_point_names or f.endswith("__main__.py")
                    if is_entry and ext in {".py", ".js", ".ts", ".sh", ".bash"}:
                        content = _read_content(full_path)
                    elif ext in {".md", ".txt", ".rst"}:
                        content = _read_content(full_path, max_chars=200_000)
                    else:
                        content = f"[{full_path.stat().st_size:,} bytes]"
                    total_chars += len(file_header(f, is_entry)) + len(content) + 12

    total_words = total_chars // 4
    repo_name = f"{spec.owner}-{spec.repo}"

    # --- Phase 3: One slice if fits, else split by directory groups ---
    def build_tree_for_files(file_paths: list[str]) -> str:
        tree: dict[str, list[str]] = {}
        for f in file_paths:
            parts = f.split("/")
            if len(parts) == 1:
                tree.setdefault(".", []).append(f)
            else:
                tree.setdefault("/".join(parts[:-1]), []).append(parts[-1])
        lines = []
        for key in sorted(tree.keys()):
            if key != ".":
                indent = "  " * key.count("/")
                lines.append(f"{indent}📁 {key}/\n")
            for fname in sorted(tree.get(key, [])):
                indent = "  " * (key.count("/") + 1)
                ext = Path(fname).suffix
                icon = "🐍" if ext == ".py" else "📄"
                lines.append(f"{indent}{icon} {fname}\n")
        return "".join(lines)

    if total_words < MAX_WORDS:
        # === ONE SLICE ===
        lines: list[str] = [
            f"# {spec.owner}/{spec.repo}\n",
            f"**Branch:** `{spec.branch}`  |  **Path:** `{spec.path or '/ (full repo)'}`  |  "
            f"**Source:** {spec.url}\n",
            f"**Total:** ~{total_words:,} words (~{total_chars:,} chars)\n",
            "\n## File tree\n",
            build_tree_for_files(repo_files),
            "\n",
        ]

        for section_title, items in all_groups:
            lines.append(f"\n{'_' * 60}\n")
            lines.append(f"{section_title}\n")
            lines.append(f"{'_' * 60}\n")
            if isinstance(items, list) and len(items) > 0 and isinstance(items[0], str) and "\n" in items[0]:
                # content blocks (agent configs / docs)
                lines.extend(items)
            else:
                for f in items:
                    full_path = repo_dir / f
                    if not full_path.exists():
                        continue
                    ext = Path(f).suffix
                    name = Path(f).name
                    is_entry = name in entry_point_names or f.endswith("__main__.py")
                    block, content = read_file_content(full_path, f)
                    lines.append(block)

        slice_path = notebooklm_dir / f"{repo_name}.md"
        slice_path.write_text("".join(lines), encoding="utf-8")
        slices.append(slice_path)
    else:
        # === SPLIT: one slice per directory group ===
        # Rebuild with per-group word count
        slice_num = 1
        current_lines: list[str] = []
        current_chars = 0

        def start_slice() -> str:
            nonlocal slice_num, current_lines, current_chars
            path = notebooklm_dir / f"{repo_name}-part-{slice_num}.md"
            path.write_text("".join(current_lines), encoding="utf-8")
            slices.append(path)
            wc = _word_count(path.read_text(encoding="utf-8"))
            print(f"  → slice: {path.name} ({path.stat().st_size:,} bytes, ~{wc:,} words)")
            slice_num += 1
            current_lines = []
            current_chars = 0
            return path.name

        # Header template
        def make_group_header(group_label: str) -> list[str]:
            return [
                f"# {spec.owner}/{spec.repo} — {group_label}\n",
                f"**Branch:** `{spec.branch}`  |  **Source:** {spec.url}\n",
                "\n## File tree\n",
                build_tree_for_files(repo_files),
                "\n",
            ]

        if not current_lines:
            current_lines.extend(make_group_header("repository + agent configs + docs"))
            current_chars = sum(len(l) for l in current_lines)

        # Add repo files grouped by directory
        for dir_key, files_in_dir in sorted(dir_groups.items()):
            for f in files_in_dir:
                full_path = repo_dir / f
                if not full_path.exists():
                    continue
                block, _ = read_file_content(full_path, f)
                if current_chars + len(block) > MAX_CHARS and current_chars > 0:
                    start_slice()
                    current_lines.extend(make_group_header(f"continued (from {dir_key}/)"))
                    current_chars = sum(len(l) for l in current_lines)
                current_lines.append(block)
                current_chars += len(block)

        # Add agent configs
        if agent_content_blocks:
            agent_section = ["\n" + "=" * 60 + "\n", "## Agent configs (.claude/)\n", "=" * 60 + "\n"]
            agent_text = "".join(agent_content_blocks)
            if current_chars + len(agent_section) + len(agent_text) > MAX_CHARS and current_chars > 0:
                start_slice()
                current_lines.extend(make_group_header("continued — agent configs"))
                current_chars = sum(len(l) for l in current_lines)
            current_lines.extend(agent_section)
            current_lines.extend(agent_content_blocks)
            current_chars += len(agent_section) + len(agent_text)

        # Add docs
        if doc_content_blocks:
            doc_section = ["\n" + "=" * 60 + "\n", "## Documentation\n", "=" * 60 + "\n"]
            doc_text = "".join(doc_content_blocks)
            if current_chars + len(doc_section) + len(doc_text) > MAX_CHARS and current_chars > 0:
                start_slice()
                current_lines.extend(make_group_header("continued — docs"))
                current_chars = sum(len(l) for l in current_lines)
            current_lines.extend(doc_section)
            current_lines.extend(doc_content_blocks)
            current_chars += len(doc_section) + len(doc_text)

        if current_lines:
            start_slice()

    # Print summary
    for s in slices:
        wc = _word_count(s.read_text(encoding="utf-8"))
        print(f"  → slice: {s.name} ({s.stat().st_size:,} bytes, ~{wc:,} words)")
    return slices


def get_existing_sources(notebooklm_id: str) -> tuple[dict[str, str], bool]:
    """Fetch existing source titles→IDs for the notebook.

    Returns (sources_dict, api_error).
    - api_error=False: sources_dict is valid (may be empty if notebook has no sources)
    - api_error=True: sources_dict is empty, API call failed
    """
    result = subprocess.run(
        ["nlm", "source", "list", notebooklm_id],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return {}, True
    try:
        sources = json.loads(result.stdout)
        return {s["title"]: s["id"] for s in sources}, False
    except (json.JSONDecodeError, KeyError):
        return {}, True


def _wait_for_delete_confirmed(notebooklm_id: str, source_id: str, max_attempts: int = 10) -> bool:
    """Poll nlm source list until source_id is gone. Returns True if confirmed deleted, False if still present after max_attempts."""
    for attempt in range(max_attempts):
        sources, api_error = get_existing_sources(notebooklm_id)
        if not api_error and source_id not in sources.values():
            return True
        time.sleep(1)
    return False


def upload_slices(
    notebooklm_id: str,
    slices: list[Path],
    repo_url: str,
    existing_sources: dict[str, str],
    dry_run: bool = False,
) -> None:
    """Upload slices + GitHub URL as a clickable web source, replacing older versions."""
    if dry_run:
        for s in slices:
            action = "replace" if s.name in existing_sources else "upload"
            print(f"  [DRY] [{action}] nlm source add {notebooklm_id} --file {s}")
        print(f"  [DRY] [new] nlm source add {notebooklm_id} --url {repo_url} --title {repo_url.split('/')[-1]}")
        return

    for s in slices:
        if s.name in existing_sources:
            old_id = existing_sources[s.name]
            print(f"  → replacing {s.name} (old source {old_id[:8]}...)...")
            result = subprocess.run(["nlm", "source", "delete", old_id], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"  ⚠ delete failed for {s.name}: {result.stderr.strip()}")
            if not _wait_for_delete_confirmed(notebooklm_id, old_id):
                print(f"  ⚠ delete not confirmed for {s.name}, skipping upload")
                continue
        else:
            print(f"  → uploading {s.name}...")
        result = subprocess.run(
            ["nlm", "source", "add", notebooklm_id, "--file", str(s), "--wait"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"  ⚠ upload failed for {s.name}: {result.stderr.strip()}")
            result2 = subprocess.run(
                ["nlm", "source", "add", notebooklm_id, "--file", str(s), "--wait"],
                capture_output=True, text=True,
            )
            if result2.returncode != 0:
                raise RuntimeError(f"Upload failed after retry: {result2.stderr.strip()}")
        else:
            print(f"  ✓ {s.name} uploaded")

    # Add GitHub repo URL as a clickable web source
    repo_name = repo_url.rstrip("/").rsplit("/", 1)[-1]
    url_key = f"GitHub - {repo_url.replace('https://github.com/', '')}"
    if url_key in existing_sources:
        old_id = existing_sources[url_key]
        print(f"  → replacing web source {old_id[:8]}... for {repo_url}...")
        result = subprocess.run(["nlm", "source", "delete", old_id], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ⚠ web source delete failed: {result.stderr.strip()}")
        elif not _wait_for_delete_confirmed(notebooklm_id, old_id):
            print(f"  ⚠ web source delete not confirmed, skipping add")
        print(f"  → adding web source for {repo_url}...")
    else:
        print(f"  → adding web source for {repo_url}...")
    result = subprocess.run(
        ["nlm", "source", "add", notebooklm_id, "--url", repo_url, "--title", url_key],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  ⚠ web source failed for {repo_url}: {result.stderr.strip()}")
    else:
        print(f"  ✓ web source added: {url_key}")


def cleanup_clone(clone_root: Path, spec: RepoSpec) -> None:
    """Remove the cloned repo."""
    dest = clone_root / f"{spec.owner}__{spec.repo}"
    if dest.exists():
        try:
            shutil.rmtree(dest)
        except OSError as e:
            print(f"  ⚠ cleanup failed for {dest}: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="gitingest pipeline runner")
    parser.add_argument("--config", required=True, type=Path, help="Path to repos.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Print steps without executing")
    args = parser.parse_args()

    # Load config
    notebooklm_id, specs = load_config(args.config)
    active_specs = [s for s in specs if not s.skip]

    print(f"gitingest runner")
    print(f"  Config:     {args.config}")
    print(f"  NotebookLM:  {notebooklm_id}")
    print(f"  Repos:       {len(active_specs)} active, {sum(1 for s in specs if s.skip)} skipped")
    print(f"  Dry run:     {args.dry_run}")
    print()

    # Setup staging dir — use system temp directory (cross-platform)
    session_id = uuid.uuid4().hex[:8]
    staging_dir = Path(tempfile.gettempdir()) / f"gitingest_{session_id}"
    clone_root = staging_dir / "clones"
    clone_root.mkdir(parents=True, exist_ok=True)

    state = RunState(
        session_id=session_id,
        staging_dir=staging_dir,
        notebooklm_id=notebooklm_id,
    )

    try:
        # Auth check
        print("=== Auth check ===")
        result = subprocess.run(
            ["nlm", "login"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 and not args.dry_run:
            print("⚠ nlm login check:", result.stderr.strip())
        print()

        # Fetch existing sources once before any uploads (for dedup/replace)
        print("=== Existing sources ===")
        if args.dry_run:
            existing_sources = {}
        else:
            existing_sources, api_error = get_existing_sources(notebooklm_id)
            if api_error:
                print(f"  ⚠ source list API error — proceeding without dedup")
        print(f"  → {len(existing_sources)} existing sources in notebook")
        print()

        # Process each repo
        for i, spec in enumerate(active_specs, 1):
            print(f"=== [{i}/{len(active_specs)}] {spec.owner}/{spec.repo} ===")

            repo_result = RepoResult(owner=spec.owner, repo=spec.repo, success=False)

            try:
                # 1. Clone
                print("--- clone ---")
                repo_dir = clone_repo(spec, clone_root, dry_run=args.dry_run)

                # 2. Build file lists
                print("--- file lists ---")
                nl_dir = staging_dir / "notebooklm" / f"{spec.owner}__{spec.repo}"
                build_file_lists(repo_dir, nl_dir, dry_run=args.dry_run)

                # 3. Generate slices
                print("--- slices ---")
                slices = generate_slices(repo_dir, nl_dir, spec)
                repo_result.slices = [s.name for s in slices]

                # 4. Upload
                print("--- upload ---")
                upload_slices(notebooklm_id, slices, spec.url, existing_sources, dry_run=args.dry_run)

                repo_result.success = True
                print(f"✓ {spec.owner}/{spec.repo} done")

            except Exception as e:
                repo_result.success = False
                repo_result.error = str(e)
                print(f"✗ {spec.owner}/{spec.repo} failed: {e}")

            finally:
                # Always cleanup clone
                if not args.dry_run:
                    cleanup_clone(clone_root, spec)

                state.results.append(repo_result)
                state.save()

            print()

        # Summary
        print("=== Summary ===")
        successes = [r for r in state.results if r.success]
        failures = [r for r in state.results if not r.success]
        print(f"  ✓ {len(successes)} succeeded")
        if failures:
            print(f"  ✗ {len(failures)} failed:")
            for f in failures:
                print(f"    - {f.owner}/{f.repo}: {f.error}")

    finally:
        # Always cleanup staging dir (unless dry-run)
        if not args.dry_run and staging_dir.exists():
            print(f"\nCleaning up {staging_dir}...")
            shutil.rmtree(staging_dir, ignore_errors=True)
        else:
            print(f"\nStaging dir (dry-run, not cleaned): {staging_dir}")


if __name__ == "__main__":
    main()
