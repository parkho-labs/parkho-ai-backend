"""
Ask Assistant - AI Agent System

A modular chat agent system using Pydantic AI + Mem0 featuring:
- Multiple agent personalities (Civilian, Judge, Advocate)
- Streaming responses with chain-of-thought
- Memory management via Mem0
- RAG knowledge base integration
"""

from .models.enums import AgentType, ResponseStyle, LLMModel
from .services.agent_manager import AgentManager, get_agent_manager

__all__ = [
    "AgentType",
    "ResponseStyle", 
    "LLMModel",
    "AgentManager",
    "get_agent_manager",
]
