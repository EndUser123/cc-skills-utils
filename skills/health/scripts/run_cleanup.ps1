# .claude directory cleanup script - Ready for deletion scope
# Cleans 145 items (130 files + 15 directories) that are safe to delete
# Excludes 1,098 items requiring manual review

$ErrorActionPreference = "Stop"

$ClaudeDir = "P:\.claude"
$CleanupScript = "$ClaudeDir\skills\cleanup\scripts\claude_directory_cleanup.py"

Write-Host "=========================================="  -ForegroundColor Cyan
Write-Host ".claude Directory Cleanup - EXECUTE"     -ForegroundColor Cyan
Write-Host "=========================================="  -ForegroundColor Cyan
Write-Host ""
Write-Host "This will DELETE 145 items:"               -ForegroundColor Yellow
Write-Host "  • 130 files (backup, temp, old docs, session debris)"
Write-Host "  • 15 directories (cache, coverage reports, backup dirs)"
Write-Host ""
Write-Host "Excluded from this run:"                  -ForegroundColor Gray
Write-Host "  • 1,098 lock files (require manual review)"
Write-Host ""

# Confirm before proceeding
$confirm = Read-Host "Proceed with deletion? (yes/no)"
if ($confirm -ne "yes") {
    Write-Host "Cleanup cancelled." -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "Running cleanup..." -ForegroundColor Green
Write-Host ""

# Run the cleanup script with --execute flag
Push-Location $ClaudeDir
try {
    python $CleanupScript --execute
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "=========================================="  -ForegroundColor Cyan
Write-Host "Cleanup Complete!"                         -ForegroundColor Green
Write-Host "=========================================="  -ForegroundColor Cyan
Write-Host ""
Write-Host "Space recovered: ~280MB (htmlcov, audit.db, fix_validations.jsonl)" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:"                               -ForegroundColor Yellow
Write-Host "  1. Review 1,098 lock files manually if needed"
Write-Host "  2. Consider audit.db rotation policy"
Write-Host "  3. Re-generate coverage reports: pytest --cov --cov-report=html"
