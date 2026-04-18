# Plan: /s List Reliability Improvements

## Overview

Implement 6 priority improvements to the `/s list` command identified through pre-mortem analysis. Focus is on reliability, usability, and data freshness.

## Architecture

**Target File**: `P:\.claude\skills\s\scripts\display.py`

**Components**:
- Rich table column sizing (Provider width fix)
- Cache timestamp tracking and display
- Model ID validation layer
- Async timeout protection
- API key availability filtering
- Cache conflict detection

## Data Flow

```
User runs: /s list
    ↓
Fetch leaderboard data (7-day cache)
    ↓
Fetch provider models (12-hour cache)
    ↓
Validate model IDs exist in provider data
    ↓
Filter by available API keys
    ↓
Display with timestamps in Rich tables
```

## Error Handling

- Cache timeout failures → Show warning, display stale data with timestamp
- Model ID validation failures → Skip model with warning
- API key not configured → Show "(needs key)" indicator
- Cache conflict detected → Show conflict warning, use most recent

## Test Strategy

### Unit Tests
- Test Provider column width displays full provider names
- Test cache timestamp formatting and display
- Test model ID validation passes/fails appropriately
- Test async timeout triggers at configured limits
- Test API key filtering excludes unavailable models
- Test cache conflict detection flags mismatches

### Integration Tests
- Test full `/s list` command with fresh caches
- Test `/s list --refresh` forces cache refresh
- Test `/s list` with missing API keys shows indicators
- Test `/s list` with stale cache shows timestamp warning

## Standards Compliance

**Python**: Follow `//p` standards
- Type hints on all functions
- pytest for testing
- Rich library for terminal UI

## Ramifications

**Backwards Compatibility**: Full - existing behavior preserved, only enhancements added

**Performance**: Negligible impact - timestamp adds minimal overhead

**User Experience**: Significantly improved - clearer provider names, data freshness visible, key requirements shown
