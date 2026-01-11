"""
Agent System for Knowlx

Provides:
- Multiple agent personalities (Legal, Constitution, BNS, News, Study)
- Different modes (Normal, Agentic, Planning)
- Different styles (Concise, Detailed, Learning, Professional)
- Memory support via Mem0
"""

from .base import BaseAgent, AgentConfig, AgentMode, AgentStyle
from .registry import AgentRegistry, get_agent_registry
from .legal_agent import LegalExpertAgent
from .constitution_agent import ConstitutionAgent
from .memory_manager import MemoryManager, get_memory_manager

__all__ = [
    "BaseAgent",
    "AgentConfig", 
    "AgentMode",
    "AgentStyle",
    "AgentRegistry",
    "get_agent_registry",
    "LegalExpertAgent",
    "ConstitutionAgent",
    "MemoryManager",
    "get_memory_manager",
]
