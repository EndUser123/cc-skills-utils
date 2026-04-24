#!/bin/bash
# ============================================================
# batch_polish.sh — Batch skill application across packages
# Usage: bash batch_polish.sh [--dry-run|--execute] [skill] [package...]
# Default skill: /gitready --check-only
# Default packages: all in P:/packages (excludes __pycache__, .archive, arch/)
#
# --dry-run: Preview what would be executed
# --execute: Show execution plan (actual execution via Skill() tool in Claude Code)
# ============================================================

set -e

# Parse arguments: [--dry-run|--execute|--evidence-dir] [skill] [packages...]
MODE="execute"
SKILL="/gitready --check-only"
PACKAGES=()
CREATE_EVIDENCE_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      MODE="dry-run"
      shift
      ;;
    --execute)
      MODE="execute"
      shift
      ;;
    --evidence-dir)
      CREATE_EVIDENCE_DIR="yes"
      shift
      ;;
    --)
      shift
      break
      ;;
    -*)
      echo "Unknown flag: $1"
      exit 1
      ;;
    *)
      # Smart detection: Skills START with /, paths contain / elsewhere
      # Check skill FIRST (starts with /, and not a multi-segment path like foo/bar)
      if [[ "$1" == /* && ! "$1" == *"/"*"/"* ]]; then
        # Starts with / and not a multi-segment path - it's a skill
        if [[ "$SKILL" == "/gitready --check-only" ]]; then
          SKILL="$1"
        else
          PACKAGES+=("$1")
        fi
      elif [[ "$1" == *"/"* || "$1" == *"\\"* || "$1" == *":"* ]] || [[ "$1" =~ ^[A-Za-z]: ]]; then
        # Contains /, \, or : or is a Windows path - treat as package(s)
        PACKAGES+=("$1")
      else
        # Plain word - treat as package
        PACKAGES+=("$1")
      fi
      shift
      ;;
  esac
done

# Any remaining args are package names
PACKAGES+=("$@")

# Detect platform
PLATFORM="$(uname -s)"
case "$PLATFORM" in
  Linux*)     PLATFORM="linux" ;;
  Darwin*)    PLATFORM="macos" ;;
  MINGW*|MSYS*|CYGWIN*) PLATFORM="windows" ;;
  *)          PLATFORM="unknown" ;;
esac

# Base packages directory
PACKAGES_DIR="P:/packages"

# Check if passed "packages" are actually the packages directory itself
FINAL_PACKAGES=()
for pkg in "${PACKAGES[@]}"; do
  # If it's the packages directory itself, expand to all packages
  if [[ "$pkg" == "$PACKAGES_DIR" ]] || [[ "$pkg" == "$PACKAGES_DIR/" ]]; then
    mapfile -t ALL_PKGS < <(ls -d "$PACKAGES_DIR"/*/ 2>/dev/null | xargs -n1 basename | grep -v -E '^__pycache__$|\.archive$|^arch$')
    FINAL_PACKAGES=("${ALL_PKGS[@]}")
    break
  elif [[ "$pkg" == *":/"* ]]; then
    # It's an absolute path (contains :/) - extract package name from it
    # e.g. P:/packages/claude-history -> claude-history
    pkg_name=$(basename "$pkg")
    if [[ -n "$pkg_name" && "$pkg_name" != "__pycache__" && "$pkg_name" != ".archive" && "$pkg_name" != "arch" ]]; then
      FINAL_PACKAGES+=("$pkg_name")
    fi
  elif [[ -d "$pkg" ]]; then
    # It's a directory - expand to packages inside it
    for subpkg in "$pkg"/*/; do
      if [[ -d "$subpkg" ]]; then
        subpkg_name=$(basename "$subpkg")
        # Exclude certain dirs
        if [[ "$subpkg_name" != "__pycache__" && "$subpkg_name" != ".archive" && "$subpkg_name" != "arch" ]]; then
          FINAL_PACKAGES+=("$subpkg_name")
        fi
      fi
    done
  elif [[ -d "$PACKAGES_DIR/$pkg" ]]; then
    # It's a package name in PACKAGES_DIR
    FINAL_PACKAGES+=("$pkg")
  else
    # Unknown - treat as-is, will get skipped later
    FINAL_PACKAGES+=("$pkg")
  fi
done
PACKAGES=("${FINAL_PACKAGES[@]}")

# Get all packages if none specified
if [[ ${#PACKAGES[@]} -eq 0 ]]; then
  mapfile -t PACKAGES < <(ls -d "$PACKAGES_DIR"/*/ 2>/dev/null | xargs -n1 basename | grep -v -E '^__pycache__$|\.archive$|^arch$')
fi

echo "============================================"
echo "Batch Skill Execution"
echo "Skill: $SKILL"
echo "Packages: ${PACKAGES[*]:-all}"
echo "Platform: $PLATFORM"
echo "Mode: $MODE"
echo "============================================"
echo ""

if [[ "$MODE" == "dry-run" ]]; then
  echo "[DRY RUN MODE]"
  echo "[This script shows what WOULD be executed]"
  echo ""
elif [[ "$MODE" == "execute" ]]; then
  echo "[EXECUTE MODE]"
  echo "[Skill() calls to execute in Claude Code]"
  echo ""
fi

# Create evidence directory for batch results (compaction immunity)
if [[ -n "$CREATE_EVIDENCE_DIR" ]]; then
  BATCH_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
  BATCH_ID="batch_${BATCH_TIMESTAMP}"
  EVIDENCE_DIR="P:/packages/gitbatch/.evidence/${BATCH_ID}"
  mkdir -p "$EVIDENCE_DIR"
  echo "Evidence directory: $EVIDENCE_DIR"
  echo "$EVIDENCE_DIR" > "$EVIDENCE_DIR/.batch_id"
  echo ""
fi

# Extract just the skill name (first word) for Skill() call
SKILL_NAME="${SKILL%% *}"
SKILL_ARGS="${SKILL#* }"
if [[ "$SKILL_ARGS" == "$SKILL" ]]; then
  SKILL_ARGS=""  # No args, just skill name
fi

FAILED_PACKAGES=()
PASSED_PACKAGES=()
SKIPPED_PACKAGES=()
_has_python_src=0

# Helper function: returns 0 if NOT a non-Python package (Rust), 1 if non-Python
# Rust packages have Cargo.toml but no Python indicators
_is_non_python() {
  local pkg_path="$1"
  # Has Cargo.toml but no Python indicators -> Rust (skip)
  if [[ -f "$pkg_path/Cargo.toml" ]]; then
    local has_python=0
    [[ -f "$pkg_path/pyproject.toml" ]] && has_python=1
    [[ -f "$pkg_path/setup.py" ]] && has_python=1
    for dir in src core; do
      [[ -d "$pkg_path/$dir" ]] && [[ -n "$(ls "$pkg_path/$dir"/*.py 2>/dev/null)" ]] && has_python=1
    done
    [[ $has_python -eq 0 ]] && return 0  # Is Rust
  fi
  return 1  # Not a non-Python package
}

for pkg in "${PACKAGES[@]}"; do
  PKG_PATH="$PACKAGES_DIR/$pkg"

  if [[ ! -d "$PKG_PATH" ]]; then
    echo "=== [$pkg] SKIPPED — not found at $PKG_PATH ==="
    echo ""
    SKIPPED_PACKAGES+=("$pkg (not found)")
    continue
  fi

  # Skip empty directories (no recognizable Python source, no tests/, no SKILL.md)
  _has_python_src=0
  for dir in src core; do
    [[ -d "$PKG_PATH/$dir" ]] && [[ -n "$(ls "$PKG_PATH/$dir"/*.py 2>/dev/null)" ]] && _has_python_src=1 && break
  done
  if [[ $_has_python_src -eq 0 ]] && [[ ! -f "$PKG_PATH/pyproject.toml" ]] && [[ ! -d "$PKG_PATH/tests" ]] && [[ ! -f "$PKG_PATH/SKILL.md" ]]; then
    echo "=== [$pkg] SKIPPED — empty/invalid package (no Python src, tests/, or SKILL.md) ==="
    echo ""
    SKIPPED_PACKAGES+=("$pkg (empty/invalid)")
    continue
  fi

  # Skip non-Python packages (Rust)
  if _is_non_python "$PKG_PATH"; then
    echo "=== [$pkg] SKIPPED — Rust package (Cargo.toml without Python indicators) ==="
    echo ""
    SKIPPED_PACKAGES+=("$pkg (non-Python)")
    continue
  fi

  echo "=== >>> $pkg ==="

  # Build target arg
  if [[ -n "$SKILL_ARGS" ]]; then
    TARGET_ARG="--target $PKG_PATH $SKILL_ARGS"
  else
    TARGET_ARG="--target $PKG_PATH"
  fi

  # Add evidence path if evidence directory is enabled
  if [[ -n "$EVIDENCE_DIR" ]]; then
    EVIDENCE_FILE="${EVIDENCE_DIR}/${pkg}.json"
    TARGET_ARG="$TARGET_ARG --evidence \"$EVIDENCE_FILE\""
  fi

  echo "Skill(skill=\"$SKILL_NAME\", args=\"$TARGET_ARG\")"
  echo ""

done

# Generate skill-adaptive summary from evidence files
if [[ -n "$EVIDENCE_DIR" ]] && [[ -d "$EVIDENCE_DIR" ]]; then
  echo ""
  echo "============================================"
  echo "BATCH SUMMARY (from evidence files)"
  echo "============================================"
  echo ""

  # Read all JSON evidence files
  EVIDENCE_FILES=("$EVIDENCE_DIR"/*.json)
  if [[ -f "${EVIDENCE_FILES[0]}" ]]; then
    PASSED=0
    FAILED=0
    SKIPPED=0

    for evidence_file in "${EVIDENCE_FILES[@]}"; do
      if [[ -f "$evidence_file" ]]; then
        pkg_name=$(basename "$evidence_file" .json)

        # Extract status from JSON (using python for cross-platform JSON parsing)
        status=$(python -c "
import json
import sys
try:
    with open('$evidence_file', 'r') as f:
        data = json.load(f)
    print(data.get('status', 'unknown'))
except:
    print('error')
" 2>/dev/null || echo "error")

        case "$status" in
          pass|PASS|passed|PASSED)
            ((PASSED++))
            ;;
          fail|FAIL|failed|FAILED)
            ((FAILED++))
            ;;
          skip|SKIP|skipped|SKIPPED)
            ((SKIPPED++))
            ;;
          *)
            ((SKIPPED++))
            ;;
        esac
      fi
    done

    echo "Packages: $PASSED passed, $FAILED failed, $SKIPPED skipped"
    echo ""
    echo "PACKAGE HEALTH:"
    for evidence_file in "${EVIDENCE_FILES[@]}"; do
      if [[ -f "$evidence_file" ]]; then
        pkg_name=$(basename "$evidence_file" .json)
        status=$(python -c "
import json
try:
    with open('$evidence_file', 'r') as f:
        data = json.load(f)
    print(data.get('status', 'unknown'))
except:
    print('error')
" 2>/dev/null || echo "error")
        summary=$(python -c "
import json
try:
    with open('$evidence_file', 'r') as f:
        data = json.load(f)
    print(data.get('summary', ''))
except:
    print('')
" 2>/dev/null || echo "")
        echo "  - $pkg_name: $status ($summary)"
      fi
    done
  else
    echo "No evidence files found."
  fi

  echo ""
  echo "============================================"
fi

echo "============================================"
if [[ "$MODE" == "dry-run" ]]; then
  echo "Dry run complete. Use --execute to run for real."
else
  echo "Execution plan shown. Run /gitbatch --execute for actual run."
fi
echo "============================================"
