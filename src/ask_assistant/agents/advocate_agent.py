"""Advocate Agent - Lawyer's Perspective"""

from ..models.enums import AgentType
from .base_agent import BaseAgent


class AdvocateAgent(BaseAgent):
    """
    Agent that provides legal advice like an experienced advocate.
    Focuses on legal strategy, rights protection, and procedural guidance.
    """
    
    agent_type = AgentType.ADVOCATE
    
    def get_name(self) -> str:
        return "Advocate"
    
    def get_description(self) -> str:
        return "Gives strategic legal advice focused on protecting rights and winning cases"
