"""
Base class for news source adapters
Clean, simple interface that all sources must implement
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any
import requests


@dataclass
class NewsItem:
    """Standardized news item format for all sources"""
    title: str
    url: str
    description: str
    source: str
    category: str
    published_at: datetime
    featured_image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    image_caption: Optional[str] = None
    image_alt_text: Optional[str] = None
    keywords: List[str] = None

    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []

        # Auto-generate thumbnail from featured image if not provided
        if self.featured_image_url and not self.thumbnail_url:
            self.thumbnail_url = self.featured_image_url

        # Auto-generate image alt text if not provided
        if self.featured_image_url and not self.image_alt_text:
            self.image_alt_text = f"Image for {self.title}"


class NewsSourceAdapter(ABC):
    """Base adapter for news sources"""

    def __init__(self, name: str, base_url: str):
        self.name = name
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36'
        })

    @abstractmethod
    def fetch_news(self, limit: int = 20) -> List[NewsItem]:
        """Fetch news from source and return standardized format"""
        pass

    @abstractmethod
    def get_categories(self) -> List[str]:
        """Get available categories from this source"""
        pass

    def categorize_article(self, title: str, content: str = "") -> str:
        """Smart categorization based on title and content"""
        text = (title + " " + content).lower()

        if any(word in text for word in ['supreme court', 'chief justice', 'constitution']):
            return 'constitutional'
        elif any(word in text for word in ['high court', 'district court', 'tribunal']):
            return 'judicial'
        elif any(word in text for word in ['parliament', 'legislation', 'bill', 'act']):
            return 'legislative'
        elif any(word in text for word in ['corporate', 'commercial', 'business', 'company']):
            return 'civil'
        elif any(word in text for word in ['environment', 'pollution', 'green', 'climate']):
            return 'environmental'
        else:
            return 'general'

    def extract_keywords(self, title: str, content: str = "") -> List[str]:
        """Extract relevant legal keywords"""
        text = (title + " " + content).lower()

        legal_keywords = [
            'supreme court', 'high court', 'constitutional', 'judgment', 'ruling',
            'petition', 'appeal', 'writ', 'fundamental rights', 'law',
            'court', 'legal', 'justice', 'case', 'hearing'
        ]

        found = []
        for keyword in legal_keywords:
            if keyword in text and keyword not in found:
                found.append(keyword)

        return found[:6]  # Limit to 6 keywords

    def safe_request(self, url: str, **kwargs) -> Optional[requests.Response]:
        """Make safe HTTP request with error handling"""
        try:
            response = self.session.get(url, timeout=10, **kwargs)
            if response.status_code == 200:
                return response
        except Exception as e:
            print(f"  ⚠️ Error fetching from {self.name}: {e}")
        return None