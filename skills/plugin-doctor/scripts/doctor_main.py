#!/usr/bin/env python3
"""
Cluster Doctor - Main diagnostic script.
Verifies the health and performance of the cc-skills plugin cluster.
"""

import json
import os
import sys
import time
from pathlib import Path

# Colors for CLI output
C_GREEN = "\033[92m"
C_RED = "\033[91m"
C_YELLOW = "\033[93m"
C_CYAN = "\033[96m"
C_RESET = "\033[0m"

def check_identity_handshake():
    """Verify the stale-proof identity handshake is working."""
    print(f"Checking Identity Handshake...", end=" ")
    
    tid = os.environ.get("CLAUDE_TERMINAL_ID")
    if not tid:
        # Fallback detection similar to hooks
        wt_session = os.environ.get("WT_SESSION")
        if wt_session:
            tid = f"console_{wt_session}"
        else:
            print(f"{C_YELLOW}WARN (No Terminal ID detected){C_RESET}")
            return

    safe_tid = tid.replace("/", "-").replace("\\", "-").replace(":", "-")
    identity_path = Path("P:/.claude/.artifacts") / safe_tid / "identity.json"

    if not identity_path.exists():
        print(f"{C_RED}FAIL (identity.json missing for {tid}){C_RESET}")
        return

    try:
        data = json.loads(identity_path.read_text(encoding="utf-8"))
        cached_sid = data.get("claude", {}).get("session_id")
        live_sid = os.environ.get("CLAUDE_SESSION_ID")

        if live_sid and cached_sid != live_sid:
             print(f"{C_RED}FAIL (Stale data: cached={cached_sid[:8]}, live={live_sid[:8]}){C_RESET}")
        else:
             print(f"{C_GREEN}OK{C_RESET}")
    except Exception as e:
        print(f"{C_RED}ERROR ({e}){C_RESET}")

def check_junctions():
    """Verify marketplace junctions are healthy."""
    print(f"Checking Marketplace Junctions...", end=" ")
    marketplace_dir = Path("P:/packages/.claude-marketplace/plugins")
    if not marketplace_dir.exists():
        print(f"{C_YELLOW}SKIP (Marketplace not found){C_RESET}")
        return

    orphans = []
    try:
        for entry in marketplace_dir.iterdir():
            if entry.is_symlink():
                target = entry.resolve()
                if not target.exists():
                    orphans.append(entry.name)

        if orphans:
            print(f"{C_RED}FAIL ({len(orphans)} orphaned junctions: {', '.join(orphans)}){C_RESET}")
        else:
            print(f"{C_GREEN}OK{C_RESET}")
    except Exception as e:
        print(f"{C_RED}ERROR ({e}){C_RESET}")

def check_version_drift():
    """Check for version misalignment in the cluster."""
    print(f"Checking Version Drift...", end=" ")
    packages_dir = Path("P:/packages")
    versions = {}
    try:
        for pkg in packages_dir.iterdir():
            if pkg.name.startswith("cc-skills-") and pkg.is_dir():
                manifest = pkg / ".claude-plugin" / "plugin.json"
                if manifest.exists():
                    try:
                        data = json.loads(manifest.read_text(encoding="utf-8"))
                        versions[pkg.name] = data.get("version", "0.0.0")
                    except:
                        pass
        
        unique_versions = set(versions.values())
        if len(unique_versions) > 1:
            print(f"{C_YELLOW}WARN (Drift detected: {versions}){C_RESET}")
        else:
            print(f"{C_GREEN}OK ({list(unique_versions)[0]}){C_RESET}")
    except Exception as e:
        print(f"{C_RED}ERROR ({e}){C_RESET}")

def main():
    print(f"\n{C_CYAN}=== Claude Code Cluster Doctor ==={C_RESET}")
    check_identity_handshake()
    check_junctions()
    check_version_drift()
    print(f"{C_CYAN}=================================={C_RESET}\n")

if __name__ == "__main__":
    main()
