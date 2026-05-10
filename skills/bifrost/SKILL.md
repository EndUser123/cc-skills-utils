---
name: bifrost
version: "1.0.0"
status: "stable"
category: infrastructure
enforcement: advisory
allowed_first_tools:
  - Bash
description: Query and filter Bifrost governance model database with provider taxonomy, UMU schema, and cost-aware filtering.
triggers:
  - /bifrost
  - /bifrost-models
---

# /bifrost — Bifrost Governance Model Query

Query the Bifrost governance SQLite database with structured filtering and provider taxonomy.

## ⚡ EXECUTION DIRECTIVE

**When /bifrost is invoked, execute the filter script with the provided arguments:**

```bash
python P:\\\\\\packages/cc-skills-utils/skills/bifrost/scripts/filter_models.py [args]
```

**Common invocations:**

```bash
# Default: free-key + subscription chat models >= 128k (cost ignored for known providers)
python P:\\\\\\packages/cc-skills-utils/skills/bifrost/scripts/filter_models.py

# List all providers
python P:\\\\\\packages/cc-skills-utils/skills/bifrost/scripts/filter_models.py --list-providers

# OpenRouter free models only
python P:\\\\\\packages/cc-skills-utils/skills/bifrost/scripts/filter_models.py --provider openrouter --free-only

# Embedding models
python P:\\\\\\packages/cc-skills-utils/skills/bifrost/scripts/filter_models.py --mode embed
```

## DB Location
`C:\Users\brsth\AppData\Roaming\bifrost\config.db`
Table: `governance_model_parameters`

## Schema (5-field UMU)

Each row has these extracted fields in `data` JSON:
- `bifrost_provider` — Bifrost configured provider (MiniMax, Nvidia, Cerebras, Groq, Mistral, OpenRouter, z.ai, etc.)
- `host` — API provider/brand (openrouter, cerebras, nvidia, etc.)
- `vendor` — Model creator (openai, anthropic, meta, deepseek, etc.)
- `model_slug` — Immutable model identifier
- `base_model` — Original model string
- `mode` — chat, embed, safety, video, translate, parse
- `max_input_tokens` — Context window size
- `input_cost_per_token`, `output_cost_per_token` — USD per token
- `source` — Data source attribution

## Provider Taxonomy

### Free-Key Providers
All chat models >= 128k context qualify (cost column ignored — our API keys cover these):
- **nvidia** — cost=0 for all models (NIM subscription)
- **cerebras** — API key covers access (DB lists $0.35-1.20/M but key is free)
- **groq** — API key covers access (DB lists $0.07-0.60/M but key is free)
- **mistral** — API key covers access (DB lists $0.10-2.00/M but key is free)

### Subscription Providers
Effectively free via subscription (cost filter ignored):
- **minimax** — MiniMax subscription
- **z.ai** — Z.AI subscription (zai in DB)

### OpenRouter
Cost-aware filtering required:
- **openrouter** — Has both free and paid models
- Free tier: `input_cost_per_token = 0 AND output_cost_per_token = 0`
- Excluded vendors (have their own subscriptions): moonshotai, minimax, z.ai, bytedance

### Other Providers (cost-based filtering)
Standard cost filtering applies:
- azure, openai, bedrock, vertex_ai, fireworks_ai, together_ai, deepinfra, etc.

## Usage

### Default: Free/Subscription chat models >= 128k context
```bash
python P:\\\\\\packages/cc-skills-utils/skills/bifrost/scripts/filter_models.py
```

### Filter by criteria
```bash
python P:\\\\\\packages/cc-skills-utils/skills/bifrost/scripts/filter_models.py \
  --mode chat --min-context 131072 --free-above-subscription
```

### List all providers
```bash
python P:\\\\\\packages/cc-skills-utils/skills/bifrost/scripts/filter_models.py --list-providers
```

### Provider-specific query
```bash
python P:\\\\\\packages/cc-skills-utils/skills/bifrost/scripts/filter_models.py \
  --provider nvidia --mode chat --min-context 131072
```

### OpenRouter free only
```bash
python P:\\\\\\packages/cc-skills-utils/skills/bifrost/scripts/filter_models.py \
  --provider openrouter --mode chat --min-context 131072 --free-only \
  --exclude-vendors moonshotai,minimax,z.ai,bytedance
```

### All modes, no cost filter (inventory)
```bash
python P:\\\\\\packages/cc-skills-utils/skills/bifrost/scripts/filter_models.py --list-all
```

## Arguments

| Arg | Description | Default |
|-----|-------------|---------|
| `--mode` | Filter by mode (chat, embed, safety, video, translate, parse) | chat |
| `--min-context` | Minimum context window | 131072 |
| `--free-above-subscription` | Apply free/subscription rules (ignores cost for known subscription providers) | true |
| `--provider` | Filter to specific bifrost_provider | all |
| `--vendor` | Filter to specific vendor | all |
| `--free-only` | Only models with cost = 0 | false |
| `--exclude-vendors` | Comma-separated vendor exclusion list | moonshotai,minimax,z.ai,bytedance |
| `--list-providers` | Show all providers and model counts | false |
| `--list-all` | Show all models, no cost filter | false |
| `--format` | Output format: table, json, count | table |

## Examples

**"What free chat models >= 128k do I have access to?"**
```bash
python P:\\\\\\packages/cc-skills-utils/skills/bifrost/scripts/filter_models.py
```

**"Show me all embedding models"**
```bash
python P:\\\\\\packages/cc-skills-utils/skills/bifrost/scripts/filter_models.py --mode embed
```

**"What's available from Nvidia?"**
```bash
python P:\\\\\\packages/cc-skills-utils/skills/bifrost/scripts/filter_models.py --provider nvidia
```

**"Show me only the free OpenRouter models"**
```bash
python P:\\\\\\packages/cc-skills-utils/skills/bifrost/scripts/filter_models.py \
  --provider openrouter --free-only --min-context 131072
```

## Architecture

```
governance_model_parameters
├── id (INTEGER PRIMARY KEY)
├── model (TEXT) — Full model string
└── data (TEXT) — JSON blob with UMU fields
```

UMU format: `{host}://{vendor}/{model_slug}`

Example: `nvidia://meta/llama-3.3-70b-instruct`
