# Troubleshooting

## Issue: "Agent tool unavailable" warning

**Symptom:** Layer 2 triggers but shows "CLI context, using keyword fallback"

**Cause:** Agent tool is only available in skill execution context, not subprocess mode.

**Solutions:**
1. **Normal behavior in CLI mode:** The fallback still provides keyword-based filtering. Results are still themed and organized.
2. **For full Agent tool filtering:** Use the skill through normal invocation (not subprocess testing).
3. **Verify execution context:** Check if `CLAUDE_CODE_SKILL_EXECUTION=1` is set in environment.

**Example:**
```bash
# CLI mode (uses keyword fallback)
/explore "authentication patterns" --force-context-filter
# Output: [Agent Filter] CLI context, using keyword fallback

# Skill execution mode (uses Agent tool if available)
# (invoked through Claude Code skill system)
# Output: [Agent Filter] Using Agent tool for semantic filtering
```

---

## Issue: Layer 2 not triggering

**Symptom:** Large result set (>20 items) but Layer 2 doesn't activate

**Possible Causes:**

1. **Threshold too high:**
   ```bash
   # Check current threshold
   /explore "query" --context-threshold 20  # Default is 20

   # Lower threshold to trigger more easily
   /explore "query" --context-threshold 15
   ```

2. **User override disabled:**
   ```bash
   # Check if --no-context-filter was used
   # Remove it to enable Layer 2
   /explore "query"  # Layer 2 auto-enabled
   ```

3. **Result count below threshold:**
   ```bash
   # Force Layer 2 even for small result sets
   /explore "query" --force-context-filter
   ```

**Verification:**
```bash
# Check Layer 2 trigger reason
/explore "query"
# Look for: [Layer 2] Trigger check = True (reason: result_count)
```

---

## Issue: Token overflow warning

**Symptom:** "Estimated tokens: 8500" warning in Layer 2 output

**Cause:** Large result set generates too many tokens for Agent tool prompt

**Impact:** Agent may truncate input or produce lower-quality results

**Solutions:**

1. **Reduce input size:**
   ```bash
   # Lower result limit
   /explore "query" --limit 20  # Default is 30
   ```

2. **Increase complexity to reduce insights:**
   ```bash
   # More specific query = fewer results
   /explore "specific query terms"  # Reduces result count
   ```

3. **Accept keyword fallback:**
   ```bash
   # Use keyword filtering for very large result sets
   /explore "query" --no-context-filter
   ```

**Prevention:**
- Layer 1B (semantic clustering) reduces 30-40 items → 20-25 items
- Layer 1D (adaptive limits) adjusts limit based on query complexity
- Combined effect: Usually keeps tokens under 8000

---

## Issue: Inconsistent Layer 2 behavior

**Symptom:** Layer 2 triggers sometimes but not always for similar queries

**Possible Causes:**

1. **Query complexity variance:**
   ```bash
   # Check complexity scores
   /explore "simple query"     # May not trigger
   /explore "complex query with context hints"  # More likely to trigger

   # Complexity scoring is based on:
   # - Term specificity (technical vs generic)
   # - Intent ambiguity (clear vs multiple interpretations)
   # - Expected diversity (based on term variance)
   ```

2. **Context hints detection:**
   ```bash
   # These phrases trigger Layer 2:
   "what did we discuss"
   "for the X feature"
   "we decided"

   # These don't trigger:
   "how to"
   "best practices"
   "example of"
   ```

3. **Result count variance:**
   ```bash
   # Check actual result count
   # Layer 2 triggers when: result_count > threshold (default 20)

   # View result count in output
   /explore "query"
   # Look for: [Layer 1A] → 25 results
   ```

**Solution:**
Use explicit flags for predictable behavior:
```bash
# Always enable Layer 2
/explore "query" --force-context-filter

# Always disable Layer 2
/explore "query" --no-context-filter
```

---

## Issue: Semantic clustering too aggressive

**Symptom:** Too many results removed by Layer 1B clustering

**Possible Causes:**

1. **Similarity threshold too high:**
   - Default threshold: 0.4 Jaccard similarity
   - Higher threshold = more aggressive clustering

2. **Diverse topics in results:**
   - Semantic clustering groups similar content
   - May reduce diversity if results are naturally similar

**Solutions:**

1. **Adjust clustering threshold:**
   ```python
# In skills/explore/semantic_cluster.py
   clustered = semantic_cluster.apply_semantic_clustering(
       results,
       similarity_threshold=0.3,  # Lower = less aggressive
       max_results=25
   )
   ```

2. **Increase max_results:**
   ```python
   clustered = semantic_cluster.apply_semantic_clustering(
       results,
       similarity_threshold=0.4,
       max_results=30  # Allow more results through
   )
   ```

3. **Skip clustering (not recommended):**
   ```bash
   # Clustering is Layer 1B, cannot be disabled via CLI
   # To disable, modify SKILL.md inline code
   ```

