"""Civilian Agent - Common Person's Perspective"""

from ..models.enums import AgentType
from .base_agent import BaseAgent


class CivilianAgent(BaseAgent):
    """
    Agent that explains law from a common citizen's perspective.
    Uses simple language, avoids jargon, focuses on practical implications.
    """
    
    agent_type = AgentType.CIVILIAN
    
    def get_name(self) -> str:
        return "Civilian"
    
    def get_description(self) -> str:
        return "Explains law from a common person's perspective using simple, everyday language"
