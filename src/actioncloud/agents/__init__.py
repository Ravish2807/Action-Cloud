"""Agent implementations for ActionCloud."""

from .base import Agent, TaskOutcome, TaskSpec
from .coordinator import CoordinatorAgent
from .roles import ROLE_REGISTRY, CodingAgent, ResearchAgent, build_agent

__all__ = [
    "Agent",
    "CoordinatorAgent",
    "TaskSpec",
    "TaskOutcome",
    "CodingAgent",
    "ResearchAgent",
    "ROLE_REGISTRY",
    "build_agent",
]
