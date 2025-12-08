import re
from urllib.parse import urlparse
from typing import Optional

from ..exceptions import ValidationError


URL_PATTERN = re.compile(
    r'^https?://'
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
    r'localhost|'
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
    r'(?::\d+)?'
    r'(?:/?|[/?]\S+)$', re.IGNORECASE
)

YOUTUBE_PATTERNS = [
    r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
    r'youtu\.be/([a-zA-Z0-9_-]{11})',
    r'youtube\.com/embed/([a-zA-Z0-9_-]{11})'
]


def validate_url(url: str) -> None:
    if not url or not URL_PATTERN.match(url):
        raise ValidationError(f"Invalid URL: {url}")


def extract_domain(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc


def is_youtube_url(url: str) -> bool:
    return any(re.search(pattern, url) for pattern in YOUTUBE_PATTERNS)


def extract_youtube_video_id(url: str) -> str:
    for pattern in YOUTUBE_PATTERNS:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValidationError(f"Invalid YouTube URL: {url}")


def supports_web_url(url: str) -> bool:
    if not url:
        return False
    return url.startswith(('http://', 'https://'))