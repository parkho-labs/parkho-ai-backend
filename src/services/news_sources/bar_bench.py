"""
Bar & Bench news source adapter
"""

import re
from datetime import datetime
from typing import List, Optional
from bs4 import BeautifulSoup

from .base import NewsSourceAdapter, NewsItem


class BarBenchAdapter(NewsSourceAdapter):
    """Bar & Bench news source adapter"""

    def __init__(self):
        super().__init__("Bar & Bench", "https://www.barandbench.com")

    def fetch_news(self, limit: int = 20) -> List[NewsItem]:
        """Fetch news from Bar & Bench homepage"""
        print(f"🔄 Fetching from {self.name}...")

        response = self.safe_request(self.base_url)
        if not response:
            return []

        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            articles = []

            # Look for article containers
            article_containers = soup.find_all(['article', 'div'], class_=re.compile(r'post|article|news'))

            for container in article_containers[:limit]:
                article = self._extract_article(container)
                if article:
                    articles.append(article)

            print(f"  ✅ Got {len(articles)} articles from {self.name}")
            return articles

        except Exception as e:
            print(f"  ⚠️ Error scraping {self.name}: {e}")
            return []

    def _extract_article(self, container) -> Optional[NewsItem]:
        """Extract article from HTML container"""
        try:
            # Look for title
            title_elem = container.find(['h1', 'h2', 'h3', 'h4'], class_=re.compile(r'title|headline'))
            if not title_elem:
                title_elem = container.find('a')

            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)

            # Look for URL
            url_elem = title_elem if title_elem.name == 'a' else title_elem.find('a')
            if not url_elem:
                url_elem = container.find('a')

            if not url_elem:
                return None

            url = url_elem.get('href', '')
            if url and not url.startswith('http'):
                url = self.base_url + url

            # Look for image
            img_elem = container.find('img')
            featured_image = None
            image_alt = title

            if img_elem:
                img_src = img_elem.get('src') or img_elem.get('data-src')
                if img_src:
                    if not img_src.startswith('http'):
                        featured_image = self.base_url + img_src
                    else:
                        featured_image = img_src

                    image_alt = img_elem.get('alt', title)

            # Look for description
            desc_elem = container.find(['p', 'div'], class_=re.compile(r'excerpt|summary|description'))
            description = desc_elem.get_text(strip=True) if desc_elem else title

            # Default image if none found
            if not featured_image:
                featured_image = "https://images.unsplash.com/photo-1589216532372-59a850b1db90?w=800&h=400&fit=crop"

            return NewsItem(
                title=title,
                url=url,
                description=description,
                source=self.name,
                category=self.categorize_article(title, description),
                published_at=datetime.now(),
                featured_image_url=featured_image,
                thumbnail_url=featured_image,
                image_caption=f"{self.name} article image",
                image_alt_text=image_alt,
                keywords=self.extract_keywords(title, description)
            )

        except Exception as e:
            print(f"    ⚠️ Error extracting article from {self.name}: {e}")
            return None

    def get_categories(self) -> List[str]:
        """Get categories for Bar & Bench"""
        return ['constitutional', 'judicial', 'legislative', 'civil', 'general']

    def get_weight(self) -> float:
        """Default weight for this source in news distribution"""
        return 0.7