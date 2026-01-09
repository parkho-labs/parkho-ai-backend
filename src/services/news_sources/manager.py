"""
Flexible News Sources Manager - orchestrates all news sources with configurable distribution
"""

from typing import List, Dict, Any, Optional, Type
from datetime import datetime
import random
import importlib
import inspect
from pathlib import Path

from .base import NewsItem, NewsSourceAdapter


class NewsSourceManager:
    """
    Manages multiple news sources with configurable distribution.
    Designed for defensive coding - adding new sources doesn't change existing code.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._default_config()
        self.sources = {}
        self._load_all_sources()

    def _default_config(self) -> Dict[str, Any]:
        """Default configuration for news sources"""
        return {
            "source_weights": {
                "indian_kanoon_rss": 1.0,  # Proven working source gets highest weight
                "livelaw_api": 0.8,
                "bar_bench": 0.7
            },
            "category_preferences": {
                "constitutional": 0.4,
                "judicial": 0.3,
                "legislative": 0.2,
                "civil": 0.1
            },
            "fallback_enabled": True,
            "timeout_seconds": 10,
            "retry_attempts": 2
        }

    def _load_all_sources(self):
        """
        Automatically discover and load all news source adapters.
        This enables defensive coding - new sources are automatically included.
        """
        print("🔍 Auto-discovering news sources...")

        # Get the directory containing news source files
        sources_dir = Path(__file__).parent

        # Find all Python files that could contain adapters
        for py_file in sources_dir.glob("*.py"):
            if py_file.name in ['__init__.py', 'base.py', 'manager.py']:
                continue

            try:
                # Import the module
                module_name = f"src.services.news_sources.{py_file.stem}"
                module = importlib.import_module(module_name)

                # Find adapter classes in the module
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and
                        issubclass(obj, NewsSourceAdapter) and
                        obj != NewsSourceAdapter):

                        # Create instance and add to sources
                        adapter_instance = obj()
                        source_key = py_file.stem
                        self.sources[source_key] = adapter_instance
                        print(f"  ✅ Loaded {adapter_instance.name} from {py_file.name}")

            except Exception as e:
                print(f"  ⚠️ Could not load {py_file.name}: {e}")

        print(f"📊 Loaded {len(self.sources)} news sources")

    def fetch_all_news(self, total_limit: int = 30) -> List[NewsItem]:
        """
        Fetch news from all sources using configured distribution.
        """
        print(f"🚀 Fetching {total_limit} articles with intelligent distribution...")
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

                # Apply category filtering if configured
                filtered_articles = self._filter_by_category_preferences(articles)
                all_articles.extend(filtered_articles)

                print(f"  ✅ Added {len(filtered_articles)} articles from {adapter.name}")

            except Exception as e:
                print(f"  ❌ Error with {adapter.name}: {e}")
                if self.config.get("fallback_enabled", True):
                    print(f"  🔄 Fallback: redistributing {limit} articles to other sources")
                    self._redistribute_failed_quota(limit, source_key, distribution)

        # Sort by published date with some randomness for diversity
        all_articles.sort(key=lambda x: (x.published_at, random.random()), reverse=True)

        print(f"\n🎉 Successfully fetched {len(all_articles)} diverse articles")
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

    def _filter_by_category_preferences(self, articles: List[NewsItem]) -> List[NewsItem]:
        """Filter articles based on category preferences"""
        if not self.config.get("category_preferences"):
            return articles

        # For now, return all articles but this could be enhanced
        # to prefer certain categories based on configuration
        return articles

    def _redistribute_failed_quota(self, failed_quota: int, failed_source: str,
                                 current_distribution: Dict[str, int]):
        """Redistribute articles from a failed source to healthy sources"""
        healthy_sources = [k for k in current_distribution.keys() if k != failed_source]
        if not healthy_sources:
            return

        per_source_extra = failed_quota // len(healthy_sources)
        for source_key in healthy_sources:
            current_distribution[source_key] += per_source_extra

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

    def test_all_sources(self, test_limit: int = 3):
        """Test all sources with detailed output"""
        print("🧪 Testing all news sources...")
        print("=" * 60)

        for source_key, adapter in self.sources.items():
            print(f"\n📰 Testing {adapter.name} ({source_key})...")
            print(f"   Weight: {getattr(adapter, 'get_weight', lambda: 1.0)()}")
            print(f"   Categories: {', '.join(adapter.get_categories())}")

            try:
                articles = adapter.fetch_news(test_limit)

                if articles:
                    print(f"  ✅ Success! Got {len(articles)} articles")
                    for i, article in enumerate(articles[:2], 1):
                        print(f"    {i}. {article.title[:50]}...")
                        print(f"       Source: {article.source}")
                        print(f"       Image: {'✅' if article.featured_image_url else '❌'}")
                        print(f"       Category: {article.category}")
                        print(f"       URL: {article.url[:50]}...")
                else:
                    print(f"  ⚠️ No articles returned")

            except Exception as e:
                print(f"  ❌ Error: {e}")

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

    def update_config(self, new_config: Dict[str, Any]):
        """Update manager configuration"""
        self.config.update(new_config)
        print("✅ Configuration updated")

    def get_diverse_articles(self, total_limit: int = 20) -> List[NewsItem]:
        """
        Get diverse articles ensuring good distribution across sources.
        This is the main method that frontends should use.
        """
        return self.fetch_all_news(total_limit)