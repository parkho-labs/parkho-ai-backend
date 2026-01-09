"""
Indian Kanoon RSS feed adapter
"""

import feedparser
from datetime import datetime
from typing import List, Optional
import re

from .base import NewsSourceAdapter, NewsItem


class IndianKanoonAdapter(NewsSourceAdapter):
    """Indian Kanoon RSS feed adapter"""

    def __init__(self):
        super().__init__("Indian Kanoon", "https://indiankanoon.org")
        self.rss_url = "https://indiankanoon.org/browse/rss/"

    def fetch_news(self, limit: int = 20) -> List[NewsItem]:
        """Fetch news from Indian Kanoon RSS"""
        print(f"🔄 Fetching from {self.name} RSS...")

        response = self.safe_request(self.rss_url)
        if not response:
            return []

        try:
            feed = feedparser.parse(response.content)
            articles = []

            for entry in feed.entries[:limit]:
                article = self._parse_rss_entry(entry)
                if article:
                    articles.append(article)

            print(f"  ✅ Got {len(articles)} articles from {self.name}")
            return articles

        except Exception as e:
            print(f"  ⚠️ Error parsing RSS from {self.name}: {e}")
            return []

    def _parse_rss_entry(self, entry) -> Optional[NewsItem]:
        """Parse RSS entry to NewsItem"""
        try:
            title = getattr(entry, 'title', 'Untitled')
            url = getattr(entry, 'link', '')
            description = getattr(entry, 'summary', title)

            # Parse date
            published_date = datetime.now()
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                try:
                    published_date = datetime(*entry.published_parsed[:6])
                except:
                    pass

            # Indian Kanoon doesn't typically have images in RSS
            # We'll use a default legal image
            default_image = "https://images.unsplash.com/photo-1589994965851-a8f479c573a9?w=800&h=400&fit=crop"

            return NewsItem(
                title=title,
                url=url,
                description=description,
                source=self.name,
                category=self.categorize_article(title, description),
                published_at=published_date,
                featured_image_url=default_image,
                thumbnail_url=default_image,
                image_caption="Indian legal document",
                image_alt_text=f"Legal document: {title}",
                keywords=self.extract_keywords(title, description)
            )

        except Exception as e:
            print(f"    ⚠️ Error parsing RSS entry: {e}")
            return None

    def get_categories(self) -> List[str]:
        """Get categories for Indian Kanoon"""
        return ['constitutional', 'judicial', 'legislative', 'civil']