"""Answer-routing categories used by ALF."""

from enum import Enum


class Route(Enum):
    SYSTEM = "system"
    MEMORY = "memory"
    RESEARCH = "research"
    LLM = "llm"
    DECLINE = "decline"
