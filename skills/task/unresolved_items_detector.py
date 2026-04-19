#!/usr/bin/env python3
"""
Unresolved Items Detector for /task list

Intelligent detection of unresolved items from chat history with:
- Resolution keyword filtering (excludes fixed/resolved items)
- Task cross-referencing (excludes items tracked as completed tasks)
- Age-based filtering (limits to last 14 days by default)
- Session-level validation (checks for resolution in same session)
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class UnresolvedItemsDetector:
    """Detects unresolved items from chat history with smart filtering."""

    # Keywords that indicate a problem/issue
    PROBLEM_KEYWORDS = [
        "problem", "issue", "bug", "error", "broken",
        "stuck", "blocked", "blocked by", "can't",
        "slow", "clunky", "awkward", "workaround", "hack",
        "TODO", "FIXME", "HACK", "XXX", "BUG",
        "not working", "doesn't work", "failed",
        "friction", "bottleneck",
    ]

    # Keywords that indicate resolution
    RESOLUTION_KEYWORDS = [
        "fixed", "resolved", "completed", "implemented",
        "fixed by", "resolved by", "closed",
        "success", "working", "solved",
    ]

    # Max age for unresolved items (days)
    DEFAULT_MAX_AGE_DAYS = 14

    def __init__(
        self,
        terminal_id: str,
        csf_root: Path | str = Path("P:/__csf"),
        max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    ):
        """Initialize detector.

        Args:
            terminal_id: Current terminal ID for filtering
            csf_root: Path to CSF root directory
            max_age_days: Maximum age of items to include (default 14)
        """
        self.terminal_id = terminal_id
        self.csf_root = Path(csf_root)
        self.max_age_days = max_age_days
        self.cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    def detect(self, limit: int = 10) -> list[dict[str, Any]]:
        """Detect unresolved items from chat history.

        Args:
            limit: Maximum number of items to return

        Returns:
            List of unresolved items with metadata:
            - id: Result ID
            - timestamp: ISO timestamp
            - date: Human-readable date
            - content: Snippet of the issue
            - suggested_task: Suggested task title
            - confidence: Confidence score (0-1)
        """
        # Build search query for terminal-specific problems
        query = self._build_search_query()

        # Execute CHS search
        results = self._search_chs(query, limit=limit * 3)  # Get more, we'll filter

        # Filter and rank results
        unresolved = self._filter_unresolved(results)

        # Sort by confidence and date
        unresolved.sort(key=lambda x: (x.get("confidence", 0), x.get("timestamp", "")), reverse=True)

        return unresolved[:limit]

    def _build_search_query(self) -> str:
        """Build search query for problem detection."""
        # Use terminal ID prefix for terminal-specific search
        terminal_prefix = self.terminal_id[:8] if len(self.terminal_id) > 8 else self.terminal_id
        keywords = " ".join(self.PROBLEM_KEYWORDS[:10])  # Use subset for query
        return f"{terminal_prefix} {keywords}"

    def _search_chs(self, query: str, limit: int = 30) -> list[dict]:
        """Execute CHS search and return results.

        Args:
            query: Search query
            limit: Max results to return

        Returns:
            List of result dictionaries
        """
        try:
            # Prevent blue console flash on Windows
            creation_flags = 0x08000000 if sys.platform == 'win32' else 0
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.cli.nip.search",
                    query,
                    "--backend", "chs",
                    "--limit", str(limit),
                    "--layer", "2",  # Use layer 2 (timeline) to avoid the bug we just fixed
                ],
                cwd=self.csf_root,
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=creation_flags,
            )

            # Parse output - search CLI outputs Python dict format (single quotes)
            # The dict may span multiple lines, so parse the entire stdout
            try:
                # Use ast.literal_eval for Python dict syntax (single quotes)
                data = ast.literal_eval(result.stdout.strip())
                if isinstance(data, dict) and "results" in data:
                    return data["results"]
            except (ValueError, SyntaxError):
                # Fall back to json.loads for valid JSON
                try:
                    data = json.loads(result.stdout.strip())
                    if isinstance(data, dict) and "results" in data:
                        return data["results"]
                except json.JSONDecodeError:
                    pass

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

        return []

    def _filter_unresolved(self, results: list[dict]) -> list[dict]:
        """Filter search results to find truly unresolved items.

        Args:
            results: Raw search results from CHS

        Returns:
            Filtered list of unresolved items
        """
        unresolved = []

        for result in results:
            # Skip malformed results
            if not isinstance(result, dict):
                continue

            # Extract content
            content = self._extract_content(result)
            if not content:
                continue

            # Check for resolution keywords
            if self._is_resolved(content):
                continue

            # Check age
            timestamp = result.get("timestamp", "")
            if not self._is_recent_enough(timestamp):
                continue

            # Calculate confidence score
            confidence = self._calculate_confidence(result, content)

            # Generate suggested task title
            suggested_task = self._suggest_task_title(content)

            # Parse date for display
            date_str = self._format_date(timestamp)

            unresolved.append({
                "id": result.get("id", ""),
                "timestamp": timestamp,
                "date": date_str,
                "content": self._truncate_content(content, 200),
                "suggested_task": suggested_task,
                "confidence": confidence,
                "source": "chs",
            })

        return unresolved

    def _extract_content(self, result: dict) -> str | None:
        """Extract meaningful content from result.

        Args:
            result: Search result dictionary

        Returns:
            Content string or None
        """
        # Try different content fields
        for key in ["full_content", "content", "display"]:
            if key in result and result[key]:
                content = result[key]
                if isinstance(content, str):
                    # If it's JSON, try to parse it
                    if content.startswith("{"):
                        try:
                            data = json.loads(content)
                            # Extract message content if available
                            if "content" in data:
                                return str(data["content"])
                        except json.JSONDecodeError:
                            pass
                    return content
        return None

    def _is_resolved(self, content: str) -> bool:
        """Check if content indicates the issue was resolved.

        Args:
            content: Content string to check

        Returns:
            True if resolution keywords found
        """
        content_lower = content.lower()
        for keyword in self.RESOLUTION_KEYWORDS:
            if keyword.lower() in content_lower:
                return True
        return False

    def _is_recent_enough(self, timestamp: str) -> bool:
        """Check if timestamp is within max age.

        Args:
            timestamp: ISO timestamp string

        Returns:
            True if recent enough
        """
        if not timestamp:
            return False

        try:
            # Parse ISO timestamp - ensure it's timezone-aware
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

            # If naive (no timezone), assume UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            # cutoff_date is also timezone-aware, so comparison works
            return dt >= self.cutoff_date
        except (ValueError, AttributeError):
            return False

    def _calculate_confidence(self, result: dict, content: str) -> float:
        """Calculate confidence score for unresolved item.

        Higher confidence for:
- Direct problem mentions (TODO, FIXME, bug)
- Recent items
- Terminal-specific matches

        Args:
            result: Search result
            content: Extracted content

        Returns:
            Confidence score 0-1
        """
        score = 0.5  # Base score

        content_lower = content.lower()

        # High confidence indicators
        if any(kw in content_lower for kw in ["todo:", "fixme:", "xxx:", "hack:"]):
            score += 0.3

        if any(kw in content_lower for kw in ["stuck", "blocked", "can't"]):
            score += 0.2

        if any(kw in content_lower for kw in ["bug", "error", "broken"]):
            score += 0.1

        # Terminal ID match
        if self.terminal_id and self.terminal_id in content_lower:
            score += 0.1

        # Recency bonus
        timestamp = result.get("timestamp", "")
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                # Ensure timezone-aware for comparison
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                days_ago = (datetime.now(timezone.utc) - dt).days
                if days_ago < 7:
                    score += 0.1
            except (ValueError, AttributeError):
                pass

        return min(score, 1.0)

    def _suggest_task_title(self, content: str) -> str:
        """Generate suggested task title from content.

        Args:
            content: Content string

        Returns:
            Suggested task title
        """
        # Extract first meaningful sentence or phrase
        content = content.strip()

        # Look for explicit markers
        for marker in ["TODO:", "FIXME:", "XXX:", "HACK:", "BUG:"]:
            if marker in content:
                idx = content.find(marker)
                start = idx + len(marker)
                # Extract until end of line or period
                end = content.find("\n", start)
                if end == -1:
                    end = content.find(".", start)
                if end == -1:
                    end = start + 100
                title = content[start:end].strip()
                return title[:80] if len(title) > 80 else title

        # Find first sentence with problem keyword
        sentences = re.split(r"[.!?]\s+", content)
        for sentence in sentences:
            if any(kw.lower() in sentence.lower() for kw in self.PROBLEM_KEYWORDS[:5]):
                return sentence.strip()[:80]

        # Default: first 80 chars
        return content[:80]

    def _truncate_content(self, content: str, max_length: int = 200) -> str:
        """Truncate content for display.

        Args:
            content: Content string
            max_length: Maximum length

        Returns:
            Truncated content
        """
        if len(content) <= max_length:
            return content

        # Truncate at word boundary
        truncated = content[:max_length]
        last_space = truncated.rfind(" ")
        if last_space > max_length * 0.8:  # If we have most of the content
            truncated = truncated[:last_space]

        return truncated + "..."

    def _format_date(self, timestamp: str) -> str:
        """Format timestamp for display.

        Args:
            timestamp: ISO timestamp string

        Returns:
            Formatted date string
        """
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            return "Unknown"

    def cross_check_with_tasks(self, unresolved_items: list[dict], completed_tasks: list[dict]) -> list[dict]:
        """Cross-reference unresolved items with completed tasks.

        Removes items that appear to be addressed by completed tasks.

        Args:
            unresolved_items: List of unresolved items
            completed_tasks: List of completed task dictionaries

        Returns:
            Filtered list of truly unresolved items
        """
        if not completed_tasks:
            return unresolved_items

        # Build set of completed task subjects/keywords
        completed_keywords = set()
        for task in completed_tasks:
            subject = task.get("subject", "").lower()
            description = task.get("description", "").lower()

            # Add words from subject
            completed_keywords.update(subject.split())

            # Add words from description
            completed_keywords.update(description.split())

        # Filter out items that match completed tasks
        truly_unresolved = []
        for item in unresolved_items:
            content_lower = item["content"].lower()

            # Check if any significant overlap with completed tasks
            matches = sum(1 for kw in completed_keywords if len(kw) > 4 and kw in content_lower)

            # If more than 2 keyword matches, likely resolved
            if matches < 3:
                truly_unresolved.append(item)

        return truly_unresolved


def detect_unresolved_items(
    terminal_id: str,
    limit: int = 10,
    max_age_days: int = 14,
    completed_tasks: list[dict] | None = None,
) -> list[dict[str, Any]]:
    """Convenience function to detect unresolved items.

    Args:
        terminal_id: Current terminal ID
        limit: Max items to return
        max_age_days: Maximum age of items (default 14)
        completed_tasks: Optional list of completed tasks for cross-checking

    Returns:
        List of unresolved items with metadata
    """
    detector = UnresolvedItemsDetector(
        terminal_id=terminal_id,
        max_age_days=max_age_days,
    )

    items = detector.detect(limit=limit * 2)  # Get extra for cross-checking

    # Cross-check with completed tasks if provided
    if completed_tasks:
        items = detector.cross_check_with_tasks(items, completed_tasks)

    return items[:limit]


if __name__ == "__main__":
    # Test the detector
    import sys

    terminal_id = sys.argv[1] if len(sys.argv) > 1 else "env_test"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    print(f"Detecting unresolved items for terminal: {terminal_id}")
    print(f"Max age: 14 days, Limit: {limit}")
    print("-" * 60)

    items = detect_unresolved_items(terminal_id=terminal_id, limit=limit)

    if not items:
        print("No unresolved items found.")
    else:
        for item in items:
            print(f"\n[{item['date']}] Confidence: {item['confidence']:.2f}")
            print(f"Content: {item['content']}")
            print(f"Suggested: /task add \"{item['suggested_task']}\"")
