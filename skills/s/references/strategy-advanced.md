# /s Strategy - Advanced Features

This document contains advanced features and implementation details for the `/s` strategy skill. See main SKILL.md for core usage and workflow.

## Table of Contents

- [Fallback Behavior (DEPRECATED)](#fallback-bebehavior-deprecated)
- [Persona Memory Recall (Optional)](#persona-memory-recall-optional)
- [Argument Fuzzy Matching (NLU-Based)](#argument-fuzzy-matching-nlu-based)
- [Graph-of-Thought (GoT) Integration](#graph-of-thought-got-integration)
- [Tree-of-Thought (ToT) Integration](#tree-of-thought-tot-integration)
- [Combined GoT + ToT Integration](#combined-got--tot-integration)

---

## Fallback Behavior (DEPRECATED)

If invoked without a topic, `/s` attempts to infer context through:
1. `/q` context (if available)
2. Recent file edits (session activity)
3. Chat transcript analysis (unreliable)
4. Falls back to "General strategic brainstorming" (low quality)

**Do not rely on fallback.** Always provide your topic explicitly for best results.

---

## Persona Memory Recall (Optional)

`/s` can optionally recall previous brainstorm sessions on the same or similar topics using Persona Memory storage.

**Flag:** `--recall` (search previous sessions)

**Usage:**
```bash
# Standard brainstorming
/s "database design"

# Brainstorm with previous session recall
/s "database design" --recall

# Recall sessions filtered by persona
/s "database design" --recall --persona INNOVATOR

# Recall high-impact sessions only
/s "database design" --recall --min-impact 0.7
```

**What `--recall` does:**
- Searches Persona Memory for previous brainstorm sessions on similar topics
- Displays historical insights alongside new analysis
- Format: "Previous sessions on this topic: N results"
- Gracefully degrades if Persona Memory unavailable

**Persona filter options:**
- `INNOVATOR`: Innovative, breakthrough ideas
- `PRAGMATIST`: Practical, implementable solutions
- `CRITIC`: Critical analysis and risk identification
- `EXPERT`: Domain-specific technical insights

**Example output:**
```
📚 Previous Sessions: 3 relevant brainstorm sessions found

1. **Database Schema Migration Strategy**
   Persona: PRAGMATIST | Impact: 0.85
   Date: 2026-03-10
   Content: Consider phased migration with backward compatibility layer...

[... new brainstorm analysis ...]
```

---

## Argument Fuzzy Matching (NLU-Based)

When handling user arguments, use natural language understanding to match intent rather than strict string matching. This makes the skill more forgiving and helpful.

**Decision Table Enhancement:**

The decision table in `step_parse_args` should use these matching strategies:

| User Input | Intent Detection | Action |
|------------|------------------|--------|
| `/s --list` | User wants to see available options | Display Supported Flags section, show available models, exit |
| `/s --providers` | Same as --list (semantic match) | Display Supported Flags section, show available models, exit |
| `/s -h` or `/s --help` | User wants help | Display Supported Flags section with examples, exit |
| `/s "topic" --verbos` | Typo of --verbose (if existed) | Warn: "Unknown flag '--verbos'. Did you mean --verbose? This flag doesn't exist, but continuing with your topic." |
| `/s "topic" --unknown-flag` | Unknown flag | Strip unknown flag, warn user, continue with remaining valid args |
| `/s` (no args) | No topic provided | Use fallback context: check `/q` output, recent files, or ask for topic |

**Semantic Intent Matching:**

Use these heuristics to detect user intent:

1. **List/Show intent** → Display providers and options:
   - Keywords: "list", "show", "what", "available"
   - Example: `/s --list`, `/s "what providers available"`

2. **Help intent** → Show usage:
   - Keywords: "help", "how", "usage"
   - Example: `/s --help`, `/s "how do I use this"`

3. **Typo detection** → Suggest corrections:
   - Use Levenshtein distance (edit distance ≤ 2)
   - Example: `--verbos` → suggest `--verbose` (if it exists)
   - Example: `--outpit` → suggest `--output`

4. **Semantic equivalents** → Map to correct flag:
   - `--providers` → same as `--list` (show options)
   - `--models` → same as `--list` (show model options)

**Implementation Pattern:**

```python
# In step_parse_args workflow step:
def parse_user_args(user_input: str) -> dict:
    args = extract_flags(user_input)

    # Check for help/list intent first
    if any(flag in args for flag in ['--list', '--help', '-h', '--providers']):
        return {'action': 'show_help', 'reason': 'User requested information'}

    # Check for typos in remaining args
    for flag in args:
        if flag not in VALID_FLAGS:
            suggestion = find_closest_match(flag, VALID_FLAGS)
            if suggestion:
                warn_user(f"Unknown flag '{flag}'. Did you mean {suggestion}?")
            else:
                warn_user(f"Unknown flag '{flag}'. Continuing without it.")
            args = [f for f in args if f != flag]

    return {'topic': extract_topic(user_input), 'flags': args}
```

**Benefits:**
- More forgiving UX - users don't need exact flag names
- Self-documenting - skill guides users toward correct usage
- Reduces friction - common intents work naturally
- Aligns with LLM strengths - use NLU instead of rigid parsing

---

## Graph-of-Thought (GoT) Integration Features (NEW in v2.5)

/s now integrates Graph-of-Thought (GoT) reasoning for enhanced strategy options analysis:

### 1. GoT Strategy Node Extraction

**What**: Automatically extract and categorize strategy nodes from multi-persona brainstorming
**When**: Automatic enhancement during Discuss phase (enabled by default)
**Benefit**: Discover hidden relationships and circular dependencies between strategic options

**Node Types Extracted**:
- **Constraints**: Strategic requirements like "Budget < $1000", "Must use PostgreSQL", "Timeline < 2 weeks"
- **Ideas**: Strategic approaches like "Use microservices", "Implement OAuth 2.0", "Adopt event-driven architecture"
- **Risks**: Strategic concerns like "Microservices complexity", "OAuth integration latency", "Event ordering issues"
- **Components**: System boundaries like "Auth Service", "User Database", "API Gateway"
- **Data flows**: Communication paths like "Client → API Gateway → Auth Service"

**Relationship Types Detected**:
- **Supports**: One strategic option enables another (e.g., "Use microservices" supports "Independent deployments")
- **Contradicts**: One strategic option conflicts with another (e.g., "Must use monolith" contradicts "Use microservices")
- **Depends**: One strategic option requires another (e.g., "Event-driven architecture" depends on "Message broker")
- **Unrelated**: No direct relationship between strategic options

**Opt-out Flag**:
```bash
# Disable GoT enhancement
export STRATEGY_NO_GOT=true
```

### 2. GoT Strategy Analysis Workflow

**Integration Point**: Discuss phase (after Diverge, before Converge)

**Workflow**:
```
Diverge phase (multi-persona brainstorming)
  ↓
GotPlanner extracts strategy nodes from all personas
  ↓
GotEdgeAnalyzer detects relationships between strategic options
  ↓
Cycle detection warns about circular strategic dependencies
  ↓
Enhanced Discuss phase with GoT relationship analysis
  ↓
Converge phase with relationship-aware ranking
```

**Example Output**:
```
GoT Analysis: Strategy Options
================================

Nodes extracted: 12
  - Constraints: 3 (Budget < $1000, Must use PostgreSQL, Timeline < 2 weeks)
  - Ideas: 5 (Microservices, OAuth 2.0, Event-driven, etc.)
  - Risks: 4 (Microservices complexity, OAuth latency, etc.)

Relationships detected: 8
  - Supports: 5 pairs (Microservices → Independent deployments, etc.)
  - Contradicts: 1 pair (Monolith vs Microservices - CONFLICT)
  - Depends: 2 pairs (Event-driven depends on Message broker)

Cycles detected: 0

Strategic Synthesis: SOUND
Reason: No conflicting constraints detected; 2 complementary strategy pairs
```

**What this catches**:
- Hidden strategic conflicts (e.g., "Must be serverless" vs "Must use PostgreSQL")
- Circular dependencies in strategic options (e.g., "Option A depends on B, B depends on A")
- Missing prerequisite relationships (e.g., "OAuth integration" requires "User service")
- Risk amplification when multiple risky strategies combine

---

## Tree-of-Thought (ToT) Integration Features (NEW in v2.5)

/s now integrates Tree-of-Thought (ToT) reasoning for enhanced outcome exploration:

### 1. ToT Outcome Branching

**What**: Automatically generate branching outcome scenarios for each strategic option
**When**: Automatic enhancement during Converge phase (enabled by default)
**Benefit**: Discover alternative outcome paths beyond linear strategic projection

**Outcome Branch Types**:

**Success Branches**:
- **sure**: Expected positive outcome (e.g., "Adoption successful within 3 months")
- **maybe**: Moderate success with caveats (e.g., "Adoption successful but requires training")
- **unlikely**: Limited success (e.g., "Adoption partial, requires revision")

**Failure Branches**:
- **sure**: Expected failure mode (e.g., "Technical incompatibility blocks adoption")
- **maybe**: Risk of failure (e.g., "Integration complexity may delay rollout")
- **unlikely**: Black swan events (e.g., "Vendor discontinues key dependency")

**Risk Scenario Branches**:
- **sure**: Known risks materialize (e.g., "Performance degradation under load")
- **maybe**: Potential risks emerge (e.g., "Team knowledge gaps may slow development")
- **unlikely**: Catastrophic risks (e.g., "Security breach due to architecture flaw")

**Branch Scoring**:
- **sure**: High-confidence outcomes (> 75% probability)
- **maybe**: Medium-confidence outcomes (25-75% probability)
- **unlikely**: Low-confidence outcomes (< 25% probability)

**Opt-out Flag**:
```bash
# Disable ToT enhancement
export STRATEGY_NO_TOT=true
```

### 2. ToT Outcome Exploration Workflow

**Integration Point**: Converge phase (during decision memo generation)

**Workflow**:
```
Converge phase begins
  ↓
BranchGenerator generates outcome scenarios for each strategic option
  ↓
Branch scoring by likelihood (sure/maybe/unlikely)
  ↓
Prune unlikely branches (focus on high-value scenarios)
  ↓
Enhanced decision memo with ToT outcome analysis
```

**Example Output**:
```
ToT Analysis: Outcome Exploration
==================================

Branches generated: 15
  - sure: 8 scenarios (expected success/failure modes)
  - maybe: 5 scenarios (moderate outcomes with caveats)
  - unlikely: 2 scenarios (black swan events - pruned)

Scenario coverage by strategic option:
  - Option 1: Microservices → 3 scenarios (sure: scalable, maybe: complexity, unlikely: vendor lock-in)
  - Option 2: Monolith → 2 scenarios (sure: simple deployment, maybe: performance bottleneck)
  - Option 3: Hybrid → 3 scenarios (sure: balanced, maybe: operational complexity, unlikely: worst of both)

Total scenarios for decision analysis: 10 (after pruning)

Selected Strategy: Option 2 (Monolith)
Reasoning:
  - sure: Simple deployment (90% confidence)
  - maybe: Performance bottleneck acceptable (30% probability, mitigable)
  - unlike: High-risk scenarios pruned
```

**What this catches**:
- Unexplored failure modes in strategic options
- Missing success scenarios (what if this works better than expected?)
- Risk scenario variability (different risk paths for each strategy)
- Black swan events (unlikely but high-impact scenarios)

---

## Combined GoT + ToT Integration

**Synergistic Benefits**:

1. **GoT guides strategy analysis** → Extract and analyze strategic option relationships
2. **ToT guides outcome exploration** → Branch scenarios for each strategic option
3. **Shared opt-out flags** → Independent control over each enhancement
4. **Complementary coverage** → GoT for relationships, ToT for outcomes

**When both enhancements are enabled** (default):
- Strategic options analyzed for hidden relationships (GoT)
- Outcome scenarios explored for branching analysis (ToT)
- Comprehensive strategic assessment with relationship-aware ranking

**Example Integration Flow**:
```
/s "architecture options for auth migration"
  ↓
Diverge phase: Multi-persona brainstorming (Innovator, Pragmatist, Critic, Expert)
  ↓
GoT analysis: Option A (Microservices) contradicts Option B (Monolith)
  ↓
ToT analysis: Option 1 has 5 scenarios (2 sure, 2 maybe, 1 unlikely pruned)
  ↓
Enhanced decision memo with:
  - GoT node relationships documented
  - ToT outcome branches enumerated
  - Circular dependency warnings (if any)
  - High-value scenario coverage
```

---

## Implementation Notes

### Opt-out Mechanism

Both GoT and ToT enhancements can be disabled independently via environment variables:

```bash
# Disable GoT only
export STRATEGY_NO_GOT=true

# Disable ToT only
export STRATEGY_NO_TOT=true

# Disable both
export STRATEGY_NO_GOT=true
export STRATEGY_NO_TOT=true
```

### Performance Considerations

- **GoT enhancement**: Adds ~10-15% processing time during Discuss phase
- **ToT enhancement**: Adds ~15-20% processing time during Converge phase
- **Both enabled**: Adds ~25-35% total processing time for enhanced analysis

### Memory Requirements

- GoT node extraction: Minimal overhead (<1MB)
- ToT branch generation: Moderate overhead (~5-10MB for complex scenarios)
- Both enabled: ~10-15MB total memory overhead

---

**Version:** 2.7.0 (2026-03-14)
**Last Updated:** See main SKILL.md for version history
