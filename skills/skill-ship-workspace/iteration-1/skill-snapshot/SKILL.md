---
name: skill-ship
description: Master coordinator for skill creation and improvement workflows. MUST BE USED when user asks to "create/build/write/develop a skill". Use PROACTIVELY for "improve/optimize/fix/enhance a skill". Consider for "audit/review/validate a skill". Coordinates discovery, creation, evaluation (3a: spec, 3b: quality, 3c: integration), optimization, and distribution. Integrates skill-creator evals, skill-development guidance, and quality gates via testing-skills, av, similarity, doc-to-skill, sharing-skills.
version: 1.8.0
category: orchestration
triggers:
  - /skill-ship
  - "complete skill"
  - "skill completion"
aliases:
  - /skill-ship
  - /sc
suggest:
  - /skill-creator
  - /skill-development
  - /similarity
  - /doc-to-skill
  - /sharing-skills
depends_on_skills: []
enforcement: advisory
workflow_steps:
  - phase_0_context: Run /gto for session context awareness (detect user corrections, learning signals, broken windows)
  - phase_1_discovery: Understand user intent, auto-invoke /similarity for conflict detection with result envelope pattern, extract requirements
  - phase_1_5_knowledge_retrieval: Query NotebookLM, CKS, memory.md for relevant patterns/lessons before building
  - phase_2_creation: Create or update skill structure using skill-creator and skill-development guidance WITH constitutional filter (no enterprise patterns), plan-and-review for complex skills (>5 steps)
  - phase_3a_spec_compliance: Verify implementation follows plan with completion evidence (RED/GREEN/REGRESSION/VERIFY) - blocks 3b until SPEC_PASS
  - phase_3b_code_quality: Validate YAML frontmatter, trigger accuracy, quality gates, context bloat prevention - blocks 3c until critical issues resolved
  - phase_3c_integration_verification: Test skill invocation and execution paths - blocks Phase 4 until integration passes
  - phase_3_5_evaluation: Run eval suite with skill-creator including benchmarks and variance analysis (skip for simple skills)
  - phase_4_optimization: Add hooks for mechanical continuation, validation patterns (PostToolUse/state transition), enforce standardized formatting via output-style-extractor (internal: av2)
  - phase_5_distribution: Package skill for sharing via GitHub PR workflow using sharing-skills
---

# Skill Complete

Master coordinator for comprehensive skill creation and improvement workflows.

## Purpose

Coordinate the entire skill lifecycle from inception to deployment, ensuring:
- Proper creation methodology
- Consistent output formatting
- Quality validation
- Optimization and improvement
- Successful distribution

## When to Use

**Trigger Strength Classification:**

| Strength | When This Applies |
|----------|-------------------|
| **MUST BE USED** | User explicitly requests: "create a skill", "build a new skill", "write a skill from scratch", or mentions skill creation, skill development, or starting skill work |
| **Use PROACTIVELY** | User asks to: "fix my skill", "improve this skill", "optimize a skill", "skill isn't working", or mentions skill debugging, skill enhancement, or skill repair |
| **Consider using** | User asks: "how do I create skills", "what's wrong with this skill", "review my skill", or seeks skill guidance, audit, or feedback |

**Use Cases:**
- Creating a new skill from scratch
- Improving an existing skill
- Auditing skill quality
- Preparing skills for sharing
- Coordinating multi-skill workflows
- Ensuring consistent formatting across skills

## Orchestrated Skills

This meta-skill coordinates the following specialized skills:

### Context Phase
- **gto**: Session gap analysis - detect user corrections, learning signals, broken windows

### Creation Phase
- **skill-creator**: (external plugin) Full iterative development loop with draft creation, test prompts, evaluation suite (`evals/evals.json`), variance analysis, performance benchmarks via `eval-viewer/generate_review.py`, and description optimization for improved triggering
- **skill-development**: SKILL.md structure, progressive disclosure patterns, plugin-specific best practices, and writing style guidance
- **doc-to-skill**: Convert documentation into skills

### Analysis Phase
- **similarity**: Find similar/redundant skills (auto-invoked in Phase 1)
- **av** (internal): Analyze and generate hook files
- **testing-skills** (internal): Quality gate validation

### Optimization Phase
- **av2** (internal): Mechanical continuation enforcement
- **output-style-extractor**: Extract display formatting patterns

### Distribution Phase
- **sharing-skills**: GitHub PR workflow automation
- **github-public-posting**: Pre-publish checklist

### Internal Skills Note
`/av`, `/av2`, and `/testing-skills` are implementation details coordinated by `/skill-ship`. Users should invoke `/skill-ship` directly rather than calling these internal skills.

## References

### Core Documentation
- **`examples/WORKFLOW-EXAMPLES.md`**: 3 complete workflow demonstrations with real scenarios
- **`references/workflow-phases.md`**: Detailed 5-phase workflow instructions (Phase 1-5)
- **`references/agent-tool-usage.md`**: Task/Agent tool usage best practices and common mistakes
- **`references/skill-frontmatter-fields.md`**: Complete reference for SKILL.md frontmatter fields, including enforcement tier configuration (REQUIRED)

### Skill-Based Hooks System
- **`references/skill-based-hooks.md`**: Comprehensive guide to the Claude Code skill-based hooks enforcement system
- **`references/hooks-implementation-guide.md`**: Quick reference for implementing hooks in skills
- **`references/hooks-design-patterns.md`**: Philosophy and architecture of specialized self-validating agents
- **`references/procedure-type-skills-embedded-enforcement.md`**: Architecture guidance for PROCEDURE-type skills (embedded enforcement, NOT global hooks)

### Quality & Verification
- **`references/skill-quality-gates.md`**: Quality verification systems for skill development
- **`skill_optimization_patterns.md`**: Pattern reference for optimizing existing skills — compact resilience, phase format alignment, opportunistic auto-cleanup, dead code removal, self-improving skills via improvement logs (stored at `P:/memory/skill_optimization_patterns.md`)
- **`references/eval-guide.md`**: Complete guide for skill-creator's evaluation system (evals, benchmarks, variance analysis, description optimization)
- **`references/eval-complete-reference.md`**: Comprehensive evaluation system spec (grader, analyzer, schemas, statistical methods)
- **`references/description-optimization-guide.md`**: Complete guide for optimizing skill descriptions (avoid overfitting, focus on user intent, be "pushy")
- **`verification_tiers.md`**: Absence Claim Protocol for verifying components before claiming they are missing
- **`examples/eval-example.json`**: Example eval suite template with test categories and success criteria
- **`references/skill-based-self-verification.md`**: Specialized self-validating agents using hooks
- **`references/external-research-findings.md`**: External research synthesis from official docs and security research
- **`references/context-bloat-prevention.md`**: Anti-context bloat patterns and detection for SKILL.md optimization

### Agent Patterns (NEW)
- **`references/subagent-result-envelope.md`**: Standardize how subagents return findings to avoid context bloat
- **`references/anti-false-done-patterns.md`**: Explicit completion evidence requirements to prevent premature "done" claims
- **`references/agentic-validation-hooks.md`**: Self-correcting patterns using PostToolUse validation + state transitions
- **`references/constitutional-filter.md`**: Auto-filter prohibited enterprise patterns during skill creation
- **`references/plan-and-review.md`**: Create plan → adversarial review → execute workflow for risky changes
- **`references/agent-failure-modes.md`**: Common coding-agent failure patterns with mitigation strategies (spec drift, tool misuse, hallucination)
- **`references/agent-command-templates.md`**: Reusable command templates for Claude Code workflows (`/implement-task`, `/review-changes`, `/implement-with-review`)

### Output Formatting
- **`references/output-format-templates.md`**: Template library for consistent skill output formatting (7 templates with selection guide)
- **`references/format-compliance-guidance.md`**: Solutions for when Claude Code ignores documented output formats (Option A: Architecture fix, Option B: Hook gate, Option C: Both)

### Related Documentation
- `P:/.claude/hooks/PROTOCOL.md` - Complete hook I/O specifications
- `P:/.claude/hooks/ARCHITECTURE.md` - Constitutional enforcement mapping
- `P:/.claude/hooks/SKILL_AUTHORS_GUIDE.md` - Author's guide for skill execution requirements
- `C:\Users\brsth\.claude\projects\P--\memory\display_templates.md` - Output format templates
- `C:\Users\brsth\.claude\projects\P--\memory\integration_verification.md` - Integration testing for skills and hooks

## Progressive Disclosure System

Reference files in `references/` include YAML frontmatter for lazy loading based on workflow phase. This prevents context bloat by loading only relevant documentation for each phase.

### Frontmatter Schema

Each reference file includes:
```yaml
---
type: [core|workflow|quality|evaluation|optional]
load_when: [discovery|creation|quality|evaluation|optimization|distribution]
priority: [mandatory|recommended|supplemental]
estimated_lines: <number>
---
```

### Loading Rules by Phase

| Phase | Load Filter |
|-------|-------------|
| 1 (Discovery) | `type=core` + `load_when=discovery` |
| 2 (Creation) | `type=core/workflow` + `load_when=creation` |
| 3a (Spec) | `load_when=quality` + `priority=mandatory` |
| 3b (Quality) | `type=quality` + `load_when=quality` |
| 3c (Integration) | `type=evaluation` + `load_when=evaluation` |
| 3.5 (Evaluation) | `type=evaluation` + `load_when=evaluation` |

### Type Definitions

**core**: Foundational | **workflow**: Patterns | **quality**: Gates | **evaluation**: Testing | **optional**: Supplementary

See `references/.TEMPLATE.md` for complete frontmatter specification.

## Workflow Phases Overview

**Detailed phase-by-phase instructions**: See `references/workflow-phases.md`

| Phase | Goal | Key Skills | Template | Skip When |
|-------|------|------------|----------|-----------|
| **0. Context** | Session awareness, detect patterns | gto | Template 2 | Fresh sessions |
| **1. Discovery** | Understand user intent, auto-detect conflicts | similarity (auto) | Template 2 | Never |
| **1.5. Knowledge** | Retrieve existing patterns/lessons | notebooklm, cks, memory | Template 2 | Simple skills, user declines |
| **2. Creation** | Build skill structure with progressive disclosure | skill-creator, skill-development | Template 1 | Never |
| **3a. Spec Compliance** | Verify implementation follows plan | internal: testing-skills (spec mode) | Template 3 | Never |
| **3b. Code Quality** | Validate YAML, triggers, quality gates | internal: av, testing-skills (quality mode) | Template 3 | Simple skills (<100 lines) |
| **3c. Integration** | Test skill invocation and execution | internal: testing-skills (integration mode) | Template 3 | Never |
| **3.5. Evaluation** | Empirical testing with evals and benchmarks | skill-creator (evals) | Template 1 | Simple skills, user declines |
| **4. Optimization** | Add hooks, enforce formatting | internal: av2, output-style-extractor | Template 6 | Multi-phase workflows only |
| **5. Distribution** | Prepare for sharing/shipping | sharing-skills | Template 5 | Local skills only |

### Phase Summaries

**Phase 0: Context Awareness**
- **NEW**: Run `/gto` to detect session context before starting skill work
- Detect user correction patterns, learning signals, broken windows from previous work
- Identify current session state (hooks disabled, pending changes, incomplete work)
- **Skip**: Only for fresh sessions with no prior skill work in the chat

**Phase 1: Discovery & Intent**

### Trigger Strength Classification

When analyzing user intent, classify the trigger requirement:

| Strength | Definition | Example | Action |
|----------|------------|---------|--------|
| `MUST BE USED` | Mandatory gate - user explicitly requests skill workflow | "Create a skill", "I need a new skill" | Always invoke skill-ship |
| `Use PROACTIVELY` | Recommended trigger - strong opportunity for skill workflow | "Fix my skill", "This skill isn't working" | Suggest skill-ship strongly |
| `Consider using` | Optional enhancement - skill workflow may help | "What's wrong with this skill?", "How do I improve this?" | Offer skill-ship as option |

**Decision:** "create/new/build" → MUST USE | "fix/broken/error" → PROACTIVE | "improve/review/audit" → Consider

### Discovery Process
- Extract user intent and context
- **AUTOMATED**: Auto-invoke `/similarity` for conflict detection (≥80% similarity → enhance vs create)
- Determine output format and verification needs
- Classify trigger strength using decision tree above
- **See**: `references/workflow-phases.md#phase-1-discovery--intent`

**Phase 1.5: Knowledge Retrieval**
- **NEW**: Query NotebookLM, CKS, and memory.md for relevant patterns/lessons before building
- Extract key terms from skill intent/description
- Query CKS: `/cks "<domain>" "<keywords>"` for semantic search
- Query NotebookLM (if available): `nlm notebook list` then `nlm notebook query <id> "<question>"`
- Query memory.md: Read MEMORY.md topic index, then relevant topic files
- Present findings as recommendations (not requirements) for Phase 2
- **Skip**: Simple skills (<5 steps), user declines, or no relevant knowledge exists
- **See**: `references/workflow-phases.md#phase-15-knowledge-retrieval`

**Phase 2: Creation & Structuring**
- Create SKILL.md with proper frontmatter (including `enforcement` field - **REQUIRED**)
- Apply progressive disclosure (<500 lines)
- Choose output format template (1-7)
- **See**: `references/workflow-phases.md#phase-2-creation--structuring`
- **Frontmatter Reference**: `references/skill-frontmatter-fields.md` - Complete guide to all required fields including `enforcement: strict|advisory|none`

### Phase 3: Quality & Validation (Split)

**Quality Gate Execution Protocol:**
Each sub-phase spawns a FRESH subagent with minimal context to prevent state contamination. Previous stage verdicts are NOT shared to avoid bias.

---

#### Phase 3a: Specification Compliance
**Question:** "Did the implementation follow the plan?"

**Focus:** RED/GREEN/REGRESSION/VERIFY completion evidence

**Process:**
1. Spawn FRESH subagent with: plan.md (if exists) + draft SKILL.md
2. Review ONLY: Does implementation match stated requirements?
3. Do NOT review code quality (that's Phase 3b)
4. Do NOT share previous verdicts or quality scores

**Output:** `SPEC_PASS` or `SPEC_FAIL` with gap list

| Requirement | Status | Evidence | Gap |
|-------------|--------|----------|-----|
| Stated user intent addressed | - | - | - |
| Required sections present | - | - | - |
| Completion evidence provided | - | - | - |
| Reference integrity (files exist) | - | - | - |

**Gate:** ⛔ Block Phase 3b until `SPEC_PASS`

**Skip:** Never - spec compliance is mandatory

---

#### Phase 3b: Code Quality
**Question:** "Is this well-structured, secure skill code?"

**Focus:** YAML completeness, trigger accuracy, quality gates, context bloat prevention

**Process:**
1. Spawn FRESH subagent with: SKILL.md + `SPEC_PASS` verdict (not spec rationale)
2. Review: Code quality, security, maintainability, best practices
3. **CRITICAL**: Context bloat prevention checks
   - SKILL.md size validation (warn if >300 lines, block if >500 lines)
   - Duplicate content detection (SKILL.md vs memory/ system)
   - Reference integrity check (all referenced files exist)
   - Memory system integration (reference memory/ files instead of duplicating)

**Output:** Quality scores + improvement suggestions

| Check | Status | Severity | Fix |
|-------|--------|----------|-----|
| YAML frontmatter completeness | - | 🔴/⚠️/ℹ️ | - |
| Enforcement tier field (required) | - | 🔴/⚠️/ℹ️ | - |
| Trigger accuracy (third person) | - | 🔴/⚠️/ℹ️ | - |
| Description length (<1024 chars) | - | 🔴/⚠️/ℹ️ | - |
| Progressive disclosure (<500 lines) | - | ⚠️/ℹ️ | - |
| Hook analysis (if applicable) | - | ℹ️ | - |
| Skill hook path resolution (if hooks) | - | 🔴/⚠️ | - |
| Absence claim verification | - | 🔴/⚠️ | - |

**Absence Claim Verification Workflow:**
Before claiming a component is missing, verify absence with tool evidence:
1. **Grep before claim**: Search codebase for the component name/pattern
2. **Read before missing**: Check referenced files exist before stating they're absent
3. **Glob before none**: Verify no matches with glob patterns before claiming "no files"
4. Document negative findings with explicit search terms used

**Gate:** ⛔ Block Phase 3c until 🔴 critical issues resolved

**Skip:** Simple skills (<100 lines) can skip to 3c after basic YAML check

---

#### Phase 3c: Integration Verification
**Question:** "Does the skill work when invoked?"

**Focus:** Actual skill invocation test, execution paths, runtime behavior

**Process:**
1. Spawn FRESH subagent with: installed skill + test prompts (blind to spec/quality)
2. Invoke skill with sample prompts
3. Verify: Skill triggers correctly, executes without errors, produces expected output
4. Test orchestrated skills: Verify coordinated skill execution

**Output:** Test execution transcript + pass/fail

| Test | Status | Evidence | Fix |
|------|--------|----------|-----|
| Skill loads without errors | - | - | - |
| Triggers on expected queries | - | - | - |
| Executes workflow correctly | - | - | - |
| Orchestrated skills work | - | - | - |
| Multi-terminal safe (if applicable) | - | - | - |
| Absence claims verified before asserting | - | - | - |

**Gate:** ⛔ Block Phase 4 until integration passes

**Skip:** Never - integration verification is mandatory

---

**See**: `references/workflow-phases.md#phase-3-quality--validation` (split)
**Context Bloat Prevention**: `references/context-bloat-prevention.md`

#### Phase 3d: Artifact Quality Validation (conditional)
**Activate when**: Target skill emits durable artifacts (plans, reports, configs consumed by other agents). Check for `produces_artifact: true` in SKILL.md frontmatter.

**Reference:** `references/artifact-rubric.md` — 5-criterion quality bar
**See**: `references/workflow-phases.md#phase-3d-artifact-quality-validation-conditional`

**Gate:** ⛔ Block Phase 4 until `ARTIFACT_PASS` (all P0/P1 criteria met) when target skill produces artifacts

**Skip:** Utility skills with transient output (no durable artifacts)

**Phase 3.5: Evaluation & Iteration** (optional)
- Run eval suite with `evals/evals.json`
- Generate performance report with variance analysis
- Description optimization if triggering < 80%
- **Skip**: Simple skills, user declines, subjective outputs
- **📖 Detailed Guide**: `references/eval-guide.md` - Complete eval suite creation, test categories, performance interpretation, and description optimization
- **See**: `references/workflow-phases.md#phase-35-evaluation--iteration`

**Phase 4: Optimization & Enhancement**
- Invoke internal `av2` for StopHook integration (multi-phase workflows only)
- Invoke `/output-style-extractor` for standardized output formatting
- Optimize description for triggering accuracy
- **Pattern synthesis**: Read `P:/memory/skill_optimization_patterns.md` and `P:/.claude/.evidence/critique/IMPROVEMENTS.md`. If improvements has entries not yet generalized into patterns, extract broader principles and append to `skill_optimization_patterns.md`. This is the "do it properly" pass — more thorough than the incremental check in `/critique`.
- **Skip**: Single-phase workflows don't need StopHook
- **See**: `references/workflow-phases.md#phase-4-optimization--enhancement`

**Phase 5: Distribution & Documentation**
- Fork repository, create feature branch
- Commit with conventional commits
- Open PR with proper description
- **See**: `references/workflow-phases.md#phase-5-distribution--documentation`

---

## Output Formatting

All skill outputs MUST use templates from `references/output-format-templates.md`:

| Template | Use Case | Example |
|----------|----------|---------|
| Template 1: Strict Analysis | API responses, test results, bug reports, RCA | debugRCA skill |
| Template 2: Executive Summary | Analysis reports, research, recommendations | Most skills default |
| Template 3: Hypothesis Testing | Debugging, RCA, investigation | adversarial-rca |
| Template 4: Comparison | Tool selection, architecture decisions | Similarity analysis |
| Template 5: Workflow Progress | Long-running tasks, multi-step workflows | Phase tracking |
| Template 6: Error Analysis | Bug reports, error investigations | Debug findings |
| Template 7: Research Findings | Research tasks, documentation analysis | Research results |

**See**: `references/output-format-templates.md` for complete template library and selection guide

### Dynamic RNS Format (/gto)

For skills that produce gap-based findings (like `/gto`), use the **dynamic RNS format** instead of static templates. This format generates domain categories based on actual gap types detected:

| Gap Type | Domain |
|----------|--------|
| test_failure, missing_test | tests |
| missing_docs, outdated_docs | docs |
| git_dirty, uncommitted_changes | git |
| import_error, missing_dependency | dependencies |
| code_quality, tech_debt | code_quality |

**Reference**: `/gto SKILL.md` — "Recommended Next Steps (RNS)" section for dynamic domain format specification

---

## Agent Tool Usage

**CRITICAL**: When using the Task tool to spawn subagents from skills, understand the difference between `subagent_type` and `model` parameters.

**❌ WRONG**: `Launch subagents (haiku model)` → Gets interpreted as `subagent_type="haiku"` → ERROR (haiku is not an agent type)

**✅ CORRECT**: `Launch subagents with model="haiku"` → Correctly passes `model: "haiku"` → Works

**See**: `references/agent-tool-usage.md` for complete parameter reference, examples, and common mistakes

---

## Execution Directive

When `/skill-ship` is invoked:

1. **CONTEXT**: Run Phase 0 with `/gto` to detect session patterns, user corrections, learning signals
2. **DISCOVER**: Run Phase 1 to understand intent and context (auto-invoke `/similarity` for conflict detection)
3. **CLASSIFY**: Determine skill type (new/existing), complexity, output format needs
4. **COORDINATE**: Invoke appropriate specialized skills based on classification
5. **FORMAT**: Apply output format templates from `references/output-format-templates.md`
6. **VALIDATE SPEC (3a)**: Spawn fresh subagent to verify implementation follows plan → Block 3b until SPEC_PASS
7. **VALIDATE QUALITY (3b)**: Spawn fresh subagent for code quality review → Block 3c until 🔴 issues resolved
8. **VALIDATE INTEGRATION (3c)**: Spawn fresh subagent to test skill invocation → Block Phase 4 until pass
9. **EVALUATE**: Run Phase 3.5 with skill-creator's evaluation system (evals, benchmarks) - skip for simple skills
10. **OPTIMIZE**: Apply internal av2/hooks if workflow complexity warrants
11. **DOCUMENT**: Ensure output format is documented in skill
12. **DISTRIBUTE**: Offer sharing-skills workflow if skill will be upstreamed

**Quality Gate Protocol**: Each validation phase spawns a FRESH subagent with minimal context. Previous verdicts are NOT shared to avoid bias.

**See**:
- `references/workflow-phases.md` - Detailed phase-by-phase instructions
- `examples/WORKFLOW-EXAMPLES.md` - 3 complete workflow demonstrations

---

## Recommended Next Steps

**When `/skill-ship` analysis is complete**, present next steps in this format:

```markdown
**Recommended Next Steps**

1 - Analyze intent and detect conflicts
- 1a: Similarity analysis → Use `/similarity <target>` - Find redundant/similar skills
- 1b: Intent clarification → Manual interview - Understand user requirements

2 - Build skill structure with proper formatting
- 2a: Create skill draft → Use `/skill-creator` - Full iterative development with evals
- 2b: Structure guidance → Use `/skill-development` - SKILL.md patterns and progressive disclosure
- 2c: Convert docs → Use `/doc-to-skill` - Transform documentation into skills

3 - Validate specification, code quality, and integration
- 3a: Spec compliance → Internal testing-skills (spec mode) - Verify implementation follows plan
- 3b: Code quality → Internal av, testing-skills (quality mode) - YAML, triggers, context bloat
- 3c: Integration test → Internal testing-skills (integration mode) - Test skill invocation

4 - Empirical testing and performance analysis (optional for simple skills)
- 4a: Run eval suite → Use `/skill-creator` - Evals, benchmarks, variance analysis
- 4b: Optimize description → Use `/skill-creator` - Improve triggering accuracy

5 - Add hooks and enforce formatting
- 5a: Mechanical continuation → Use `/av2` - StopHook for multi-phase workflows
- 5b: Standardize output → Use `/output-style-extractor` - Enforce formatting templates

6 - Prepare for sharing and upstreaming
- 6a: Share via GitHub → Use `/sharing-skills` - Automated PR workflow
- 6b: Pre-publish checklist → Use `/github-public-posting` - Final quality checks

0 - Do ALL Recommended Next Steps
```

**Conditional format (when no next steps needed)**:

```markdown
**Recommended Next Steps**

No next steps required - skill analysis complete.

0 - Nothing left to do
```

**Format Requirements**:
- Line 1: `1 - description` format (no parenthetical domain labels)
- Lines 2+: `- 1a: Action → Use /skill OR manual - context` format (dash prefix required)
- Skill recommendations: Use arrow syntax `→ Use /skill-name` (Claude executes this)
- Manual actions: Use `→ Manual check` or `→ No skill applies` (User does this themselves)
- End with: `0 - Do ALL Recommended Next Steps` OR `0 - Nothing left to do`
- Domains numbered 1, 2, 3...; Actions lettered a, b, c...
- Practical limit: ~20 total actions (3-6 domains × 2-4 items) for cognitive load
- **Critical**: Actions within a domain must NOT conflict. If selecting "0" or the domain number would create contradictory outcomes (e.g., "test" AND "skip testing"), split into separate domains
