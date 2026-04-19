# Subagent Delegation Patterns

## When to Delegate

Use subagents when:
- Query spans multiple independent sources (parallel research)
- Analysis requires deep exploration (would consume your context)
- Synthesis needed across multiple result sets
- Cross-referencing between different backends

## Delegation Pattern

```python
# Single subagent for deep exploration
Task(
    subagent_type="general-purpose",
    prompt="Search CKS for 'async patterns' and analyze the top 10 results for common themes",
    description="Analyze async patterns in CKS"
)

# Parallel subagents for independent sources
Task(subagent_type="general-purpose", prompt="Search CHS for conversations about 'async'", description="Search chat history")
Task(subagent_type="general-purpose", prompt="Search CKS for patterns about 'async'", description="Search knowledge base")
Task(subagent_type="general-purpose", prompt="Grep code for 'async def' patterns", description="Search source code")
# Then synthesize all results yourself

# Specialized subagent for synthesis
Task(
    subagent_type="general-purpose",
    prompt="Synthesize these search results into a coherent summary with citations",
    description="Synthesize multi-source results"
)
```

## Benefits

- **Context preservation**: Your memory stays clean
- **Parallel execution**: Multiple subagents run simultaneously
- **Focused scope**: Each subagent has clear task boundaries
- **Editorial control**: You stay in charge of synthesis

## Example Workflow

```
User: /search "compare async approaches across codebase, docs, and conversations"

You: Delegating to parallel subagents...

-> Task 1: Search Code/Grep for "async def" patterns
-> Task 2: Search CKS for async knowledge entries
-> Task 3: Search CHS for async discussions
-> Task 4: Search DOCS for async documentation

[All run in parallel, results return to you]

You: Synthesizing results from 4 sources...
[Provide consolidated summary]
```
