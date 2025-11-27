"""
Content Processing Strategies

This module implements a strategy pattern for content processing,
supporting multiple flows:
- Complex Pipeline Strategy (existing multi-agent workflow)
- Direct Gemini Strategy (single API call for video content)
"""

from .base_strategy import ContentProcessingStrategy, ProcessingResult
from .strategy_factory import ContentProcessingStrategyFactory

__all__ = [
    "ContentProcessingStrategy",
    "ProcessingResult",
    "ContentProcessingStrategyFactory"
]