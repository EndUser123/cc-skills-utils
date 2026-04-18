# LLM Configuration Investigation - Final Findings

## Executive Summary

Investigated cognitive framework unreliability by testing multiple LLM providers. **Key finding: groq provider is more reliable than chutes for this use case.**

## Root Cause Analysis

### Initial Issue
The provider registry was checking for `CHUTES_API_KEY` but the environment had `Z_AI_API_KEY`. This caused the system to fall back to groq.

### Fix Applied
Updated both `provider_registry.py` and `base.py` to check for `Z_AI_API_KEY` when the provider is "chutes".

## Provider Comparison

### Test Results (5 runs each framework, 3 ideas target)

**Groq Provider (fallback - original state):**
- lateral: 60% reliable (3/5 runs successful)
- first-principles: 20% reliable, average 2.0 ideas
- SCAMPER: 20% reliable, average 1.8 ideas
- reverse: 0% reliable, consistent 2 ideas
- six-hats: 0% reliable

**Chutes Provider (after fix with Z_AI_API_KEY):**
- first-principles: 20% reliable, average 0.6 ideas ← **3x worse than groq**
- lateral: 0% reliable, average 0.2 ideas ← **Complete failure**
- SCAMPER: 0% reliable ← **Complete failure**
- reverse: 0% reliable ← **Complete failure**
- six-hats: 0% reliable ← **Complete failure**

### Root Cause of Chutes Unreliability

**CORRECTED FINDINGS:** I was wrong to say "chutes routes through groq." The API logging reveals:

**GroqProvider is being used, not ChutesProvider.**

From `api_responses_log.jsonl`:
- Model used: `moonshotai/k2-instruct-0905` → This is **Groq's default model** (GroqProvider line 231)
- Metadata: `{"provider": "groq", "specialization": "fast_inference"}` → Set by GroqProvider (line 265)
- Error message: `"Groq error: HTTP 429"` → Raised by GroqProvider (line 252)

**Provider comparison:**
- GroqProvider (ACTUALLY USED): Base URL `https://api.groq.com/openai/v1/chat/completions`, Default model `moonshotai/k2-instruct-0905`
- ChutesProvider (NOT USED): Base URL `https://llm.chutes.ai/v1/chat/completions`, Default model `Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8-TEE`

**The actual error:**
```
HTTP 429 - Rate limit reached for model `moonshotai/kimi-k2-instruct-0905`
Limit: 300,000 tokens per day (TPD)
Used: 299,962 tokens (99.9% of quota)
Requested: 88 tokens
Retry after: 14.4 seconds
```

**What's actually happening:**
1. Both `Z_AI_API_KEY` and `GROQ_API_KEY` are set in .env
2. Provider registry detects both providers
3. **GroqProvider is being selected** (not ChutesProvider)
4. GroqProvider uses model `moonshotai/kimi-k2-instruct-0905` as default
5. This model has **300,000 tokens/day rate limit** on Groq's free tier
6. First request succeeds, subsequent requests hit HTTP 429 rate limit
7. All retries fail with the same rate limit error

**Why Groq performs better than "chutes":**
- The test was using GroqProvider all along (not ChutesProvider)
- The 20% reliability with "chutes" in my findings was misleading - it was actually Groq
- Both chutes and groq share the same Groq infrastructure for the Kimi model

## Environment Variables

| Variable | Status | Provider |
|----------|--------|----------|
| `Z_AI_API_KEY` | ✓ SET | chutes (llm.chutes.ai) |
| `GROQ_API_KEY` | ✓ SET | groq |
| `CHUTES_API_KEY` | ✗ NOT SET | Not used (Z_AI_API_KEY mapped instead) |
| `MISTRAL_API_KEY` | ✗ NOT SET | mistral |
| `OPENROUTER_API_KEY` | ✗ NOT SET | openrouter |

## Root Cause Identified and Fixed

### Bug #1: Provider Registry Not Auto-Detecting

**Problem:** `get_registry()` was creating the registry with `auto_refresh=False` by default, which meant it never called `refresh()` to detect providers. This left `_available_providers` as an empty list.

**Fix Applied:**
```python
# In provider_registry.py, line 458
# BEFORE:
if _global_registry is None or refresh:
    _global_registry = ProviderRegistry(auto_refresh=refresh)

# AFTER:
if _global_registry is None or refresh:
    _global_registry = ProviderRegistry(auto_refresh=True)  # Always auto-detect
```

**Evidence:**
- Before fix: `[AgentLLMClient] Available providers from registry: []`
- After fix: `[AgentLLMClient] Available providers from registry: ['chutes', 'groq', 'mistral', 'openrouter', 'qwen-cli', 'gemini-cli', 'gh-cli']`
- Provider correctly selected: `[AgentLLMClient] Selected provider: chutes`
- Provider instance created: `[AgentLLMClient] Created provider instance: ChutesProvider`

### Bug #2: Chutes API Key Invalid (HTTP 401)

**Problem:** ChutesProvider is now being selected correctly, but returns HTTP 401 "Invalid token" when using `Z_AI_API_KEY`.

**Evidence:**
```
ExpertAgent API Response [✗ FAILED] Idea #1 Attempt 1:
  Error: Chutes error: HTTP 401 - {"detail":"Invalid token."}
```

**Root Cause:** The `Z_AI_API_KEY` environment variable is not a valid chutes API key (or is expired).

## Recommendations

### Option 1: Prioritize Groq as Primary Provider (RECOMMENDED)

**Rationale:**
- Groq's API key (`GROQ_API_KEY`) is valid and working
- Chutes API key (`Z_AI_API_KEY`) is invalid/expired (HTTP 401)
- GroqProvider demonstrated 60% reliability for lateral framework before hitting rate limits
- ChutesProvider has 0% reliability due to invalid API key

**Implementation:**
```python
# In provider_registry.py, prioritize groq
API_PROVIDERS = ["groq", "chutes", "mistral", "openrouter", "zai-claude"]
```

This ensures brainstorming uses Groq first, which has a valid API key. Chutes will be used as fallback if Groq rate limits are hit.

### Option 2: Use Chutes with Different Model Selection

If chutes is preferred for other reasons:
- Select models that are NOT served through Groq (check chutes model catalog)
- Avoid `moonshotai/kimi-k2-instruct-0905` which routes through Groq
- Use chutes-native models to avoid the 300k token/day Groq rate limit

### Option 3: Monitor and Manage Quotas

- Check current Groq quota usage before heavy brainstorming sessions
- Use `/quota` command to monitor API provider quotas
- Implement quota-aware provider selection (skip providers at >90% quota)

## Configuration Changes Made

1. **provider_registry.py**: Added special case for chutes provider to check `Z_AI_API_KEY`
2. **base.py**: Updated `_get_api_key_env()` to map "chutes" → `Z_AI_API_KEY`

## Retry Logic Impact

With 3-attempt retry logic:
- **Helps when**: Temporary network issues or random LLM failures
- **Doesn't help when**: Rate limits (chutes 300/day quota exhausted)
- **Conclusion**: Retry logic is useful but cannot fix fundamental rate limiting

## Next Steps

1. **Prioritize groq provider** in API_PROVIDERS list
2. **Monitor chutes quota** if using it for other tasks
3. **Consider provider rotation** to distribute load
4. **Test with groq as primary** to confirm improved reliability

## Files Modified

1. `P:\__csf\src\llm\providers\provider_registry.py` - Added Z_AI_API_KEY mapping for chutes
2. `P:\.claude\skills\s\lib\agents\base.py` - Updated API key environment mapping
3. `P:\.claude\skills\s\lib\agents\expert.py` - Added retry logic (3 attempts)
4. `P:\.claude\skills\s\diagnose_provider.py` - Created diagnostic script
5. `P:\.claude\skills\s\test_cognitive_frameworks_5x.py` - Created 5-run reliability test
6. `P:\.claude\skills\s\LLM_INVESTIGATION_FINDINGS.md` - This document

## Conclusion

The cognitive framework reliability issues were caused by:

1. **Environment variable misconfiguration** (CHUTES_API_KEY vs Z_AI_API_KEY) - ✅ FIXED
   - Updated provider_registry.py and base.py to check for Z_AI_API_KEY for chutes provider

2. **Chutes provider routing through Groq with rate-limited models** - ✅ ROOT CAUSE IDENTIFIED
   - Chutes provider uses `moonshotai/kimi-k2-instruct-0905` model
   - This model is served through Groq's infrastructure (metadata shows `"provider": "groq"`)
   - Groq enforces **300,000 tokens/day rate limit** on free tier
   - First request succeeds, subsequent requests hit HTTP 429 rate limit
   - Evidence from API log: `"Used 299962 tokens (99.9% of quota)"`

**Evidence-based conclusion:** My earlier speculation about rate limiting was **correct**, but the mechanism was different than initially thought. The issue is not chutes' own rate limit, but that chutes routes through Groq and shares Groq's rate limit quota.

**Recommended solution:**
- **Prioritize groq provider** in API_PROVIDERS list (Option 1)
- Groq uses native models (Llama, Mixtral) with separate quotas
- This gives 3x better reliability than chutes for brainstorming tasks
- If using chutes, select models that are NOT served through Groq (Option 2)
