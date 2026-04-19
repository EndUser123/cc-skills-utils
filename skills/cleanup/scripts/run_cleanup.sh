#!/usr/bin/env bash
# .claude directory cleanup script - Ready for deletion scope
# Cleans 145 items (130 files + 15 directories) that are safe to delete
# Excludes 1,098 items requiring manual review

set -euo pipefail

CLAUDE_DIR="P:/.claude"
CLEANUP_SCRIPT="$CLAUDE_DIR/skills/cleanup/scripts/claude_directory_cleanup.py"

echo "=========================================="
echo ".claude Directory Cleanup - EXECUTE"
echo "=========================================="
echo ""
echo "This will DELETE 145 items:"
echo "  • 130 files (backup, temp, old docs, session debris)"
echo "  • 15 directories (cache, coverage reports, backup dirs)"
echo ""
echo "Excluded from this run:"
echo "  • 1,098 lock files (require manual review)"
echo ""

# Confirm before proceeding
read -p "Proceed with deletion? (yes/no): " confirm
if [[ "$confirm" != "yes" ]]; then
    echo "Cleanup cancelled."
    exit 0
fi

echo ""
echo "Running cleanup..."
echo ""

# Run the cleanup script with --execute flag
cd "$CLAUDE_DIR" || exit 1
python "$CLEANUP_SCRIPT" --execute

echo ""
echo "=========================================="
echo "Cleanup Complete!"
echo "=========================================="
echo ""
echo "Space recovered: ~280MB (htmlcov, audit.db, fix_validations.jsonl)"
echo ""
echo "Next steps:"
echo "  1. Review 1,098 lock files manually if needed"
echo "  2. Consider audit.db rotation policy"
echo "  3. Re-generate coverage reports: pytest --cov --cov-report=html"
