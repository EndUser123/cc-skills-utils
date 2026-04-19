---
type: core
load_when: discovery
priority: mandatory
estimated_lines: 350
---

# Skill Complete - Detailed Workflow Phases

This document contains the detailed phase-by-phase instructions for the skill-ship workflow. See SKILL.md for overview and quick reference.

## Phase 1: Discovery & Intent

**Goal**: Understand what the user wants to accomplish

**Questions to answer**:
1. What should this skill enable Claude to do?
2. When should this skill trigger? (user phrases/contexts)
3. What's the expected output format?
4. Is this a new skill or improvement to existing?
5. Should we set up test cases for verification?

**Actions**:
1. **Extract intent** from conversation if available
2. **AUTOMATED CONFLICT DETECTION** (enforced):
   - Invoke `/similarity` skill automatically with skill description/intent
   - If similarity score ≥ 80%:
     - Display conflict table: | Existing Skill | Similarity | Overlapping Features |
     - Ask user: "Continue creating new skill OR enhance existing [skill-name]?"
     - If enhance: Route to `/skill-ship` with improvement intent for existing skill
     - If continue: Document overlap rationale and proceed with creation
3. Clarify output format requirements
4. Determine if objective verification is needed

**Output Format**: Use Template 2 (Executive Summary Format)

```markdown
# Discovery Summary

## Intent
[What the skill should do]

## Context
- Triggering phrases: [list]
- Output format: [description]
- Conflict detection: [similarity score / conflicts found / none]
- Test coverage: [yes/no with rationale]

## Similarity Analysis
[If conflicts detected:]
| Existing Skill | Similarity | Overlapping Features | Action |
|----------------|------------|---------------------|---------|
| [skill-name] | [score%] | [features] | [Enhance/Continue/New]

## Recommendation
[Proposed approach with skill type classification]
[If conflicts: Document decision rationale for creating new vs enhancing existing]
```

---

## Phase 1.5: Knowledge Retrieval

**Goal**: Retrieve relevant patterns, lessons, and research before building

**Questions to answer**:
1. What related patterns exist in CKS?
2. What research exists in NotebookLM about this domain?
3. What relevant lessons are in memory.md?

**Actions**:
1. **Query CKS** for relevant patterns:
   - Extract key terms from skill intent/description
   - Run `/cks search "<domain>" "<keywords>"` for semantic search
   - Run `/cks search "<pattern_type>"` for hook/pattern/anti-pattern queries

2. **Query NotebookLM** (if available):
   - Check `nlm auth status`
   - List notebooks: `nlm notebook list`
   - Query relevant notebooks: `nlm notebook query <id> "<question about skill domain>"`

3. **Query memory.md**:
   - Read MEMORY.md topic index
   - Read relevant topic files based on keywords
   - Priority files: working_principles.md, discovery_patterns.md, skill_optimization_patterns.md

**Output Format**: Use Template 2 (Executive Summary Format)

```markdown
## Knowledge Retrieval Summary

### CKS Results
[Relevant patterns found in CKS]

### NotebookLM Results
[Relevant research from notebooks]

### Memory.md Results
[Relevant topic files and lessons]

### Recommendations
[What patterns/lessons should be incorporated into the skill]
```

**Skip this phase when**:
- Simple skills (<5 steps, straightforward execution)
- User explicitly declines knowledge retrieval
- Domain has no existing CKS/memory entries

---

## Phase 2: Creation & Structuring

**Goal**: Create or update the skill structure

**Skill Coordination**:
- Invoke **skill-creator** for draft creation and test prompt generation
- Invoke **skill-development** for SKILL.md structure and best practices
- Use **display_templates.md** for output formatting guidance

**Actions**:
1. Create SKILL.md with proper YAML frontmatter
2. **Set Degrees of Freedom** (NEW):
   - Add `freedom: high|medium|low` field to YAML frontmatter
   - **High freedom** (text-based instructions): Multiple approaches valid, decisions depend on context
   - **Medium freedom** (pseudocode/scripts with parameters): Preferred pattern exists, some variation acceptable
   - **Low freedom** (specific scripts, few parameters): Operations fragile, consistency critical
3. Apply progressive disclosure pattern (keep under 500 lines)
4. Choose appropriate output format template from display_templates.md:
   - Template 1: Strict Analysis Format (API-like)
   - Template 2: Executive Summary Format (flexible)
   - Template 3: Hypothesis Testing Format
   - Template 4: Comparison Format
   - Template 5: Workflow Progress Format
   - Template 6: Error Analysis Format
   - Template 7: Research Findings Format

**Output Format**: Use Template 1 (Strict Analysis Format)

```markdown
## Skill Structure Analysis

**Confidence:** [Score]% (Tier [1-4])

### Skill Classification
**Type:** [EXECUTION/KNOWLEDGE/PROCEDURE]
**Freedom Level:** [high/medium/low]
**Complexity Score:** [calculated score]
**Hook Recommendation:** [yes/no with rationale]

### Structure
- YAML frontmatter: ✓
- Description quality: [assessment]
- Progressive disclosure: [assessment]
- Output format template: [Template #]

### Evidence
| Aspect | Status | Notes |
|--------|--------|-------|
| Triggers | [status] | [details] |
| Workflow | [status] | [details] |
| Output | [status] | [details] |
| Tests | [status] | [details] |
```

---

## Phase 3: Quality & Validation

**Goal**: Ensure skill meets quality standards

**Skill Coordination**:
- Invoke **testing-skills** for trigger and execution path validation
- Invoke **av** for hook generation and improvement analysis
- Run test prompts if configured

**Quality Validation Integration**:

1. **Skill Validation** (recommended):
   - Invoke `/testing-skills` with skill path for validation
   - Testing-skills will verify: YAML completeness, trigger accuracy, constitution links
   - Review validation report and address critical issues before proceeding

2. **Manual Verification Checks** (always performed):
   - **YAML frontmatter**: Verify name, description, triggers, category present
   - **Description quality**: Check ≤100 characters (registry constraint)
   - **Trigger phrases**: Test that phrases actually invoke the skill
   - **Constitution links**: Ensure skill declares which PARTs it extends
   - **Execution paths**: Walk through workflow steps to verify they complete

3. **Integration Check** (for orchestrated skills):
   - Verify all skills in `suggest:` field actually exist
   - Use `/similarity` to check for redundant/conflicting skills
   - Document any gaps or overlaps

4. **Progressive Disclosure** (enforced for >300 lines):
   - If SKILL.md exceeds 300 lines, move detailed content to references/
   - Keep main workflow in SKILL.md, advanced guides in references/

5. **Isolation Testing** (NEW - critical safety check):
   - Spawn sub-agent with ONLY the test skill
   - Run 2-3 representative tasks in isolated context
   - Verify: No environment mutations, no side effects
   - Check: Skill executes without affecting user's environment

**Actions**:
1. **Skill validation** (recommended):
   - Invoke `/testing-skills` with skill path
   - Review validation report for critical issues
   - Address FAILED checks before proceeding

2. **Integration verification** (if orchestrated):
   - Check all skills in `suggest:` field exist
   - Use `/similarity` to detect redundancy/conflicts
   - Document any integration gaps

3. **Absence claim verification** (if claims present):
   - Use Read/Grep tools to verify absence claims
   - Require Tier 1 or Tier 2 evidence before accepting
   - Flag unverified claims for user correction

4. **Test trigger phrases** (if complex triggering):
   - Manually test trigger phrases
   - Verify skill activates with intended phrases
   - Optimize description if triggering fails

5. **Check progressive disclosure** (if SKILL.md >300 lines):
   - Verify main content in SKILL.md, details in references/
   - If not compliant: Move content to references/ and restructure

6. **Isolation testing** (NEW - critical safety check):
   - Spawn sub-agent with ONLY the test skill
   - Run 2-3 representative tasks
   - Verify: No environment mutations, no side effects
   - Check: Skill executes in isolated context

7. **Generate hooks** (if complexity score ≥ 1):
   - Invoke **av** for hook generation
   - Apply StopHook for multi-phase workflows
   - Apply PreToolUse hooks for execution requirements

**Output Format**: Use Template 3 (Hypothesis Testing Format)

```markdown
## Quality Validation

| Test | Status | Evidence | Fix |
|------|--------|----------|-----|
| YAML completeness | ✓/✗ | [details] | [action if needed] |
| Trigger accuracy | ✓/✗ | [details] | [action if needed] |
| Output consistency | ✓/✗ | [details] | [action if needed] |
| Execution flow | ✓/✗ | [details] | [action if needed] |
| Absence claim verification | ✓/✗ | [details] | [action if needed] |
| Isolation testing | ✓/✗ | [details] | [action if needed] |
| Test coverage | ✓/✗ | [details] | [action if needed] |

### Selected Issues
**Priority:** [High/Medium/Low]
**Issue:** [Description]
**Fix:** [Specific action]

### Validation Plan
1. [Validation step 1]
2. [Validation step 2]
3. [Validation step 3]
```

---

## Phase 3d: Artifact Quality Validation (Conditional)

**Goal**: Validate downstream artifact quality when target skill emits durable artifacts

**Activation**: This phase activates ONLY when target skill produces persistent artifacts (plans, reports, configs consumed by other agents). Check:
- `produces_artifact: true` in SKILL.md frontmatter
- Skill writes files to disk that another agent/human will consume
- NOT for utility skills with transient output

**Actions**:
1. **Load artifact-rubric.md** — the 5-criterion quality bar for artifact-emitting skills
2. **Locate the artifact** — Find the primary output file(s) the skill produces
3. **Apply the 5 checks**:
   - Single-purpose: artifact addresses one goal, not multiple
   - No raw findings: audit logs/review output synthesized, not pasted verbatim
   - No placeholder residue: no `{{TODO}}`, `[UNRESOLVED]`, unresolved markers
   - Contradiction-free: status is internally consistent (e.g., "ACCEPTED" = no P0 blockers)
   - Decision-complete: all P0/P1 findings incorporated or explicitly deferred with rationale
4. **Synthesize findings** — Do not append raw check output; summarize by criterion

**Blocking gate**: Phase 4 is blocked until `ARTIFACT_PASS` (all P0/P1 criteria met).

**Output Format**:
```markdown
## Artifact Quality Validation

| Criterion | Result | Details |
|-----------|--------|---------|
| Single-purpose | ✓/✗ | [details] |
| No raw findings | ✓/✗ | [details] |
| No placeholder residue | ✓/✗ | [details] |
| Contradiction-free | ✓/✗ | [details] |
| Decision-complete | ✓/✗ | [details] |

### Verdict
**ARTIFACT_PASS** or **ARTIFACT_FAIL** — [list failures if any]
```

---

## Phase 3.5: Evaluation & Iteration

**Goal**: Validate skill performance through empirical testing and iteration

**Choose Evaluation Mode** (NEW):

**Trial Mode** (before installing):
- Test-drive skill with 2-3 representative tasks
- Evaluate: Does it help? Clear instructions?
- Decision: keep, pass, or try another
- Use case: "Try before commit" - quick informal testing

**Evaluation Mode** (before publishing):
- Spawn specialized reviewers for structure/safety/usefulness
- Comprehensive quality audit with formal test suite
- Generate recommendations for improvements
- Use case: "Evaluate before publish" - formal quality gate

**Prerequisites**:
- Requires **skill-creator** plugin (from `~/.claude/plugins/cache/claude-plugins-official/skill-creator/`)
- Eval suite structure: Create `evals/evals.json` in skill directory with test prompts
- Eval viewer: Uses `eval-viewer/generate_review.py` for performance reports (skill-creator feature)

**📖 Detailed Guide**: See `references/eval-guide.md` for complete eval suite creation, test categories, performance interpretation, and description optimization.

**Skill Coordination**:
- Invoke **skill-creator** to run eval suite with `evals/evals.json`
- Use eval-viewer to generate performance reports via `eval-viewer/generate_review.py`
- Apply description optimization script if triggering issues detected
- Iterate until satisfaction threshold met

**Actions**:
1. **Choose mode**: Ask user "Trial mode (test-drive) or Evaluation mode (quality audit)?"
2. Create test prompts (2-3 realistic user queries)
3. Save to `evals/evals.json` format
4. Run evaluation suite with skill-creator
5. Generate performance report with variance analysis
6. Review results with user using eval-viewer
7. Apply description optimization if triggering accuracy < 80%
8. Rewrite skill based on empirical feedback
9. Repeat until performance threshold met

**Output Format**: Use Template 1 (Strict Analysis Format)

```markdown
## Evaluation Results

**Confidence:** [Score]% (Tier [1-4])

### Performance Metrics
| Metric | Score | Target | Status |
|--------|-------|--------|--------|
| Trigger accuracy | [%] | ≥80% | ✓/✗ |
| Output consistency | [%] | ≥90% | ✓/✗ |
| Execution success | [%] | ≥95% | ✓/✗ |
| Variance analysis | [score] | Low variance | ✓/✗ |

### Test Results
| Test Prompt | Expected | Actual | Pass/Fail | Notes |
|-------------|----------|--------|-----------|-------|
| [prompt 1] | [expectation] | [result] | ✓/✗ | [notes] |
| [prompt 2] | [expectation] | [result] | ✓/✗ | [notes] |

### Iteration Plan
1. [Issue identified] → [Fix applied]
2. [Issue identified] → [Fix applied]
3. Re-run eval suite after fixes

### Evidence
| Aspect | Evidence Source |
|--------|-----------------|
| Test output | eval-viewer/generate_review.py |
| Performance | evals/evals.json results |
| Variance | Benchmark comparison |
```

**When to skip this phase**:
- Simple skills with objectively verifiable outputs (file transforms, data extraction)
- User explicitly declines evaluation ("just vibe with me")
- Skills with subjective outputs (writing style, art)

---

## Phase 4: Optimization & Enhancement

**Goal**: Improve skill performance and reliability

**Skill Coordination**:
- Invoke **av2** for mechanical continuation enforcement (if multi-phase workflow)
- Invoke **output-style-extractor** to ensure consistent formatting
- Review display_templates.md for format improvements

**Actions**:
1. Analyze workflow for phase enforcement needs
2. Add StopHook if multi-phase workflow detected
3. Optimize description for triggering accuracy (if Phase 3.5 showed issues)
4. Ensure output format matches chosen template
5. Add progressive disclosure if skill > 300 lines
6. **Consistency verification** (NEW - flaky test detection):
   - Run skill 3x with identical prompts
   - Measure output variance across runs
   - Flag non-deterministic behavior
   - High variance = requires fixing before deployment

**Output Format**: Use Template 6 (Error Analysis Format)

```markdown
## Optimization Analysis

### Summary
**Skill:** [skill-name]
**Location:** [file:line or component]
**Optimization Type:** [Continuation/Format/Performance]

### Issues Identified
| Issue | Impact | Fix |
|-------|--------|-----|
| [Issue 1] | [High/Med/Low] | [Solution] |
| [Issue 2] | [High/Med/Low] | [Solution] |

### Resolution
**Continuation Enforcement:** [StopHook added/updated/skipped]
**Format Standardization:** [Template # applied]
**Performance:** [optimizations applied]

### Prevention
[How to prevent future issues]
```

---

## Phase 5: Distribution & Documentation

**Goal**: Prepare skill for sharing or deployment

**Skill Coordination**:
- Invoke **sharing-skills** for GitHub PR workflow
- Invoke **github-public-posting** for pre-publish checklist
- Document output format in skill if not present

**Actions**:
1. Create fork if needed
2. Create feature branch
3. Commit changes with conventional commits
4. Open PR with proper description
5. Ensure output format documented in SKILL.md

**Output Format**: Use Template 5 (Workflow Progress Format)

```markdown
## Distribution Progress

### Phase 1: Preparation
- [x] Skill validated
- [x] Output format documented
- [x ] PR description written

### Phase 2: Git Workflow
- [ ] Fork repository
- [ ] Create feature branch
- [ ] Commit changes
- [ ] Push to remote

### Phase 3: PR Creation
- [ ] Open pull request
- [ ] Add reviewers
- [ ] Link to issues

### Current Status
**Phase:** [Current phase]
**Blockers:** [Any blockers or "None"]
**Next action:** [Specific next step]
```

---

## When to Skip Phases

**Skip Phase 3.5 (Evaluation) when:**
- Simple skills with objectively verifiable outputs
- User explicitly declines evaluation
- Skills with subjective outputs (writing style, art)

**Skip Phase 5 (Distribution) when:**
- Local skill improvements
- Plugin skills (use plugin distribution workflow)
- Skills not intended for sharing

## Quick Reference Table

| Phase | Goal | Key Skills | Output Template | Skip When |
|-------|------|------------|-----------------|-----------|
| Phase 1 | Discovery & Intent | similarity | Template 2 | Never |
| Phase 1.5 | Knowledge Retrieval | notebooklm, cks, memory | Template 2 | Simple skills, user declines |
| Phase 2 | Creation & Structuring | skill-creator, skill-development | Template 1 | Never |
| Phase 3 | Quality & Validation | testing-skills, av | Template 3 | Never |
| Phase 3.5 | Evaluation & Iteration | skill-creator (evals) | Template 1 | Simple skills, user declines, subjective outputs |
| Phase 4 | Optimization & Enhancement | av2, output-style-extractor | Template 6 | Multi-phase workflows only |
| Phase 5 | Distribution & Documentation | sharing-skills | Template 5 | Local skills, plugins, not sharing |
