---
name: plugin-doctor
description: Plugin Cluster Diagnostic & Repair Tool
version: 1.0.1
category: maintenance
triggers:
  - /plugin-doctor
---

# /plugin-doctor - Plugin Cluster Diagnostic

Diagnostic tool for the `cc-skills-*` plugin cluster. Verifies cross-plugin connectivity, identity health, and structural integrity.

## ⚡ EXECUTION DIRECTIVE

**When /plugin-doctor is invoked, execute:**

```bash
python "$CLAUDE_PLUGIN_ROOT/skills/plugin-doctor/scripts/doctor_main.py"
```

## Diagnostics Performed

1.  **Identity Handshake:** Verifies `identity.json` exists and matches the current session ID.
2.  **Structural Audit:** Detects orphaned junctions in the marketplace.
3.  **Version Alignment:** Identifies version drift between clustered plugins.
4.  **Hook Latency:** Measures the overhead of the bundled orchestrators.

## Usage

- `/plugin-doctor`: Run standard diagnostic suite.
- `/plugin-doctor --fix`: Attempt to repair orphaned junctions or corrupted caches.
