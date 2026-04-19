# PHASE 4.7: Media Generation (Detailed Reference)

**Objective**: Generate professional portfolio assets (banners, diagrams, videos) for GitHub showcase.

**When**: Automatically runs after PHASE 4.5 (Code Review) completes, before PHASE 5 (Portfolio Polish).

**What this does**:
- Generates visual assets for portfolio-quality packages
- Creates banner images for GitHub social preview
- Builds static overview images plus GitHub-safe Mermaid flowcharts
- Produces one concise technical explainer video focused on architecture, workflow, and outputs
- Creates a dedicated HTML video player page for GitHub Pages playback
- Verifies asset quality with vision API before acceptance

## Generated Assets

| Asset | Purpose | Tools (recommended first) | Time | Output Formats |
|-------|---------|---------------------------|------|---------------|
| **Banner** | GitHub social preview (1200x630) | OpenRouter (DALL-E 3), Midjourney, Stable Diffusion, PIL (manual) | ~30s | `assets/banners/{package}_banner.png` |
| **Architecture overview image** | Visual system overview | NotebookLM, DALL-E 3, Mermaid -> PNG, PlantUML, Graphviz | ~2min | `assets/infographics/{package}_architecture.png` |
| **System overview flowchart** | GitHub-safe architecture view | Mermaid, PlantUML, Graphviz DOT, draw.io | ~1min | `docs/diagrams/system_overview.mmd` |
| **Workflow flowchart** | Phase-by-phase pipeline view | Mermaid, PlantUML, Graphviz DOT | ~1min | `docs/diagrams/workflow.mmd` |
| **Explainer video** | AI-narrated technical walkthrough | NotebookLM, Luma Dream Machine, Runway Gen-3, HeyGen | ~1-3min target | `assets/videos/{package}_explainer_pbs.mp4` |
| **Slide deck** | Interactive presentation | NotebookLM, Marp, Pandoc, PowerPoint | ~2min | `assets/slides/{package}_slides.pdf` |
| **Video player page** | Browser playback via GitHub Pages | Static HTML, GitHub default (no player) | ~30s | `docs/video.html` |

## Tool Selection Notes

- **NotebookLM**: Best for comprehensive assets (infographics + videos + slides) from source code analysis
- **OpenRouter/DALL-E 3**: Best for branded banner generation with text rendering
- **Mermaid**: Best for code-as-diagram flowcharts that render directly in GitHub
- **PIL (Python Imaging Library)**: Manual fallback for simple gradient/text banners
- **Marp**: Markdown-based slide deck alternative with GitHub rendering
- **PlantUML**: Alternative to Mermaid for UML-specific diagrams

## Auto-skip Conditions

- No README images detected (`.gif`, `.png` in README)
- User explicitly opts out with `--skip media`

## Provider Requirements

- **NotebookLM**: `uv tool install notebooklm-mcp-cli` (v0.4.4+) + `nlm login`
- **visual-explainer:generate-web-diagram**: Installed via `/universal-skills-manager` or ClawHub
- **OpenRouter**: `OPENROUTER_API_KEY` environment variable (for banner generation, optional)

## If Providers Missing

- Check provider status and display clear setup instructions
- Skip assets that require unavailable providers
- Continue with available assets only

## Execution Flow

```
Provider detection -> Review bundle generation -> Video brief generation -> Multi-source upload (brief + review bundle + source files) -> Asset generation (NotebookLM + video page) -> Quality verification -> Notebook cleanup
```

## Asset Generation via nlm CLI (v0.4.4+)

```bash
# After uploading sources to notebook, generate artifacts:
NOTEBOOK_ID="<your-notebook-id>"

# Create architecture diagram (infographic)
nlm infographic create "$NOTEBOOK_ID" --orientation landscape --detail standard --style professional --confirm

# Create explainer video
# Prefer a concise technical walkthrough, not a broad marketing script.
nlm video create "$NOTEBOOK_ID" --format explainer --style documentary --confirm

# Create slide deck
nlm slides create "$NOTEBOOK_ID" --slide-format detailed_deck --confirm

# Poll for completion (background task recommended)
nlm studio status "$NOTEBOOK_ID"

# Download completed artifacts
nlm download infographic "$NOTEBOOK_ID" --id "$ARTIFACT_ID" --output assets/infographics/{package}_notebooklm.png
nlm download video "$NOTEBOOK_ID" --id "$ARTIFACT_ID" --output assets/videos/{package}_explainer.mp4
nlm download slide-deck "$NOTEBOOK_ID" --id "$ARTIFACT_ID" --output assets/slides/{package}_slides.pdf
```

## Multi-Source Upload Strategy

**Why multiple sources matter:**
- Single README uploads produce generic assets lacking technical depth
- Review bundle provides architectural context and design intent
- Multiple source files provide NotebookLM with complete implementation details
- Better source material -> More accurate, detailed, and professional assets
- Code examples, tests, and documentation improve asset quality significantly

**Hybrid approach (BEST): Review bundle + source files**

- **Review bundle** = Executive summary with architecture, design intent, and component relationships
- **Source files** = Implementation details, concrete code examples, and actual behavior
- **Combined** = High-level understanding + low-level evidence = Best artifacts

### Source File Identification

```bash
# Step 1: Generate review bundle (architectural context)
/review_bundle {{TARGET_DIR}}

# Step 2: Find all relevant source files (excludes cache, build artifacts, venv, templates)
cd {{TARGET_DIR}}
```

### Priority Upload Order

1. **Review bundle** (generated via `/review_bundle`) - Architectural overview
2. **Core implementation** - `core/*.py`, `*.py` (the actual code)
3. **Plugin configuration** - `.claude-plugin/plugin.json`, `hooks/hooks.json`
4. **Tests** - `tests/*.py`
5. **Skill documentation** - `SKILL.md` (if exists)
6. **Key README** - README.md (package overview)
7. **Templates/guides** - Only if they explain IMPLEMENTATION details

### Exclusion Patterns

**QUICK CHECKLIST - Always exclude these:**
- Lock files: `package-lock.json`, `poetry.lock`, `requirements.lock`, `yarn.lock`, `Cargo.lock`
- Test outputs: `htmlcov/`, `coverage.xml`, `.coverage*`, `.pytest_cache/`
- Version control: `.git/`, `.gitignore`, `.gitattributes`
- Cache/build: `__pycache__/`, `*.pyc`, `build/`, `dist/`, `venv/`, `.venv/`
- Generic templates: `CONTRIBUTING.md`, `SECURITY.md`, `LICENSE`, `CHANGELOG.md`
- State/diagnostics: `*-tree.txt`, `.claude/state/`, `*.pid`
- Generated media: `assets/videos/*.mp4`, `assets/infographics/*.png`, `assets/slides/*`
- CI/CD config: `.github/workflows/`
- IDE/temp files: `.vscode/`, `.idea/`, `*.swp`, `*.tmp`, `*.bak`
- Binary artifacts: `*.so`, `*.pyd`, `*.dll`, `*.exe`, `*.zip`, `*.tar.gz`

## Upload Process

```bash
# === STEP 1: Generate review bundle (architectural context) ===
echo "Generating review bundle for architectural context..."
Skill(skill="review_bundle", args="{{TARGET_DIR}}")

REVIEW_BUNDLE=$(ls -t P:/__csf/.staging/review_bundle_*.md 2>/dev/null | head -1)

# === STEP 2: Create NotebookLM notebook with clear temporary naming ===
TEMP_NOTEBOOK_NAME="TEMP: {{package_name}} Media Generation [$(date +%Y%m%d_%H%M%S)]"
nlm notebook create "$TEMP_NOTEBOOK_NAME"
NOTEBOOK_ID=$(nlm notebook list | grep "$TEMP_NOTEBOOK_NAME" | head -1 | awk '{print $1}')

# === STEP 3: Upload review bundle FIRST (architectural overview) ===
if [ -n "$REVIEW_BUNDLE" ] && [ -f "$REVIEW_BUNDLE" ]; then
  nlm source add "$NOTEBOOK_ID" --file "$REVIEW_BUNDLE" --wait
fi

# === STEP 3.5: Upload a narration brief to control tone and length ===
cat > /tmp/video_brief.md <<'EOF'
# Video Brief

Create a concise technical explainer video for engineers evaluating this package.

Requirements:
- Tone: technical, calm, direct, low-hype
- Audience: developers, maintainers, technical reviewers
- Length target: 60 to 120 seconds
- Focus on:
  1. what the package does
  2. how the workflow operates
  3. what files and outputs it creates
  4. why the result is useful in practice
- Prefer concrete nouns and file paths over abstract claims
- Avoid marketing language, rhetorical questions, and dramatic setup
- Avoid extended "before/after pain" storytelling
- Avoid filler such as "imagine", "revolutionary", "seamless", "game-changing"
- End with a brief technical summary, not a call-to-action
EOF

nlm source add "$NOTEBOOK_ID" --file /tmp/video_brief.md --wait

# === STEP 4: Upload source files (implementation details) ===
find . -type f \( -name "*.py" -o -name "*.json" -o -name "SKILL.md" -o -name "README.md" \) \
  ! -path "./.git/*" \
  ! -path "./__pycache__/*" \
  ! -path "./venv/*" \
  ! -path "./.venv/*" \
  ! -path "./.pytest_cache/*" \
  ! -path "./.ruff_cache/*" \
  ! -path "./.benchmarks/*" \
  ! -path "./build/*" \
  ! -path "./dist/*" \
  ! -path "./.eggs/*" \
  ! -path "./htmlcov/*" \
  ! -path "./assets/videos/*" \
  ! -path "./assets/infographics/*" \
  ! -path "./assets/slides/*" \
  ! -path "./.github/workflows/*" \
  ! -name "package-lock.json" \
  ! -name "poetry.lock" \
  ! -name "requirements.lock" \
  ! -name "yarn.lock" \
  ! -name "Cargo.lock" \
  ! -name "*.egg-info/*" \
  ! -name "*-tree.txt" \
  ! -name ".coverage*" \
  ! -name "coverage.xml" \
  ! -name "junit.xml" | head -30 | \
  while read file; do
    echo "Uploading: $file"
    nlm source add "$NOTEBOOK_ID" --text "$(cat "$file")" --title "$(basename "$file")" --wait
  done

# === STEP 5-6: Upload key documentation and verify ===
if [ -f "README.md" ]; then
  nlm source add "$NOTEBOOK_ID" --file README.md --wait 2>/dev/null || true
fi
nlm source list "$NOTEBOOK_ID"

# === STEP 7: Generate assets ===
echo "Starting asset generation..."
```

## Video Compliance Verification & Regeneration (Option B Pipeline)

**Objective**: Verify generated videos comply with technical writing standards and regenerate non-compliant videos.

**When**: Automatically runs after video download.

**Compliance standards**:
- **Absolutely forbidden**: "cool", "awesome", "super", "amazing", "ultra", "mega", "neat", "nifty", "handy", "sweet", "sick", "dope", "fire"
- **Marketing hype**: "game-changing", "revolutionary", "seamless", "transformative"
- **Anti-patterns**: "imagine", "picture this", "envision"

### Verification with faster-whisper

```bash
pip install faster-whisper

python << 'VERIFY_EOF'
from faster_whisper import WhisperModel
import json, re

FORBIDDEN_PATTERNS = [
    r'\bsuper\b', r'\bcool\b', r'\bawesome\b', r'\bamazing\b',
    r'\bultra\b', r'\bmega\b', r'\bneat\b', r'\bnifty\b',
    r'\bhandy\b', r'\bsweet\b', r'\bsick\b', r'\bdope\b',
    r'\bfire\b', r'\bgame.?changing\b', r'\brevolutionary\b',
    r'\bseamless\b', r'\btransformative\b', r'\bimagine\b',
    r'\bpicture this\b', r'\benvision\b'
]

def check_compliance(text):
    violations = []
    text_lower = text.lower()
    for pattern in FORBIDDEN_PATTERNS:
        matches = re.finditer(pattern, text_lower, re.IGNORECASE)
        for match in matches:
            violations.append({
                'word': match.group(),
                'position': match.start(),
                'context': text[max(0, match.start()-30):min(len(text), match.end()+30)]
            })
    return violations

model = WhisperModel("base", device="cpu", compute_type="int8")
segments, info = model.transcribe("assets/videos/{package}_explainer.mp4", beam_size=5)

all_violations = []
for segment in segments:
    violations = check_compliance(segment.text.strip())
    for v in violations:
        all_violations.append({**v, 'time': f"{segment.start:.1f}-{segment.end:.1f}s"})

with open('assets/videos/{package}_transcript.json', 'w') as f:
    json.dump({'violations': all_violations, 'count': len(all_violations)}, f)

if all_violations:
    print(f"FAILED: {len(all_violations)} violations found")
    exit(1)
else:
    print("PASSED: No forbidden words")
    exit(0)
VERIFY_EOF
```

### Option B Regeneration Pipeline (if violations found)

```bash
# Step 1: Generate compliant script
cat > assets/scripts/{package}_compliant_script.txt << 'SCRIPT_EOF'
[Write technical script without forbidden words]
SCRIPT_EOF

# Step 2: Install free TTS (edge-tts)
pip install edge-tts

# Step 3: Generate compliant audio
edge-tts --file assets/scripts/{package}_compliant_script.txt \
  --write-media assets/audio/{package}_compliant_audio.mp3

# Step 4: Replace audio track using ffmpeg
ffmpeg -i assets/videos/{package}_explainer.mp4 \
  -i assets/audio/{package}_compliant_audio.mp3 \
  -c:v copy -map 0:v:0 -map 1:a:0 -shortest \
  assets/videos/{package}_compliant.mp4 -y

# Step 5: Re-verify compliance
```

**Decision factors**:
- **Speed**: Option B (2-3 minutes) vs NotebookLM regeneration (5-10 minutes + uncertain)
- **Control**: Full script control vs AI generation variability
- **Cost**: Free (edge-tts) vs NotebookLM credits
- **Iteration**: Script changes are instant vs re-uploading sources to NotebookLM

## Notebook Cleanup After Asset Generation

```bash
# SAFETY: This cleanup is OPTIONAL and MANUAL
# Review the matched notebook ID before running

# Step 1: List all notebooks
echo "Current notebooks:"
nlm notebook list

# Step 2: Find the temporary notebook by name pattern
NOTEBOOK_ID=$(nlm notebook list | grep "TEMP: {{package_name}} Media Generation" | head -1 | awk '{print $1}')

# Step 3: Show what would be deleted (SAFETY CHECK)
if [ -n "$NOTEBOOK_ID" ]; then
  echo "Found temporary notebook: $NOTEBOOK_ID"
  echo "This will ONLY delete notebooks matching: 'TEMP: {{package_name}} Media Generation'"
  read -p "Delete this temporary notebook? (y/N): " CONFIRM

  if [ "$CONFIRM" = "y" ] || [ "$CONFIRM" = "Y" ]; then
    if nlm notebook delete --id "$NOTEBOOK_ID" 2>/dev/null; then
      echo "Deleted temporary notebook: $NOTEBOOK_ID"
    else
      echo "Failed to delete notebook (may have been deleted already)"
      exit 1
    fi
  else
    echo "Cleanup cancelled - notebook kept"
  fi
else
  echo "No temporary notebooks found matching pattern"
fi
```

**Safety features**:
- **Confirmation prompt**: Requires explicit `y` before deletion
- **Pattern matching**: Only deletes notebooks with exact pattern match
- **Error handling**: Detects and reports deletion failures
- **Dry-run mode**: Shows what will be deleted before asking for confirmation

### Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| NOTEBOOK_ID is empty | Already deleted or never created | No cleanup needed. Run `nlm notebook list` |
| Pattern doesn't match | Package name mismatch | Use broader pattern or manually select ID |
| Multiple notebooks match | Multiple /package runs | Review and delete individually |
| Permission denied | Auth or network issue | Run `nlm auth status`, then `nlm login` |

## Quality Comparison

| Approach | Source Material | Asset Quality | Time |
|----------|----------------|---------------|------|
| **Single README** | 1 file | Generic, shallow | Fast (~30s upload) |
| **Multi-source** | 10-50 files | Accurate, detailed, professional | Medium (~2min upload) |
| **Review bundle only** | 1 comprehensive file | Good architecture, missing implementation details | Fast (~30s upload) |
| **Review bundle + source files** | 1 architecture doc + 10-50 files | **Best quality** - context + implementation | Medium (~2min total) |

## Recommended Video Structure

```
CONTEXT (10-15s): Name the package and its purpose in one sentence.
WORKFLOW (25-40s): Show how it detects type, generates structure, and validates outputs.
ARTIFACTS (20-30s): Call out the key outputs: docs, CI/CD, flowchart, video, slides.
SUMMARY (10-15s): Close with the practical result for a developer using the package.
```

**Avoid**: long "problem/pain/agitate" intros, generic business narration, theatrical transitions, repeating the same feature list, durations over 2 minutes unless explicitly requested.

## Banner Validation (validate_banner.py)

After banner generation, automatically validate quality using `scripts/validate_banner.py`:

**Basic checks (always run):**
- File exists and readable
- Dimensions: 1200x630 (GitHub social preview standard)
- File size: 10KB - 500KB (reasonable range)
- Image not corrupted

**Vision analysis (requires `Z_AI_API_KEY`):**
- Text readability (contrast ratio >= 4.5:1)
- Package name visibility
- Professionalism assessment
- Visual appeal rating (1-10 scale)
- Specific issues + recommendations

**Usage:**
```bash
# Basic validation only
python scripts/validate_banner.py assets/banners/{package}_banner.png

# Exit with error if validation fails
python scripts/validate_banner.py assets/banners/{package}_banner.png --fail-on-issues
```

**Quality criteria:**
- **Excellent** (8-10): Ready for portfolio use
- **Good** (6-7): Acceptable, minor improvements possible
- **Needs improvement** (<6): Should regenerate before publishing

## Duration

5-10 minutes (depending on selected assets)

## Output

Professional visual assets in `assets/` directory:
- `assets/banners/{package}_banner.png`
- `assets/infographics/{package}_architecture.png`
- `assets/videos/{package}_explainer_pbs.mp4`
- `assets/slides/{package}_slides.pdf` (view and download as PDF)
