#!/usr/bin/env python3
"""
hook_health_check.py - Analyze hook performance and health from logs

Run: python P:\\\\\\.claude/skills/_tools/hook_health_check.py
Returns exit code 0 if healthy, 1 if issues found

Checks:
1. Hook timeout rate (>20% = unhealthy)
2. Average latency (>2s = slow)
3. Stale hooks (no runs in 7+ days)
4. Log directory size
5. Hook error patterns
"""

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Thresholds
TIMEOUT_RATE_THRESHOLD = 0.20  # 20%
LATENCY_THRESHOLD_MS = 2000  # 2 seconds
STALE_DAYS = 7
LOG_SIZE_WARN_MB = 50
SAMPLE_SIZE = 50  # Last N runs to analyze

# Hooks intentionally retired from ACTIVE_RUNTIME_HOOKS in Stop_router.py.
# They have old log files from when they were active but add zero runtime overhead.
# Suppress staleness warnings for these — they are not broken, just disabled.
KNOWN_RETIRED_HOOKS: frozenset[str] = frozenset(
    {
        "behavioral_quality_gate",
        "investigation_required",
        "overconfidence_detector",
        "sycophancy_agreement",
        "tool_thrashing",
        "value_assessment",
    }
)

HOOKS_DIR = Path(r"P:\\\\\\.claude/hooks")
LOGS_DIR = HOOKS_DIR / "logs"
SETTINGS_PATH = Path(r"P:\\\\\\.claude/settings.json")


def parse_log_entry(line: str) -> dict | None:
    """Parse a pipe-delimited log entry."""
    # Format: timestamp|TYPE|details|key=value...
    parts = line.strip().split("|")
    if len(parts) < 2:
        return None

    try:
        timestamp = datetime.fromisoformat(parts[0])
        entry_type = parts[1]
        return {
            "timestamp": timestamp,
            "type": entry_type,
            "details": parts[2] if len(parts) > 2 else "",
            "raw": line,
        }
    except (ValueError, IndexError):
        return None


def analyze_log_file(log_path: Path) -> dict:
    """Analyze a single log file for health metrics."""
    stats = {
        "name": log_path.stem,
        "entries": 0,
        "timeouts": 0,
        "errors": 0,
        "last_run": None,
        "latencies": [],
        "size_mb": 0,
    }

    try:
        # Skip files > 50MB (likely corrupted or runaway logging)
        file_size = log_path.stat().st_size
        stats["size_mb"] = file_size / (1024 * 1024)
        if file_size > 50 * 1024 * 1024:
            stats["error"] = f"File too large: {stats['size_mb']:.0f}MB"
            return stats

        # Read only last N lines efficiently using tail-like approach
        lines = []
        with open(log_path, "rb") as f:
            # Seek to end, read backwards to find last N lines
            f.seek(0, 2)  # End of file
            file_size = f.tell()
            block_size = min(8192, file_size)
            blocks = []
            while len(lines) < SAMPLE_SIZE and f.tell() > 0:
                read_size = min(block_size, f.tell())
                f.seek(f.tell() - read_size)
                blocks.append(f.read(read_size))
                f.seek(f.tell() - read_size)
            content = b"".join(reversed(blocks)).decode("utf-8", errors="ignore")
            lines = content.splitlines()[-SAMPLE_SIZE:]

        for line in lines:
            entry = parse_log_entry(line)
            if not entry:
                continue

            stats["entries"] += 1

            # Track last run time
            if stats["last_run"] is None or entry["timestamp"] > stats["last_run"]:
                stats["last_run"] = entry["timestamp"]

            # Count timeouts
            if "TIMEOUT" in entry["type"].upper() or "timeout" in line.lower():
                stats["timeouts"] += 1

            # Count errors
            if "ERROR" in entry["type"].upper() or "FAIL" in entry["type"].upper():
                stats["errors"] += 1

            # Extract latency if present (look for ms= or duration=)
            latency_match = re.search(r"(?:ms|duration|latency)[=:](\d+)", line, re.I)
            if latency_match:
                stats["latencies"].append(int(latency_match.group(1)))

    except Exception as e:
        stats["error"] = str(e)

    return stats


def get_configured_hooks() -> set:
    """Get list of hooks from settings.json."""
    hooks = set()
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            settings = json.load(f)

        for lifecycle, entries in settings.get("hooks", {}).items():
            for entry in entries:
                for hook in entry.get("hooks", []):
                    cmd = hook.get("command", "")
                    # Extract hook name from command
                    match = re.search(r"(\w+)\.py", cmd)
                    if match:
                        hooks.add(match.group(1))
    except Exception:
        pass
    return hooks


def get_log_directory_size() -> float:
    """Get total size of logs directory in MB."""
    total = 0
    if LOGS_DIR.exists():
        for f in LOGS_DIR.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    return total / (1024 * 1024)


def main():
    issues = []
    warnings = []
    metrics = []

    now = datetime.now(timezone.utc)
    stale_threshold = now - timedelta(days=STALE_DAYS)

    # 1. Check log directory size
    log_size_mb = get_log_directory_size()
    if log_size_mb > LOG_SIZE_WARN_MB:
        warnings.append(f"Log directory size: {log_size_mb:.1f}MB (>{LOG_SIZE_WARN_MB}MB)")

    # 1b. Flag oversized individual log files
    oversized_logs = []
    if LOGS_DIR.exists():
        for log_file in LOGS_DIR.glob("*.log"):
            size_mb = log_file.stat().st_size / (1024 * 1024)
            if size_mb > 50:
                oversized_logs.append((log_file.stem, size_mb))
    if oversized_logs:
        for name, size in oversized_logs:
            issues.append(f"{name}.log: {size:.0f}MB (runaway logging, truncate or delete)")

    # 2. Get configured hooks for staleness check
    configured_hooks = get_configured_hooks()

    # 3. Analyze each log file
    if LOGS_DIR.exists():
        for log_file in LOGS_DIR.glob("*.log"):
            stats = analyze_log_file(log_file)

            if stats["entries"] == 0:
                continue

            hook_name = stats["name"]

            # Timeout rate
            timeout_rate = stats["timeouts"] / stats["entries"] if stats["entries"] > 0 else 0
            if timeout_rate > TIMEOUT_RATE_THRESHOLD:
                issues.append(
                    f"{hook_name}: {timeout_rate:.0%} timeout rate ({stats['timeouts']}/{stats['entries']})"
                )

            # Average latency
            if stats["latencies"]:
                avg_latency = sum(stats["latencies"]) / len(stats["latencies"])
                if avg_latency > LATENCY_THRESHOLD_MS:
                    warnings.append(
                        f"{hook_name}: {avg_latency:.0f}ms avg latency (>{LATENCY_THRESHOLD_MS}ms)"
                    )
                metrics.append((hook_name, avg_latency, stats["entries"]))

            # Staleness — skip intentionally retired hooks
            if hook_name not in KNOWN_RETIRED_HOOKS:
                if stats["last_run"] and stats["last_run"] < stale_threshold:
                    days_old = (now - stats["last_run"]).days
                    warnings.append(f"{hook_name}: no activity in {days_old} days")

    # 4. Check for hooks without any log files
    logged_hooks = {f.stem for f in LOGS_DIR.glob("*.log")} if LOGS_DIR.exists() else set()
    # Only flag if we know about configured hooks and they're missing logs
    # (Some hooks intentionally don't log)

    # Output
    if issues or warnings:
        print("⚠️  HOOK HEALTH CHECK")
        print(f"   Log dir: {log_size_mb:.1f}MB | Analyzed: {len(metrics)} hooks")

        if issues:
            print("\n❌ ISSUES (action required):")
            for i in issues:
                print(f"   • {i}")

        if warnings:
            print("\n⚡ WARNINGS:")
            for w in warnings:
                print(f"   • {w}")

        # Show top 5 slowest hooks
        if metrics:
            print("\n📊 LATENCY (top 5):")
            for name, latency, count in sorted(metrics, key=lambda x: -x[1])[:5]:
                print(f"   • {name}: {latency:.0f}ms (n={count})")

        print("\nRun: claude 'analyze hook performance for [hook_name]'")
        return 1
    else:
        hook_count = len(metrics) if metrics else 0
        print(f"✅ Hooks healthy ({hook_count} analyzed, {log_size_mb:.1f}MB logs)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
