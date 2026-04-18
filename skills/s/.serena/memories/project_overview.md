# Project Overview: /s Strategic Thinking Engine

This project, named `s`, is a strategic thinking engine for AI-human hybrid workflows.

## Purpose
The `/s` skill is designed to provide exploratory multi-persona brainstorming and outcome scenario analysis. It uses a range of cognitive frameworks (SCAMPER, Lateral Thinking, Six Thinking Hats, First Principles, etc.) to generate diverse perspectives and options for any strategic topic.

## Core Components
- `lib/`: Contains the core implementation of the strategy engine.
    - `agents/`: Defines various AI personas (Innovator, Critic, Expert, Pragmatist, Synthesizer).
    - `convergence/`: Logic for ranking, filtering, and synthesizing ideas.
    - `debate/`: Adversarial debate system for stress-testing ideas.
    - `reasoning/`: Implementations of Graph-of-Thought (GoT) and Tree-of-Thought (ToT).
    - `memory/`: Memory adapters for deterministic execution.
- `scripts/`: Entry point scripts for the skill.
    - `run_heavy.py`: Main execution script for the `/s` skill.
- `tests/`: Integration and unit tests for the engine and its components.

## Development Workflow
- **Human Director**: Provides requirements, reviews work, and guides direction.
- **AI Developer**: Writes code, tests, and documentation under human oversight.
- **Quality-First**: Prioritizes thoroughness and functional verification over speed.
- **Async-First**: Uses asynchronous programming (`asyncio`) for efficiency.

## Key Features
- **Multi-persona Brainstorming**: Diverge, Discuss, and Converge phases using multiple AI personas.
- **Strategic Frameworks**: SCAMPER, Six Thinking Hats, First Principles, Lateral Thinking, etc.
- **Adversarial Debate**: Stress-tests ideas through PRO → CON → REBUTTAL rounds.
- **GoT + ToT Enhancement**: Improved reasoning through graph and tree representations of thoughts.
- **Outcome Analysis**: Decision memo with tradeoffs, risks, and next-step hints.

## Recent Improvements (v2.7.1)
- Input sanitization for prompt injection protection.
- Path traversal validation for context paths.
- Exponential backoff retry logic for LLM rate limiting.
- Gzip-compressed API response log rotation.
- Integration test for 3-phase workflow.
