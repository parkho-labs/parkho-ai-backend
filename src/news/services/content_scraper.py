"""
Content Scraper Service
Extracts full article content and images from news URLs
"""

import requests
import logging
from typing import Optional, Tuple, Dict, Any
from urllib.parse import urljoin, urlparse
import time
import hashlib

try:
    from newspaper import Article, Config
    NEWSPAPER_AVAILABLE = True
except ImportError:
    NEWSPAPER_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

from ...core.firebase import upload_file_to_gcs

logger = logging.getLogger(__name__)


class ContentScraperService:
    """Service for extracting full article content and images from URLs"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

        # Configure newspaper if available
        if NEWSPAPER_AVAILABLE:
            self.newspaper_config = Config()
            self.newspaper_config.browser_user_agent = self.session.headers['User-Agent']
            self.newspaper_config.request_timeout = 10
            self.newspaper_config.number_threads = 1

    def extract_article_content(self, url: str) -> Dict[str, Any]:
        """
        Extract full article content from URL

        Returns:
            Dict with keys: content, success, error, method_used
        """
        if not url or not url.startswith('http'):
            return {
                'content': '',
                'success': False,
                'error': 'Invalid URL',
                'method_used': 'none'
            }

        # Try newspaper3k first (best for article extraction)
        if NEWSPAPER_AVAILABLE:
            result = self._extract_with_newspaper(url)
            if result['success']:
                return result

        # Fallback to BeautifulSoup
        if BS4_AVAILABLE:
            result = self._extract_with_beautifulsoup(url)
            if result['success']:
                return result

        # Final fallback - basic text extraction
        return self._extract_basic(url)

    def _extract_with_newspaper(self, url: str) -> Dict[str, Any]:
        """Extract content using newspaper3k library"""
        try:
            article = Article(url, config=self.newspaper_config)
            article.download()
            article.parse()

            if article.text and len(article.text.strip()) > 100:
                return {
                    'content': article.text.strip(),
                    'success': True,
                    'error': None,
                    'method_used': 'newspaper3k'
                }
            else:
                return {
                    'content': '',
                    'success': False,
                    'error': 'No substantial content extracted',
                    'method_used': 'newspaper3k'
                }

        except Exception as e:
            logger.warning(f"Newspaper3k failed for {url}: {e}")
            return {
                'content': '',
                'success': False,
                'error': str(e),
                'method_used': 'newspaper3k'
            }

    def _extract_with_beautifulsoup(self, url: str) -> Dict[str, Any]:
        """Extract content using BeautifulSoup with common article selectors"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'advertisement']):
                element.decompose()

            # Try common article content selectors
            content_selectors = [
                'article',
                '.post-content',
                '.entry-content',
                '.article-content',
                '.content',
                'main',
                '.story-body',
                '.article-body'
            ]

            content = ""
            for selector in content_selectors:
                elements = soup.select(selector)
                if elements:
                    for element in elements:
                        text = element.get_text(separator=' ', strip=True)
                        if len(text) > len(content):
                            content = text

            # If no specific selectors work, try to get all paragraph text
            if not content or len(content.strip()) < 100:
                paragraphs = soup.find_all('p')
                content = ' '.join([p.get_text(strip=True) for p in paragraphs])

            if content and len(content.strip()) > 100:
                return {
                    'content': content.strip(),
                    'success': True,
                    'error': None,
                    'method_used': 'beautifulsoup'
                }
            else:
                return {
                    'content': '',
                    'success': False,
                    'error': 'No substantial content found',
                    'method_used': 'beautifulsoup'
                }

        except Exception as e:
            logger.warning(f"BeautifulSoup failed for {url}: {e}")
            return {
                'content': '',
                'success': False,
                'error': str(e),
                'method_used': 'beautifulsoup'
            }

    def _extract_basic(self, url: str) -> Dict[str, Any]:
        """Basic text extraction as final fallback"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            # Very basic text extraction
            content = response.text

            # Remove obvious HTML tags
            import re
            content = re.sub(r'<[^>]+>', ' ', content)
            content = re.sub(r'\s+', ' ', content).strip()

            if len(content) > 200:
                # Take first reasonable chunk
                content = content[:5000]
                return {
                    'content': content,
                    'success': True,
                    'error': None,
                    'method_used': 'basic'
                }
            else:
                return {
                    'content': '',
                    'success': False,
                    'error': 'Content too short',
                    'method_used': 'basic'
                }

        except Exception as e:
            logger.error(f"Basic extraction failed for {url}: {e}")
            return {
                'content': '',
                'success': False,
                'error': str(e),
                'method_used': 'basic'
            }

    def download_and_store_image(self, image_url: str, article_id: int) -> Optional[str]:
        """
        Download image and store in GCS

        Returns:
            GCS URL of stored image or None if failed
        """
        if not image_url or not image_url.startswith('http'):
            return None

        try:
            # Download image
            response = self.session.get(image_url, timeout=10, stream=True)
            response.raise_for_status()

            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if not content_type.startswith('image/'):
                logger.warning(f"URL {image_url} is not an image: {content_type}")
                return None

            # Check file size (limit to 5MB)
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > 5 * 1024 * 1024:
                logger.warning(f"Image too large: {content_length} bytes")
                return None

            # Generate filename
            url_hash = hashlib.md5(image_url.encode()).hexdigest()[:8]
            extension = '.jpg'  # Default to jpg
            if 'png' in content_type:
                extension = '.png'
            elif 'webp' in content_type:
                extension = '.webp'

            filename = f"news/{article_id}/image_{url_hash}{extension}"

            # Upload to GCS
            gcs_url = upload_file_to_gcs(
                file_data=response.content,
                filename=filename,
                content_type=content_type
            )

            if gcs_url:
                logger.info(f"Successfully uploaded image for article {article_id}: {gcs_url}")
                return gcs_url
            else:
                logger.error(f"Failed to upload image to GCS for article {article_id}")
                return None

        except Exception as e:
            logger.error(f"Failed to download/store image {image_url}: {e}")
            return None

    def extract_article_image(self, url: str) -> Optional[str]:
        """
        Extract main article image from webpage

        Returns:
            URL of the main article image or None
        """
        if not BS4_AVAILABLE:
            return None

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Try to find main article image
            image_selectors = [
                'article img',
                '.post-content img',
                '.entry-content img',
                '.article-content img',
                '.featured-image img',
                'meta[property="og:image"]',
                'meta[name="twitter:image"]'
            ]

            for selector in image_selectors:
                if 'meta' in selector:
                    element = soup.select_one(selector)
                    if element:
                        image_url = element.get('content')
                        if image_url:
                            return urljoin(url, image_url)
                else:
                    images = soup.select(selector)
                    for img in images:
                        src = img.get('src') or img.get('data-src')
                        if src:
                            return urljoin(url, src)

            return None

        except Exception as e:
            logger.warning(f"Failed to extract image from {url}: {e}")
            return None

    def process_article(self, url: str, article_id: int) -> Tuple[Optional[str], Optional[str]]:
        """
        Process article: extract content and download image

        Returns:
            Tuple of (content, image_gcs_url)
        """
        # Extract content
        content_result = self.extract_article_content(url)
        content = content_result['content'] if content_result['success'] else None

        # Extract and download image
        image_gcs_url = None
        try:
            image_url = self.extract_article_image(url)
            if image_url:
                image_gcs_url = self.download_and_store_image(image_url, article_id)
        except Exception as e:
            logger.warning(f"Image processing failed for article {article_id}: {e}")

        return content, image_gcs_url