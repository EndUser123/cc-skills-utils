# Frontmatter Validation Reference

## claude.ai / Claude Desktop Frontmatter Compatibility

When packaging a skill for **claude.ai** or **Claude Desktop**, validate the SKILL.md frontmatter against the [Agent Skills specification](https://agentskills.io/specification). Claude Desktop uses `strictyaml` (not standard PyYAML) which rejects ambiguous YAML constructs like block scalars. It will reject non-compliant skills with "malformed YAML frontmatter" or "unexpected key" errors.

### Allowed Top-Level Frontmatter Fields (Agent Skills spec)

| Field | Required | Constraints |
| :--- | :--- | :--- |
| `name` | Yes | Max 64 chars, lowercase letters/numbers/hyphens only, must match directory name |
| `description` | Yes | Max 1024 chars. No angle brackets (`<` or `>`). Avoid literal block scalars (`|`) -- known to fail with blank lines. Folded scalars (`>`) work but inline strings are safest |
| `license` | No | License name or reference to bundled file |
| `compatibility` | No | Max 500 chars, environment requirements |
| `metadata` | No | Flat key-value pairs only (string keys to string values -- no nested objects, no arrays) |
| `allowed-tools` | No | Space-delimited list of pre-approved tools (experimental) |

### Using the Validation Script

```bash
# Validate a SKILL.md
python3 scripts/validate_frontmatter.py /path/to/SKILL.md

# Validate and auto-fix in place
python3 scripts/validate_frontmatter.py /path/to/SKILL.md --fix

# Validate and fix a ZIP file (rewrites SKILL.md inside the ZIP)
python3 scripts/validate_frontmatter.py /path/to/skill.zip --fix
```

The script (`scripts/validate_frontmatter.py`) is zero-dependency Python 3. It checks all constraints and with `--fix` automatically applies these corrections:
- Moves unsupported top-level keys (e.g., `version`, `author`, `homepage`, `category`) into `metadata` as string values
- Flattens nested `metadata` objects (e.g., `metadata.clawdbot.requires.bins: [x, y]` -> `metadata.clawdbot-requires-bins: "x, y"`)
- Converts non-string metadata values to quoted strings (e.g., `true` -> `"true"`)
- Collapses literal block scalar (`|`) descriptions to inline quoted strings (known to fail with blank lines). Folded scalars (`>`) trigger a warning but work in current Claude Desktop
- Strips angle brackets (`<` `>`) from description (Anthropic's validator rejects them)
- Converts YAML list-format `allowed-tools` to space-delimited string
- Truncates `description` if over 1024 chars
- Validates the fix and reports if any issues remain

### Manual Validation (if script unavailable)

1. Read the SKILL.md frontmatter
2. Check all top-level keys are in the allowed set: `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`
3. If `metadata` is present, verify all values are strings (no nested objects or arrays)
4. Verify `name` is lowercase with hyphens only, max 64 chars
5. Verify `description` is max 1024 chars

If validation fails, tell the user exactly what's wrong and offer to fix it (run the script with `--fix`, or apply the fixes manually).
