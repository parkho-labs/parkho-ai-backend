"""
Smart Image Extractor with multiple fallback strategies
Handles image extraction from news articles with intelligent fallbacks
"""

import logging
import hashlib
from typing import Optional, Dict, List
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class SmartImageExtractor:
    """Multi-strategy image extractor with fallbacks"""

    def __init__(self, gcp_service):
        self.gcp_service = gcp_service
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        # Category-specific stock images for fallbacks
        self.fallback_images = {
            'supreme court': 'https://images.unsplash.com/photo-1589829545856-d10d557cf95f?w=800&h=400&fit=crop',
            'high court': 'https://images.unsplash.com/photo-1521587760476-6c12a4b040da?w=800&h=400&fit=crop',
            'judicial': 'https://images.unsplash.com/photo-1589216532372-59a850b1db90?w=800&h=400&fit=crop',
            'constitutional': 'https://images.unsplash.com/photo-1555374018-13a8994ab246?w=800&h=400&fit=crop',
            'legislative': 'https://images.unsplash.com/photo-1589994965851-a8f479c573a9?w=800&h=400&fit=crop',
            'business': 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=800&h=400&fit=crop',
            'general': 'https://images.unsplash.com/photo-1589216532372-59a850b1db90?w=800&h=400&fit=crop'
        }

    def extract_and_store_image(self, url: str, article_id: int, source: str, category: str) -> Optional[str]:
        """
        Extract image using multi-strategy approach and store in GCS

        Args:
            url: Article URL
            article_id: Database article ID
            source: News source name
            category: Article category

        Returns:
            GCS URL of stored image or None
        """
        strategies = [
            ('article_page', self._extract_from_article_page),
            ('category_fallback', self._get_category_fallback),
            ('source_fallback', self._get_source_fallback),
            ('default_fallback', self._get_default_fallback)
        ]

        for strategy_name, strategy_func in strategies:
            try:
                logger.info(f"🖼️ Trying {strategy_name} for article {article_id}")

                if strategy_name == 'article_page':
                    image_url = strategy_func(url)
                elif strategy_name == 'category_fallback':
                    image_url = strategy_func(category, source)
                else:
                    image_url = strategy_func(source, category)

                if image_url:
                    logger.info(f"  📸 Found image with {strategy_name}: {image_url[:60]}...")

                    # Download and store the image
                    gcs_url = self._download_and_store(image_url, article_id, strategy_name)
                    if gcs_url:
                        logger.info(f"  ✅ Successfully stored image: {gcs_url}")
                        return gcs_url
                    else:
                        logger.warning(f"  ⚠️ Failed to store image from {strategy_name}")
                else:
                    logger.info(f"  ❌ No image found with {strategy_name}")

            except Exception as e:
                logger.warning(f"  ⚠️ Error with {strategy_name}: {e}")
                continue

        logger.error(f"❌ All image extraction strategies failed for article {article_id}")
        return None

    def _extract_from_article_page(self, url: str) -> Optional[str]:
        """Extract image from article page using various selectors"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Try different image extraction strategies
            strategies = [
                self._try_og_image,
                self._try_twitter_image,
                self._try_featured_image,
                self._try_article_images,
                self._try_schema_image
            ]

            for strategy in strategies:
                image_url = strategy(soup, url)
                if image_url and self._is_valid_image_url(image_url):
                    return image_url

        except Exception as e:
            logger.warning(f"Failed to extract from article page {url}: {e}")

        return None

    def _try_og_image(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Try Open Graph image"""
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            return urljoin(base_url, og_image['content'])
        return None

    def _try_twitter_image(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Try Twitter Card image"""
        twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
        if twitter_image and twitter_image.get('content'):
            return urljoin(base_url, twitter_image['content'])
        return None

    def _try_featured_image(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Try featured image selectors"""
        selectors = [
            '.featured-image img',
            '.post-thumbnail img',
            '.entry-image img',
            '.article-image img',
            '.hero-image img'
        ]

        for selector in selectors:
            img = soup.select_one(selector)
            if img and img.get('src'):
                return urljoin(base_url, img['src'])

        return None

    def _try_article_images(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Try first image in article content"""
        selectors = [
            'article img',
            '.post-content img',
            '.entry-content img',
            '.article-content img',
            'main img'
        ]

        for selector in selectors:
            images = soup.select(selector)
            for img in images:
                src = img.get('src') or img.get('data-src')
                if src and self._is_content_image(img):
                    return urljoin(base_url, src)

        return None

    def _try_schema_image(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Try schema.org structured data"""
        script_tags = soup.find_all('script', type='application/ld+json')
        for script in script_tags:
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, dict) and 'image' in data:
                    image = data['image']
                    if isinstance(image, str):
                        return urljoin(base_url, image)
                    elif isinstance(image, dict) and 'url' in image:
                        return urljoin(base_url, image['url'])
                    elif isinstance(image, list) and image:
                        return urljoin(base_url, image[0])
            except:
                continue

        return None

    def _is_content_image(self, img) -> bool:
        """Check if image is likely content (not logo/icon/ad)"""
        # Skip small images (likely icons/logos)
        width = img.get('width')
        height = img.get('height')

        if width and height:
            try:
                w, h = int(width), int(height)
                if w < 200 or h < 100:  # Too small
                    return False
            except ValueError:
                pass

        # Skip images with certain patterns in src/class
        src = img.get('src', '').lower()
        css_class = ' '.join(img.get('class', [])).lower()

        skip_patterns = ['logo', 'icon', 'avatar', 'ad', 'banner', 'header', 'footer']
        if any(pattern in src or pattern in css_class for pattern in skip_patterns):
            return False

        return True

    def _is_valid_image_url(self, url: str) -> bool:
        """Check if URL points to a valid image"""
        try:
            # Check URL format
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False

            # Check file extension
            path = parsed.path.lower()
            valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
            if any(path.endswith(ext) for ext in valid_extensions):
                return True

            # Try HEAD request to check content type
            response = self.session.head(url, timeout=5)
            content_type = response.headers.get('content-type', '').lower()
            return content_type.startswith('image/')

        except Exception:
            return False

    def _get_category_fallback(self, category: str, source: str) -> Optional[str]:
        """Get category-specific fallback image"""
        category_lower = category.lower()

        # Try exact match first
        if category_lower in self.fallback_images:
            return self.fallback_images[category_lower]

        # Try partial matches
        for cat_key, image_url in self.fallback_images.items():
            if cat_key in category_lower or category_lower in cat_key:
                return image_url

        return None

    def _get_source_fallback(self, source: str, category: str) -> Optional[str]:
        """Get source-specific fallback image"""
        source_lower = source.lower()

        # Source-specific mappings
        source_mapping = {
            'supreme court': 'supreme court',
            'high court': 'high court',
            'bombay hc': 'high court',
            'delhi hc': 'high court',
            'bar and bench': 'judicial'
        }

        for source_key, fallback_category in source_mapping.items():
            if source_key in source_lower:
                return self.fallback_images.get(fallback_category)

        return self._get_category_fallback(category, source)

    def _get_default_fallback(self, source: str, category: str) -> Optional[str]:
        """Get default fallback image"""
        return self.fallback_images['general']

    def _download_and_store(self, image_url: str, article_id: int, strategy: str) -> Optional[str]:
        """Download image and store in GCS"""
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

            # Read image data
            image_data = response.content

            # Validate actual content
            if len(image_data) < 1024:  # Too small, probably an error page
                return None

            # Generate unique filename
            url_hash = hashlib.md5(image_url.encode()).hexdigest()[:8]
            strategy_prefix = strategy.replace('_', '')[0:3]  # First 3 chars
            file_extension = self._get_file_extension(content_type, image_url)
            filename = f"image_{strategy_prefix}_{url_hash}{file_extension}"

            # Upload to GCS
            blob_name = f"news/{article_id}/{filename}"
            gcs_url = self.gcp_service.upload_file_from_bytes(
                blob_name=blob_name,
                file_bytes=image_data,
                content_type=content_type
            )

            return gcs_url

        except Exception as e:
            logger.warning(f"Failed to download/store image {image_url}: {e}")
            return None

    def _get_file_extension(self, content_type: str, url: str) -> str:
        """Get appropriate file extension"""
        if 'jpeg' in content_type or 'jpg' in content_type:
            return '.jpg'
        elif 'png' in content_type:
            return '.png'
        elif 'webp' in content_type:
            return '.webp'
        elif 'gif' in content_type:
            return '.gif'
        else:
            # Try to get from URL
            parsed_url = urlparse(url)
            path = parsed_url.path.lower()
            if path.endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                return path[path.rfind('.'):]
            return '.jpg'  # Default fallback