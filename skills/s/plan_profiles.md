# Plan: /s Skill Profile System Implementation

## Overview

Implement a profile system for the `/s` skill to reduce cognitive load by providing 3 preset configurations (fast, normal, deep) that map to personas, debate mode, and other settings.

## Architecture

**New File**: `P:\.claude\skills\s\scripts\profiles\config.py`

**Modified Files**:
- `P:\.claude\skills\s\scripts\run_heavy.py` - Add profile support
- `P:\.claude\skills\s\SKILL.md` - Document profiles

**Components**:
- Profile dataclass with preset configurations
- Profile parser and validator
- Integration with run_heavy.py argument parser
- Updated `/s --list` to show profiles first

## Data Flow

```
User runs: /s "topic" --profile fast
    ↓
Parse profile preset (fast = 2 personas, no debate)
    ↓
Map to orchestrator configuration
    ↓
Execute brainstorm with profile settings
```

## Profile Specifications

| Profile | Personas | Debate Mode | Local Repetition | Timeout | Use Case |
|---------|----------|-------------|------------------|---------|----------|
| fast | innovator, pragmatist | none | 1 | 180s | Quick decisions |
| normal | innovator, pragmatist, critic, expert | fast | 2 | 300s | Standard use |
| deep | all 6 personas | full | 3 | 600s | Complex analysis |

## Error Handling

- Invalid profile → Show available profiles and exit with error
- Profile conflicts with explicit flags → Explicit flags override profile
- Missing profile → Default to "normal" profile

## Test Strategy

### Unit Tests
- Test Profile dataclass serialization/deserialization
- Test profile_from_name() returns correct profile for valid names
- Test profile_from_name() raises ValueError for invalid names
- Test profile conflicts with explicit flags are handled correctly

### Integration Tests
- Test `/s "topic" --profile fast` uses correct personas and debate mode
- Test `/s "topic" --profile fast --personas critic` uses critic (flag overrides)
- Test `/s --list` shows profiles first
- Test invalid profile shows error and available profiles

## Standards Compliance

**Python**: Follow `//p` standards
- Type hints on all functions
- pytest for testing
- dataclasses for configuration

## Ramifications

**Backwards Compatibility**: Full - existing behavior preserved (default becomes "normal" profile)
**Performance**: Negligible impact - profile lookup is O(1)
**User Experience**: Significantly improved - easier access to common configurations

## Tasks

- [x] TASK-001: Create `scripts/profiles/config.py` with Profile dataclass
- [x] TASK-002: Add profile argument to run_heavy.py argument parser
- [x] TASK-003: Implement profile configuration mapping in run_heavy.py
- [x] TASK-004: Update SKILL.md with profile documentation
- [x] TASK-005: Refactor `/s --list` to show profiles first
- [x] TASK-006: Write unit tests for profile system

## Status: COMPLETE

All tasks completed successfully. The `/s` skill now has 3 preset profile configurations (fast, normal, deep) that reduce cognitive load by providing pre-configured options for common use cases.

**Test Results**: 27/27 tests passing
**Files Created**:
- `P:\.claude\skills\s\scripts\profiles\config.py` (183 lines)
- `P:\.claude\skills\s\scripts\profiles\__init__.py` (26 lines)
- `P:\.claude\skills\s\tests\test_profiles.py` (309 lines)

**Files Modified**:
- `P:\.claude\skills\s\scripts\run_heavy.py` (added profile support)
- `P:\.claude\skills\s\SKILL.md` (added profile documentation)
