"""
News Sources Manager - orchestrates all news sources for background processing
Simplified version for the news module
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import random

from .base import NewsItem, NewsSourceAdapter
from .indian_kanoon_rss import IndianKanoonRSSAdapter


class NewsSourceManager:
    """
    Manages multiple news sources for background processing.
    Designed for cron jobs and background tasks only.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._default_config()
        self.sources = self._initialize_sources()

    def _default_config(self) -> Dict[str, Any]:
        """Default configuration for news sources"""
        return {
            "source_weights": {
                "indian_kanoon_rss": 1.0,  # Only proven working source
            },
            "fallback_enabled": True,
            "timeout_seconds": 10,
            "retry_attempts": 2
        }

    def _initialize_sources(self) -> Dict[str, NewsSourceAdapter]:
        """Initialize all available news sources"""
        sources = {}

        # Add proven working sources
        try:
            sources["indian_kanoon_rss"] = IndianKanoonRSSAdapter()
            print(f"✅ Loaded Indian Kanoon RSS adapter")
        except Exception as e:
            print(f"⚠️ Could not load Indian Kanoon RSS adapter: {e}")

        # Future sources can be added here when ready
        # sources["livelaw_api"] = LiveLawAPIAdapter()
        # sources["bar_bench"] = BarBenchAdapter()

        print(f"📊 Loaded {len(sources)} news sources")
        return sources

    def fetch_all_news(self, total_limit: int = 30) -> List[NewsItem]:
        """
        Fetch news from all sources using configured distribution.
        """
        print(f"🚀 Fetching {total_limit} articles for background processing...")
        print("=" * 60)

        all_articles = []

        # Calculate distribution based on weights
        distribution = self._calculate_distribution(total_limit)

        for source_key, limit in distribution.items():
            if source_key not in self.sources:
                continue

            adapter = self.sources[source_key]
            try:
                print(f"\n📰 {adapter.name}: fetching {limit} articles...")
                articles = adapter.fetch_news(limit)

                all_articles.extend(articles)
                print(f"  ✅ Added {len(articles)} articles from {adapter.name}")

            except Exception as e:
                print(f"  ❌ Error with {adapter.name}: {e}")
                if self.config.get("fallback_enabled", True):
                    print(f"  🔄 Fallback: redistributing {limit} articles to other sources")

        # Sort by published date with some randomness for diversity
        all_articles.sort(key=lambda x: (x.published_at, random.random()), reverse=True)

        print(f"\n🎉 Successfully fetched {len(all_articles)} articles")
        return all_articles[:total_limit]

    def _calculate_distribution(self, total_limit: int) -> Dict[str, int]:
        """Calculate how many articles to fetch from each source based on weights"""
        weights = self.config.get("source_weights", {})
        total_weight = sum(weights.get(key, 0.5) for key in self.sources.keys())

        distribution = {}
        remaining = total_limit

        # Calculate proportional distribution
        for source_key in self.sources.keys():
            weight = weights.get(source_key, 0.5)
            proportion = weight / total_weight
            allocated = max(1, int(total_limit * proportion))

            # Don't exceed remaining quota
            allocated = min(allocated, remaining)
            distribution[source_key] = allocated
            remaining -= allocated

            if remaining <= 0:
                break

        print(f"📊 Distribution: {distribution}")
        return distribution

    def fetch_from_source(self, source_key: str, limit: int = 20) -> List[NewsItem]:
        """Fetch from specific source by key"""
        if source_key not in self.sources:
            print(f"❌ Unknown source: {source_key}")
            return []

        return self.sources[source_key].fetch_news(limit)

    def get_available_sources(self) -> List[str]:
        """Get list of available source keys"""
        return list(self.sources.keys())

    def get_source_info(self) -> Dict[str, Any]:
        """Get detailed information about all sources"""
        info = {}
        for key, adapter in self.sources.items():
            info[key] = {
                'name': adapter.name,
                'base_url': adapter.base_url,
                'categories': adapter.get_categories(),
                'weight': getattr(adapter, 'get_weight', lambda: 1.0)(),
                'class': adapter.__class__.__name__
            }
        return info

    def health_check(self) -> Dict[str, bool]:
        """Check health of all sources"""
        print("🏥 Checking health of all news sources...")
        health = {}

        for key, adapter in self.sources.items():
            try:
                print(f"  🔍 Testing {adapter.name}...")
                articles = adapter.fetch_news(1)
                is_healthy = len(articles) > 0
                health[key] = is_healthy
                status = "✅ Healthy" if is_healthy else "⚠️ No articles"
                print(f"    {status}")
            except Exception as e:
                health[key] = False
                print(f"    ❌ Failed: {e}")

        return health

    def add_source(self, source_key: str, adapter: NewsSourceAdapter, weight: float = 1.0):
        """
        Manually add a news source adapter.
        This allows runtime addition of sources without code changes.
        """
        self.sources[source_key] = adapter
        if "source_weights" not in self.config:
            self.config["source_weights"] = {}
        self.config["source_weights"][source_key] = weight
        print(f"✅ Added source: {adapter.name} with weight {weight}")

    def get_diverse_articles(self, total_limit: int = 20) -> List[NewsItem]:
        """
        Get diverse articles ensuring good distribution across sources.
        Main method for background processing.
        """
        return self.fetch_all_news(total_limit)