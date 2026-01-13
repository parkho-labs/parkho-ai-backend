"""
Content cleaning utilities for news articles
Handles HTML removal, text formatting, and content standardization
"""

import re
import html
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

class ContentCleaner:
    """Utility class for cleaning and formatting news article content"""

    @staticmethod
    def clean_html_content(content: str) -> str:
        """
        Clean HTML content by removing tags and formatting properly

        Args:
            content: Raw HTML content string

        Returns:
            Clean, formatted text content
        """
        if not content:
            return ""

        try:
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(content, 'html.parser')

            # Remove unwanted tags but keep text
            for tag in soup(['script', 'style', 'nav', 'header', 'footer']):
                tag.decompose()

            # Get text and clean it
            text = soup.get_text()

            # Clean up whitespace and formatting
            text = ContentCleaner._normalize_whitespace(text)

            # Fix common formatting issues
            text = ContentCleaner._fix_legal_formatting(text)

            return text.strip()

        except Exception as e:
            logger.warning(f"Error cleaning HTML content: {e}")
            # Fallback to simple tag removal
            return ContentCleaner._simple_html_removal(content)

    @staticmethod
    def _simple_html_removal(content: str) -> str:
        """Simple fallback HTML tag removal"""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', content)

        # Decode HTML entities
        text = html.unescape(text)

        # Clean whitespace
        text = ContentCleaner._normalize_whitespace(text)

        return text.strip()

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        """Normalize whitespace and line breaks"""
        # Replace multiple spaces with single space
        text = re.sub(r'\s+', ' ', text)

        # Replace multiple line breaks with proper paragraphs
        text = re.sub(r'\n\s*\n\s*', '\n\n', text)

        # Remove leading/trailing whitespace from each line
        lines = text.split('\n')
        lines = [line.strip() for line in lines]
        text = '\n'.join(lines)

        return text

    @staticmethod
    def _fix_legal_formatting(text: str) -> str:
        """Fix common formatting issues in legal content"""
        # Fix numbered points (ensure proper spacing)
        text = re.sub(r'(\d+)\.\s*', r'\n\n\1. ', text)

        # Fix sub-points
        text = re.sub(r'([a-z])\)\s*', r'\n  \1) ', text)

        # Fix roman numerals
        text = re.sub(r'([ivx]+)\)\s*', r'\n  \1) ', text)

        # Remove extra line breaks at start
        text = text.lstrip('\n')

        # Ensure proper paragraph spacing
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text

    @staticmethod
    def extract_summary(content: str, max_length: int = 300) -> str:
        """
        Extract a clean summary from content

        Args:
            content: Full article content
            max_length: Maximum summary length

        Returns:
            Clean summary text
        """
        if not content:
            return ""

        # Clean the content first
        clean_content = ContentCleaner.clean_html_content(content)

        # Take first few sentences
        sentences = re.split(r'[.!?]+', clean_content)

        summary = ""
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Check if adding this sentence would exceed max length
            if len(summary + sentence) > max_length:
                break

            summary += sentence + ". "

        return summary.strip()

    @staticmethod
    def extract_keywords(content: str, max_keywords: int = 10) -> list:
        """
        Extract keywords from content

        Args:
            content: Article content
            max_keywords: Maximum number of keywords

        Returns:
            List of keywords
        """
        if not content:
            return []

        # Clean content
        clean_content = ContentCleaner.clean_html_content(content)

        # Common legal terms
        legal_keywords = {
            'supreme court', 'high court', 'judgment', 'appeal', 'petition',
            'writ', 'case', 'court', 'law', 'legal', 'constitution',
            'tribunal', 'magistrate', 'justice', 'order', 'hearing'
        }

        # Find legal keywords in content
        found_keywords = []
        content_lower = clean_content.lower()

        for keyword in legal_keywords:
            if keyword in content_lower:
                found_keywords.append(keyword)

        # Limit to max_keywords
        return found_keywords[:max_keywords]