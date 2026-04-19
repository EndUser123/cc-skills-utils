# Search Integration Reference

## Search Integration Overview

When `/task list` is invoked (without `--no-suggest`), the skill performs contextual search to surface relevant tasks and unresolved items.

### Terminal Context Building

Terminal context factors:
- Current working directory (e.g., `P:\__csf\src\daemons` -> "semantic daemon work")
- Git branch name (e.g., `feature/safety-hooks` -> "safety hooks implementation")
- Recent file edits (last 5 modified files indicate active work)
- Pending task subjects (indicate ongoing themes)

**Example search query for terminal context:**
```
"terminal tasks pending semantic daemon safety hooks implementation patterns"
```

**Example terminal context build:**
```python
# Pseudo-code for terminal context extraction
cwd_parts = Path.cwd().parts  # ("P:", "__csf", "src", "daemons")
context_keywords = " ".join(cwd_parts[-2:])  # "src daemons"
git_branch = get_git_branch()  # "main"
pending_themes = " ".join([t.subject for t in pending_tasks[:3]])  # "intent classification fail-fast"

query = f"{context_keywords} {git_branch} {pending_themes} tasks patterns"
# Result: "src daemons main intent classification fail-fast tasks patterns"
```

### Search Execution Flow

1. **Gets current terminal_id** from terminal_detection.py
2. **Filters tasks** by terminal_id (unless `--all` flag specified)
3. **Builds terminal context query** from:
   - Current working directory path
   - Git branch name
   - Recent file edits
   - Pending task subjects

4. **Executes CKS/CHS search** for terminal context:
   ```
   "{terminal_context} tasks pending patterns implementation"
   ```

5. **Executes CHS search** for unresolved items:
   ```
   "{terminal_id} problem issue bug error FIXME TODO stuck blocked friction workaround"
   ```

6. **Filters unresolved results** by:
   - Exclude results containing "fixed/resolved/completed/implemented"
   - Check for resolution confirmation in same session
   - Limit to 10 results max

7. **Formats suggestions** as:
   ```
   [SOURCE score] Type: "Title" - Content snippet
   ```

8. **Formats unresolved items** with quick-add prompt:
   ```
   [CHS date] "Content snippet"
     -> /task add "Suggested task title"
   ```

### CHS Unresolved Detection Keywords

| Category | Keywords |
|----------|----------|
| Problems | "problem", "issue", "bug", "error", "broken" |
| Blocked | "stuck", "blocked", "blocked by", "can't" |
| Frictions | "slow", "clunky", "awkward", "workaround", "hack" |
| Action items | "TODO", "FIXME", "should", "need to" |
| Unresolved | "not working", "doesn't work", "failed" |

### Quick-Add Prompt Generation

```python
# Generate task title from CHS result
content = "Daemon crashes when concurrent requests exceed 4"
# Extract key phrases and convert to action-oriented task title
title = f"Fix {content.lower()}"
# Result: "Fix daemon crash on concurrent requests"
```
