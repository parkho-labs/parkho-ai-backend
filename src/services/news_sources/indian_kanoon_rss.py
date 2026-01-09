"""
Indian Kanoon RSS feed adapter - proven working source from POC
"""

import feedparser
from datetime import datetime
from typing import List, Optional

from .base import NewsSourceAdapter, NewsItem


class IndianKanoonRSSAdapter(NewsSourceAdapter):
    """Indian Kanoon RSS feeds - proven working sources from POC"""

    def __init__(self):
        super().__init__("Indian Kanoon", "https://indiankanoon.org")
        self.rss_feeds = {
            "Supreme Court": "https://indiankanoon.org/feeds/latest/supremecourt/",
            "All Judgments": "https://indiankanoon.org/feeds/latest/judgments/",
            "Delhi HC": "https://indiankanoon.org/feeds/latest/delhi/",
            "Bombay HC": "https://indiankanoon.org/feeds/latest/bombay/"
        }

    def fetch_news(self, limit: int = 20) -> List[NewsItem]:
        """Fetch from all Indian Kanoon RSS feeds"""
        print(f"🔄 Fetching from {self.name} RSS feeds...")

        all_articles = []
        per_feed_limit = max(1, limit // len(self.rss_feeds))

        for feed_name, feed_url in self.rss_feeds.items():
            try:
                print(f"  📰 Fetching {feed_name}...")
                articles = self._fetch_single_rss(feed_url, feed_name, per_feed_limit)
                all_articles.extend(articles)
                print(f"    ✅ Got {len(articles)} articles from {feed_name}")
            except Exception as e:
                print(f"    ⚠️ Error with {feed_name}: {e}")

        # Sort by date and limit
        all_articles.sort(key=lambda x: x.published_at, reverse=True)
        return all_articles[:limit]

    def _fetch_single_rss(self, feed_url: str, feed_name: str, limit: int) -> List[NewsItem]:
        """Fetch from single RSS feed"""
        try:
            response = self.safe_request(feed_url)
            if not response:
                return []

            feed = feedparser.parse(response.content)
            articles = []

            for entry in feed.entries[:limit]:
                article = self._parse_rss_entry(entry, feed_name)
                if article:
                    articles.append(article)

            return articles

        except Exception as e:
            print(f"      ⚠️ Error parsing RSS from {feed_url}: {e}")
            return []

    def _parse_rss_entry(self, entry, feed_name: str) -> Optional[NewsItem]:
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

            # Use appropriate image based on court type
            image_map = {
                "Supreme Court": "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?w=800&h=400&fit=crop",
                "Delhi HC": "https://images.unsplash.com/photo-1521587760476-6c12a4b040da?w=800&h=400&fit=crop",
                "Bombay HC": "https://images.unsplash.com/photo-1589216532372-59a850b1db90?w=800&h=400&fit=crop",
                "All Judgments": "https://images.unsplash.com/photo-1589994965851-a8f479c573a9?w=800&h=400&fit=crop"
            }

            featured_image = image_map.get(feed_name, image_map["All Judgments"])

            return NewsItem(
                title=title,
                url=url,
                description=description,
                source=f"Indian Kanoon - {feed_name}",
                category=self.categorize_article(title, description),
                published_at=published_date,
                featured_image_url=featured_image,
                thumbnail_url=featured_image,
                image_caption=f"Indian Kanoon {feed_name} article",
                image_alt_text=f"{feed_name}: {title}",
                keywords=self.extract_keywords(title, description)
            )

        except Exception as e:
            print(f"      ⚠️ Error parsing RSS entry: {e}")
            return None

    def get_categories(self) -> List[str]:
        return ['constitutional', 'judicial', 'civil']

    def get_weight(self) -> float:
        """Default weight for this source in news distribution"""
        return 1.0