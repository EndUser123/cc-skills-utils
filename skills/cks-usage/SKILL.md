---
name: cks-usage
description: "Constitutional Knowledge System usage patterns and queries"
category: strategy
version: 1.0.0
status: stable
triggers:
  - '/cks-usage'
aliases:
  - '/cks-usage'

suggest:
  - /cks
  - /search
  - /analyze
---

# CKS Proper Usage Enforcement

## Purpose

Ensures all knowledge is properly ingested into the CKS database via DirectCKSIngestion API, not written as loose files. Enforces proper knowledge storage patterns and prevents bypassing CKS ingestion.

## Project Context

### Constitution / Constraints
- **Solo-dev constraints apply** (CLAUDE.md)
- **Centralized knowledge**: All knowledge must go through CKS database, not scattered files
- **API-first**: Use DirectCKSIngestion class, not file I/O for knowledge
- **Verification required**: Confirm ingestion, verify via search, show statistics

### Technical Context
- **API class**: `P:/__csf/src/features/cks/integration/commands/direct_knowledge_ingestion.py`
- **Databases**: Main CKS at `.speckit/data/cks.db`, Hypergraph CKS at `data/cks_hypergraph/cks_hypergraph.db`
- **Ingestion method**: `DirectCKSIngestion.ingest_knowledge(title, content, category, knowledge_type, tags)`
- **Verification methods**: `search_knowledge()`, `get_statistics()`

### Architecture Alignment
- Integrates with /cks (knowledge search), /search (unified search), /analyze (analysis)
- Links to /learn (session learning)
- Part of knowledge management ecosystem

## Your Workflow

1. **DETECT VIOLATIONS** — Check for JSON writes to data/cks/, file I/O for knowledge, /learn invocation
2. **STOP IMMEDIATELY** — Halt any incorrect flat file creation
3. **USE PROPER API** — Invoke DirectCKSIngestion.ingest_knowledge()
4. **VERIFY INGESTION** — Confirm entry exists via search_knowledge()
5. **SHOW STATISTICS** — Display CKS statistics after ingestion
6. **CLEANUP** — Remove any incorrectly created flat files

## Validation Rules

- **Before knowledge storage**: Must use DirectCKSIngestion, not file I/O
- **After ingestion**: Verify entry exists in database via search
- **Before completing /learn**: Show CKS statistics, confirm API usage
- **Pattern detection**: Catch JSON writes to data/cks/, flat file knowledge creation

### Prohibited Actions
- Writing JSON files to data/cks/lessons/
- Creating knowledge as flat files
- Bypassing CKS ingestion API
- Using Path("data/cks/...").write_text() for knowledge

## When This Skill Activates

When ANY of these patterns are detected:
- Writing `.json` files to `data/cks/` directory
- Creating knowledge files outside CKS database
- Using file I/O for knowledge storage instead of CKS API
- `/learn` command invocation

## What You MUST Do Instead

1. **Use DirectCKSIngestion class** from `src.cks.integration.commands.direct_knowledge_ingestion`

2. **Proper ingestion pattern:**
   ```python
   from src.cks.integration.commands.direct_knowledge_ingestion import DirectCKSIngestion

   ingestion = DirectCKSIngestion()
   result = ingestion.ingest_knowledge(
       title="Lesson Title",
       content="Full lesson content...",
       category="technical_lessons",
       knowledge_type="lesson",
       tags=["tag1", "tag2"],
   )
   ```

3. **For session learning (/learn):**
   - Read any existing JSON files
   - Ingest into CKS using the API above
   - Optionally keep JSON as backup/reference but NOT primary storage

## CKS Database Locations

| Database | Path |
|----------|------|
| Main CKS | `.speckit/data/cks.db` |
| Hypergraph CKS | `data/cks_hypergraph/cks_hypergraph.db` |

## Forbidden Patterns

❌ DO NOT:
- Write JSON files to `data/cks/lessons/`
- Create knowledge as flat files
- Bypass CKS ingestion API
- Use `Path("data/cks/...").write_text()` for knowledge

✅ DO:
- Use `DirectCKSIngestion.ingest_knowledge()`
- Verify ingestion with `search_knowledge()`
- Check statistics with `get_statistics()`
- Close connection when done

## Validation

Before completing `/learn` or knowledge storage:
1. Confirm `DirectCKSIngestion` was used
2. Verify entry exists in database via search
3. Show CKS statistics after ingestion

## Consequences

If you detect yourself taking the shortcut:
1. STOP immediately
2. Use proper CKS API
3. Remove any incorrectly created flat files
4. Ingest properly
