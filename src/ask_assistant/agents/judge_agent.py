"""Judge Agent - Supreme Court Judge's Perspective"""

from ..models.enums import AgentType
from .base_agent import BaseAgent


class JudgeAgent(BaseAgent):
    """
    Agent that provides judicial analysis like a Supreme Court Judge.
    Focuses on constitutional interpretation, precedent, and balanced analysis.
    """
    
    agent_type = AgentType.JUDGE
    
    def get_name(self) -> str:
        return "Supreme Court Judge"
    
    def get_description(self) -> str:
        return "Provides authoritative judicial analysis with constitutional interpretation and precedent"
