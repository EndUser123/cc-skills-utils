#!/usr/bin/env python3
"""
/main-review — slow, evidence-first behavioral auditor for the `main` skill family.

Complements /main (real-time infrastructure health) by auditing RECENT HISTORY:
transcripts, the diagnostics DB, gate telemetry, and logs. Detects:

  1. Unsupported factual / "fixed" / "root cause" claims (no tool receipt in window)
  2. "Not found / doesn't exist" claims without a preceding search tool call
  3. Gate drift / silent / inert / fail-open checks
  4. Claim/receipt mismatches ("Verified" above an error/traceback tool result)
  5. Regression candidates (recurring error signatures -> replay tests)
  6. Promotion candidates (recurring narrow patterns -> runtime gates)

Deterministic-first; the LLM critic (Stage 3) is optional and vendor-neutral and only
ever inspects extracted evidence slices — never whole repos.
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import sqlite3
import sys
import tempfile
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parents[1]
CLAUDE_DIR = Path("P:/") / ".claude"
PROJECT_ROOT = Path("P:/")

DEFAULT_TRANSCRIPTS_ROOT = Path.home() / ".claude" / "projects"
DEFAULT_DIAGNOSTICS_DB = CLAUDE_DIR / "hooks" / "logs" / "diagnostics" / "diagnostics.db"
DEFAULT_HEALTH_HISTORY = CLAUDE_DIR / "session_data" / "health_history.jsonl"
DEFAULT_ANTI_DODGE = CLAUDE_DIR / "hooks" / "logs" / "anti_dodge_decisions.jsonl"
DEFAULT_HOOK_ROOTS = [
    CLAUDE_DIR,
    PROJECT_ROOT / "packages" / ".claude-marketplace" / "plugins",
]
DEFAULT_REVIEW_HISTORY = CLAUDE_DIR / "session_data" / "review_history.jsonl"

SEVERITIES = ("critical", "high", "medium", "info")
CATEGORIES = ("claims", "gates", "receipts", "regression", "promotion")

VERDICT_PATTERNS = [
    re.compile(r"\bRoot Cause\b\s*:", re.I),
    re.compile(r"\bThe fix is\b", re.I),
    re.compile(r"\bThis works because\b", re.I),
    re.compile(r"\bConfirmed working\b", re.I),
    re.compile(r"\bVerified\b(?=\s*[.:)\n]|$)", re.I),
    re.compile(r"\bFixed\b(?=\s*[.:)\n]|$)", re.I),
    re.compile(r"\bResolved\b(?=\s*[.:)\n]|$)", re.I),
    re.compile(r"\bDone\b(?=\s*[.:)\n]|$)", re.I),
]

NEGATIVE_EXISTENCE_PATTERNS = [
    re.compile(r"\bdoesn'?t exist\b", re.I),
    re.compile(r"\bdoes not exist\b", re.I),
    re.compile(r"\bnot found\b", re.I),
    re.compile(r"\bno such (?:file|module|command|directory|attribute)\b", re.I),
    re.compile(r"\bis(?: still)? unused\b", re.I),
    re.compile(r"\bare unused\b", re.I),
    re.compile(r"\bno consumers\b", re.I),
    re.compile(r"\bno callers\b", re.I),
    re.compile(r"\bno references to\b", re.I),
    re.compile(r"\bisn'?t used\b", re.I),
    re.compile(r"\bnever called\b", re.I),
    re.compile(r"\bnot used anywhere\b", re.I),
]

SEARCH_TOOL_NAMES = {"Grep", "Glob", "Read", "LS"}
ANY_TOOL_NAMES = {"Bash", "Read", "Grep", "Glob", "Edit", "Write", "MultiEdit",
                  "NotebookEdit", "Task", "WebSearch", "WebFetch"}

ERROR_SIGNATURE_RES = [
    re.compile(r"Traceback \(most recent call last\):\n.*?\n(\s*\w*(?:Error|Exception):[^\n]+)", re.S),
    re.compile(r"\b(ModuleNotFoundError:[^\n]+)", re.I),
    re.compile(r"\b(ImportError:[^\n]+)", re.I),
    re.compile(r"\b(AttributeError:[^\n]+)", re.I),
    re.compile(r"\b(FileNotFoundError:[^\n]+)", re.I),
    re.compile(r"\b(SyntaxError:[^\n]+)", re.I),
]
ERROR_NORMALIZE_RE = re.compile(r"[\'\"]+|0x[0-9a-fA-F]+|line \d+|\d+")

CONTRADICTION_RE = re.compile(
    r"\b(?:Traceback|Error|Exception|No such file|not found|FAILED|failed to|"
    r"ModuleNotFoundError|cannot find|does not exist)\b", re.I
)

ID_COUNTER = itertools.count(1)


@dataclass(frozen=True)
class Finding:
    """One audit finding. Mirrors CheckResult / HealthFinding style."""

    id: str
    severity: str
    category: str
    title: str
    evidence: list
    confidence: float
    source_refs: list
    recommended_action: str
    rationale: str = ""
    promotion_ready: bool = False
    proposed_test: str | None = None
    proposed_runtime_gate: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Finding":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__})


@dataclass
class AuditReport:
    scope: dict
    summary: dict
    findings: list
    unsupported_claims: list
    gate_health_findings: list
    regression_candidates: list
    promotion_candidates: list
    recommended_actions: list
    duration_ms: int = 0
    timestamp: str = ""
    critic_used: bool = False


@dataclass
class Config:
    """All knobs injectable — mirrors HealthBaseline pattern for testability."""

    since_days: int = 30
    focus: set = field(default_factory=set)
    json_output: bool = False
    quiet: bool = False
    critic: bool = False
    save_history: bool = True
    max_transcripts: int = 50
    max_entries_per_transcript: int = 0
    lookback: int = 6
    transcripts_root: Path = field(default_factory=lambda: DEFAULT_TRANSCRIPTS_ROOT)
    diagnostics_db: Path = field(default_factory=lambda: DEFAULT_DIAGNOSTICS_DB)
    health_history: Path = field(default_factory=lambda: DEFAULT_HEALTH_HISTORY)
    anti_dodge_log: Path = field(default_factory=lambda: DEFAULT_ANTI_DODGE)
    registered_hooks_roots: list = field(default_factory=lambda: list(DEFAULT_HOOK_ROOTS))
    history_file: Path = field(default_factory=lambda: DEFAULT_REVIEW_HISTORY)
    regression_recurrence: int = 3
    promotion_recurrence: int = 3


def _new_id() -> str:
    return f"MR-{next(ID_COUNTER):04d}"


def _reset_ids() -> None:
    global ID_COUNTER
    ID_COUNTER = itertools.count(1)


def _parse_since(spec: str) -> int:
    m = re.fullmatch(r"(\d+)\s*([dwm])?", spec.strip())
    if not m:
        raise ValueError(f"invalid --since value: {spec!r} (e.g. 7d, 30d, 2w)")
    n = int(m.group(1))
    unit = m.group(2) or "d"
    return n * {"d": 1, "w": 7, "m": 30}[unit]


@dataclass
class TranscriptEvent:
    kind: str
    text: str
    tool_uses: list
    tool_results: list
    index: int = 0


def parse_transcript(path: Path, max_entries: int = 0) -> list:
    events: list = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                if max_entries and len(events) >= max_entries:
                    break
                line = raw.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = obj.get("message") or {}
                content = msg.get("content")
                text_parts: list = []
                tool_uses: list = []
                tool_results: list = []
                if isinstance(content, str):
                    text_parts.append(content)
                elif isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        btype = block.get("type")
                        if btype == "text" and block.get("text"):
                            text_parts.append(block["text"])
                        elif btype == "tool_use":
                            tool_uses.append(block.get("name", "?"))
                        elif btype == "tool_result":
                            rc = block.get("content")
                            if isinstance(rc, str):
                                tool_results.append(rc)
                            elif isinstance(rc, list):
                                tool_results.append(
                                    " ".join(b.get("text", "") for b in rc
                                             if isinstance(b, dict))
                                )
                role = msg.get("role") or obj.get("type") or "other"
                kind = role if role in {"assistant", "user", "system"} else "other"
                events.append(TranscriptEvent(
                    kind=kind,
                    text="\n".join(text_parts),
                    tool_uses=tool_uses,
                    tool_results=tool_results,
                    index=len(events),
                ))
    except OSError:
        return events
    return events


def extract_matches(text: str, patterns: list) -> list:
    out: list = []
    for pat in patterns:
        for m in pat.finditer(text):
            start = max(0, m.start() - 10)
            snippet = re.sub(r"\s+", " ", text[start:m.end() + 40]).strip()
            out.append(snippet[:120])
    return out


def _has_tool_in_window(events: list, idx: int, names: set, lookback: int) -> bool:
    lo = max(0, idx - lookback)
    for ev in events[lo:idx + 1]:
        for name in ev.tool_uses:
            if name in names:
                return True
    return False


def detect_unsupported_claims(events: list, source_ref: str, lookback: int) -> list:
    findings: list = []
    for ev in events:
        if ev.kind != "assistant" or not ev.text:
            continue
        for phrase in extract_matches(ev.text, VERDICT_PATTERNS):
            if not _has_tool_in_window(events, ev.index, ANY_TOOL_NAMES, lookback):
                findings.append(Finding(
                    id=_new_id(), severity="high", category="claims",
                    title="Confident verdict without a supporting tool receipt",
                    evidence=["verdict phrase: " + repr(phrase)],
                    confidence=0.8,
                    source_refs=[f"{source_ref}#entry{ev.index}"],
                    recommended_action=(
                        "Run the discriminating tool call before asserting the verdict, "
                        "or hedge the claim (likely/probably)."
                    ),
                    rationale=(
                        "Claim-Verification rule requires a tool call in the recent window "
                        "for any Root Cause / Fixed / Verified class claim."
                    ),
                ))
    return findings


def detect_negative_existence(events: list, source_ref: str, lookback: int) -> list:
    findings: list = []
    for ev in events:
        if ev.kind != "assistant" or not ev.text:
            continue
        for phrase in extract_matches(ev.text, NEGATIVE_EXISTENCE_PATTERNS):
            if not _has_tool_in_window(events, ev.index, SEARCH_TOOL_NAMES, lookback):
                findings.append(Finding(
                    id=_new_id(), severity="medium", category="claims",
                    title="Negative-existence claim without a search tool receipt",
                    evidence=["claim: " + repr(phrase)],
                    confidence=0.7,
                    source_refs=[f"{source_ref}#entry{ev.index}"],
                    recommended_action=(
                        "Back the claim with Grep/Glob/Read evidence before asserting absence."
                    ),
                    rationale="Absence claims need a positive search, not inference.",
                ))
    return findings


def detect_receipt_mismatches(events: list, source_ref: str, lookback: int) -> list:
    findings: list = []
    for ev in events:
        if ev.kind != "assistant" or not ev.text:
            continue
        verdicts = extract_matches(ev.text, VERDICT_PATTERNS)
        if not verdicts:
            continue
        lo = max(0, ev.index - lookback)
        preceding_results: list = []
        for pev in events[lo:ev.index]:
            preceding_results.extend(pev.tool_results)
        contradicting = [r for r in preceding_results if CONTRADICTION_RE.search(r)]
        if contradicting:
            evidence_bit = re.sub(r"\s+", " ", contradicting[0]).strip()[:160]
            findings.append(Finding(
                id=_new_id(), severity="critical", category="receipts",
                title="Verdict contradicted by the immediately preceding tool result",
                evidence=["verdict: " + repr(verdicts[0]), "preceding result: " + repr(evidence_bit)],
                confidence=0.9,
                source_refs=[f"{source_ref}#entry{ev.index}"],
                recommended_action=(
                    "Withdraw or re-qualify the verdict; the receipt shows an error/not-found, "
                    "not success."
                ),
                rationale="Highest-confidence finding: the cited receipt refutes the claim.",
            ))
    return findings


def collect_error_signatures(events: list) -> list:
    sigs: list = []
    for ev in events:
        blob = ev.text + "\n" + "\n".join(ev.tool_results)
        for rx in ERROR_SIGNATURE_RES:
            for m in rx.finditer(blob):
                sig = ERROR_NORMALIZE_RE.sub("", m.group(1)).strip()
                if sig:
                    sigs.append(sig[:140])
    return sigs


def gather_transcripts(cfg: Config, cutoff: datetime) -> tuple:
    paths: list = []
    info: list = []
    root = cfg.transcripts_root
    if not root.exists():
        info.append(Finding(
            id=_new_id(), severity="info", category="claims",
            title="Transcripts root not available",
            evidence=["looked for: " + str(root)],
            confidence=1.0, source_refs=[str(root)],
            recommended_action="Run on a host with session transcripts, or pass --data-dir.",
            rationale="Stage 1 could not find any transcripts to audit.",
        ))
        return paths, info
    for p in root.rglob("*.jsonl"):
        try:
            mtime = datetime.fromtimestamp(p.stat().st_mtime)
        except OSError:
            continue
        if mtime >= cutoff:
            paths.append(p)
    paths.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    if len(paths) > cfg.max_transcripts:
        dropped = len(paths) - cfg.max_transcripts
        paths = paths[:cfg.max_transcripts]
        info.append(Finding(
            id=_new_id(), severity="info", category="claims",
            title=f"Transcript cap applied ({cfg.max_transcripts})",
            evidence=[f"{dropped} older transcript(s) skipped"],
            confidence=1.0, source_refs=[str(root)],
            recommended_action="Raise --max-transcripts for broader coverage.",
            rationale="Bounding volume; no silent truncation - dropped count surfaced.",
        ))
    return paths, info


def gather_diagnostics(cfg: Config, cutoff: datetime) -> tuple:
    rows: list = []
    info: list = []
    db = cfg.diagnostics_db
    if not db.exists():
        info.append(Finding(
            id=_new_id(), severity="info", category="gates",
            title="Diagnostics DB not available",
            evidence=["looked for: " + str(db)],
            confidence=1.0, source_refs=[str(db)],
            recommended_action="Gate-health stage skipped; enable hook diagnostics.",
            rationale="No diagnostics.db to derive gate invocation telemetry.",
        ))
        return rows, info
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        tables = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        tbl = next((t for t in tables if "invoc" in t.lower() or "hook" in t.lower()), None)
        if tbl is None:
            info.append(Finding(
                id=_new_id(), severity="info", category="gates",
                title="Diagnostics DB has no hook-invocation table",
                evidence=["tables found: " + str(tables)],
                confidence=1.0, source_refs=[str(db)],
                recommended_action="Gate-health stage skipped.",
                rationale="Cannot derive gate telemetry without an invocations table.",
            ))
            con.close()
            return rows, info
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({tbl})").fetchall()]

        def col(*candidates: str):
            for c in candidates:
                for real in cols:
                    if c.lower() in real.lower():
                        return real
            return None

        select = []
        for alias, cands in (
            ("hook", ("hook_name", "hook", "name")),
            ("event", ("event_type", "event")),
            ("action", ("action",)),
            ("reason", ("reason",)),
            ("ts", ("timestamp", "created_at", "ts", "time")),
            ("session", ("session_id", "session")),
        ):
            real = col(*cands)
            if real:
                select.append(f"{real} AS {alias}")
        if not select:
            con.close()
            return rows, info
        q = f"SELECT {', '.join(select)} FROM {tbl}"
        ts_col = col("timestamp", "created_at", "ts", "time")
        if ts_col:
            q += f" ORDER BY {ts_col} DESC LIMIT 20000"
        for r in con.execute(q).fetchall():
            d = dict(r)
            if ts_col and isinstance(d.get("ts"), str):
                try:
                    ts = d["ts"].replace("Z", "+00:00")
                    if datetime.fromisoformat(ts) < cutoff:
                        continue
                except (ValueError, TypeError):
                    pass
            rows.append(d)
        con.close()
    except sqlite3.DatabaseError as e:
        info.append(Finding(
            id=_new_id(), severity="info", category="gates",
            title="Diagnostics DB unreadable",
            evidence=["error: " + str(e)],
            confidence=1.0, source_refs=[str(db)],
            recommended_action="Gate-health stage skipped.",
            rationale="DB could not be queried read-only.",
        ))
    return rows, info


def gather_health_history(cfg: Config) -> list:
    if not cfg.health_history.exists():
        return []
    out: list = []
    try:
        with open(cfg.health_history, encoding="utf-8") as fh:
            for line in fh:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return out


def gather_registered_hook_names(cfg: Config) -> set:
    names: set = set()
    for root in cfg.registered_hooks_roots:
        if not root.exists():
            continue
        candidates: list = []
        settings = root / "settings.json"
        if settings.exists():
            candidates.append(settings)
        try:
            candidates.extend(root.rglob("hooks.json"))
        except OSError:
            pass
        for c in candidates:
            try:
                data = json.loads(c.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for cmd in _iter_hook_commands(data):
                parts = cmd.replace(chr(34), " ").replace(chr(39), " ").split()
                for tok in parts:
                    if tok.endswith(".py"):
                        names.add(Path(tok).name)
    return names


def _iter_hook_commands(obj) -> list:
    cmds: list = []
    if isinstance(obj, dict):
        if isinstance(obj.get("command"), str):
            cmds.append(obj["command"])
        for v in obj.values():
            cmds.extend(_iter_hook_commands(v))
    elif isinstance(obj, list):
        for v in obj:
            cmds.extend(_iter_hook_commands(v))
    return cmds


def detect_gate_health(rows: list, registered: set) -> list:
    findings: list = []
    if not rows and not registered:
        return findings

    per_hook: dict = defaultdict(Counter)
    for r in rows:
        h = r.get("hook") or r.get("event") or "unknown"
        per_hook[h][r.get("action") or "unknown"] += 1

    seen = set(per_hook)
    for name in sorted(registered - seen):
        findings.append(Finding(
            id=_new_id(), severity="medium", category="gates",
            title=f"Registered hook with zero recent invocations: {name}",
            evidence=["registered in hooks.json/settings.json, absent from diagnostics"],
            confidence=0.6,
            source_refs=[f"diagnostics.db:hook={name}"],
            recommended_action="Confirm the hook is wired and firing; it may be inert.",
            rationale="A gate that never fires provides no protection - verify liveness.",
        ))

    gate_rx = re.compile(r"(gate|stop|pretooluse|posttooluse|rca|verif|claim)", re.I)
    for h, acts in per_hook.items():
        total = sum(acts.values())
        if total < 5:
            continue
        blocks = acts.get("block", 0) + acts.get("deny", 0)
        errors = acts.get("error", 0)
        if gate_rx.search(h) and blocks == 0:
            findings.append(Finding(
                id=_new_id(), severity="high", category="gates",
                title=f"Gate-class hook never blocks ({h}: {total} invocations, 0 blocks)",
                evidence=["action distribution: " + str(dict(acts))],
                confidence=0.7,
                source_refs=[f"diagnostics.db:hook={h}"],
                recommended_action=(
                    "Confirm the gate is fail-closed where it should be; a never-blocking gate "
                    "may be warn-mode or fail-open."
                ),
                rationale="A blocking gate that never blocks is either inert or permissive.",
            ))
        if errors / total > 0.5:
            findings.append(Finding(
                id=_new_id(), severity="high", category="gates",
                title=f"Hook error-dominated ({h}: {errors}/{total} errors)",
                evidence=["action distribution: " + str(dict(acts))],
                confidence=0.8,
                source_refs=[f"diagnostics.db:hook={h}"],
                recommended_action="Inspect hook stderr; an erroring hook may be fail-open.",
                rationale="Hooks that error over half the time are likely not enforcing.",
            ))
    return findings


def detect_regression_candidates(sig_by_transcript: dict, recurrence: int) -> list:
    findings: list = []
    sig_sources: dict = defaultdict(set)
    for tname, sigs in sig_by_transcript.items():
        for s in set(sigs):
            sig_sources[s].add(tname)
    for sig, sources in sig_sources.items():
        if len(sources) >= recurrence:
            findings.append(Finding(
                id=_new_id(), severity="high", category="regression",
                title=f"Recurring error signature across {len(sources)} transcripts",
                evidence=["signature: " + repr(sig), "in: " + repr(sorted(sources))],
                confidence=0.75,
                source_refs=["transcript-cluster:" + sig[:60]],
                recommended_action="Add a replay test that reproduces this signature.",
                rationale="Recurring identical errors are prime regression-test material.",
                proposed_test=(
                    "Fixture a transcript/tool_result containing: " + sig[:100] +
                    " and assert the responsible code path raises (or no longer raises) it."
                ),
            ))
    return findings


def detect_history_regressions(history: list, recurrence: int) -> list:
    findings: list = []
    flips: Counter = Counter()
    prev: dict = {}
    for entry in history:
        checks = entry.get("checks", {})
        for name, status in checks.items():
            if prev.get(name) == "healthy" and status == "critical":
                flips[name] += 1
            prev[name] = status
    for name, n in flips.items():
        if n >= recurrence:
            findings.append(Finding(
                id=_new_id(), severity="medium", category="regression",
                title=f"Health check [{name}] flipped healthy to critical {n} times",
                evidence=[f"flips observed: {n}"],
                confidence=0.7,
                source_refs=["health_history.jsonl:check=" + name],
                recommended_action="Stabilize the check or its underlying subsystem.",
                rationale="Intermittent health flips indicate a flaky/regressing condition.",
            ))
    return findings


PROMOTION_CRITERIA = [
    "recurrence (distinct sessions >= threshold)",
    "narrow and teachable (single detectable pattern)",
    "low ambiguity (regex/state can decide)",
    "testable (a fixture can reproduce it)",
    "low false-positive (replay suggests few FPs)",
]


def analyze_promotions(findings: list, cfg: Config) -> list:
    out: list = []
    by_pattern: dict = defaultdict(list)
    for f in findings:
        if f.category not in {"claims", "receipts"}:
            continue
        head = f.evidence[0] if f.evidence else ""
        if "verdict phrase" in head:
            key = "verdict-without-receipt"
        elif "claim:" in head:
            key = "negative-existence-without-search"
        else:
            key = f.category
        by_pattern[key].append(f)

    for pattern, group in by_pattern.items():
        distinct_sources = {ref.split("#")[0] for f in group for ref in f.source_refs}
        if len(distinct_sources) < cfg.promotion_recurrence:
            continue
        gate, test = _propose_gate(pattern)
        out.append(Finding(
            id=_new_id(), severity="info", category="promotion",
            title=f"Pattern [{pattern}] recurs across {len(distinct_sources)} source(s)",
            evidence=[f"recurrence: {len(group)} finding(s), {len(distinct_sources)} source(s)"],
            confidence=0.6,
            source_refs=sorted(distinct_sources),
            recommended_action=(
                "Consider graduating this into a deterministic runtime gate (conservative; "
                "gate should warn before block in production)."
            ),
            rationale="Meets recurrence bar; remaining promotion criteria need a replay pass.",
            promotion_ready=True,
            proposed_runtime_gate=gate,
            proposed_test=test,
        ))
    return out


def _propose_gate(pattern: str) -> tuple:
    if pattern == "verdict-without-receipt":
        return (
            "Stop hook: regex-match verdict phrases (Root Cause/Fixed/Verified/Resolved) and "
            "require a tool_use event in the preceding window; warn-first.",
            "Fixture: assistant turn with a Root Cause verdict and no preceding tool_use triggers the gate.",
        )
    if pattern == "negative-existence-without-search":
        return (
            "PreToolUse/Stop hook: on absence claims require a Grep/Glob/Read in the same turn; warn-first.",
            "Fixture: an absence claim with no preceding search tool triggers the gate.",
        )
    return (
        "Stop hook: detect this recurring pattern and require supporting evidence; warn-first.",
        "Fixture: reproduce the pattern and assert the gate fires.",
    )


def run_critic(findings: list, cfg: Config) -> list:
    if not cfg.critic:
        return findings
    suspicious_ids = {f.id for f in findings if f.severity in {"critical", "high"}}
    if not suspicious_ids:
        return findings
    reviewed: list = []
    for f in findings:
        if f.id in suspicious_ids:
            note = _critic_backend(f)
            new_ev = list(f.evidence) + (["critic: " + note] if note else [])
            d = f.to_dict()
            d["evidence"] = new_ev
            d["confidence"] = min(0.99, f.confidence + 0.05)
            reviewed.append(Finding.from_dict(d))
        else:
            reviewed.append(f)
    return reviewed


def _critic_backend(f: Finding) -> str:
    # ponytail: no default vendor - keeps the tool dependency-free and deterministic.
    return ""


def finalize(findings: list) -> list:
    out: list = []
    for f in findings:
        if f.severity == "critical" and (not f.evidence or not f.source_refs):
            d = f.to_dict()
            d["severity"] = "high"
            d["rationale"] = (f.rationale + " "
                              "[downgraded: critical requires explicit refs].").strip()
            out.append(Finding.from_dict(d))
        else:
            out.append(f)
    seen: set = set()
    deduped: list = []
    for f in out:
        key = (f.category, f.title, (f.evidence[0] if f.evidence else ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(f)
    return deduped


_SEV_RANK = {"critical": 0, "high": 1, "medium": 2, "info": 3}


def _severity_sort(f: Finding) -> tuple:
    return (_SEV_RANK.get(f.severity, 9), f.category)


def run(cfg: Config) -> AuditReport:
    start = time.time()
    _reset_ids()
    cutoff = datetime.now() - timedelta(days=cfg.since_days)
    focus = cfg.focus or set(CATEGORIES)

    scope = {
        "since_days": cfg.since_days,
        "cutoff": cutoff.isoformat(),
        "focus": sorted(focus),
        "lookback": cfg.lookback,
        "transcripts_scanned": 0,
        "diagnostics_rows": 0,
        "sources": {},
    }

    all_findings: list = []

    transcript_paths, t_info = gather_transcripts(cfg, cutoff)
    all_findings.extend(t_info)
    diag_rows, d_info = gather_diagnostics(cfg, cutoff)
    all_findings.extend(d_info)
    history = gather_health_history(cfg)
    registered = gather_registered_hook_names(cfg)
    scope["sources"] = {
        "transcripts_root": str(cfg.transcripts_root),
        "diagnostics_db": str(cfg.diagnostics_db),
        "health_history": str(cfg.health_history),
        "registered_hooks": len(registered),
    }
    scope["diagnostics_rows"] = len(diag_rows)

    sig_by_transcript: dict = {}
    for tp in transcript_paths:
        events = parse_transcript(tp, cfg.max_entries_per_transcript)
        if not events:
            continue
        scope["transcripts_scanned"] += 1
        ref = f"transcript:{tp.name}"
        if "claims" in focus:
            all_findings.extend(detect_unsupported_claims(events, ref, cfg.lookback))
            all_findings.extend(detect_negative_existence(events, ref, cfg.lookback))
        if "receipts" in focus:
            all_findings.extend(detect_receipt_mismatches(events, ref, cfg.lookback))
        if "regression" in focus:
            sig_by_transcript[tp.name] = collect_error_signatures(events)

    if "gates" in focus:
        all_findings.extend(detect_gate_health(diag_rows, registered))

    if "regression" in focus:
        all_findings.extend(
            detect_regression_candidates(sig_by_transcript, cfg.regression_recurrence))
        all_findings.extend(detect_history_regressions(history, cfg.regression_recurrence))

    all_findings = run_critic(all_findings, cfg)

    if "promotion" in focus:
        all_findings.extend(analyze_promotions(all_findings, cfg))

    all_findings = sorted(finalize(all_findings), key=_severity_sort)

    def cat(c: str) -> list:
        return [f for f in all_findings if f.category == c]

    by_sev = Counter(f.severity for f in all_findings)
    summary = {
        "total_findings": len(all_findings),
        "by_severity": {s: by_sev.get(s, 0) for s in SEVERITIES},
        "by_category": {c: len(cat(c)) for c in CATEGORIES},
        "overall": _overall_status(all_findings),
    }

    recommended = _recommend(all_findings)
    duration_ms = int((time.time() - start) * 1000)

    report = AuditReport(
        scope=scope,
        summary=summary,
        findings=all_findings,
        unsupported_claims=cat("claims"),
        gate_health_findings=cat("gates"),
        regression_candidates=cat("regression"),
        promotion_candidates=cat("promotion"),
        recommended_actions=recommended,
        duration_ms=duration_ms,
        timestamp=datetime.now().isoformat(),
        critic_used=cfg.critic,
    )

    if cfg.save_history:
        save_history(report, cfg)
    return report


def _overall_status(findings: list) -> str:
    sevs = {f.severity for f in findings}
    if "critical" in sevs:
        return "critical"
    if "high" in sevs:
        return "attention"
    if "medium" in sevs:
        return "watch"
    return "clean"


def _recommend(findings: list) -> list:
    recs: list = []
    n_crit = sum(1 for f in findings if f.severity == "critical")
    n_high = sum(1 for f in findings if f.severity == "high")
    if n_crit:
        recs.append(f"Triage {n_crit} critical finding(s) first - each ships with explicit evidence refs.")
    if n_high:
        recs.append(f"Review {n_high} high-severity finding(s); reproduce before acting.")
    promo = [f for f in findings if f.promotion_ready]
    if promo:
        recs.append(f"Evaluate {len(promo)} promotion candidate(s); replay-test before graduating to a runtime gate.")
    inert = [f for f in findings if f.category == "gates" and "zero recent invocations" in f.title]
    if inert:
        recs.append(f"Verify liveness of {len(inert)} registered-but-silent hook(s).")
    if not recs:
        recs.append("No actionable findings; system behavior looks consistent over the window.")
    return recs


def save_history(report: AuditReport, cfg: Config) -> None:
    try:
        cfg.history_file.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": report.timestamp,
            "overall": report.summary["overall"],
            "total_findings": report.summary["total_findings"],
            "by_severity": report.summary["by_severity"],
        }
        with open(cfg.history_file, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def report_to_dict(report: AuditReport) -> dict:
    return {
        "timestamp": report.timestamp,
        "duration_ms": report.duration_ms,
        "critic_used": report.critic_used,
        "scope": report.scope,
        "summary": report.summary,
        "findings": [f.to_dict() for f in report.findings],
        "unsupported_claims": [f.to_dict() for f in report.unsupported_claims],
        "gate_health_findings": [f.to_dict() for f in report.gate_health_findings],
        "regression_candidates": [f.to_dict() for f in report.regression_candidates],
        "promotion_candidates": [f.to_dict() for f in report.promotion_candidates],
        "recommended_actions": report.recommended_actions,
    }


_SEV_ICON = {"critical": "[X]", "high": "[!]", "medium": "[~]", "info": "[i]"}
_OVERALL_ICON = {"critical": "[X]", "attention": "[!]", "watch": "[~]", "clean": "[OK]"}


def render_text(report: AuditReport) -> str:
    s = report.summary
    L: list = []
    L.append("\n" + _OVERALL_ICON[s["overall"]] + " MAIN-REVIEW -- "
             + s["overall"].upper() + " [" + str(report.duration_ms) + "ms, since "
             + str(report.scope["since_days"]) + "d]")
    L.append("=" * 64)
    L.append("Transcripts scanned : " + str(report.scope["transcripts_scanned"]))
    L.append("Diagnostics rows    : " + str(report.scope["diagnostics_rows"]))
    L.append("Registered hooks    : " + str(report.scope["sources"].get("registered_hooks", 0)))
    L.append("Findings            : " + str(s["total_findings"])
             + " (crit " + str(s["by_severity"]["critical"])
             + ", high " + str(s["by_severity"]["high"])
             + ", med " + str(s["by_severity"]["medium"])
             + ", info " + str(s["by_severity"]["info"]) + ")")
    L.append("Critic              : " + ("on" if report.critic_used else "off"))
    L.append("")

    def section(title: str, items: list) -> None:
        if not items:
            return
        L.append("## " + title + " (" + str(len(items)) + ")")
        for f in items:
            L.append(_SEV_ICON[f.severity] + " [" + f.id + "] " + f.title
                     + "  (conf " + f"{f.confidence:.2f}" + ")")
            for ev in f.evidence[:3]:
                L.append("     - " + ev)
            for ref in f.source_refs[:3]:
                L.append("     ref " + ref)
            if f.recommended_action:
                L.append("     -> " + f.recommended_action)
            if f.proposed_runtime_gate:
                L.append("     propose gate: " + f.proposed_runtime_gate)
            L.append("")

    section("UNSUPPORTED CLAIMS", report.unsupported_claims)
    section("GATE HEALTH", report.gate_health_findings)
    section("REGRESSION CANDIDATES", report.regression_candidates)
    section("PROMOTION CANDIDATES", report.promotion_candidates)

    L.append("## RECOMMENDED ACTIONS")
    for r in report.recommended_actions:
        L.append("  - " + r)
    return "\n".join(L) + "\n"


def build_self_test_root(base: Path) -> Config:
    """Materialize a synthetic telemetry root; recurrence thresholds lowered for the demo."""
    base.mkdir(parents=True, exist_ok=True)
    proj = base / "projects" / "console_selftest"
    proj.mkdir(parents=True, exist_ok=True)

    t1 = proj / "t1.jsonl"
    t1.write_text("\n".join([
        json.dumps({"type": "user", "message": {"role": "user",
            "content": [{"type": "text", "text": "Why did the build break?"}]}}),
        json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text": "Root Cause: the env var was unset. Fixed. Verified."}
        ]}}),
        json.dumps({"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "content":
                "Traceback: ModuleNotFoundError: No module named foo"}]}}),
        json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text": "Confirmed working now."}
        ]}}),
    ]), encoding="utf-8")

    t2 = proj / "t2.jsonl"
    t2.write_text("\n".join([
        json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "text", "text":
                "The helper is unused, so I removed it. ModuleNotFoundError: No module named foo"}
        ]}}),
    ]), encoding="utf-8")

    db = base / "diagnostics" / "diagnostics.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE hook_invocations (hook_name TEXT, event_type TEXT, "
                "action TEXT, reason TEXT, timestamp TEXT, session_id TEXT)")
    now = datetime.now().isoformat()
    for i in range(6):
        con.execute("INSERT INTO hook_invocations VALUES (?,?,?,?,?,?)",
                    ("rca_gate", "Stop", "allow", "", now, "s" + str(i)))
    for i in range(6):
        con.execute("INSERT INTO hook_invocations VALUES (?,?,?,?,?,?)",
                    ("broken_hook", "PostToolUse", "error", "boom", now, "e" + str(i)))
    con.commit()
    con.close()

    hooks_json = base / "plugin_a" / "hooks" / "hooks.json"
    hooks_json.parent.mkdir(parents=True, exist_ok=True)
    cmd = "python " + chr(34) + "X/inert_ghost_Stop.py" + chr(34)
    hooks_json.write_text(json.dumps({"hooks": {"Stop": [{"matcher": ".*", "hooks": [
        {"type": "command", "command": cmd}]}]}}), encoding="utf-8")

    hh = base / "health_history.jsonl"
    hh.write_text("\n".join([
        json.dumps({"checks": {"cks": "healthy"}}),
        json.dumps({"checks": {"cks": "critical"}}),
        json.dumps({"checks": {"cks": "healthy"}}),
        json.dumps({"checks": {"cks": "critical"}}),
        json.dumps({"checks": {"cks": "critical"}}),
    ]), encoding="utf-8")

    return Config(
        since_days=365,
        transcripts_root=base / "projects",
        diagnostics_db=db,
        health_history=hh,
        registered_hooks_roots=[base / "plugin_a"],
        history_file=base / "review_history.jsonl",
        max_transcripts=50,
        save_history=False,
        regression_recurrence=2,
        promotion_recurrence=1,
    )


def self_test() -> AuditReport:
    with tempfile.TemporaryDirectory() as td:
        cfg = build_self_test_root(Path(td))
        return run(cfg)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="/main-review evidence-first behavioral auditor")
    p.add_argument("--since", default="30d", help="Window: 7d, 30d, 2w, 3m (default 30d)")
    p.add_argument("--focus", action="append", choices=list(CATEGORIES),
                   help="Narrow to a category (repeatable); default = all")
    p.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    p.add_argument("--quiet", action="store_true", help="One-line summary only")
    p.add_argument("--critic", action="store_true", help="Enable optional evidence-only LLM critic")
    p.add_argument("--no-history", action="store_true", help="Do not append to review_history.jsonl")
    p.add_argument("--max-transcripts", type=int, default=50, help="Cap transcripts scanned")
    p.add_argument("--max-entries", type=int, default=0, help="Cap entries per transcript (0=unlimited)")
    p.add_argument("--lookback", type=int, default=6, help="Receipt window in entries (~3 turns)")
    p.add_argument("--data-dir", default=None,
                   help="Telemetry root override (contains projects/, diagnostics/, etc.)")
    p.add_argument("--self-test", action="store_true",
                   help="Run against a synthetic fixture (also generates sample outputs)")
    return p


def config_from_args(args) -> Config:
    cfg = Config(
        since_days=_parse_since(args.since),
        focus=set(args.focus or []),
        json_output=args.json,
        quiet=args.quiet,
        critic=args.critic,
        save_history=not args.no_history,
        max_transcripts=args.max_transcripts,
        max_entries_per_transcript=args.max_entries,
        lookback=args.lookback,
    )
    if args.data_dir:
        dd = Path(args.data_dir)
        cfg.transcripts_root = dd / "projects"
        cfg.diagnostics_db = dd / "diagnostics" / "diagnostics.db"
        cfg.health_history = dd / "health_history.jsonl"
        cfg.registered_hooks_roots = [dd]
        cfg.history_file = dd / "review_history.jsonl"
    return cfg


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.self_test:
        report = self_test()
    else:
        cfg = config_from_args(args)
        report = run(cfg)
    if args.json:
        print(json.dumps(report_to_dict(report), indent=2))
    elif args.quiet:
        s = report.summary
        print(_OVERALL_ICON[s["overall"]] + " main-review: " + s["overall"] + " -- "
              + str(s["total_findings"]) + " finding(s) [" + str(report.duration_ms) + "ms]")
    else:
        print(render_text(report))
    return _exit_code(report)


def _exit_code(report: AuditReport) -> int:
    sevs = {f.severity for f in report.findings}
    if "critical" in sevs:
        return 2
    if {"high", "medium"} & sevs:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
