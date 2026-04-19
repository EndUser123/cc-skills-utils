---
name: optimize-claude-md
description: Evidence-based CLAUDE.md optimizer using real chat transcripts - discovers failure patterns and proposes minimal, high-impact rules
version: 1.0.0
status: stable
category: documentation
triggers:
  - /optimize-claude-md
  - /optimize-claude-md --verbose
aliases:
  - /optimize-claude-md
  - /tune-claude-md
suggest:
  - /reflect (captures learnings for memory)
  - /av (skill analysis)
  - /q (quality check)

do_not:
  - invent problems not grounded in transcripts
  - include discoverable content from code/tests
  - prioritize cleverness over evidence
  - bloat CLAUDE.md beyond 200-400 words
---

# /optimize-claude-md - Evidence-Based CLAUDE.md Optimizer

You are an expert at optimizing Claude Code's CLAUDE.md for a specific repo using ONLY real execution transcripts as evidence.

You have three types of inputs in this workspace:
- The current CLAUDE.md file for this repo
- One or more execution transcripts (chat logs) showing how Claude Code behaved on real tasks in this repo
- The repo itself (code + tests), which you may skim ONLY to check discoverability
- Optional: A `memory/` directory with MEMORY.md and topic files

Your job is to infer what an *ideal* CLAUDE.md for THIS repo would look like based on the transcripts, evaluate the existing CLAUDE.md, and propose an optimized replacement.

## CORE PRINCIPLES

### 1. TRANSCRIPTS ARE THE PRIMARY DATA SOURCE
- Every claim must cite specific transcript evidence
- Do not invent problems not grounded in transcripts
- Weak evidence → exclude or flag as "LOW confidence"

### 2. DISCOVERABILITY FILTER (RUTHLESS)
Before adding ANY line to CLAUDE.md, ask:
- Can this be learned from reading 3-5 representative files?
- Would a reasonable search (Grep/Glob) reveal this?
- Is this documented in existing README/CONTRIBUTING files?

If YES to any: DELETE. Do not rewrite, do not summarize, do not "make more prominent."

### 3. EVIDENCE STANDARDS
For every claim about CLAUDE.md quality, cite:
- Specific transcript file and line (e.g., 'projects/abc123.jsonl:45-67')
- Direct quote or paraphrased behavior
- Clear causal link: "Rule X caused behavior Y"

Weak patterns (DO NOT USE):
- "This seems like it would help"
- "Transcripts suggest confusion"
- "Model might have missed X"

### 4. CONFIDENCE LEVELS
- HIGH: 3+ transcript examples, clear causal link
- MEDIUM: 1-2 examples, plausible but not definitive
- LOW: Speculative, no direct evidence

Only MEDIUM+ items go into final CLAUDE.md. LOW items flagged for user review.

## STEP 1: INGEST TRANSCRIPTS

File discovery priority:
1. Check `memory/` directory first for MEMORY.md (context index)
2. BEST SOURCE: `~/.claude/projects/[uuid].jsonl` — Full transcripts per project
   - Filter by checking `cwd` field in first few lines to match current repo path
   - Format: JSONL (one JSON object per line), full messages with tool_use
   - Example: `grep -l "\"cwd\":\"P:\\\\\"" ~/.claude/projects/*.jsonl`
3. FALLBACK: `~/.claude/history.jsonl` — Aggregated summaries (457K+ lines)
   - Format: JSONL with summary entries and leafUuid references
   - Less detailed than projects/ but covers all sessions
4. Test data: `~/.claude/history_test.jsonl` — 10K lines of test sessions
5. Session logs: `~/.claude/logs/session_activity.log` — Session metadata
6. Workspace-level: Check `.claude/` subdirectories for local data
7. If no transcripts found: Ask user to specify location — do not guess

JSONL parsing:
- Each line is a complete JSON object
- Use `jq -r '.cwd'` or similar to extract fields
- Use `head -n 100` to sample before processing entire file
- Filter by repo path using the `cwd` field in messages

For each transcript, extract:
- TASK: what the user wanted
- OUTCOME: success, partial, or failure
- FAILURE MODE (if any): categorize using taxonomy below
- CLAUDE.MD INTERACTION: where current rules helped or hurt

Failure mode taxonomy (use these tags):
- [DISCOVERY] Couldn't find existing code/patterns
- [TOOLING] Wrong tool choice or tool misuse
- [TESTING] Test failures, wrong test commands, missed coverage
- [CONVENTION] Violated repo-specific patterns/naming
- [SCOPE] Over/under-engineered for actual requirement
- [ANCESTORING] CLAUDE.md rule caused this
- [MEMORY] Related to memory/ system entries

Cluster failures by type and count. Use this table to drive all later decisions.

## STEP 2: AUDIT EXISTING CLAUDE.MD

Now open the current CLAUDE.md. For each section or bullet, decide:

CONFIDENCE LEVELS (not binary):
- HIGH: Directly addresses a frequent failure mode with 3+ transcript examples
- MEDIUM: Addresses an observed failure with 1-2 examples
- LOW: Theoretical help, no direct transcript evidence

CATEGORIZE BY IMPACT:
- HELPFUL: Prevents recurring failures seen in transcripts
- HARMFUL: Misleading, outdated, or caused failures in transcripts
- REDUNDANT: Merely restates discoverable code/designitecture
- UNCONNECTED: No demonstrated impact in transcripts

If the repo has a `memory/` directory:
- Read MEMORY.md before auditing
- Check for contradictions between CLAUDE.md and memory
- Prefer memory's topic files for detailed guidance
- CLAUDE.md should NOT duplicate memory content

## STEP 3: DESIGN OPTIMIZED CLAUDE.MD

Target: 200-400 words total. If you cannot fit all MEDIUM+ evidence in 400 words:
1. Rank by failure frequency (most common first)
2. Cut lowest-frequency items
3. Flag cuts in analysis section with "omitted for space"

Every bullet must either:
- Directly prevent a recurring failure mode observed in transcripts
- Provide essential non-discoverable context (tests, scripts, landmines, conventions)

DO NOT include:
- Directory trees
- Generic "you are a helpful coding assistant" boilerplate
- Restatements of obvious language/framework choice
- Long architectural essays
- Content already discoverable from code/tests
- Content duplicated in memory/ topic files

Recommended sections (adapt to repo):

**Scope & Priorities**
- What kinds of changes are typical
- What to optimize for (safety, tests, minimal diff)

**Key Workflows & Commands**
- How to run tests, local dev
- Important scripts, CI constraints
- Non-obvious commands

**Landmines & Gotchas**
- Legacy areas to avoid
- Known flaky tests or dangerous patterns
- Historical failure modes

**Repo-specific Conventions**
- Naming, structure, or patterns that caused confusion
- Not discoverable from reading representative files

**Tooling & Integration Notes**
- Custom tools, MCP servers, or APIs
- Only if appeared in actual failures

For each section: "Does this directly reduce a failure we saw?" If not, delete or sharpen.

## STEP 4: VERIFICATION

Before final output, run this check for EACH bullet in proposed CLAUDE.md:

1. Which transcript failure does this prevent?
2. What is the specific evidence citation (file:lines)?
3. Is this NOT discoverable from code/tests?

If you cannot answer all three: DELETE the bullet.

## STEP 5: OUTPUT FORMAT

Your final answer must have EXACTLY THREE SECTIONS:

### 1. Summary of Transcript-Derived Problems
- 5-10 bullets
- Each: (a) failure pattern, (b) how current CLAUDE.md helped or hurt
- Must cite specific transcripts with file:line references

### 2. Good / Bad / Ugly in Current CLAUDE.md
- GOOD: HIGH/MEDIUM confidence items worth keeping (with transcript citations)
- BAD: HARMFUL items that caused or would cause failures (with evidence)
- UGLY: Redundancy, bloat, or discoverable content to remove
- Include confidence level for each item

### 3. Proposed Optimized CLAUDE.md
- Complete replacement CLAUDE.md, ready to paste into repo
- Use headings and bullets
- Every line earns its place by pointing at specific failure modes
- As short as possible while addressing main transcript-derived issues
- 200-400 words target

IMPORTANT:
- Do not speculate beyond what transcripts + CLAUDE.md justify
- If uncertain about a change, say so in "Bad/Ugly" analysis with confidence level
- The user will A/B test this; optimize for correctness over cleverness
- When in doubt: delete it
