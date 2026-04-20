# Language Detection & Translation Guide

Detailed procedures for detecting non-English skills and translating them.

## Detection Procedure

1. **Detect Language:**
   - Scan the SKILL.md content for non-ASCII characters and language patterns
   - Check for Chinese characters (CJK range), Arabic, Cyrillic, etc.
   - Analyze prose sections (excluding code blocks and YAML frontmatter)

2. **If Non-English Detected:**
   - **Ask User:** "This skill is written in [detected language]. Would you like me to:
       > A) Translate it to English before installing
       > B) Install it as-is (you'll need to read [language])
       > C) Skip this skill"

## Translation Workflow (if user chooses A)

- **Preserve YAML frontmatter exactly** -- critical for skill metadata
- **Preserve all code blocks** -- don't translate code, examples, or commands
- **Translate only prose sections** -- descriptions, instructions, comments
- **Validate after translation** -- ensure YAML still parses, structure intact
- **Add translation note** to frontmatter metadata:
    ```yaml
    metadata:
      translated-from: "chinese"
      translated-date: "2026-03-03"
    ```

## Implementation

```bash
# Use Python to detect and translate
python3 -c "
import sys
import re

# Read skill file
with open('/tmp/skill-download.md', 'r', encoding='utf-8') as f:
    content = f.read()

# Detect non-ASCII characters
non_ascii = sum(1 for c in content if ord(c) > 127)
total = len(content)
ratio = non_ascii / total if total > 0 else 0

# Simple language detection
has_cjk = bool(re.search(r'[\u4e00-\u9fff]', content))  # Chinese
has_cyrillic = bool(re.search(r'[\u0400-\u04FF]', content))  # Russian
has_arabic = bool(re.search(r'[\u0600-\u06FF]', content))  # Arabic

if has_cjk or has_cyrillic or has_arabic or ratio > 0.1:
    print(f'NON_ENGLISH_DETECTED:{has_cjk}:{has_cyrillic}:{has_arabic}:{ratio:.2f}')
else:
    print('ENGLISH')
"

# If translation needed, use translation API or LLM
# Preserve YAML frontmatter and code blocks during translation
```

## Translation Quality Checks

- YAML frontmatter must remain valid
- Code blocks (```) must not be translated
- Skill name and description should be translated to English
- Technical terms should be preserved or accompanied by English equivalents
- Examples and commands should remain functional
