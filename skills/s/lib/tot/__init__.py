"""
Tree-of-Thought (ToT) Analysis for Outcome Exploration

This module implements ToT reasoning to generate branching outcome scenarios
for each strategic option.

Components:
- BranchGenerator: Generates outcome scenarios for strategic options
- ToT analysis integrates into Converge phase
"""

from .generator import BranchGenerator, OutcomeBranch

__all__ = ["BranchGenerator", "OutcomeBranch"]
