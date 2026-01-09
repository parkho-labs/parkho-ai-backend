"""
Indian Kanoon mapper
Handles content formatting for Indian Kanoon RSS feeds and API responses
"""

from typing import Dict, Any, Optional
from datetime import datetime
import re
import logging

from .base_mapper import BaseMapper
from ..content_cleaner import ContentCleaner

logger = logging.getLogger(__name__)


class IndianKanoonMapper(BaseMapper):
    """Mapper for Indian Kanoon legal content"""

    def __init__(self):
        super().__init__("Indian Kanoon")

    def map_article(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map Indian Kanoon RSS entry to standardized format

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
            keywords = ContentCleaner.extract_keywords(clean_description)

            # Determine source and category
            source = self._determine_source(url, title)
            category = self.extract_category(raw_data)

            # Generate image info (Indian Kanoon doesn't have images)
            image_info = self._generate_image_info(source, category)

            return {
                'title': title,
                'url': url,
                'source': source,
                'category': category,
                'description': clean_description,
                'full_content': None,  # Will be extracted later by content scraper
                'summary': summary,
                'keywords': keywords,
                'published_at': published_at,
                'featured_image_url': image_info['featured'],
                'thumbnail_url': image_info['thumbnail'],
                'image_caption': image_info['caption'],
                'image_alt_text': image_info['alt_text']
            }

        except Exception as e:
            logger.error(f"Error mapping Indian Kanoon article: {e}")
            raise

    def clean_content(self, content: str) -> str:
        """
        Clean Indian Kanoon HTML content

        Args:
            content: Raw HTML content

        Returns:
            Cleaned content
        """
        if not content:
            return ""

        # Use content cleaner for HTML removal
        clean_content = ContentCleaner.clean_html_content(content)

        # Indian Kanoon specific cleaning
        clean_content = self._fix_indian_kanoon_formatting(clean_content)

        return clean_content

    def extract_category(self, raw_data: Dict[str, Any]) -> str:
        """
        Extract category from Indian Kanoon data

        Args:
            raw_data: RSS entry data

        Returns:
            Standardized category
        """
        # Get URL to determine court
        url = raw_data.get('link', '').lower()
        title = raw_data.get('title', '').lower()

        # Determine category based on source
        if 'supremecourt' in url:
            return 'judicial'
        elif any(court in url for court in ['delhi', 'bombay', 'madras', 'calcutta']):
            return 'judicial'
        elif 'tribunal' in url or 'tribunal' in title:
            return 'judicial'
        elif 'constitution' in title:
            return 'constitutional'
        else:
            return 'judicial'  # Default for Indian Kanoon

    def _clean_title(self, title: str) -> str:
        """Clean and format article title"""
        if not title:
            return ""

        # Remove HTML entities
        title = ContentCleaner.clean_html_content(title)

        # Remove extra whitespace
        title = re.sub(r'\s+', ' ', title).strip()

        # Ensure proper capitalization
        title = self._fix_title_capitalization(title)

        return title

    def _fix_title_capitalization(self, title: str) -> str:
        """Fix capitalization in legal titles"""
        # Common legal abbreviations that should stay uppercase
        legal_abbrevs = ['HC', 'SC', 'CJI', 'J.', 'CJ', 'vs', 'v.', 'Ors.', 'Anr.']

        words = title.split()
        result = []

        for word in words:
            if word.upper() in [abbr.upper() for abbr in legal_abbrevs]:
                result.append(word.title())
            elif word.isupper() and len(word) > 3:
                # Convert all caps words to title case
                result.append(word.title())
            else:
                result.append(word)

        return ' '.join(result)

    def _fix_indian_kanoon_formatting(self, content: str) -> str:
        """Fix specific formatting issues in Indian Kanoon content"""
        # Fix numbered points
        content = re.sub(r'(\d+)\.\s+', r'\n\n\1. ', content)

        # Fix sub-points
        content = re.sub(r'([a-z])\)\s+', r'\n  \1) ', content)

        # Fix case citations
        content = re.sub(r'(\d{4})\s+\((\d+)\)\s+([A-Z]+)', r'\1 (\2) \3', content)

        # Remove excessive spacing
        content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)

        return content.strip()

    def _parse_published_date(self, date_str: str) -> Optional[datetime]:
        """Parse Indian Kanoon date format"""
        if not date_str:
            return datetime.now()

        # Indian Kanoon uses RFC 2822 format
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except Exception:
            # Fallback to current time
            return datetime.now()

    def _determine_source(self, url: str, title: str) -> str:
        """Determine specific Indian Kanoon source from URL"""
        url_lower = url.lower()

        if 'supremecourt' in url_lower:
            return 'Indian Kanoon - Supreme Court'
        elif 'delhi' in url_lower:
            return 'Indian Kanoon - Delhi HC'
        elif 'bombay' in url_lower:
            return 'Indian Kanoon - Bombay HC'
        elif 'madras' in url_lower:
            return 'Indian Kanoon - Madras HC'
        elif 'calcutta' in url_lower:
            return 'Indian Kanoon - Calcutta HC'
        elif 'tribunal' in url_lower:
            return 'Indian Kanoon - Tribunals'
        elif 'districtcourt' in url_lower:
            return 'Indian Kanoon - District Courts'
        else:
            return 'Indian Kanoon - All Judgments'

    def _generate_image_info(self, source: str, category: str) -> Dict[str, str]:
        """Generate appropriate image URLs for Indian Kanoon articles"""
        # Use different stock images based on court type
        image_map = {
            'Supreme Court': 'https://images.unsplash.com/photo-1589829545856-d10d557cf95f?w=800&h=400&fit=crop',
            'Delhi HC': 'https://images.unsplash.com/photo-1521587760476-6c12a4b040da?w=800&h=400&fit=crop',
            'Bombay HC': 'https://images.unsplash.com/photo-1589216532372-59a850b1db90?w=800&h=400&fit=crop',
            'Tribunals': 'https://images.unsplash.com/photo-1589994965851-a8f479c573a9?w=800&h=400&fit=crop',
            'default': 'https://images.unsplash.com/photo-1555374018-13a8994ab246?w=800&h=400&fit=crop'
        }

        # Choose image based on source
        image_url = image_map['default']
        for court_name, court_image in image_map.items():
            if court_name.lower() in source.lower():
                image_url = court_image
                break

        # Extract court name for caption
        court_name = source.replace('Indian Kanoon - ', '')

        return {
            'featured': image_url,
            'thumbnail': image_url,
            'caption': f'Indian Kanoon {court_name} article',
            'alt_text': f'{court_name}: {source}'
        }