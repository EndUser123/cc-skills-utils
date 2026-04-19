---
name: serena
description: **ALWAYS use this skill for semantic code analysis** - finding symbols, searching references, analyzing class hierarchies, refactoring code, or understanding codebase structure. This skill provides AST-based semantic analysis superior to grep/text search. Trigger on ANY code intelligence task: "find all classes", "what references X", "analyze code structure", "search for functions", "understand dependencies", "code navigation", "symbol operations". Use this skill BEFORE reaching for grep/ripgrep - semantic analysis beats text search for code understanding tasks. Even simple "find X in codebase" queries should use this skill for accurate results.
version: 1.0.0
status: stable
category: analysis

# Serena API - Semantic Code Analysis

Programmatic access to Serena's semantic code analysis capabilities. Use Serena's Python API directly instead of MCP for symbol operations, security scanning, refactoring, and knowledge persistence.

## Import

Import from the knowledge.analysis.serena module:

```python
from knowledge.analysis.serena import (
    SymbolTools,      # Find symbols, references, refactor
    MemorySystem,     # Knowledge persistence
    SecurityScanner,  # Security and pattern analysis
    SerenaAnalyzer,   # Code analysis
    Symbol, SymbolKind, SymbolLocation,
)
```

## Initialize

Create instances with workspace root:

```python
from pathlib import Path

workspace = Path.cwd()  # or specify path
tools = SymbolTools(workspace_root=workspace)
memory = MemorySystem(workspace_root=str(workspace))
```

## Error Handling

Handle common errors gracefully:

```python
from pathlib import Path
from knowledge.analysis.serena import SerenaMemoryError

# Validate workspace exists
workspace = Path.cwd()
if not workspace.exists():
    raise ValueError(f"Workspace not found: {workspace}")

# Handle memory write failures
try:
    memory.write_memory(
        title="Test insight",
        content="Test content"
    )
except SerenaMemoryError as e:
    print(f"Failed to write memory: {e}")
    if e.cause:
        print(f"Cause: {e.cause}")

# Handle symbol search failures
try:
    symbols = tools.find_symbol("NonExistent")
except Exception as e:
    print(f"Symbol search failed: {e}")
    symbols = []  # Fallback to empty list
```
```

## SymbolTools - Find and Navigate

### Find Symbols

Search for classes, functions, variables by name:

```python
# Find all symbols matching name
symbols = tools.find_symbol("MyClass")

# Filter by kind
symbols = tools.find_symbol("process", kind=SymbolKind.FUNCTION)

# Substring matching (default)
symbols = tools.find_symbol("auth")  # matches "authenticate", "authorizer", etc.

# Exact match
symbols = tools.find_symbol("User", substring_matching=False)
```

### Find References

Find where symbols are used:

```python
# All references in workspace
refs = tools.find_references("User")

# References in specific file
refs = tools.find_references("User", file_path="src/models/user.py")
```

### Get File Overview

List all symbols in a file:

```python
overview = tools.get_symbols_overview("src/main.py")
print(overview["overview"])  # Human-readable symbol list
```

### Find Importers

Find files importing a module:

```python
# Find all files importing "pandas"
importers = tools.find_importers("pandas")

# Find files importing local module
importers = tools.find_importers("src.models")
```

## Symbol Objects

Symbol results contain location and metadata:

```python
for symbol in symbols:
    print(f"Name: {symbol.name}")
    print(f"Kind: {symbol.kind}")  # CLASS, FUNCTION, VARIABLE
    print(f"File: {symbol.location.uri}")
    print(f"Line: {symbol.location.range['start']['line'] + 1}")
```

## MemorySystem - Persist Knowledge

Store and retrieve code insights:

```python
# Store memory about a symbol
memory.write_memory(
    title="User class dependencies",
    content="User class depends on Profile, Role, Permission",
    symbol_name="User",
    file_path="src/models/user.py",
    tags=["class", "dependencies"]
)

# Retrieve memories
memories = memory.read_memories(symbol_name="User")
for entry in memories:
    print(f"{entry.title}: {entry.content}")

# Search memories
memories = memory.search_memories("authentication")
```

## SecurityScanner - Analyze Patterns

```python
from knowledge.analysis.serena import SecurityScanner

scanner = SecurityScanner(workspace_root=workspace)

# Scan for security issues
issues = scanner.scan_file("src/auth.py")
for issue in issues:
    print(f"{issue.severity}: {issue.description}")
```

## Common Workflows

### Understand Class Hierarchy

```python
# Find base class
base_classes = tools.find_symbol("BaseModel")

# Find all subclasses through reference analysis
subclasses = set()
for base in base_classes:
    # Find all classes that reference the base class
    refs = tools.find_references(base.name)
    for ref in refs:
        if ref.kind == SymbolKind.CLASS:
            subclasses.add(ref.name)

# Find methods in hierarchy
all_methods = []
for cls in base_classes:
    methods = tools.find_symbol(cls.name, kind=SymbolKind.FUNCTION)
    all_methods.extend(methods)
```

### Track Symbol Usage

```python
# Find all usages of a function
func_refs = tools.find_references("process_data")

# Store usage pattern in memory
memory.write_memory(
    title="process_data usage pattern",
    content=f"Called in {len(func_refs)} places, mostly in data_pipeline/",
    symbol_name="process_data"
)
```

### Refactor Guidance

```python
# Find all instances before refactoring
old_symbols = tools.find_symbol("old_name")

# After refactoring, verify no old references remain
refs = tools.find_references("old_name")
if refs:
    print(f"Warning: {len(refs)} remaining references to old_name")
```

## Integration with CKS/CHS

Serena integrates with Constitutional Knowledge System for persistence:

```python
from knowledge.systems.cks.unified import CKS

# Initialize CKS
cks = CKS()

# Store analysis results
cks.ingest_memory(
    title="Codebase analysis summary",
    content="SymbolTools found 450 classes, 1200 functions"
)

# Store usage patterns
cks.ingest_pattern(
    title="Symbol discovery pattern",
    pattern_content="Use find_symbol() with kind filters for targeted searches"
)

# Search stored insights later
results = cks.search("symbol hierarchy")
```

## When to Use

- **Semantic search needed**: When grep/ast aren't enough
- **Symbol relationships**: Finding dependencies, inheritance, usage
- **Code navigation**: Understanding structure and connections
- **Knowledge persistence**: Storing insights about codebase
- **Security analysis**: Scanning for patterns and vulnerabilities

## Notes

- Serena uses AST parsing for Python (more accurate than grep)
- Symbol results include file paths and line numbers
- MemorySystem persists to `.serena/memories/` in workspace
- CDS backend integration available for import tracking (optional)
- Thread-safe for concurrent access

## See Also

- `__csf/src/knowledge/analysis/serena/` - Implementation
- SymbolTools source: `tools/find.py`
- MemorySystem source: `memory/memory_system.py`
- SecurityScanner source: `tools/security.py`
