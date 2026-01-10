"""
Bar and Bench mapper
Handles content formatting for Bar and Bench RSS feeds
"""

from typing import Dict, Any, Optional
from datetime import datetime
import re
import logging

from .base_mapper import BaseMapper
from ..content_cleaner import ContentCleaner

logger = logging.getLogger(__name__)


class BarAndBenchMapper(BaseMapper):
    """Mapper for Bar and Bench legal news content"""

    def __init__(self):
        super().__init__("Bar and Bench")

    def map_article(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map Bar and Bench RSS entry to standardized format

        Args:
            raw_data: RSS entry data from feedparser

        Returns:
            Standardized article data
        """
        try:
            # Extract basic info
            title = self._clean_title(raw_data.get('title', ''))
            url = raw_data.get('link', '')
            description = raw_data.get('summary', '')
            published_at = self._parse_published_date(raw_data.get('published', ''))

            # Clean content
            clean_description = self.clean_content(description)
            summary = ContentCleaner.extract_summary(clean_description, max_length=500)
            keywords = self._extract_legal_keywords(clean_description)

            # Determine category
            category = self.extract_category(raw_data)

            return {
                'title': title,
                'url': url,
                'source': 'Bar and Bench',
                'category': category,
                'description': clean_description,
                'full_content': None,  # Will be extracted later by content scraper
                'summary': summary,
                'keywords': keywords,
                'published_at': published_at,
                'featured_image_url': None,  # Will be extracted from article page
                'thumbnail_url': None,
                'image_caption': 'Bar and Bench legal news article',
                'image_alt_text': f'Bar and Bench: {title}'
            }

        except Exception as e:
            logger.error(f"Error mapping Bar and Bench article: {e}")
            raise

    def clean_content(self, content: str) -> str:
        """
        Clean Bar and Bench content

        Args:
            content: Raw content from RSS

        Returns:
            Cleaned content
        """
        if not content:
            return ""

        # Use content cleaner for HTML removal
        clean_content = ContentCleaner.clean_html_content(content)

        # Bar and Bench specific cleaning
        clean_content = self._fix_bar_and_bench_formatting(clean_content)

        return clean_content

    def extract_category(self, raw_data: Dict[str, Any]) -> str:
        """
        Extract category from Bar and Bench data

        Args:
            raw_data: RSS entry data

        Returns:
            Standardized category
        """
        title = raw_data.get('title', '').lower()
        description = raw_data.get('summary', '').lower()

        # Category keywords
        if any(keyword in title or keyword in description for keyword in [
            'supreme court', 'sc ', 'apex court'
        ]):
            return 'judicial'
        elif any(keyword in title or keyword in description for keyword in [
            'high court', 'hc ', 'delhi hc', 'bombay hc', 'madras hc'
        ]):
            return 'judicial'
        elif any(keyword in title or keyword in description for keyword in [
            'constitutional', 'constitution', 'fundamental rights'
        ]):
            return 'constitutional'
        elif any(keyword in title or keyword in description for keyword in [
            'legislation', 'bill', 'act', 'amendment', 'parliament'
        ]):
            return 'legislative'
        elif any(keyword in title or keyword in description for keyword in [
            'corporate', 'company', 'business', 'merger', 'acquisition'
        ]):
            return 'business'
        elif any(keyword in title or keyword in description for keyword in [
            'appointment', 'elevation', 'transfer', 'judge'
        ]):
            return 'general'
        else:
            return 'general'

    def _clean_title(self, title: str) -> str:
        """Clean and format article title"""
        if not title:
            return ""

        # Remove HTML entities and tags
        title = ContentCleaner.clean_html_content(title)

        # Remove common RSS feed artifacts
        title = re.sub(r'\s*\|\s*Bar\s*&\s*Bench.*$', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*-\s*Bar\s*&\s*Bench.*$', '', title, flags=re.IGNORECASE)

        # Fix spacing
        title = re.sub(r'\s+', ' ', title).strip()

        return title

    def _fix_bar_and_bench_formatting(self, content: str) -> str:
        """Fix specific formatting issues in Bar and Bench content"""
        # Remove common artifacts
        content = re.sub(r'The post.*appeared first on Bar & Bench.*$', '', content, flags=re.IGNORECASE)
        content = re.sub(r'Continue reading.*$', '', content, flags=re.IGNORECASE)

        # Fix quote formatting
        content = re.sub(r'"([^"]*)"', r'"\1"', content)

        # Fix numbered points
        content = re.sub(r'(\d+)\.\s+', r'\n\n\1. ', content)

        # Remove excessive spacing
        content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)

        return content.strip()

    def _parse_published_date(self, date_str: str) -> Optional[datetime]:
        """Parse Bar and Bench date format"""
        if not date_str:
            return datetime.now()

        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except Exception:
            # Try common formats
            return self.format_published_date(date_str) or datetime.now()

    def _extract_legal_keywords(self, content: str) -> list:
        """
        Extract legal keywords specific to Bar and Bench content

        Args:
            content: Article content

        Returns:
            List of keywords
        """
        if not content:
            return []

        content_lower = content.lower()

        # Legal keywords specific to news articles
        keywords = []

        keyword_map = {
            'supreme court': ['supreme court', 'sc', 'apex court'],
            'high court': ['high court', 'hc', 'delhi hc', 'bombay hc'],
            'constitutional': ['constitution', 'constitutional', 'fundamental rights'],
            'legislation': ['bill', 'act', 'amendment', 'parliament'],
            'judgment': ['judgment', 'judgement', 'order', 'ruling'],
            'legal news': ['legal', 'law', 'court', 'justice'],
            'appointment': ['appointment', 'elevation', 'transfer', 'judge'],
            'corporate': ['corporate', 'company', 'business'],
            'litigation': ['litigation', 'case', 'petition', 'appeal']
        }

        for category, terms in keyword_map.items():
            if any(term in content_lower for term in terms):
                keywords.append(category)

        return keywords[:8]  # Limit to 8 keywords