"""
Live Law news source adapter
"""

import json
import re
from datetime import datetime
from typing import List, Optional
from bs4 import BeautifulSoup

from .base import NewsSourceAdapter, NewsItem


class LiveLawAdapter(NewsSourceAdapter):
    """Live Law news source adapter"""

    def __init__(self):
        super().__init__("Live Law", "https://www.livelaw.in")
        self.session.headers.update({
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://www.livelaw.in/'
        })

    def fetch_news(self, limit: int = 20) -> List[NewsItem]:
        """Fetch news from Live Law API"""
        print(f"🔄 Fetching from {self.name}...")

        # Use the working API endpoint we found
        api_url = f"{self.base_url}/xhr/getNewsMixin"

        params = {
            'id': '7321782',
            'categoryId': '7321782',
            'link': '/lawschool/call-for-papers',
            'newsCount': str(min(limit, 20)),
            'element_type': 'CONTENT',
            'content_type': 'CATEGORY_NEWS',
            'partner': 'livelaw',
            'page': 'all'
        }

        response = self.safe_request(api_url, params=params)
        if not response:
            return []

        try:
            data = response.json()
            return self._parse_response(data)
        except json.JSONDecodeError:
            print(f"  ⚠️ Invalid JSON from {self.name}")
            return []

    def _parse_response(self, data: dict) -> List[NewsItem]:
        """Parse Live Law API response"""
        if 'viewData' not in data:
            return []

        html_content = data['viewData']
        soup = BeautifulSoup(html_content, 'html.parser')

        articles = []
        article_divs = soup.find_all('div', class_='law_schl_corner_col')

        for div in article_divs:
            article = self._extract_article(div)
            if article:
                articles.append(article)

        print(f"  ✅ Got {len(articles)} articles from {self.name}")
        return articles

    def _extract_article(self, div) -> Optional[NewsItem]:
        """Extract article data from HTML div"""
        try:
            # Extract title and URL
            title_link = div.find('h5')
            if not title_link or not title_link.parent:
                return None

            title = title_link.get_text(strip=True)
            url_elem = title_link.find_parent('a')
            if not url_elem:
                return None

            url = url_elem.get('href', '')
            if url and not url.startswith('http'):
                url = self.base_url + url

            # Extract image
            img_tag = div.find('img')
            featured_image = None
            image_alt = title

            if img_tag:
                img_src = img_tag.get('data-src') or img_tag.get('src')
                if img_src and img_src != '/images/placeholder.svg':
                    if not img_src.startswith('http'):
                        featured_image = self.base_url + img_src
                    else:
                        featured_image = img_src

                    image_alt = img_tag.get('alt', title)

            # Extract date
            date_elem = div.find('p', class_='days_ago')
            published_date = datetime.now()

            if date_elem and date_elem.get('data-datestring'):
                try:
                    date_str = date_elem.get('data-datestring')
                    published_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                except:
                    pass

            # Extract source info
            source_elem = div.find('p', class_='by_athul_sharma')
            source_text = self.name
            if source_elem:
                source_text = source_elem.get_text(strip=True).replace('&nbsp;', '').strip()

            return NewsItem(
                title=title,
                url=url,
                description=title,  # Live Law doesn't provide separate description
                source=source_text,
                category=self.categorize_article(title),
                published_at=published_date,
                featured_image_url=featured_image,
                thumbnail_url=featured_image,
                image_caption=f"{source_text} article",
                image_alt_text=image_alt,
                keywords=self.extract_keywords(title)
            )

        except Exception as e:
            print(f"    ⚠️ Error extracting article: {e}")
            return None

    def get_categories(self) -> List[str]:
        """Get categories for Live Law"""
        return ['constitutional', 'judicial', 'legislative', 'general']