# CHS Usage Examples

## Find and Summarize Debugging Session

```bash
/chs "CSRF error" --mode debug-postmortem
```

## Track Changes Over Time

```bash
/chs "authentication" --mode changelog --since "30 days ago"
```

## Find All Edit Usage on a File

```bash
/chs --tool Edit --file "config/api.php" --since "7 days ago"
```

## Search Across Related Workspaces

```bash
/chs "deployment" --workspace-alias frontend
```

## Generate Onboarding Docs

```bash
/chs "project architecture" --mode onboarding --output docs/onboarding.md
```

## View Context Around Match

```bash
/chs show abc123 --context 10
```

## Session Statistics

```bash
/chs stats --workspace tiny-vacation --since "30 days ago"
```

## Summarization Mode Examples

```bash
/chs "authentication" --mode documentation
/chs "session-abc123" --mode short-memory
/chs "migration" --mode changelog
/chs "error handling" --mode debug-postmortem
/chs "project-architecture" --mode onboarding
```

## Two-Stage Search Examples

```bash
/chs "authentication" --stage 1  # Fast index search
/chs "authentication" --stage 2  # Deep content scan
/chs "authentication" --stage auto  # Auto-select (default)
```

## Tool-Based Filtering Examples

```bash
# Find all Edit tool usage on a file
/chs --tool Edit --file "config/api.php"

# Find Task tool usage in last 7 days
/chs --tool Task --since "7 days ago"

# Find Bash tool usage with keyword
/chs "npm" --tool Bash --limit 50
```

## Branch-Based Filtering Examples

```bash
/chs "deploy" --branch "main"
/chs "feature" --branch "feature/story-6.5"
/chs "bugfix" --branch "fix/auth-error"
```
