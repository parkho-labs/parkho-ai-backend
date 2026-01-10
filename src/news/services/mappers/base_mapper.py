"""
Base mapper class for news sources
Defines the interface that all source mappers must implement
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime


class BaseMapper(ABC):
    """Base class for news source mappers"""

    def __init__(self, source_name: str):
        self.source_name = source_name

    @abstractmethod
    def map_article(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map raw article data to standardized format

        Args:
            raw_data: Raw article data from source

        Returns:
            Standardized article data dict with keys:
            - title: str
            - url: str
            - source: str
            - category: str
            - description: str
            - full_content: str
            - summary: str
            - keywords: list
            - published_at: datetime
            - featured_image_url: Optional[str]
            - thumbnail_url: Optional[str]
            - image_caption: Optional[str]
            - image_alt_text: Optional[str]
        """
        pass

    @abstractmethod
    def clean_content(self, content: str) -> str:
        """
        Clean and format content specific to this source

        Args:
            content: Raw content from source

        Returns:
            Cleaned and formatted content
        """
        pass

    @abstractmethod
    def extract_category(self, raw_data: Dict[str, Any]) -> str:
        """
        Extract or determine category from raw data

        Args:
            raw_data: Raw article data

        Returns:
            Standardized category name
        """
        pass

    def get_standard_categories(self) -> Dict[str, str]:
        """
        Get mapping of source categories to standard categories

        Returns:
            Dict mapping source categories to standard ones
        """
        return {
            'supreme court': 'judicial',
            'high court': 'judicial',
            'tribunal': 'judicial',
            'constitutional': 'constitutional',
            'legislation': 'legislative',
            'legal news': 'general',
            'appointments': 'general',
            'business law': 'business',
            'criminal law': 'criminal',
            'civil law': 'civil'
        }

    def standardize_category(self, source_category: str) -> str:
        """
        Convert source-specific category to standard category

        Args:
            source_category: Category from source

        Returns:
            Standardized category
        """
        if not source_category:
            return 'general'

        category_lower = source_category.lower()
        category_map = self.get_standard_categories()

        # Direct match
        if category_lower in category_map:
            return category_map[category_lower]

        # Partial matches
        for source_cat, standard_cat in category_map.items():
            if source_cat in category_lower:
                return standard_cat

        return 'general'

    def format_published_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse and format published date

        Args:
            date_str: Date string from source

        Returns:
            Parsed datetime or None
        """
        if not date_str:
            return None

        # Common date formats to try
        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%d',
            '%d-%m-%Y',
            '%d/%m/%Y'
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return None