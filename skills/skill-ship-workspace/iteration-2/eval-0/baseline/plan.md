# Skill Creation Plan: Code Review Workflow Automation

## Objective
Create a skill that automates code review workflow by dispatching parallel specialist agents and synthesizing findings into actionable recommendations.

## Analysis Summary

### Existing Skills
| Skill | Focus | Strengths |
|-------|-------|-----------|
| /code-review | Parallel specialists | Session management, synthesis |
| /adversarial-review | 7-agent + meta-critic | Comprehensive, JSON output schema |
| /meta-review | Cross-file Python | Architecture, security analysis |

### Gap Analysis
The existing skills are comprehensive but could benefit from:
- Streamlined workflow for common cases
- Git diff auto-detection
- Simplified health score formula
- Clearer trigger phrases

## Proposed Skill: code-review-workflow

### Core Functionality
1. Context-aware target resolution (args > git diff > ask)
2. Session-based tracking
3. Parallel specialist dispatch
4. Health score calculation
5. Synthesized report delivery

### Differentiation from Existing
- More streamlined than /adversarial-review
- Git-aware (auto-detect changed files)
- Focus on common use cases

## Implementation Notes

### Phase 1: Draft Creation
- [x] SKILL.md drafted
- [x] Triggers defined
- [x] Workflow documented

### Phase 2: Evals
- [x] 3 test cases created
- [ ] Test prompts need execution

### Phase 3: Validation
- [ ] Spec compliance (Phase 3a)
- [ ] Code quality (Phase 3b)
- [ ] Integration test (Phase 3c)

### Phase 4: Optimization
- [ ] Hook integration (av2)
- [ ] Output formatting

### Phase 5: Distribution
- [ ] GitHub workflow preparation
