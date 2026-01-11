"""Prompts for Ask Assistant agents"""

from .agent_prompts import AGENT_PROMPTS, get_agent_prompt
from .style_prompts import STYLE_PROMPTS, get_style_prompt

__all__ = [
    "AGENT_PROMPTS",
    "get_agent_prompt",
    "STYLE_PROMPTS",
    "get_style_prompt",
]
