"""
Agent Package - Base Classes and Implementations

This package contains the agent classes that perform idea generation and evaluation.
All agents inherit from the base Agent class and implement the required interface.

Modules:
- base: Abstract base class for all agents
- expert: Domain knowledge expert with evidence-based reasoning
- critic: Critical analyst who finds flaws and risks
- innovator: Creative thinker who generates novel, breakthrough ideas
- synthesizer: Idea integrator who combines concepts into holistic solutions
- pragmatist: Implementation-focused agent who generates practical, actionable ideas
"""
from __future__ import annotations

from .base import Agent
from .critic import CriticAgent
from .expert import ExpertAgent
from .innovator import InnovatorAgent
from .pragmatist import PragmatistAgent
from .synthesizer import SynthesizerAgent
from .futurist import FuturistAgent

__all__ = [

    "Agent",

    "CriticAgent",

    "ExpertAgent",

    "InnovatorAgent",

    "PragmatistAgent",

    "SynthesizerAgent",

    "FuturistAgent",
]
