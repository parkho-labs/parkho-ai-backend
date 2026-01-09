"""
Bar and Bench RSS adapter
Fetches legal news from Bar and Bench RSS feed
"""

import feedparser
import logging
from datetime import datetime
from typing import List

from .base import NewsSourceAdapter, NewsItem
from ..mappers.bar_and_bench_mapper import BarAndBenchMapper

logger = logging.getLogger(__name__)


class BarAndBenchAdapter(NewsSourceAdapter):
    """Adapter for Bar and Bench RSS feed"""

    def __init__(self):
        super().__init__("Bar and Bench", "https://www.barandbench.com")
        self.rss_url = "https://www.barandbench.com/feed"
        self.mapper = BarAndBenchMapper()

    def fetch_news(self, limit: int = 10) -> List[NewsItem]:
        """
        Fetch articles from Bar and Bench RSS feed

        Args:
            limit: Maximum number of articles to fetch

        Returns:
            List of NewsItem objects
        """
        try:
            logger.info(f"🔄 Fetching from Bar and Bench RSS...")

            # Parse RSS feed
            feed = feedparser.parse(self.rss_url)

            if feed.bozo:
                logger.warning(f"RSS feed parsing had issues: {feed.bozo_exception}")

            articles = []
            entries = feed.entries[:limit] if feed.entries else []

            logger.info(f"  📰 Found {len(entries)} articles from Bar and Bench")

            for entry in entries:
                try:
                    # Map RSS entry to standardized format
                    article_data = self.mapper.map_article(entry)

                    # Create NewsItem object
                    news_item = NewsItem(
                        title=article_data['title'],
                        url=article_data['url'],
                        source=article_data['source'],
                        category=article_data['category'],
                        description=article_data['description'],
                        published_at=article_data['published_at'],
                        keywords=article_data['keywords'],
                        featured_image_url=article_data['featured_image_url'],
                        thumbnail_url=article_data['thumbnail_url'],
                        image_caption=article_data['image_caption'],
                        image_alt_text=article_data['image_alt_text']
                    )

                    articles.append(news_item)

                except Exception as e:
                    logger.warning(f"Error processing Bar and Bench article '{entry.get('title', 'Unknown')}': {e}")
                    continue

            logger.info(f"  ✅ Successfully processed {len(articles)} Bar and Bench articles")
            return articles

        except Exception as e:
            logger.error(f"Failed to fetch from Bar and Bench: {e}")
            return []

    def get_categories(self) -> List[str]:
        """
        Get available categories for Bar and Bench

        Returns:
            List of category names
        """
        return ['judicial', 'constitutional', 'legislative', 'business', 'general']

    def health_check(self) -> dict:
        """
        Check the health of Bar and Bench RSS feed

        Returns:
            Health status dictionary
        """
        try:
            # Try to parse the RSS feed
            feed = feedparser.parse(self.rss_url)

            if feed.bozo:
                return {
                    "status": "degraded",
                    "message": f"RSS parsing issues: {feed.bozo_exception}",
                    "feed_url": self.rss_url,
                    "entries_count": len(feed.entries) if hasattr(feed, 'entries') else 0
                }

            entries_count = len(feed.entries) if hasattr(feed, 'entries') else 0

            if entries_count == 0:
                return {
                    "status": "unhealthy",
                    "message": "No articles found in RSS feed",
                    "feed_url": self.rss_url,
                    "entries_count": 0
                }

            # Check if articles are recent (within last 7 days)
            recent_articles = 0
            if entries_count > 0:
                week_ago = datetime.now().timestamp() - (7 * 24 * 60 * 60)
                for entry in feed.entries[:5]:  # Check first 5 entries
                    try:
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            entry_time = datetime(*entry.published_parsed[:6]).timestamp()
                            if entry_time > week_ago:
                                recent_articles += 1
                    except Exception:
                        continue

            status = "healthy" if recent_articles >= 3 else "degraded"
            message = f"Found {entries_count} articles, {recent_articles} recent"

            return {
                "status": status,
                "message": message,
                "feed_url": self.rss_url,
                "entries_count": entries_count,
                "recent_articles": recent_articles
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Health check failed: {str(e)}",
                "feed_url": self.rss_url,
                "entries_count": 0
            }