---
name: reports
description: Comprehensive report management system with intelligent organization and search
version: 1.0.0
status: stable
category: documentation
triggers:
  - /reports
aliases:
  - /reports

suggest:
  - /search
  - /nse
  - /analyze
---

# Report Manager

Comprehensive report management system for organizing, searching, and maintaining smart review reports.

## Purpose

Comprehensive report management system with intelligent organization, search, and maintenance for smart review reports.

## Project Context

### Constitution/Constraints
- On-demand report generation (no continuous monitoring)
- Solo-developer report management
- Evidence-based reporting only

### Technical Context
- Storage location: `P:/__csf/reports/`
- Categories: security_analysis, performance_analysis, etc.
- Filtering by content-type, tags, date range, confidence score

### Architecture Alignment
- Integrates with `/search` for report discovery
- Works alongside `/analyze` for report generation
- Suggests `/nse` for intelligent recommendations

## Your Workflow

1. **List**: Display reports with optional filtering
2. **Search**: Find reports by content and metadata
3. **Clean**: Remove old reports with preview option
4. **Stats**: Show report statistics and summaries

### Subcommands
- `list`: Display with filtering (limit, category, format)
- `search`: Search by content and metadata
- `clean`: Remove old reports (with --dry-run)
- `stats`: Show report statistics

## Validation Rules

### Prohibited Actions
- Do NOT delete reports without --dry-run or --force flag
- Do NOT generate reports without actual analysis content
- Do NOT claim report exists without file verification

### Options
- `--limit`: Maximum results to show
- `--category`: Filter by category
- `--content-type`: Filter by content type
- `--tags`: Filter by tags (comma-separated)
- `--format`: Output format (table|json)
- `--date-from/--date-to`: Date range filter
- `--confidence`: Minimum confidence score (0.0-1.0)

## Quick Start

```bash
/reports list                    # List recent reports
/reports search "security"       # Search by content
/reports clean --days 30          # Remove old reports
```

## Subcommands

### list
Display reports with filtering:

```bash
/reports list --limit 50
/reports list --category security_analysis
/reports list --format json
```

### search
Search by content and metadata:

```bash
/reports search "vulnerability"
/reports search "performance" --category performance_analysis
/reports search "critical" --confidence 0.8
```

### clean
Remove old reports with preview:

```bash
/reports clean --days 30 --dry-run
/reports clean --category security --force
```

### stats
Show report statistics:

```bash
/reports stats
```

## Options

- `--limit` - Maximum results to show
- `--category` - Filter by category
- `--content-type` - Filter by content type
- `--tags` - Filter by tags (comma-separated)
- `--format` - Output: table|json
- `--date-from` / `--date-to` - Date range filter
- `--confidence` - Minimum confidence score (0.0-1.0)
- `--days` - Age in days to clean
- `--dry-run` - Preview without deleting
