---
name: memory-integration
description: Memory integration layer for agent coordination and task dispatch.
version: 1.0.0
status: stable
category: strategy
triggers:
  - subagent
  - dispatch
  - store.*memory
  - remember
  - learned.*lesson
  - pattern.*recogni
  - solved.*before
  - coordinat
aliases:
  - /memory-integration

suggest:
  - "See: shared/memory-system.md"
  - /cks
  - /nse
---

# Memory Integration

**Primary Directive:** Use CKS for persistent knowledge and MemoryCacheManager for session coordination. Enable agents to learn from past work and coordinate without explicit messaging.

## Purpose

Enable agent coordination and learning through shared memory systems.

## Project Context

### Constitution/Constraints
- Preserve everything: Store learnings for reuse
- Evidence-first: Only store verified learnings, not speculation

### Technical Context
- CKS (Constitutional Knowledge System): Persistent semantic storage
- MemoryCacheManager: Session-based coordination cache
- Five memory types: corrections, patterns, decisions, learnings, insights

### Architecture Alignment
- Integrates with /cks for knowledge retrieval
- Supports /orchestrator for multi-agent coordination

## Your Workflow

### Before Agent Work (Retrieval)
1. Search CKS for similar past solutions
2. Check session cache for coordination state
3. Inject relevant context into subagent prompts

### During Agent Work (Coordination)
1. Use MemoryCacheManager for in-process state sharing
2. Set status/progress keys for cross-agent coordination

### After Agent Work (Storage)
1. Identify learnings, corrections, patterns from work
2. Store appropriate entries in CKS with metadata
3. Index for future retrieval

## Validation Rules

### Prohibited Actions
- Do NOT store unverified speculation as learnings
- Do NOT use session cache for persistent knowledge
- Do NOT skip context retrieval before complex tasks

## When to Use Memory

### Before Agent Work (Retrieval)

**Always retrieve relevant context before dispatching subagents when:**

1. **Problem-solving tasks** - Search for similar past solutions
   ```python
   from src.lib.memory.coordinator import MemoryCoordinator

   memory = MemoryCoordinator()
   context = memory.get_context(task_description)
   # Returns: corrections, patterns, learnings from src.cks
   ```

2. **Multi-agent tasks** - Check for previous coordination patterns
   ```python
   # Get session state
   state = memory.cache_get("multi_agent:state")
   # Returns: current coordination state (if exists)
   ```

### During Agent Work (Coordination)

**Use MemoryCacheManager for in-process coordination:**

```python
from lib.context.persistence.memory_cache import MemoryCoordinator

cache = MemoryCacheManager()

# Agent 1: Finds available API quota
cache.set("quota:available", {"anthropic": 1000, "openrouter": 50000})

# Agent 2: Routes based on quota (no messaging needed)
quota = cache.get("quota:available")
if task_size > quota["anthropic"]:
    return "openrouter"
```

**Session coordination patterns:**
- `cache.set(f"agent:{agent_name}:status", "working")`
- `cache.set(f"task:{task_id}:progress", {"step": 3, "total": 5})`
- `cache.get("current_user_preference")`

### After Agent Work (Storage)

**Store learnings in CKS when:**

| Situation | Entry Type | Example |
|----------|------------|---------|
| Fixed a bug | `correction` | "FAISS lazy-load fix: use streaming embeddings" |
| Found a pattern | `pattern` | "TDD: RED→GREEN→REFACTOR, never mix phases" |
| Made a choice | `decision` | "Chose FTS5 over external search for embedded" |
| Learned something | `learning` | "Exponential backoff: 5s→10s→20s→300s" |
| Had insight | `insight` | "Subagents need memory to avoid redundant work" |

```python
from csf.cks.unified import CKS

cks = CKS()

# Store a correction
cks.ingest_correction(
    title="Don't concatenate /TN flag in schtasks",
    content="The /TN flag and task name must be separate arguments: ['/TN', task_name] not [f'/TN{task_name}']",
    context="task_manager.py fix"
)

# Store a pattern
cks.ingest_pattern(
    title="Session Coordination with MemoryCacheManager",
    content="Agents coordinate via shared cache without messaging. First agent sets state, second agent reads state. No explicit coordination needed.",
    category="multi-agent"
)
```

## Decision Tree: CKS vs MemoryCacheManager

```
┌─────────────────────────────────────────────────────────────┐
│  Need to remember something...                                │
└─────────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            │                               │
     Should survive restart?          Only needed now?
            │                               │
            YES                              NO
            │                               │
    ┌───────┴───────┐              ┌───────┴───────┐
    │               │              │               │
   CKS           CKS          MemoryCache    MemoryCache
   (persistent)  (semantic)     (session)      (session)
                                          │
                              ┌───────────────┴───────────────┐
                              │                               │
                        Is it a learning?              Is it state?
                              │                               │
                              YES                             NO
                              │                               │
                        CKS entry_type:            Simple key-value
                      correction/learning        set(key, value)
```

## Integration Points

### 1. Subagent Dispatch

**When dispatching subagents, inject relevant memories:**

```python
from src.lib.memory.coordinator import MemoryCoordinator

memory = MemoryCoordinator()

# Get context for the subagent
context = memory.get_context(task_description)

# Add to subagent prompt
subagent_prompt = f"""
{task_description}

## Relevant Past Work:
{format_memories(context)}

Use these insights to avoid repeating mistakes.
"""
```

### 2. Task Execution

**Before complex tasks, retrieve patterns:**

```python
# Search for relevant patterns
patterns = cks.search_patterns(task_type, limit=5)
if patterns:
    print(f"Found {len(patterns)} relevant patterns for {task_type}")
```

### 3. Post-Task Learning

**After completing work, store learnings:**

```python
# What did we learn?
cks.ingest_learning(
    title=f"{project}: {task_type} optimization",
    content=f"Optimized {component} using {technique}. Result: {outcome}. ROI: {improvement}%",
    context=f"{project} {task_type}"
)
```

## Examples

### Example 1: Problem with Known Solution

```python
# ORCHESTRATOR: Detects similar problem
memory = MemoryCoordinator()
corrections = memory.cks.search_corrections("FAISS slow", limit=3)

if corrections:
    # Direct solution from memory
    apply_fix(corrections[0]['content'])
else:
    # Need to investigate
    dispatch_subagent("investigate", problem)
    # Store result for next time
    cks.ingest_correction(title, solution)
```

### Example 2: Multi-Agent Coordination

```python
# Agent 1: Investigates
cache.set("investigation:complete", {"root_cause": "X", "files": ["a.py"]})

# Agent 2: Fixes (reads investigation without messaging)
investigation = cache.get("investigation:complete")
if investigation:
    apply_fix(investigation["root_cause"], investigation["files"])
```

### Example 3: User Preference Learning

```python
# Store preference
cks.ingest_memory(
    question="User's response style preference",
    answer="Prefers: brief responses, no emojis, code-first, practical examples. Avoids: verbose explanations, excessive praise, generic advice.",
    source_chunk="user prefers concise technical responses"
)

# Later agents retrieve automatically
preferences = cks.search_memories("response style")
```

## Quick Reference

| Action | API |
|--------|-----|
| Search past solutions | `cks.search_corrections(query)` |
| Find patterns | `cks.search_patterns(query)` |
| Get learnings | `cks.search_learnings(query)` |
| Store correction | `cks.ingest_correction(title, content)` |
| Store pattern | `cks.ingest_pattern(title, content)` |
| Store learning | `cks.ingest_learning(title, content)` |
| Session cache set | `cache.set(key, value)` |
| Session cache get | `cache.get(key)` |

## Key Insight

**Without memory integration:**
- Each agent starts from zero
- Same problems solved repeatedly
- No organizational learning
- Coordination requires explicit messaging

**With memory integration:**
- Agents build on past work
- Problems solved once, reused forever
- System gets smarter over time
- Coordination via shared state

