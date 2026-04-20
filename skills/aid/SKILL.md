---
name: ai_distiller
description: AI-Distiller wrapper for code analysis - refactoring, security, performance, architecture.
version: "1.0.0"
status: stable
category: development
tags: ['code-analysis', 'refactoring', 'security', 'performance', 'architecture', 'documentation', 'ai-distiller']
triggers:
  - '/ai_distiller'
aliases:
  - '/ai_distiller'
  - '/aid'

suggest:
  - /analyze
  - /bug-hunt
  - /comply

execution:
  directive: |
    Execute the AI-Distiller (aid.exe) wrapper to analyze code.
    Use specific subcommands (refactor, arch, security, perf, best, bugs, docs, diagrams, flow, multi, git) based on user need.
    Results are typically saved to P:\.aid\ unless --stdout is used.
  default_args: ""
  examples:
    - "/aid refactor src/main.py"
    - "/aid arch . --format md"
    - "/aid security . --private"

do_not:
  - sugarcoat technical debt
  - recommend enterprise bloat
  - ignore security vulnerabilities

output_template: |
  Analysis results are saved to: P:\.aid\[ANALYSIS-TYPE].[timestamp].[filename].md
  
  (Or stdout content if --stdout is used)
---


# AI-Distiller (aid) - Code Analysis Skill

## Purpose

Interface to AI-Distiller (aid.exe) for intelligent code distillation — extracting essential structure while preserving semantic information for LLM consumption. Provides comprehensive code analysis including refactoring, security, performance, architecture, and documentation.

## Project Context

### Constitution / Constraints
- **Solo-dev constraints apply** (CLAUDE.md)
- **No enterprise patterns**: Recommend solo-appropriate solutions, not complex abstractions
- **Truthfulness required**: Report findings accurately, don't sugarcoat technical debt
- **Evidence-based analysis**: Specific file locations and line numbers, not speculation
- **READ-BEFORE-WRITE**: Always explore existing code before recommending changes

### Technical Context
- **Python wrapper**: `P:\__csf\src\commands\aid\aid.py`
- **aid.exe location**: `P:\__csf\tools\ai-distiller-optimized\aid.exe`
- **AI-Distiller Version**: v1.3.1 (built 2025-06-21)
- **Output location**: `P:\.aid\[ANALYSIS-TYPE].[timestamp].[filename].md`
- **Supported languages**: Python, TypeScript, JavaScript, Go, Rust, Java, C#, Kotlin, C++, PHP, Ruby, Swift
- **Compression ratio**: 60-90% size reduction while preserving semantic information

### Architecture Alignment
- Uses structured subcommands (refactor, arch, security, perf, best, bugs, docs, diagrams, flow, multi, git)
- Integrates with CSF NIP ecosystem (aid-status, aid-security, aid-performance, aid-diagrams)
- Results saved with timestamps for traceability

## Your Workflow

1. **Identify analysis type** — Determine which subcommand fits user need (refactor, security, perf, arch, etc.)
2. **Set visibility level** — Use --private/--protected/--internal as appropriate
3. **Choose output format** --format md|text|jsonl|xml, and optionally --stdout
4. **Execute aid.exe** — Run via wrapper with appropriate arguments
5. **Locate results** — Check `P:\.aid\` for timestamped output files
6. **Present findings** — Summarize key insights with file:line citations

## Validation Rules

- **Before refactoring recommendations**: Verify analysis was actually run on current code
- **Before security claims**: Ensure --private flag was used if needed
- **Before architectural changes**: Verify findings with actual file reads
- **Filter all recommendations**: Apply SoloDevConstitutionalFilter (no enterprise bloat)
- **Report accurately**: Don't sugarcoat technical debt or severity

### Prohibited Actions
- Sugarcoating technical debt severity
- Recommending patterns without proven need or director approval
- Ignoring security vulnerabilities
- Making claims without reading actual files first

## When to Use

Use `/aid` when you need to:
- Analyze code for refactoring opportunities (technical debt, SOLID violations)
- Generate architecture diagrams and visualizations
- Perform security audits (OWASP Top 10 focus)
- Identify performance bottlenecks
- Create comprehensive documentation
- Generate structured analysis workflows
- Analyze git history with AI insights

## Quick Reference

| Shortcut | Purpose | Example |
|----------|---------|---------|
| `refactor` | Refactoring analysis | `/aid refactor src/main.py` |
| `arch` | Codebase architecture | `/aid arch . --format md` |
| `security` | Security audit (OWASP) | `/aid security . --private` |
| `perf` | Performance analysis | `/aid perf src/` |
| `best` | Best practices review | `/aid best core.py` |
| `bugs` | Bug hunting | `/aid bugs .` |
| `docs` | Documentation | `/aid docs file.py` |
| `diagrams` | Mermaid diagrams (10x) | `/aid diagrams src/` |
| `flow` | Analysis workflow | `/aid flow . --stdout` |
| `multi` | Multi-file docs | `/aid multi src/` |
| `git` | Git history | `/aid git 50` |

## Advanced Options

| Option | Purpose |
|--------|---------|
| `--format md|text|jsonl|xml` | Output format |
| `--stdout` | Print to stdout (in addition to file) |
| `--private/--protected/--internal` | Visibility control |
| `--implementation` | Include function bodies |
| `--include "*.py,*.ts"` | File patterns to include |
| `--exclude "*test*"` | File patterns to exclude |

## Output Location

Results saved to `P:\.aid\[ANALYSIS-TYPE].[timestamp].[filename].md`

## Reference Files

| File | Contents |
|------|----------|
| `references/capabilities-and-examples.md` | Key capabilities (refactoring, security, perf, arch, docs), git mode, use-case examples |
| `references/integration-and-technical.md` | CSF NIP integration, technical details (version, languages, compression), constitutional notes |
