# Code Review, Quality Scanning & Meta-Review (Detailed Reference)

## PHASE 4.5: Code Review & Meta-Review

**Objective**: Run automated code review AND meta-review to catch quality and cross-file issues before portfolio polish.

**When**: Automatically runs after PHASE 4 (Validate) completes, before PHASE 5 (Portfolio Polish).

**What this does:**
1. **Code Review Plugin**: Comprehensive code review with confidence-based scoring
   - Checks for security, performance, and maintainability issues
   - Confidence threshold (80+) for filtering findings
   - Generates summary report with actionable recommendations

2. **Meta-Review System**: Cross-file analysis for architectural issues
   - Path traversal vulnerability detection (taint propagation)
   - Import graph analysis (circular dependencies, layering violations)
   - Documentation consistency validation
   - AnalysisUnit-based manifest-driven review

**Execution:**
```python
# Code review
Skill(skill="code-review:code-review", args="{{TARGET_DIR}}")

# Meta-review
from lib.meta_review.prepare_context import prepare_agent_context
from lib.analysis_unit import create_analysis_unit

unit_id = create_analysis_unit(Path("{{TARGET_DIR}}"))
context = prepare_agent_context(unit_id, perspective="security", max_tokens=8000)

from lib.analysis_unit.analyzers.path_traversal import PathTraversalAnalyzer
from lib.analysis_unit.analyzers.import_graph import ImportGraphAnalyzer
from lib.analysis_unit.analyzers.doc_consistency import DocConsistencyAnalyzer

pt_findings = PathTraversalAnalyzer().analyze(manifest)["findings"]
ig_findings = ImportGraphAnalyzer().analyze(manifest)["findings"]
dc_findings = DocConsistencyAnalyzer(manifest).analyze()
```

**Integration notes:**
- Run AFTER structure validation passes
- Run BEFORE portfolio polish (prevents polishing bad code)
- Meta-review optional (controlled by META_REVIEW_ENABLED env var, default: true)
- Critical findings (HIGH): fix before proceeding
- Advisory findings (MEDIUM/LOW): document, proceed

**Duration**: 1-3 minutes (combined)

## PHASE 4.5b: Quality Scanning (Optional)

**Objective**: Automated security and dependency scanning during validation phase.

**Trigger**: `--scan-quality` flag.

**What this does:**
1. **Security Scanning**: `bandit` for Python security, `safety` for vulnerable deps
2. **Dependency Auditing**: `pip-audit` for vulnerability scanning
3. **Badge Validation**: Verifies badge URLs in README are reachable
4. **Quality Metrics**: Python/test file counts, test ratio, lines of code

**Script**: `scripts/scan_package_quality.py`

**Options**:
- `--skip-security`, `--skip-audit`, `--skip-badges`, `--skip-quality`
- `--save-report`, `--fail-on-issues`
