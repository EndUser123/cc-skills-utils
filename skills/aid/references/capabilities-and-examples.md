# AI-Distiller Capabilities & Examples

## Key Capabilities

### 1. Refactoring Analysis
Identifies:
- Architectural weaknesses and anti-patterns
- SOLID principle violations
- Technical debt assessment
- Code quality issues
- Performance bottlenecks
- Security concerns

### 2. Security Audit
OWASP Top 10 focus:
- Injection vulnerabilities
- Broken authentication
- Sensitive data exposure
- XML external entities (XXE)
- Broken access control
- Security misconfigurations

### 3. Performance Analysis
Identifies:
- Inefficient algorithms (O(n^2) where O(n) possible)
- Resource leaks
- Unnecessary database/API calls
- Missing caching opportunities

### 4. Architecture Analysis
Generates:
- Enterprise-grade codebase overview
- Dependency mappings
- 10 Mermaid diagrams (diagrams shortcut)
- Pattern analysis

### 5. Documentation
Creates:
- Single file documentation (docs shortcut)
- Multi-file documentation workflows (multi shortcut)
- API documentation from code structure

## Git Mode

Special mode for git history analysis:

```bash
# Show last 50 commits
/aid git 50

# Git history with AI analysis prompt
/aid git --with-analysis-prompt

# Both combined
/aid git 50 --with-analysis-prompt
```

Output format:
```
[commit_hash] date time | author | subject
        | body lines (if any)
        |
```

## Examples by Use Case

### Large File Refactoring
```bash
# Analyze a 2800+ line file for refactoring
/aid refactor src/download/download_handler.py

# Output includes:
# - Executive summary with health score
# - Top 3 critical issues
# - Detailed findings with locations
# - Refactoring roadmap by phase
# - Code examples (before/after)
# - Testing strategy
# - Migration plan
```

### Security Audit
```bash
# Scan for security vulnerabilities
/aid security . --private --internal

# Checks for:
# - SQL injection patterns
# - XSS vulnerabilities
# - Hardcoded secrets
# - Insecure deserialization
# - Broken authentication patterns
```

### Performance Investigation
```bash
# Find performance bottlenecks
/aid perf src/ --implementation

# Identifies:
# - Nested loops (O(n^2) patterns)
# - N+1 query problems
# - Missing caching
# - Inefficient data structures
```

### Architecture Documentation
```bash
# Generate architecture documentation
/aid arch . --format md --stdout

# Produces:
# - Component relationships
# - Data flow diagrams
# - Dependency graphs
# - Pattern analysis
```
