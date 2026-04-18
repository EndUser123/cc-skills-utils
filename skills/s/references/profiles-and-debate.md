# Profiles, Debate, and Advanced Features

## Local LLM Repetition (Free Diversity Improvement)

`--local-llm-repetition N` runs the brainstorm N times with different cognitive approach variations:
- **First-principles thinking**: Challenge fundamental assumptions
- **Lateral thinking**: Consider random entry points and unexpected connections
- **SCAMPER**: Substitute, Combine, Adapt, Modify, Put to other uses, Eliminate, Reverse
- **Reverse engineering**: Start from ideal outcome and work backwards
- **Six Thinking Hats**: Facts, feelings, caution, benefits, creativity, process

This is **free** compared to external LLMs -- you get 2-3x the idea diversity without additional API costs.

## Debate Integration

`/s` supports adversarial debate mode for stress-testing ideas through multi-round analysis:

```bash
# Disable debate (default single-pass Discuss)
/s "strategy topic" --debate-mode none

# Full 3-round adversarial debate (PRO -> CON -> REBUTTAL)
/s "strategy topic" --debate-mode full

# Fast abbreviated debate
/s "strategy topic" --debate-mode fast
```

## Profile Presets

`/s` provides preset configurations to reduce cognitive load for common use cases:

| Profile | Personas | Debate Mode | Repetitions | Timeout | Use Case |
|--------|----------|-------------|------------|---------|----------|
| **fast** | innovator, pragmatist | none | 1 | 180s | Quick decisions |
| **normal** | innovator, pragmatist, critic, expert | fast | 2 | 300s | Standard use |
| **deep** | innovator, pragmatist, critic, expert, futurist, synthesizer | full | 3 | 600s | Complex analysis |

```bash
# Quick decision (2 personas, no debate, 1 repetition)
/s "quick decision" --profile fast

# Standard use (4 personas: innovator, pragmatist, critic, expert; fast debate, 2 repetitions)
/s "standard analysis" --profile normal

# Complex analysis (6 personas: innovator, pragmatist, critic, expert, futurist, synthesizer; full debate, 3 repetitions)
/s "complex tradeoffs" --profile deep
```

### Profile Override Behavior

Explicit flags always override profile defaults:

```bash
# Profile sets personas, but explicit flag overrides
/s "topic" --profile fast --personas critic,expert
# -> Uses critic,expert (not innovator,pragmatist)

# Profile sets timeout, but explicit flag overrides
/s "topic" --profile fast --timeout 900
# -> Uses 900s (not 180s)
```

## Advanced Features (Experimental)

```bash
# Enable pheromone trails for learning from previous sessions
/s "strategy topic" --enable-pheromone-trail

# Enable experience replay buffer for improved idea generation
/s "strategy topic" --enable-replay-buffer
```

## Confidence-Based Turn Taking

The `/s` skill implements confidence-based scheduling for multi-agent brainstorming sessions. Agents compute confidence scores for their contributions, and the scheduler orders turn-taking based on three available strategies:

- **PRIORITY_BASED** (default): Agents with higher confidence contribute first
- **ROUND_ROBIN**: Agents take turns in their original order (regardless of confidence)
- **WEIGHTED_RANDOM**: Random turn order weighted by confidence scores (higher confidence = more likely to speak earlier)

The scheduler also supports filtering agents below a minimum confidence threshold, ensuring only qualified agents participate.

**Implementation:** `lib/scheduler.py` - `ConfidenceScheduler`, `SchedulingStrategy`, `TurnOrder`

Experimental features require database setup and are subject to change.
