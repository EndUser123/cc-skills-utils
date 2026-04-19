---
name: sar-inst
description: SAR Implementation - CWO-compliant coordination execution
version: "1.0.0"
status: stable
category: development
triggers:
  - /sar-inst
aliases:
  - /sar-inst

suggest:
  - /sar-help
  - /build
  - /nse
---

# SAR Implementation

CWO-Compliant sub-agent coordination.

## Purpose

Execute complex tasks using coordinated sub-agent delegation following CWO workflow standards.

## Project Context

### Constitution/Constraints
- Follows CWO (Concurrent Workflow Orchestrator) 16-step unified orchestration
- Enforces TDD compliance via hooks
- Requires spec compliance before execution

### Technical Context
- Integrates with CSF NIP agent system
- Supports parallel, sequential, and adaptive execution strategies
- Uses CKS for handoff and knowledge persistence

### Architecture Alignment
- Part of CSF NIP orchestration layer
- Works alongside orchestrator, nse, and cwo skills

## Your Workflow

1. **Input Quality Gate** - Validate task description completeness
2. **CWO 7-Step Execution** - Follow concurrent workflow steps
3. **Agent Selection** - Choose appropriate CSF NIP specialists
4. **Output Validation** - Verify results against acceptance criteria

## Validation Rules

### Prohibited Actions
- Skipping spec compliance validation
- Bypassing TDD gates for implementation tasks
- Executing without clear acceptance criteria

## Variables

- task_description: Complex task (required)
- agents: Specific CSF NIP agents (optional)
- strategy: parallel, sequential, adaptive

## Workflow

1. Input Quality Gate
2. CWO 7-Step Execution
3. Agent Selection
4. Output Validation
