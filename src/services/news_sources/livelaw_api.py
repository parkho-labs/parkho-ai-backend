"""
Live Law API adapter using working endpoint from network inspection
"""

from datetime import datetime
from typing import List, Optional
from bs4 import BeautifulSoup

from .base import NewsSourceAdapter, NewsItem


class LiveLawAPIAdapter(NewsSourceAdapter):
    """Live Law API adapter using working endpoint"""

    def __init__(self):
        super().__init__("Live Law", "https://www.livelaw.in")
        self.api_url = "https://www.livelaw.in/xhr/getNewsMixin"
        self.headers = {
            'sec-ch-ua-platform': '"Android"',
            'Referer': 'https://www.livelaw.in/',
            'X-Requested-With': 'XMLHttpRequest',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Mobile Safari/537.36',
            'Accept': '*/*',
            'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
            'sec-ch-ua-mobile': '?1'
        }

    def fetch_news(self, limit: int = 20) -> List[NewsItem]:
        """Fetch from Live Law API"""
        print(f"🔄 Fetching from {self.name} API...")

        try:
            # Use the working API parameters
            params = {
                'id': '7321788',
                'moreClasses': 'homepage_level_17',
                'mixinName': 'longCard',
                'theme': 'theme_leo',
                'categoryId': '7321788',
                'link': '/lawschool/seminars',
                'newsCount': str(limit),
                'element_type': 'CONTENT',
                'element_id': 'menu8',
                'is_visible': 'true',
                'content': '',
                'default_content': '',
                'is_sync': 'false',
                'page': 'all',
                'description': '',
                'content_type': 'CATEGORY_NEWS',
                'heading': 'Seminars',
                'partner': 'livelaw',
                'refer_page': '/'
            }

            response = self.safe_request(self.api_url, params=params, headers=self.headers)
            if not response:
                return []

            # Parse the HTML response
            soup = BeautifulSoup(response.content, 'html.parser')
            articles = []

            # Look for article containers
            article_containers = soup.find_all(['article', 'div'], class_=lambda x: x and any(cls in x.lower() for cls in ['news', 'article', 'post', 'card']))

            for container in article_containers[:limit]:
                article = self._extract_article_from_html(container)
                if article:
                    articles.append(article)

            print(f"  ✅ Got {len(articles)} articles from {self.name}")
            return articles

        except Exception as e:
            print(f"  ⚠️ Error fetching from {self.name} API: {e}")
            return []

    def _extract_article_from_html(self, container) -> Optional[NewsItem]:
        """Extract article from HTML container"""
        try:
            # Look for title
            title_elem = container.find(['h1', 'h2', 'h3', 'h4', 'a'])
            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)
            if not title or len(title) < 10:
                return None

            # Look for URL
            url_elem = title_elem if title_elem.name == 'a' else container.find('a')
            url = ""
            if url_elem:
                url = url_elem.get('href', '')
                if url and not url.startswith('http'):
                    url = self.base_url + url

            # Look for image
            img_elem = container.find('img')
            featured_image = "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=800&h=400&fit=crop"
            image_alt = title

            if img_elem:
                img_src = img_elem.get('src') or img_elem.get('data-src')
                if img_src and img_src.startswith('http'):
                    featured_image = img_src
                    image_alt = img_elem.get('alt', title)

            # Look for description
            desc_elem = container.find(['p', 'div'], class_=lambda x: x and 'desc' in x.lower())
            description = desc_elem.get_text(strip=True) if desc_elem else title[:200]

            return NewsItem(
                title=title,
                url=url,
                description=description,
                source=self.name,
                category=self.categorize_article(title, description),
                published_at=datetime.now(),
                featured_image_url=featured_image,
                thumbnail_url=featured_image,
                image_caption=f"{self.name} legal news",
                image_alt_text=image_alt,
                keywords=self.extract_keywords(title, description)
            )

        except Exception as e:
            print(f"    ⚠️ Error extracting article from {self.name}: {e}")
            return None

    def get_categories(self) -> List[str]:
        return ['constitutional', 'judicial', 'legislative', 'general']

    def get_weight(self) -> float:
        """Default weight for this source in news distribution"""
        return 0.8