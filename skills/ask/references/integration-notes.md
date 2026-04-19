# Integration Notes

Session context, command registry, workflow integration, error handling, and ambiguous request handling.

## Error Handling

```
IF routing fails:
    -> Display available commands with brief descriptions
    -> Suggest based on partial matches
    -> Offer: "Tell me more about what you're trying to accomplish"

IF target command unavailable:
    -> Report specific issue
    -> Suggest alternative commands
    -> Do not fabricate capabilities
```

## Ambiguous Request Handling

```
IF multiple commands match equally:
    -> Present top 2-3 options with brief rationale
    -> Ask user to confirm intended direction
    -> "This could be handled by /design (for design decisions) or /analyze (for quality). Which fits better?"

IF no command matches:
    -> Offer to decompose the request
    -> Suggest most likely category
    -> "Tell me more about what you're trying to accomplish"
```

## Session Context

- Auto-creates session for multi-step workflows
- Tracks routing decisions for pattern analysis
- Preserves context across command handoffs

## Command Registry

- All commands registered in `skill_registry`
- Auto-discovery via `skill_registry` loading
- Metadata includes: aliases, category, handles, description

## Workflow Integration

- Detects work from: `/research`, `/discover`, `/analyze`
- Can continue to: `/cwo`, `/exec`, `/breakdown`
- Prevents redundant work via context inheritance

## Truth Audit

- Automatic claim blocking when enabled
- Evidence validation before routing execution commands
- Constitutional compliance checking
