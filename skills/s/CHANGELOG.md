# Changelog

All notable changes to the /s skill will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.7.1] - 2026-03-16

### Security
- **P0-3**: Added input sanitization to prevent prompt injection attacks
  - Sanitizes user prompts (50,000 char limit) before sending to LLMs
  - Removes dangerous patterns (e.g., "ignore previous instructions")
- **P0-2**: Added path traversal validation for `--context-path` argument
  - Validates all paths against project root
  - Blocks `../` attacks and directory traversal attempts
- **P0-6**: Implemented exponential backoff retry logic for rate limiting
  - 1s → 2s → 4s → 8s backoff strategy
  - Empty response validation to avoid timeout
  - Transient error detection (429, timeout, connection errors)

### Added
- **P0-4**: Created `lib/utils/log_rotation.py` utility for API response log management
  - 10MB size threshold with automatic rotation
  - Gzip compression (~90% space savings)
  - Keeps 5 most recent rotated logs
  - Functions: `rotate_log_file()`, `append_log_entry()`, `ensure_log_rotation()`
- **P0-5**: Added integration test file `tests/test_integration_3phase_workflow.py`
  - Tests 3-phase workflow (Diverge → Discuss → Converge)
  - Phase timeout enforcement
  - Result ranking and filtering
- Created `tests/test_log_rotation.py` with 4 passing tests

### Fixed
- CLI provider timeout now configurable (was hardcoded 30s, default 300s)
- Fixed `lib/agents/base.py` fallback timeout configuration

### Changed
- **P0-1**: Async file I/O using `asyncio.to_thread()` (already implemented)
- **P1-1**: Directory scan caching with 5-minute TTL (already implemented)
- Updated SKILL.md with new Security section documenting all features

### Deferred
- **P1-2**: Phase timeout reduction - percentage-based provides better user control

### Known Issues
- Integration test requires LLM providers module fix (CLI timeout issue)
  - Located in `P:\__csf\src\llm\providers\cli_providers.py`
  - Outside /s skill scope

## [2.7.0] - 2026-03-14

### Changed
- Reduced SKILL.md from 688 to 350 lines for improved scanability
- Added `id` field to frontmatter
- Added `output_template` reference (Template 1 - Strict Analysis Format)
- Added `extends:` PART references (PART C, PART P)
- Applied progressive disclosure (moved advanced features to references/)
