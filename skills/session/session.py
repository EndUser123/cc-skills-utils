#!/usr/bin/env python3
"""
Session Management Skill Implementation

Provides CLI commands for managing logical work sessions.
Multi-terminal safe: Uses session_id for logical grouping, terminal_id for collision safety.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add hooks directory to path for imports
hooks_dir = Path(__file__).parent.parent.parent / "hooks"
sys.path.insert(0, str(hooks_dir))

from __lib.session_manager import (
    SessionManager,
    create_session,
    get_current_session_id,
    list_sessions,
    rename_session,
    switch_session,
    claim_task,
    get_session_info,
)


def format_session_list(sessions: list[dict]) -> str:
    """Format session list for display."""
    if not sessions:
        return "No sessions found."

    lines = ["**Sessions:**", ""]
    current_id = get_current_session_id()

    for i, session in enumerate(sessions, 1):
        session_id = session.get("session_id", "unknown")
        name = session.get("name", session_id)
        is_current = " → *current*" if session_id == current_id else ""
        task_count = session.get("task_count", 0)

        # Format timestamp
        created = session.get("created_at", 0)
        if created:
            created_str = datetime.fromtimestamp(created).strftime("%Y-%m-%d %H:%M")
        else:
            created_str = "Unknown"

        lines.append(f"{i}. **{name}**{is_current}")
        lines.append(f"   ID: `{session_id}`")
        lines.append(f"   Tasks: {task_count}")
        lines.append(f"   Created: {created_str}")
        lines.append("")

    return "\n".join(lines)


def format_session_info(info: dict) -> str:
    """Format session info for display."""
    lines = ["**Current Session:**", ""]
    lines.append(f"**Name:** {info.get('name', 'unknown')}")
    lines.append(f"**ID:** `{info.get('session_id', 'unknown')}`")

    created = info.get("created_at", 0)
    if created:
        created_str = datetime.fromtimestamp(created).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"**Created:** {created_str}")

    activity = info.get("last_activity", 0)
    if activity:
        activity_str = datetime.fromtimestamp(activity).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"**Last Activity:** {activity_str}")

    tasks = info.get("tasks", [])
    if tasks:
        lines.append(f"**Tasks:** {len(tasks)}")
        for task_id in tasks[:10]:
            lines.append(f"  - #{task_id}")
        if len(tasks) > 10:
            lines.append(f"  - ... and {len(tasks) - 10} more")
    else:
        lines.append("**Tasks:** None")

    metadata = info.get("metadata", {})
    if metadata:
        lines.append("**Metadata:**")
        for key, value in metadata.items():
            lines.append(f"  - {key}: {value}")

    return "\n".join(lines)


def cmd_list() -> str:
    """List all sessions."""
    sessions = list_sessions()
    return format_session_list(sessions)


def cmd_create(name: str) -> str:
    """Create new session and switch to it."""
    sm = SessionManager()
    session_id = sm.create(name)
    return f"✓ Created session: **{name}**\n**ID:** `{session_id}`\n\nSwitched to new session."


def cmd_rename(new_name: str) -> str:
    """Rename current session."""
    sm = SessionManager()
    old_name = sm.get_info().get("name", sm.get_current_id())
    sm.rename(new_name)
    return f"✓ Renamed session: **{old_name}** → **{new_name}**"


def cmd_switch(session_id: str) -> str:
    """Switch to different session."""
    sm = SessionManager()

    # Find session by partial ID match or full ID
    sessions = list_sessions()
    target_id = None

    # Try exact match first
    for session in sessions:
        if session.get("session_id") == session_id:
            target_id = session_id
            break

    # Try partial match
    if not target_id:
        for session in sessions:
            sid = session.get("session_id", "")
            if session_id in sid:
                target_id = sid
                break

    # Try name match
    if not target_id:
        for session in sessions:
            if session.get("name", "").lower() == session_id.lower():
                target_id = session.get("session_id")
                break

    if not target_id:
        return f"❌ Session not found: `{session_id}`\n\nUse `/session` to list available sessions."

    sm.switch_to(target_id)
    info = sm.get_info()
    return f"✓ Switched to session: **{info.get('name')}**\n**ID:** `{target_id}`"


def cmd_claim(task_id: str) -> str:
    """Claim task for current session."""
    sm = SessionManager()
    try:
        sm.claim(task_id)
        info = sm.get_info()
        return f"✓ Claimed task **#{task_id}** for session: **{info.get('name')}**"
    except ValueError as e:
        return f"❌ {str(e)}\n\nUse `/session` to see current session tasks."


def cmd_info() -> str:
    """Show current session info."""
    sm = SessionManager()
    info = sm.get_info()
    return format_session_info(info)


def main():
    """Execute session management command."""
    import argparse

    parser = argparse.ArgumentParser(description="Session Management CLI")
    parser.add_argument("command", nargs="?", default="list", help="Command to execute")
    parser.add_argument("arg", nargs="?", help="Command argument")

    args = parser.parse_args()

    command = args.command.lower()
    arg = args.arg

    try:
        if command == "list" or not command:
            result = cmd_list()
        elif command == "rename" and arg:
            result = cmd_rename(arg)
        elif command == "switch" and arg:
            result = cmd_switch(arg)
        elif command == "claim" and arg:
            result = cmd_claim(arg)
        elif command == "info":
            result = cmd_info()
        else:
            # Treat as create command
            if command and not arg:
                result = cmd_create(command)
            else:
                result = f"❌ Unknown command: {command}\n\nSee `/session` SKILL.md for usage."

        print(result)
        return 0

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
