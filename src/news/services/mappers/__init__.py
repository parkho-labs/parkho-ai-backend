"""
News source mappers
Each mapper handles content formatting and standardization for a specific news source
"""

from .base_mapper import BaseMapper
from .indian_kanoon_mapper import IndianKanoonMapper

__all__ = [
    'BaseMapper',
    'IndianKanoonMapper'
]