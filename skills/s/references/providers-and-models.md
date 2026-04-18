# Providers and Models Reference

## Local-Only Mode

`--local-only` skips external LLM providers entirely and uses only local agents with prompt variations. Useful for:
- Faster brainstorming without external API calls
- Privacy-sensitive topics
- Testing without API quota usage

## External LLM Providers

### T1 - Primary (Recommended)
- **openai/gpt**: GPT-4o, GPT-4 Turbo - Strong performance across most tasks

### T3 - Experimental
- **groq**: Fast inference with various open models (Llama, Mixtral, etc.)
- **chutes**: Enterprise models (Qwen, DeepSeek, Kimi) with TEE security
- **openrouter**: Free tier models (Gemma, Hermes, DeepSeek)
- **mistral**: Mistral Large/Medium/Small - Various quality tiers

### CLI - Local Tools
- **qwen-cli**: Qwen 3.5 Plus (coder-model) - Efficient hybrid model with leading coding performance, 1M token context window, multimodal (text/image/video)
- **gemini-cli**: Auto mode (Gemini 3) - CLI selects best model for task: gemini-3.1-pro, gemini-3-flash, 1M token context window
- **vibe**: Devstral 2 - Python-focused model, 200K token context window
- **opencode**: Multi-provider meta-tool - Aggregates models from chutes (TEE-secured), groq (fast), and huggingface (open). Key models: Kimi K2.5 (256K context), MiniMax M2.1 TEE (SOTA coding 74% SWE-bench), DeepSeek V3, Qwen Coder 480B. Requires CHUTES_API_KEY

## API Host vs Model Creator

When viewing `/s list` output, the **API Host** column shows the provider hosting the model's API (openrouter, chutes, groq), which tells you which API key to use. This is distinct from the model creator (Google, DeepSeek, Meta, etc.):

- **API Host** = Where to access the model (which API provider holds your API key)
  - `openrouter` -> Use OPENROUTER_API_KEY
  - `chutes` -> Use CHUTES_API_KEY
  - `groq` -> Use GROQ_API_KEY

- **Model Creator** = Company that created the model (Google, DeepSeek, Meta, etc.)
  - Example: `gemini-2.5-flash` is created by Google, hosted via chutes
  - Example: `deepseek-chat` is created by DeepSeek, hosted via openrouter

This distinction matters because:
1. The same model can be available from multiple API hosts
2. You need the API key for the host, not the creator
3. Pricing and rate limits are determined by the API host

## `/s list` Output Format

The `/s list` command displays available models organized by category (top 6 per category):

```text
REASONING (Top 6)
+----------------------------------+--------------------+---------+---------+
| Model                            | API Host           | Cost    | Score   |
|----------------------------------|--------------------|---------|---------|
| gemini-2.5-flash-exp             | chutes             | FREE    | 108.5   |
| gemini-2.0-flash-exp-thinking    | chutes             | FREE    | 105.2   |
| deepseek-r1                      | openrouter         | FREE    | 104.8   |
| gemini-2.0-flash-thinking-exp    | chutes             | FREE    | 103.1   |
| qwen-2.5-coder-32b-instruct      | chutes             | FREE    | 101.5   |
| deepseek-chat                    | openrouter         | FREE    | 99.2    |
+----------------------------------+--------------------+---------+---------+

CODING (Top 6)
+----------------------------------+--------------------+---------+---------+
| Model                            | API Host           | Cost    | Score   |
|----------------------------------|--------------------|---------|---------|
| qwen-2.5-coder-32b-instruct      | chutes             | FREE    | 89.3    |
| deepseek-coder-v3                | openrouter         | FREE    | 87.1    |
| gemini-2.5-flash-exp             | chutes             | FREE    | 85.6    |
| qwen-coder-2.5                   | chutes             | FREE    | 82.4    |
| llama-3.3-70b-instruct           | groq               | FREE    | 79.8    |
| mixtral-8x7b-instruct-v0.1       | openrouter         | FREE    | 77.2    |
+----------------------------------+--------------------+---------+---------+

GENERAL (Top 6)
+----------------------------------+--------------------+---------+---------+
| Model                            | API Host           | Cost    | Score   |
|----------------------------------|--------------------|---------|---------|
| gemini-2.5-flash-exp             | chutes             | FREE    | 95.4    |
| gemini-2.0-flash-exp             | chutes             | FREE    | 93.1    |
| llama-3.1-8b-instruct            | groq               | FREE    | 88.7    |
| mistral-nemo-instruct-2407       | openrouter         | FREE    | 85.2    |
| phi-3-medium-128k-instruct       | openrouter         | FREE    | 82.9    |
| gemma-2-27b-it                   | openrouter         | FREE    | 80.5    |
+----------------------------------+--------------------+---------+---------+

CLI - Local Tools
+----------------------------------+--------------+-------------------------------+
| Tool                             | Cost         | Notes                         |
|----------------------------------|--------------|-------------------------------|
| qwen-cli                         | FREE         | Qwen 3.5 Plus (1M context)   |
| gemini-cli                       | FREE         | Gemini 3 Auto (1M context)   |
| vibe                             | FREE         | Devstral 2 (200K context)    |
| opencode                         | Variable     | Multi-provider meta-tool      |
+----------------------------------+--------------+-------------------------------+
```

**Notes:**
- **API Host** shows which API provider hosts the model (use the corresponding API key)
- **Cost** shows FREE models (subscription-based, $0, or free tier) - paid providers like anthropic/claude are excluded
- **Score** shows the model's performance ranking in that category
- **(needs key)** indicator appears when the API host has no configured API key
- Use `/s list --refresh` to update the cache from provider APIs

## Provider Data Source Truth

Provider classification (FREE vs PAID) is grounded in `P:\__csf\src\llm\providers\utils\model_enumerator.py`, where each provider's `enumerate_*_models()` function returns `ModelInfo` objects with an `is_free` boolean flag.

**Source of truth hierarchy:**
1. **Primary**: `model_enumerator.py` - Each provider's enumerator function sets `is_free=True/False`
2. **Secondary**: Provider documentation and actual API behavior (free tier vs paid service)
3. **Audit**: `P:\.claude\skills\s\tests\provider_audit.md` - Manual verification of all 10 providers in FREE_PROVIDERS

**Verification process:**
- Run regression tests: `pytest P:/.claude/skills/s/tests/test_provider_classification.py -v`
- Review provider audit document for classification discrepancies
- For provider pricing questions, check `model_enumerator.py` line numbers referenced in audit

**Updating provider classifications:**
1. Verify actual provider pricing model (free tier, subscription-based, or paid API)
2. Update `enumerate_*_models()` function in `model_enumerator.py` with correct `is_free` flag
3. Run regression tests to verify changes: `pytest P:/.claude/skills/s/tests/test_provider_classification.py -v`
4. Update provider audit document with findings

**Known discrepancies (from audit):**
- **qwen**: z.ai API is paid, but qwen-cli is free (local). Currently classified as free for CLI usage.
- **deepseek, meta-llama, mistralai**: No dedicated enumerators (hosted via other providers like openrouter/chutes).
- **mistral**: Potential duplicate with "mistralai" - may need consolidation.

See `provider_audit.md` for complete analysis of all 10 providers in FREE_PROVIDERS set.
