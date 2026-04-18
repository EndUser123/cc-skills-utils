---
name: discover
description: "Discover and explore codebase patterns"
version: "1.0.0"
status: "stable"
category: discovery
purpose: Intelligent codebase discovery with ML-enhanced pattern detection and GPU acceleration
usage: /discover [query] [--mode=quick|medium|very_thorough]
handles: ['codebase discovery', 'architecture analysis', 'pattern discovery', 'technical debt analysis', 'semantic code search', 'RAG-enhanced discovery', 'GPU-accelerated analysis']
complexity: advanced
dependencies: ['src/features/commands/nip/discover.md']
validation_mode: comprehensive
quality_gate: 0.9
author: CSF NIP
ml_enhanced: True
gpu_accelerated: True
triggers:
  - '/discover'
aliases:
  - '/discover'

suggest:
  - /search (integrated - first step for context discovery)
  - /analyze
  - /nse

# First-tool coherence (v3.5): /discover is for codebase exploration.
# First tool must be a discovery/search action, not execution.
allowed_first_tools:
  - Grep
  - Glob
  - Read
  - Task
---


# Discover - Intelligent Codebase Discovery


## ⚡ EXECUTION DIRECTIVE

**When invoked, IMMEDIATELY:**
1. Read the full command documentation
2. Execute the primary action described in Quick Start
3. Return results without summarization

**DO NOT:**
- Summarize this documentation
- Describe what the command does
- Ask clarifying questions unless critical info is missing

---

## Main Documentation

**Full implementation:** `P:/__csf/src/features/commands/nip/discover.md`

## Purpose

Discover codebase patterns, architecture, technical debt, and implementation opportunities with ML-enhanced pattern detection and GPU acceleration.

## Project Context

### Constitution/Constraints
- Follows CLAUDE.md constitutional principles
- Solo-dev appropriate (Director + AI workforce model)
- Evidence-first discovery (actual code analysis)
- On-demand execution (no background services)

### Technical Context
- 95%+ accuracy with HD1 integration
- 20x faster with GPU acceleration for large codebases
- 71.4% cache hit rate for repeated queries
- Semantic understanding via GraphCodeBERT + CodeT5
- RAG integration for enhanced search

### Architecture Alignment
- Integrates with /search and /analyze workflows
- Part of CSF NIP discovery tools
- Complements /design and /explore

## Your Workflow

1. **Search First** - Check existing context before discovery
   ```bash
   /search "{query}" --backend chs,cks,code
   ```
   - Find prior analyses, discussions, or similar patterns
   - Avoid redundant discovery work

2. Select thoroughness level (quick/medium/very_thorough)

3. Provide query or topic for discovery

4. Review generated findings

5. Take action on identified patterns/debt

6. Cache results for future queries

## Validation Rules

- Quick mode: <1 min for core patterns
- Medium mode: 5-15 min for comprehensive analysis
- Very thorough mode: 30-60 min with GPU acceleration
- Always verify findings with actual code

## Key Features

| Feature | Description |
|---------|-------------|
| **Hybrid Pattern Detection** | 95%+ accuracy with HD1 integration |
| **GPU Acceleration** | 20x faster for large codebases |
| **Intelligent Caching** | 71.4% cache hit rate |
| **Semantic Understanding** | GraphCodeBERT + CodeT5 |
| **RAG Integration** | Enhanced semantic search |

## Quick Start

```bash
# Quick discovery
/discover "routing patterns"

# Thorough analysis
/discover "authentication" --mode=very_thorough

# The main documentation contains:
# - Phase 1: Quick Discovery (<1min)
# - Phase 2: Medium Analysis (5-15min)
# - Phase 3: Very Thorough (GPU-accelerated, 20x faster)
```

## Thoroughness Levels

| Mode | Time | Coverage | Use Case |
|------|------|----------|----------|
| `quick` | <1 min | Core patterns | Fast answers |
| `medium` | 5-15 min | Comprehensive | Deep analysis |
| `very_thorough` | 30-60 min | ML + GPU | Large codebases |

## Implementation

- **Specification**: `src/features/commands/nip/discover.md`
- **Architecture**: Modular (stub → main documentation)
- **Token Savings:** ~11k tokens per invocation (stub ~0.4k vs full 11.4k)

## Related

- **Architecture**: `/design` (ML enhanced architectural analysis)
- **Explore**: `/explore` (systematic investigation with ML)
- **Analyze**: `/analyze` (unified analysis engine)

## AID Integration (v1.1.0)

**Enterprise-grade codebase analysis via AI Distiller (AID):**

```bash
# Perform comprehensive codebase analysis
aid <path> --ai-action prompt-for-complex-codebase-analysis
```

**AID `prompt-for-complex-codebase-analysis` provides:**
- **Compliance & Governance**: Standards adherence, policy violations
- **Scalability Assessment**: Architectural bottlenecks, growth risks
- **Technical Debt Inventory**: Debt classification, prioritization
- **Module Boundaries**: Dependency analysis, coupling issues
- **Documentation Gaps**: Missing/incomplete documentation

**When to use AID for codebase discovery:**
- New codebase onboarding (comprehensive overview)
- Pre-acquisition due diligence (code quality assessment)
- Architecture reviews (dependency analysis)
- Legacy modernization planning (debt inventory)

**Integration module**: `P:\.claude\skills\arch\aid_integration.py`
