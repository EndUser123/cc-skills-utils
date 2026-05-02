---
name: ask
description: Universal CLI router for intelligent command discovery, prompt enhancement, and orchestration
version: "3.6"
status: stable
category: consultation
enforcement: advisory
triggers:
  - /ask
  - "help"
  - "what can you do"
aliases:
  - /ask

follow_up_offer:
  - /search
  - /orchestrator

workflow_steps:
  - name: triage
    description: Assess complexity and select cognitive approach
  - name: parse
    description: Extract intent from user request
  - name: enhance
    description: Detect ambiguity, expand vague prompts, inject domain context
  - name: explore
    description: Understand context before routing
  - name: validate
    description: Truth-check any claims with evidence-based scoring
  - name: route
    description: Match to best command via intent patterns or command discovery
  - name: execute
    description: Hand off to target command with gathered context

# First-tool coherence (v3.6): /ask is a router — its first substantive
# tool must be a discovery/search action, NOT execution (Bash/python).
# Discovery questions ("what uses X?") require code search first.
# Routing questions ("which command for X?") require reading skills.
allowed_first_tools:
  - Grep
  - Glob
  - Read
  - Task
  - WebSearch
---


# /ask - Universal CLI Router

## Purpose

Primary entry point for all CLI operations with intelligent command discovery, routing, and orchestration. Triages requests, parses intent, explores context, validates claims, and routes to the optimal command.

## Project Context

### Constitution / Constraints
- **Solo-dev constraints apply** (CLAUDE.md)
- **No enterprise patterns**: Simple routing, not complex orchestration frameworks
- **Truthfulness required**: Validate claims before routing execution commands
- **Evidence-based routing**: Understand context before routing, don't guess

### Technical Context
- **Skill registry**: `P:\.claude\hooks\skill_registry.py` for command discovery
- **Search integration**: `/search --backend skills` for command discovery
- **Triage levels**: FAST (<2s), STANDARD (<15s), CAREFUL (<60s)
- **Evidence tiers**: Tier 1 (95%), Tier 2 (85%), Tier 3 (75%), Tier 4 (50%)

### Architecture Alignment
- Universal router for 192+ commands/skills
- Integrates with CHS (session context), CKS (patterns), skill_registry
- Links to /orchestrator, /nse, /search for related operations

## Your Workflow

1. **TRIAGE** — Assess complexity (reversibility, dependencies) → select path (FAST/STANDARD/CAREFUL)
2. **PARSE** — Extract intent, explicit commands, claims, context references
3. **ENHANCE** — Detect ambiguity, expand vague prompts, inject domain context
4. **EXPLORE** — Understand context before routing (scan files, search skills, check session history)
5. **VALIDATE** — Truth-check any claims with evidence-based scoring
6. **ROUTE** — Match to best command via intent patterns or command discovery
7. **EXECUTE** — Hand off to target command with gathered context

## Validation Rules

- **Before routing**: Understand request context, don't route blindly
- **Before accepting claims**: Apply evidence-based scoring, block if truth_score < 0.7
- **Before command discovery**: Use /search with skills backend, don't guess
- **Ambiguous requests**: Ask one clarifying question, don't fabricate route

### Prohibited Actions
- Routing without understanding request context
- Accepting unverified claims about completed work
- Summarizing this documentation instead of executing
- Fabricating command capabilities

## ⚡ EXECUTION DIRECTIVE

When invoked, execute these steps in order. Do not summarize this file.

```
STEP 0: TRIAGE → Assess complexity and select cognitive approach
STEP 1: PARSE  → Extract intent from user request
STEP 1.5: ENHANCE → Detect ambiguity, expand vague prompts, inject domain context
STEP 2: EXPLORE → Understand context before routing (if needed)
STEP 3: VALIDATE → Truth-check any claims (if present)
STEP 4: ROUTE  → Match to best command
STEP 5: EXECUTE → Hand off to target command
```

**Avoid:**

- Summarizing this documentation
- Routing without understanding request context
- Accepting unverified claims about completed work

**Default (no arguments):** Display available commands and offer routing assistance.


## STEP 0: RAPID TRIAGE

Assess before routing to select appropriate cognitive approach.

```
Reversibility Assessment:
├─ 1.0-1.25 (trivial: help, status, simple query) → FAST PATH
├─ 1.5-1.75 (moderate: analysis, planning, research) → STANDARD PATH
└─ 2.0 (irreversible: execution, deployment) → CAREFUL PATH

Dependency Count:
├─ 0-1 dependencies → Direct routing
├─ 2-4 dependencies → Confirm understanding first
└─ 5+ dependencies → Decompose before routing
```

| Path     | Approach                            | Budget |
| -------- | ----------------------------------- | ------ |
| FAST     | Direct route, minimal validation    | <2s    |
| STANDARD | Context exploration + routing       | <15s   |
| CAREFUL  | Full validation + user confirmation | <60s   |


## STEP 1: PARSE USER INPUT

Extract from user request:

- **Intent:** What does the user want to accomplish?
- **Explicit command:** Did they mention a specific command? (arch, rca, plan, etc.)
- **Claims:** Are they asserting completed work? (triggers truth validation)
- **Context references:** Do they reference files, projects, or prior work?


## STEP 1.5: PROMPT ENHANCEMENT

After parsing, evaluate whether the user's prompt is ambiguous, vague, or lacks sufficient context. Enhancement operates on the parsed intent — it does not change the routing decision, only improves the quality of information available for it.

### Ambiguity Detection

Check for these patterns:

| Pattern | Example | Issue |
|---------|---------|-------|
| Unclear antecedent | "fix it", "check this" | What specifically? |
| Missing specifics | "implement this", "add that" | What should be built? |
| Ambiguous improvement | "make it better", "optimize this" | Which aspects? |
| Too brief (1-2 words) | "help", "fix", "debug" | No actionable context |

### Domain Context Injection

When domain is detectable from prompt keywords or working directory, inject relevant context:

| Domain | Indicators | Context to Inject |
|--------|------------|-------------------|
| Security | auth, vulnerability, XSS, injection | Consider OWASP Top 10, input validation, output encoding |
| Testing | test, pytest, mock, fixture | TDD principles, arrange-act-assert, edge cases |
| Database | sql, migration, schema, query | Data integrity, transaction safety, indexing |
| Frontend | react, component, css, html | Component reusability, accessibility, responsive design |

### Enhancement Actions

```
IF prompt is ambiguous:
    → Ask ONE clarifying question before routing
    → "Which file/component should I focus on?"

IF prompt is too brief (1-2 words) AND no slash command:
    → Ask what they want to accomplish
    → Offer 2-3 likely interpretations

IF prompt has detectable domain:
    → Inject domain context into exploration step
    → Domain awareness carries through to routed command

IF prompt is specific and clear:
    → PASS — proceed directly to STEP 2 (no enhancement needed)
```

**Key constraint**: Enhancement asks at most ONE question. If the prompt is already clear, skip entirely. Enhancement serves routing accuracy, not conversation expansion.


## STEP 2: CONTEXT EXPLORATION

**When to explore (STANDARD or CAREFUL path):**

```
IF request references specific files or code:
    → Scan file/directory to understand structure
    → Map dependencies before proposing route

IF request asks "what [category] command would help..." or seeks command discovery:
    → Use /search with skills backend FIRST
    → Execute: cd "P:/__csf" && python src/csf/cli/nip/search.py "query" --backend skills --layer 3
    → Review results and route to best match

IF request is ambiguous:
    → Ask one clarifying question before routing
    → "Are you asking about X or Y?"

IF request builds on prior work:
    → Check session context for relevant history
    → Carry forward established context
```

**Skip exploration when:**

- Request is explicit command invocation
- Request is simple help/status query
- FAST path triage


## STEP 3: TRUTH VALIDATION

Execute when user request contains development claims. Block routing if truth_score < 0.7.

_See `references/truth-validation.md` for claim detection patterns, evidence-based scoring formula, and blocking logic._


## STEP 4: ROUTING DECISION

### 4.1 Explicit Command Detection

```
IF user mentions specific command:
    → Route directly to that command
    → Pass original request as context
```

### 4.2 Intent-Based Routing

_See `references/intent-routing-table.md` for the complete intent-to-command mapping, command categories, and discovery commands._

### 4.3 Command Discovery Integration

Commands are sourced from the `skill_registry`.

### 4.4 Ambiguous Request Handling

_See `references/integration-notes.md` for ambiguous request handling and fallback behavior._


## STEP 5: EXECUTE HANDOFF

```
1. Confirm selected route (for STANDARD/CAREFUL paths)
2. Pass original user request to target command
3. Include context gathered during exploration
4. Include any truth validation notes
5. Transfer session context if applicable
```


## QUICK REFERENCE

### Common Routes

| User Says                            | Routes To          |
| ------------------------------------ | ------------------ |
| "help", "what can you do"            | Help display       |
| "plan project", "break down task"    | `/breakdown`            |
| "should I extract this service"      | `/adf`             |
| "architecture design", "how to design" | `/design`            |
| "why is this failing"                | `/rca` or `/debug` |
| "research X", "learn about Y"        | `/research`        |
| "document this code", "ingest docs"  | `/doc`             |
| "verify my claims", "did I actually" | `/truth`           |
| "analyze code quality"               | `/analyze`         |
| "what did we discuss about X"        | `/search`             |
| "list available commands"            | Command discovery  |
| "discover patterns in codebase"      | `/discover`        |

### Routing Principles

1. **Understand before routing** — Context exploration prevents misroutes
2. **Verify before trusting** — Claims about work require evidence
3. **Ask when uncertain** — One clarifying question beats wrong routing
4. **Preserve context** — Carry forward relevant session state


## ERROR HANDLING

_See `references/integration-notes.md` for error handling, session context, command registry, and workflow integration details._
